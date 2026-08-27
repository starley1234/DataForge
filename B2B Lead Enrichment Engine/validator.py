import re
import socket
import smtplib
from typing import Dict, Any, Optional
import dns.resolver
import phonenumbers
from phonenumbers import geocoder, carrier

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "yopmail.com", "trashmail.com"
}

FREE_MAIL_DOMAINS = {
    "mail.ru", "bk.ru", "inbox.ru", "list.ru", "yandex.ru", "ya.ru",
    "gmail.com", "rambler.ru", "internet.ru", "vk.com"
}


def normalize_phone(raw_phone: str, default_region: str = "RU") -> Dict[str, Any]:
    """
    Нормализует номер телефона в формат E.164 (+79991234567),
    определяет тип (мобильный/городской/8-800) и регион/оператора.
    """
    if not raw_phone:
        return {"valid": False, "formatted": None, "type": None, "region": None}

    # Очистка от лишних символов
    cleaned = re.sub(r'[^\d+]', '', raw_phone)
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 11 and not cleaned.startswith('+'):
        cleaned = '+' + cleaned

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
        if not phonenumbers.is_valid_number(parsed):
            return {"valid": False, "formatted": None, "type": "invalid", "region": None}

        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        num_type = phonenumbers.number_type(parsed)

        type_str = "other"
        if num_type == phonenumbers.PhoneNumberType.MOBILE:
            type_str = "mobile"
        elif num_type == phonenumbers.PhoneNumberType.FIXED_LINE:
            type_str = "office"
        elif num_type == phonenumbers.PhoneNumberType.TOLL_FREE:
            type_str = "8800"

        region_name = geocoder.description_for_number(parsed, "ru") or ""
        carrier_name = carrier.name_for_number(parsed, "ru") or ""

        return {
            "valid": True,
            "formatted": formatted,
            "type": type_str,
            "region": region_name,
            "carrier": carrier_name
        }
    except Exception:
        return {"valid": False, "formatted": None, "type": "error", "region": None}


def validate_email_syntax(email: str) -> bool:
    """Проверка базового синтаксиса email."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def check_domain_mx(domain: str) -> bool:
    """Проверка наличия MX-записей у домена через DNS."""
    if not domain:
        return False
    domain = domain.strip().lower()
    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=3.0)
        return len(answers) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout, Exception):
        # Fallback на проверку A-записи
        try:
            answers_a = dns.resolver.resolve(domain, 'A', lifetime=2.0)
            return len(answers_a) > 0
        except Exception:
            return False


def verify_email_full(email: str, check_smtp: bool = False, timeout: float = 3.0) -> Dict[str, Any]:
    """
    Комплексная проверка email:
    1. Синтаксис
    2. Одноразовый домен
    3. MX записи DNS
    4. Опциональный SMTP handshake
    """
    if not validate_email_syntax(email):
        return {"email": email, "is_valid": False, "status": "syntax_invalid", "reason": "Bad syntax"}

    domain = email.split("@")[1].lower()
    if domain in DISPOSABLE_DOMAINS:
        return {"email": email, "is_valid": False, "status": "disposable", "reason": "Disposable email"}

    has_mx = check_domain_mx(domain)
    if not has_mx:
        return {"email": email, "is_valid": False, "status": "no_mx", "reason": "Domain has no MX records"}

    is_corporate = domain not in FREE_MAIL_DOMAINS

    if not check_smtp:
        return {
            "email": email,
            "is_valid": True,
            "status": "valid_mx",
            "is_corporate": is_corporate,
            "reason": "Valid domain and MX"
        }

    # Быстрый SMTP handshake (без отправки DATA)
    try:
        mx_records = dns.resolver.resolve(domain, 'MX', lifetime=timeout)
        best_mx = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip('.')
        
        server = smtplib.SMTP(timeout=timeout)
        server.connect(best_mx, 25)
        server.helo('validator.domain.com')
        server.mail('probe@validator.domain.com')
        code, _ = server.rcpt(email)
        server.quit()

        if code == 250:
            return {"email": email, "is_valid": True, "status": "verified", "is_corporate": is_corporate, "code": code}
        elif code in (550, 551, 552, 553, 554):
            return {"email": email, "is_valid": False, "status": "mailbox_not_found", "code": code}
        else:
            return {"email": email, "is_valid": True, "status": "ambiguous", "code": code}
    except Exception as e:
        # Если SMTP заблокирован провайдером или порты закрыты, возвращаем valid_mx
        return {
            "email": email,
            "is_valid": True,
            "status": "valid_mx",
            "is_corporate": is_corporate,
            "smtp_skipped": True,
            "reason": str(e)
        }
