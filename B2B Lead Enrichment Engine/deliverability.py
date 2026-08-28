import dns.resolver
from typing import Dict, Any, Optional
from email_generator import clean_domain
from validator import check_domain_mx


def analyze_domain_deliverability(domain: str) -> Dict[str, Any]:
    """
    Комплексная диагностика доставляемости почты и безопасности корпоративного домена:
    1. Наличие и тип MX почтового провайдера (Яндекс 360, VK WorkSpace, Google, Microsoft, Собственный).
    2. SPF-политика (Sender Policy Framework)
    3. DMARC-политика (Domain-based Message Authentication)
    4. Оценка риска попадания в спам (Deliverability Score: 0 - 100)
    """
    clean_dom = clean_domain(domain)
    if not clean_dom:
        return {"valid": False, "domain": "", "error": "Пустой домен"}

    has_mx, best_mx = check_domain_mx(clean_dom)

    # 1. Определение почтового сервиса организации
    provider = "Собственный почтовый сервер (On-Premise)"
    mx_lower = (best_mx or "").lower()

    if any(k in mx_lower for k in ["yandex", "ya.ru"]):
        provider = "Яндекс 360 для бизнеса (Yandex Workspace)"
    elif any(k in mx_lower for k in ["mail.ru", "vk.com", "biz.mail.ru"]):
        provider = "VK WorkSpace / Mail.ru для бизнеса"
    elif any(k in mx_lower for k in ["google", "googlemail"]):
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
    try:
        txt_records = dns.resolver.resolve(clean_dom, 'TXT', lifetime=3.0)
        for r in txt_records:
            t = str(r).strip('"')
            if t.startswith("v=spf1"):
                has_spf = True
                spf_record = t
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
                    dmarc_policy = "reject"
                elif "p=quarantine" in t:
                    dmarc_policy = "quarantine"
                break
    except Exception:
        has_dmarc = False

    # 4. Расчет индекса доставляемости и репутации
    deliverability_score = 40
    if has_mx:
        deliverability_score += 30
    if has_spf:
        deliverability_score += 15
    if has_dmarc:
        deliverability_score += 15

    recommendations = []
    if not has_mx:
        recommendations.append("Домен не имеет настроенных MX-записей. Отправка почты невозможна.")
    if not has_spf:
        recommendations.append("Рекомендуется настроить SPF-запись (v=spf1...) для защиты от подделки домена.")
    if not has_dmarc:
        recommendations.append("Рекомендуется настроить DMARC-политику для максимальной доставляемости во входящие.")

    return {
        "valid": True,
        "domain": clean_dom,
        "has_mx": has_mx,
        "mx_host": best_mx,
        "provider": provider,
        "has_spf": has_spf,
        "spf_record": spf_record,
        "has_dmarc": has_dmarc,
        "dmarc_policy": dmarc_policy,
        "dmarc_record": dmarc_record,
        "deliverability_score": deliverability_score,
        "recommendations": recommendations
    }
