import re
import time
import socket
import smtplib
import threading
from typing import Dict, Any, Optional, Tuple, List
import dns.resolver
import phonenumbers
from phonenumbers import geocoder, carrier
from config import settings

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

# Расширенный список одноразовых (disposable / temp) почтовых доменов
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "yopmail.com", "trashmail.com", "dispostable.com",
    "temp-mail.org", "fakeinbox.com", "getairmail.com", "mohmal.com",
    "crazymailing.com", "fakemailgenerator.com", "throwawaymail.com",
    "dropmail.me", "nada.ltd", "burnermail.io", "maildrop.cc", "emailondeck.com",
    "mytemp.email", "harakirimail.com", "generator.email", "guerrillamail.biz",
    "guerrillamail.net", "guerrillamail.org", "grr.la", "guerrillamailblock.com",
    "spam4.me", "pokemail.net", "inboxkitten.com", "trashmail.net", "10mail.org"
}

# Бесплатные публичные почтовые сервисы (не корпоративные домены)
FREE_MAIL_DOMAINS = {
    # Mail.ru Group
    "mail.ru", "bk.ru", "inbox.ru", "list.ru", "internet.ru", "vk.com",
    # Яндекс
    "yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz", "narod.ru",
    # Rambler
    "rambler.ru", "lenta.ru", "autorambler.ru", "myrambler.ru", "ro.ru",
    # Google
    "gmail.com", "googlemail.com",
    # Microsoft
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    # Apple
    "icloud.com", "me.com", "mac.com",
    # Прочие
    "yahoo.com", "ymail.com", "proton.me", "protonmail.com", "zoho.com",
    "aol.com", "gmx.com", "mail.com", "fastmail.com"
}

# Ролевые (служебные) префиксы email
ROLE_BASED_PREFIXES = {
    "info", "support", "contact", "sales", "admin", "administrator",
    "office", "mail", "post", "general", "hello", "press", "pr",
    "hr", "job", "jobs", "career", "resume", "buh", "buhgalter",
    "buhgalteriya", "tender", "zakupki", "b2b", "order", "orders",
    "client", "service", "reception", "secretary", "director", "ceo",
    "inbox", "marketing", "billing", "help", "dev", "tech", "security"
}

# Потокобезопасный LRU-кэш для DNS MX записей
_dns_cache_lock = threading.Lock()
_DNS_MX_CACHE: Dict[str, Tuple[bool, Optional[str], float]] = {}


def is_role_based_email(email: str) -> bool:
    """Проверяет, является ли email ролевым (общим ящиком компании, а не личным)."""
    if not email or "@" not in email:
        return False
    local_part = email.split("@")[0].lower().strip()
    return local_part in ROLE_BASED_PREFIXES


def normalize_phone(raw_phone: str, default_region: str = "RU") -> Dict[str, Any]:
    """
    Комплексная нормализация и анализ номера телефона РФ:
    1. Приведение к E.164 (+79991234567)
    2. Приведение к российскому национальному формату (+7 (999) 123-45-67)
    3. Определение типа: direct mobile / office / toll-free 8800
    4. Определение мобильного оператора и географического региона РФ
    """
    if not raw_phone:
        return {
            "valid": False,
            "formatted": None,
            "national": None,
            "type": None,
            "region": None,
            "carrier": None
        }

    # Очистка от пробелов, скобок, тире
    cleaned = re.sub(r'[^\d+]', '', raw_phone)
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 11 and not cleaned.startswith('+'):
        cleaned = '+' + cleaned

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
        if not phonenumbers.is_valid_number(parsed):
            return {
                "valid": False,
                "formatted": None,
                "national": None,
                "type": "invalid",
                "region": None,
                "carrier": None
            }

        formatted_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        formatted_national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        num_type = phonenumbers.number_type(parsed)

        type_str = "other"
        if num_type == phonenumbers.PhoneNumberType.MOBILE:
            type_str = "mobile"
        elif num_type in (phonenumbers.PhoneNumberType.FIXED_LINE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE):
            type_str = "office"
        elif num_type == phonenumbers.PhoneNumberType.TOLL_FREE:
            type_str = "8800"

        # Определение региона и мобильного оператора
        region_name = geocoder.description_for_number(parsed, "ru") or ""
        carrier_name = carrier.name_for_number(parsed, "ru") or ""

        # Дополнительная эвристика для DEF-кодов РФ (900-999)
        if formatted_e164.startswith("+79") and type_str != "mobile":
            type_str = "mobile"

        return {
            "valid": True,
            "formatted": formatted_e164,
            "national": formatted_national,
            "type": type_str,
            "region": region_name,
            "carrier": carrier_name
        }
    except Exception:
        return {
            "valid": False,
            "formatted": None,
            "national": None,
            "type": "error",
            "region": None,
            "carrier": None
        }


