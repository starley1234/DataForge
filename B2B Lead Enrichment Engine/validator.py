import re
import time
import socket
import smtplib
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
import dns.resolver
import phonenumbers
from phonenumbers import geocoder, carrier
from config import settings

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

# База одноразовых (disposable / temp) почтовых доменов
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "yopmail.com", "trashmail.com", "dispostable.com",
    "temp-mail.org", "fakeinbox.com", "getairmail.com", "mohmal.com",
    "crazymailing.com", "fakemailgenerator.com", "throwawaymail.com",
    "dropmail.me", "nada.ltd", "burnermail.io", "maildrop.cc", "emailondeck.com",
    "mytemp.email", "harakirimail.com", "generator.email", "guerrillamail.biz",
    "guerrillamail.net", "guerrillamail.org", "grr.la", "guerrillamailblock.com",
    "spam4.me", "pokemail.net", "inboxkitten.com", "trashmail.net", "10mail.org",
    "tempmailo.com", "temp-mail.io", "tempmail.net", "fakemail.net", "incognitomail.org",
    "getnada.com", "disposablemail.com", "throwawayemailaddress.com", "mohmal.im"
}

# Бесплатные публичные почтовые сервисы (не корпоративные домены)
FREE_MAIL_DOMAINS = {
    # Mail.ru Group / VK
    "mail.ru", "bk.ru", "inbox.ru", "list.ru", "internet.ru", "vk.com",
    # Яндекс
    "yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz", "narod.ru",
    # Rambler Group
    "rambler.ru", "lenta.ru", "autorambler.ru", "myrambler.ru", "ro.ru",
    # Google
    "gmail.com", "googlemail.com",
    # Microsoft
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    # Apple
    "icloud.com", "me.com", "mac.com",
    # Международные
    "yahoo.com", "ymail.com", "proton.me", "protonmail.com", "zoho.com",
    "aol.com", "gmx.com", "mail.com", "fastmail.com", "tutanota.com"
}

# Ролевые (служебные) префиксы email
ROLE_BASED_PREFIXES = {
    "info", "support", "contact", "sales", "admin", "administrator",
    "office", "mail", "post", "general", "hello", "press", "pr",
    "hr", "job", "jobs", "career", "resume", "buh", "buhgalter",
    "buhgalteriya", "tender", "zakupki", "b2b", "order", "orders",
    "client", "service", "reception", "secretary", "director", "ceo",
    "inbox", "marketing", "billing", "help", "dev", "tech", "security",
    "customercare", "legal", "corp", "partner", "partners", "commercial"
}

# Маппинг регионов РФ на часовые пояса (смещение от UTC в часах)
REGION_TIMEZONES = {
    # UTC+2 (Калининград, MSK-1)
    "калининград": 2,
    # UTC+3 (Москва, СПб, Центр, Юг, Кавказ, Северо-Запад, MSK)
    "москва": 3, "санкт-петербург": 3, "московск": 3, "ленинградск": 3, "белгород": 3,
    "брянск": 3, "владимир": 3, "воронеж": 3, "иванов": 3, "калуж": 3, "костром": 3,
    "курск": 3, "липецк": 3, "орлов": 3, "рязан": 3, "смоленск": 3, "тамбов": 3,
    "твер": 3, "тульск": 3, "ярослав": 3, "архангельск": 3, "вологод": 3, "мурман": 3,
    "новгород": 3, "псков": 3, "карели": 3, "коми": 3, "татарстан": 3, "казань": 3,
    "краснодар": 3, "ростов": 3, "сочи": 3, "крым": 3, "севастополь": 3, "волгоград": 3,
    "астрахан": 4, "ставрополь": 3, "дагестан": 3, "чечен": 3, "чуваш": 3, "мордови": 3,
    # UTC+4 (Самара, Ульяновск, Ижевск, Саратов, MSK+1)
    "самар": 4, "саратов": 4, "ульяновск": 4, "удмурт": 4, "ижевск": 4,
    # UTC+5 (Екатеринбург, Тюмень, Челябинск, Пермь, Башкортостан, Уфа, MSK+2)
    "свердловск": 5, "екатеринбург": 5, "челябинск": 5, "тюмен": 5, "перм": 5,
    "башкортостан": 5, "уфа": 5, "оренбург": 5, "курган": 5, "ханты": 5, "ямал": 5, "хмао": 5, "янао": 5,
    # UTC+6 (Омск, MSK+3)
    "омск": 6,
    # UTC+7 (Новосибирск, Красноярск, Кемерово, Томск, Алтай, MSK+4)
    "новосибирск": 7, "красноярск": 7, "кемерово": 7, "кузбасс": 7, "томск": 7,
    "алтай": 7, "барнаул": 7, "хакаси": 7, "тыва": 7,
    # UTC+8 (Иркутск, Бурятия, MSK+5)
    "иркутск": 8, "бурят": 8, "улан-удэ": 8,
    # UTC+9 (Якутия, Забайкалье, Чита, MSK+6)
    "якут": 9, "саха": 9, "забайкал": 9, "чита": 9,
    # UTC+10 (Владивосток, Хабаровск, Приморье, MSK+7)
    "примор": 10, "владивосток": 10, "хабаровск": 10, "амурск": 9, "благовещенск": 9, "еврейск": 10,
    # UTC+11 (Магадан, Сахалин, MSK+8)
    "магадан": 11, "сахалин": 11,
    # UTC+12 (Камчатка, Чукотка, MSK+9)
    "камчат": 12, "чукот": 12
}

