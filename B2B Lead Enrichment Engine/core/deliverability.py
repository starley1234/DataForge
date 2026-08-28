import re
from typing import Dict, Any, Optional, List, Tuple
import dns.resolver
from core.email_generator import clean_domain
from core.validator import check_domain_mx

# Популярные DNSBL (Spam Blacklist) списки
RBL_SERVERS = [
    "zen.spamhaus.org",
    "bl.spamcop.net",
    "b.barracudacentral.org"
]

COMMON_DKIM_SELECTORS = ["default", "mail", "k1", "google", "yandex", "mailru", "s1", "s2"]


def check_domain_rbl(domain: str) -> Dict[str, Any]:
    """Проверка домена по основным базам спам-листов (RBL / DNSBL)."""
    blacklisted_on: List[str] = []
    clean_dom = clean_domain(domain)
    if not clean_dom:
        return {"is_blacklisted": False, "listings": []}

    for rbl in RBL_SERVERS:
        try:
            query = f"{clean_dom}.{rbl}"
            answers = dns.resolver.resolve(query, 'A', lifetime=2.0)
            if len(answers) > 0:
                blacklisted_on.append(rbl)
        except Exception:
            pass

    return {
        "is_blacklisted": len(blacklisted_on) > 0,
        "listings": blacklisted_on
    }


def analyze_domain_deliverability(domain: str) -> Dict[str, Any]:
    """
    Комплексная диагностика доставляемости почты и безопасности корпоративного домена:
    1. Наличие и тип MX почтового провайдера (Яндекс 360, VK WorkSpace, Google, Microsoft, On-Premise).
    2. SPF-политика (Sender Policy Framework: -all, ~all, ?all)
    3. DMARC-политика (p=reject, p=quarantine, p=none)
    4. DKIM-селекторы
    5. Проверка по черным спискам (RBL)
    6. Расчет общего рейтинга доставляемости (Deliverability Score: 0 - 100)
    """
    clean_dom = clean_domain(domain)
    if not clean_dom:
        return {"valid": False, "domain": "", "error": "Пустой домен"}

    has_mx, best_mx = check_domain_mx(clean_dom)

    # 1. Определение почтового сервиса организации
    provider = "Собственный почтовый сервер (On-Premise / Postfix / Exim)"
    mx_lower = (best_mx or "").lower()

    if any(k in mx_lower for k in ["yandex", "ya.ru", "mx.yandex.net"]):
        provider = "Яндекс 360 для бизнеса (Yandex Workspace)"
    elif any(k in mx_lower for k in ["mail.ru", "vk.com", "biz.mail.ru", "mxs.mail.ru"]):
        provider = "VK WorkSpace / Mail.ru для бизнеса"
    elif any(k in mx_lower for k in ["google", "googlemail", "aspmx.l.google.com"]):
        provider = "Google Workspace"
    elif any(k in mx_lower for k in ["outlook", "protection.outlook", "microsoft"]):
        provider = "Microsoft 365 Exchange Online"
    elif any(k in mx_lower for k in ["selectel"]):
        provider = "Selectel Mail"
    elif any(k in mx_lower for k in ["reg.ru"]):
        provider = "Reg.ru Mail"
    elif any(k in mx_lower for k in ["beget"]):
        provider = "Beget Mail"
    elif any(k in mx_lower for k in ["timeweb"]):
        provider = "Timeweb Mail"

    # 2. Проверка SPF-записи
    has_spf = False
    spf_record = None
    spf_qualifier = "neutral"
    try:
        txt_records = dns.resolver.resolve(clean_dom, 'TXT', lifetime=3.0)
        for r in txt_records:
            t = str(r).strip('"')
            if t.startswith("v=spf1"):
                has_spf = True
                spf_record = t
                if "-all" in t:
                    spf_qualifier = "strict (-all)"
                elif "~all" in t:
                    spf_qualifier = "softfail (~all)"
                elif "?all" in t:
                    spf_qualifier = "neutral (?all)"
                break
    except Exception:
        has_spf = False

    # 3. Проверка DMARC-записи
    has_dmarc = False
    dmarc_record = None
    dmarc_policy = "none"
    try:
        dmarc_recs = dns.resolver.resolve(f"_dmarc.{clean_dom}", 'TXT', lifetime=3.0)
        for r in dmarc_recs:
            t = str(r).strip('"')
            if t.startswith("v=DMARC1"):
                has_dmarc = True
                dmarc_record = t
                if "p=reject" in t:
                    dmarc_policy = "reject (строгая защита)"
                elif "p=quarantine" in t:
                    dmarc_policy = "quarantine (карантин)"
                else:
                    dmarc_policy = "none (мониторинг)"
                break
    except Exception:
        has_dmarc = False

    # 4. Проверка DKIM
    has_dkim = False
    found_selector = None
    for sel in COMMON_DKIM_SELECTORS:
        try:
            dkim_recs = dns.resolver.resolve(f"{sel}._domainkey.{clean_dom}", 'TXT', lifetime=1.5)
            for r in dkim_recs:
                t = str(r).strip('"')
                if "v=DKIM1" in t or "p=" in t:
                    has_dkim = True
                    found_selector = sel
                    break
            if has_dkim:
                break
        except Exception:
            pass

    # 5. Проверка RBL
    rbl_res = check_domain_rbl(clean_dom)

    # 6. Расчет Deliverability Score (0 - 100)
    deliverability_score = 30
    if has_mx:
        deliverability_score += 35
    if has_spf:
        deliverability_score += 15
    if has_dmarc:
        deliverability_score += 10
    if has_dkim:
        deliverability_score += 10
    if rbl_res["is_blacklisted"]:
        deliverability_score = max(10, deliverability_score - 40)

    recommendations = []
    if not has_mx:
        recommendations.append("Домен не имеет настроенных MX-записей. Отправка и прием почты невозможны.")
    if not has_spf:
        recommendations.append("Рекомендуется настроить SPF-запись (v=spf1...) для предотвращения подделки адреса отправителя.")
    if not has_dmarc:
        recommendations.append("Рекомендуется настроить DMARC-политику (_dmarc...) для исключения попадания в спам.")
    if not has_dkim:
        recommendations.append("Рекомендуется опубликовать публичный DKIM-ключ в DNS.")
    if rbl_res["is_blacklisted"]:
        recommendations.append(f"Внимание! Домен обнаружен в спам-базах: {', '.join(rbl_res['listings'])}")

    return {
        "valid": True,
        "domain": clean_dom,
        "has_mx": has_mx,
        "mx_host": best_mx,
        "provider": provider,
        "has_spf": has_spf,
        "spf_record": spf_record,
        "spf_qualifier": spf_qualifier,
        "has_dmarc": has_dmarc,
        "dmarc_policy": dmarc_policy,
        "dmarc_record": dmarc_record,
        "has_dkim": has_dkim,
        "dkim_selector": found_selector,
        "rbl_status": rbl_res,
        "deliverability_score": min(100, max(0, deliverability_score)),
        "recommendations": recommendations
    }