def validate_email_syntax(email: str) -> bool:
    """Проверка синтаксиса email по RFC 5322."""
    if not email or len(email) > 254:
        return False
    clean = email.strip()
    if " " in clean or "\t" in clean or "\n" in clean:
        return False
    if not EMAIL_REGEX.match(clean):
        return False
    domain = clean.split("@")[1]
    if "." not in domain or domain.endswith("."):
        return False
    return True


def check_domain_mx(domain: str, use_cache: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Проверка наличия почтовых MX-записей у домена через DNS с кэшированием.
    Возвращает (has_mx, best_mx_host).
    """
    if not domain:
        return False, None
    domain = domain.strip().lower()

    now = time.time()
    if use_cache:
        with _dns_cache_lock:
            cached = _DNS_MX_CACHE.get(domain)
            if cached and (now - cached[2]) < settings.DNS_CACHE_TTL_SECONDS:
                return cached[0], cached[1]

    has_mx = False
    best_mx = None

    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=3.5)
        if len(answers) > 0:
            has_mx = True
            sorted_records = sorted(answers, key=lambda r: r.preference)
            best_mx = str(sorted_records[0].exchange).rstrip('.')
    except Exception:
        # Fallback: если MX отсутствует, проверяем A-запись
        try:
            answers_a = dns.resolver.resolve(domain, 'A', lifetime=2.5)
            if len(answers_a) > 0:
                has_mx = True
                best_mx = domain
        except Exception:
            has_mx = False
            best_mx = None

    if use_cache:
        with _dns_cache_lock:
            _DNS_MX_CACHE[domain] = (has_mx, best_mx, now)

    return has_mx, best_mx


def verify_email_full(
    email: str,
    check_smtp: Optional[bool] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Многоуровневая валидация email:
    1. RFC 5322 синтаксис
    2. Детекция одноразовых ящиков (disposable)
    3. Определение бесплатного / корпоративного статуса
    4. Детекция ролевых адресов (info@, sales@)
    5. DNS MX резолвинг с кэшированием
    6. Опциональный SMTP Handshake
    7. Расчет итогового индекса доверия (confidence score: 0 - 100)
    """
    if check_smtp is None:
        check_smtp = settings.CHECK_SMTP
    if timeout is None:
        timeout = settings.SMTP_TIMEOUT

    if not validate_email_syntax(email):
        return {
            "email": email,
            "is_valid": False,
            "status": "syntax_invalid",
            "is_corporate": False,
            "is_role": False,
            "confidence": 0,
            "reason": "Некорректный синтаксис адреса"
        }

    clean_email = email.lower().strip()
    domain = clean_email.split("@")[1]

    if domain in DISPOSABLE_DOMAINS:
        return {
            "email": clean_email,
            "is_valid": False,
            "status": "disposable",
            "is_corporate": False,
            "is_role": False,
            "confidence": 5,
            "reason": "Одноразовый почтовый сервис"
        }

    has_mx, best_mx = check_domain_mx(domain)
    if not has_mx:
        return {
            "email": clean_email,
            "is_valid": False,
            "status": "no_mx",
            "is_corporate": False,
            "is_role": False,
            "confidence": 10,
            "reason": "У домена отсутствуют MX-записи почты"
        }

    is_corporate = domain not in FREE_MAIL_DOMAINS
    is_role = is_role_based_email(clean_email)

    base_confidence = 90 if is_corporate else 75
    if is_role:
        base_confidence -= 10

    result = {
        "email": clean_email,
        "is_valid": True,
        "status": "valid_mx",
        "is_corporate": is_corporate,
        "is_role": is_role,
        "mx_host": best_mx,
        "confidence": base_confidence,
        "reason": "Корпоративный домен с действующими MX-записями" if is_corporate else "Действующий публичный почтовый сервис"
    }

    # Опциональный SMTP Handshake
    if check_smtp and best_mx:
        try:
            server = smtplib.SMTP(timeout=timeout)
            server.connect(best_mx, 25)
            server.helo('mail.leadengine.pro')
            server.mail('verify@leadengine.pro')
            code, _ = server.rcpt(clean_email)
            server.quit()

            if code == 250:
                result["status"] = "verified"
                result["confidence"] = min(100, base_confidence + 10)
                result["smtp_code"] = code
            elif code in (550, 551, 552, 553, 554):
                result["is_valid"] = False
                result["status"] = "mailbox_not_found"
                result["confidence"] = 10
                result["smtp_code"] = code
                result["reason"] = "Почтовый ящик не существует на сервере"
        except Exception as e:
            result["smtp_skipped"] = True
            result["smtp_note"] = f"SMTP-порт недоступен или заблокирован провайдером ({e})"

    return result