# Потокобезопасный LRU-кэш для DNS MX записей
_dns_cache_lock = threading.Lock()
_DNS_MX_CACHE: Dict[str, Tuple[bool, Optional[str], float]] = {}


def is_role_based_email(email: str) -> bool:
    """Проверяет, является ли email ролевым (общим ящиком компании, а не персональным)."""
    if not email or "@" not in email:
        return False
    local_part = email.split("@")[0].lower().strip()
    return local_part in ROLE_BASED_PREFIXES


def detect_timezone_offset(region_str: Optional[str]) -> Tuple[int, str]:
    """Определяет смещение часового пояса от UTC (в часах) и кодовое обозначение (MSK+x)."""
    if not region_str:
        return 3, "MSK (UTC+3)"
    r_low = region_str.lower()
    for key, offset in REGION_TIMEZONES.items():
        if key in r_low:
            msk_diff = offset - 3
            msk_label = f"MSK{'+' + str(msk_diff) if msk_diff > 0 else (str(msk_diff) if msk_diff < 0 else '')}"
            return offset, f"{msk_label} (UTC+{offset})"
    return 3, "MSK (UTC+3)"


def is_calling_window_open(utc_offset: int) -> Tuple[bool, str]:
    """
    Проверяет, попадает ли текущий момент в рабочее время звонков (09:00 - 18:00 по местному времени).
    Возвращает (is_open, local_time_str).
    """
    now_utc = datetime.now(timezone.utc)
    target_tz = timezone(timedelta(hours=utc_offset))
    local_now = now_utc.astimezone(target_tz)
    local_time_str = local_now.strftime("%H:%M")
    
    # 09:00 - 18:00 в будние дни (пн-пт)
    is_weekday = local_now.weekday() < 5
    is_work_hour = 9 <= local_now.hour < 18
    is_open = is_weekday and is_work_hour
    return is_open, local_time_str


def normalize_phone(raw_phone: str, default_region: str = "RU") -> Dict[str, Any]:
    """
    Комплексная нормализация и анализ номера телефона РФ:
    1. Приведение к E.164 (+79991234567)
    2. Приведение к российскому национальному формату (+7 (999) 123-45-67)
    3. Определение типа: direct mobile / office / toll-free 8800
    4. Определение мобильного оператора и географического региона РФ
    5. Расчет часового пояса, текущего локального времени и окна звонков
    6. Формирование ссылки WhatsApp
    """
    if not raw_phone:
        return {
            "valid": False,
            "formatted": None,
            "national": None,
            "type": None,
            "region": None,
            "carrier": None,
            "timezone": None,
            "local_time": None,
            "is_calling_window": False,
            "whatsapp_link": None
        }

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
                "carrier": None,
                "timezone": None,
                "local_time": None,
                "is_calling_window": False,
                "whatsapp_link": None
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

        # DEF-коды РФ (900-999)
        if formatted_e164.startswith("+79") and type_str != "mobile":
            type_str = "mobile"

        region_name = geocoder.description_for_number(parsed, "ru") or ""
        carrier_name = carrier.name_for_number(parsed, "ru") or ""

        # Уточнение оператора по DEF-кодам
        if not carrier_name and type_str == "mobile":
            def_code = formatted_e164[2:5] if len(formatted_e164) >= 5 else ""
            if def_code in ("910", "911", "912", "913", "914", "915", "916", "917", "918", "919", "980", "981", "982", "983", "984", "985", "986", "987", "988", "989"):
                carrier_name = "МТС"
            elif def_code in ("920", "921", "922", "923", "924", "925", "926", "927", "928", "929", "930", "931", "932", "933", "934", "935", "936", "937", "938", "939"):
                carrier_name = "МегаФон"
            elif def_code in ("903", "905", "906", "909", "960", "961", "962", "963", "964", "965", "966", "967", "968", "969"):
                carrier_name = "Билайн"
            elif def_code in ("900", "901", "902", "904", "908", "950", "951", "952", "953", "977", "991", "992", "993", "994", "995", "996", "999"):
                carrier_name = "Tele2 / T2"

        # Часовой пояс и время
        utc_off, tz_str = detect_timezone_offset(region_name)
        is_open, loc_time = is_calling_window_open(utc_off)

        # WhatsApp ссылка для мобильных
        wa_link = f"https://wa.me/{formatted_e164.lstrip('+')}" if type_str == "mobile" else None

        return {
            "valid": True,
            "formatted": formatted_e164,
            "national": formatted_national,
            "type": type_str,
            "region": region_name or "Россия",
            "carrier": carrier_name or "Федеральный оператор",
            "timezone": tz_str,
            "local_time": loc_time,
            "is_calling_window": is_open,
            "whatsapp_link": wa_link
        }
    except Exception:
        return {
            "valid": False,
            "formatted": None,
            "national": None,
            "type": "error",
            "region": None,
            "carrier": None,
            "timezone": None,
            "local_time": None,
            "is_calling_window": False,
            "whatsapp_link": None
        }


def validate_email_syntax(email: str) -> bool:
    """Проверка синтаксиса email по стандарту RFC 5322."""
    if not email or len(email) > 254:
        return False
    clean = email.strip()
    if " " in clean or "\t" in clean or "\n" in clean:
        return False
    if not EMAIL_REGEX.match(clean):
        return False
    domain = clean.split("@")[1]
    if "." not in domain or domain.endswith(".") or domain.startswith("."):
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
    if use_cache and settings.ENABLE_DNS_CACHE:
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
        # Fallback на A-запись
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


def check_catch_all_domain(domain: str, best_mx: str, timeout: float = 3.0) -> bool:
    """
    Проверяет, настроен ли на домене Catch-All (прием любой входящей почты на несуществующий ящик).
    Позволяет избежать ложноположительной уверенности в сгенерированных email.
    """
    if not best_mx or not settings.CHECK_CATCH_ALL:
        return False

    random_test_email = f"catchall_test_{int(time.time())}_{abs(hash(domain)) % 99999}@{domain}"
    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(best_mx, 25)
        server.helo('mail.leadengine.pro')
        server.mail('verify@leadengine.pro')
        code, _ = server.rcpt(random_test_email)
        server.quit()
        # Если сервер ответил 250 OK на заведомо случайный ящик -> Catch-All активен
        return code == 250
    except Exception:
        return False


def verify_email_full(
    email: str,
    check_smtp: Optional[bool] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Многоуровневая валидация email:
    1. RFC 5322 синтаксис
    2. Детекция одноразовых (disposable) сервисов
    3. Определение бесплатного / корпоративного статуса
    4. Детекция ролевых адресов (info@, sales@)
    5. DNS MX резолвинг с потокобезопасным кэшем
    6. Опциональный SMTP Handshake и Catch-All детекция
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
            "is_catch_all": False,
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
            "is_catch_all": False,
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
            "is_catch_all": False,
            "confidence": 10,
            "reason": "У домена отсутствуют MX-записи почты"
        }

    is_corporate = domain not in FREE_MAIL_DOMAINS
    is_role = is_role_based_email(clean_email)

    base_confidence = 92 if is_corporate else 75
    if is_role:
        base_confidence -= 12

    result = {
        "email": clean_email,
        "is_valid": True,
        "status": "valid_mx",
        "is_corporate": is_corporate,
        "is_role": is_role,
        "is_catch_all": False,
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
                # Проверяем на catch-all
                is_catchall = check_catch_all_domain(domain, best_mx, timeout)
                result["is_catch_all"] = is_catchall
                if is_catchall:
                    result["status"] = "catch_all"
                    result["confidence"] = 80
                    result["reason"] = "Почтовый сервер в режиме Catch-All (принимает всю почту)"
                else:
                    result["status"] = "verified"
                    result["confidence"] = min(100, base_confidence + 8)
                    result["reason"] = "Почтовый ящик подтвержден через SMTP Handshake"
                result["smtp_code"] = code
            elif code in (550, 551, 552, 553, 554):
                result["is_valid"] = False
                result["status"] = "mailbox_not_found"
                result["confidence"] = 10
                result["smtp_code"] = code
                result["reason"] = "Почтовый ящик не существует на сервере"
        except Exception as e:
            result["smtp_skipped"] = True
            result["smtp_note"] = f"SMTP-порт недоступен ({e})"

    return result
