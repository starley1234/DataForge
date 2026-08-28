import re
from typing import List, Dict, Optional, Any
from translit import split_russian_name, transliterate, transliterate_variants


def clean_domain(domain: str) -> str:
    """Очищает домен от URL-префиксов, протоколов и завершающих слэшей."""
    if not domain:
        return ""
    d = domain.lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.split('/')[0].split('?')[0].split(':')[0].strip()
    return d


def detect_pattern_from_sample(sample_email: str, full_name: str, domain: str) -> Optional[str]:
    """
    Определяет используемый в компании шаблон email на основе известного адреса сотрудника.
    Например: sample_email='a.petrov@company.ru', full_name='Алексей Петров' -> '{f}.{last}'
    """
    if not sample_email or not full_name or not domain:
        return None

    clean_dom = clean_domain(domain)
    clean_sample = sample_email.lower().strip()
    if "@" not in clean_sample:
        return None

    local_part, email_domain = clean_sample.split("@", 1)
    if clean_domain(email_domain) != clean_dom:
        return None

    last, first, middle = split_russian_name(full_name)
    if not last:
        return None

    l_variants = transliterate_variants(last)
    f_variants = transliterate_variants(first) if first else [""]
    m_variants = transliterate_variants(middle) if middle else [""]

    for l_lat in l_variants:
        for f_lat in f_variants:
            for m_lat in m_variants:
                f_init = f_lat[0] if f_lat else ""
                m_init = m_lat[0] if m_lat else ""

                if f_init and l_lat and local_part == f"{f_init}.{l_lat}":
                    return "{f}.{last}"
                if f_init and l_lat and local_part == f"{l_lat}.{f_init}":
                    return "{last}.{f}"
                if f_lat and l_lat and local_part == f"{f_lat}.{l_lat}":
                    return "{first}.{last}"
                if l_lat and local_part == l_lat:
                    return "{last}"
                if f_lat and local_part == f_lat:
                    return "{first}"
                if f_init and l_lat and local_part == f"{f_init}{l_lat}":
                    return "{f}{last}"
                if l_lat and f_init and local_part == f"{l_lat}{f_init}":
                    return "{last}{f}"
                if l_lat and f_init and local_part == f"{l_lat}_{f_init}":
                    return "{last}_{f}"
                if f_lat and l_lat and local_part == f"{f_lat}_{l_lat}":
                    return "{first}_{last}"
                if l_lat and f_init and local_part == f"{l_lat}-{f_init}":
                    return "{last}-{f}"
                if f_lat and l_lat and local_part == f"{f_lat}-{l_lat}":
                    return "{first}-{last}"
                if f_init and m_init and l_lat and local_part == f"{l_lat}.{f_init}.{m_init}":
                    return "{last}.{f}.{m}"
                if f_init and m_init and l_lat and local_part == f"{f_init}.{m_init}.{l_lat}":
                    return "{f}.{m}.{last}"
    return None


def generate_email_permutations(
    full_name: str,
    domain: str,
    known_pattern: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Генерирует список вероятных корпоративных email по популярным российским и международным шаблонам.
    Если известен паттерн компании (`known_pattern`), он поднимается на 1-е место с наивысшим скорингом.
    """
    if not full_name or not domain:
        return []

    clean_dom = clean_domain(domain)
    if not clean_dom or "." not in clean_dom:
        return []

    last, first, middle = split_russian_name(full_name)
    if not last and not first:
        return []

    l_variants = transliterate_variants(last) if last else [""]
    f_variants = transliterate_variants(first) if first else [""]
    m_variants = transliterate_variants(middle) if middle else [""]

    seen_emails = set()
    candidates: List[Dict[str, Any]] = []

    def add_cand(email_str: str, pattern: str, base_conf: int):
        clean_em = email_str.lower().strip()
        if clean_em and clean_em not in seen_emails:
            seen_emails.add(clean_em)
            conf = 98 if (known_pattern and pattern == known_pattern) else base_conf
            candidates.append({
                "email": clean_em,
                "pattern": pattern,
                "confidence": conf
            })

    # Перебираем варианты транслитерации (основная таблица идет первой)
    for v_idx, l_lat in enumerate(l_variants):
        for f_idx, f_lat in enumerate(f_variants):
            for m_idx, m_lat in enumerate(m_variants):
                penalty = 5 if (v_idx > 0 or f_idx > 0 or m_idx > 0) else 0

                f_init = f_lat[0] if f_lat else ""
                m_init = m_lat[0] if m_lat else ""

                if f_lat and l_lat:
                    # 1. {f}.{last}@domain (самый популярный в корпоративном сегменте РФ)
                    add_cand(f"{f_init}.{l_lat}@{clean_dom}", "{f}.{last}", max(10, 90 - penalty))
                    # 2. {last}.{f}@domain (очень распространен в гос. секторе и на промпредприятиях РФ)
                    add_cand(f"{l_lat}.{f_init}@{clean_dom}", "{last}.{f}", max(10, 85 - penalty))
                    # 3. {first}.{last}@domain (стандарт в IT, международных и инновационных компаниях)
                    add_cand(f"{f_lat}.{l_lat}@{clean_dom}", "{first}.{last}", max(10, 80 - penalty))
                    # 4. {last}@domain (топ-менеджеры, средний бизнес)
                    add_cand(f"{l_lat}@{clean_dom}", "{last}", max(10, 75 - penalty))
                    # 5. {first}@domain (основатели, стартапы)
                    add_cand(f"{f_lat}@{clean_dom}", "{first}", max(10, 70 - penalty))
                    # 6. {f}{last}@domain (слитно с инициалом)
                    add_cand(f"{f_init}{l_lat}@{clean_dom}", "{f}{last}", max(10, 65 - penalty))
                    # 7. {last}{f}@domain
                    add_cand(f"{l_lat}{f_init}@{clean_dom}", "{last}{f}", max(10, 60 - penalty))
                    # 8. {last}_{f}@domain
                    add_cand(f"{l_lat}_{f_init}@{clean_dom}", "{last}_{f}", max(10, 55 - penalty))
                    # 9. {first}_{last}@domain
                    add_cand(f"{f_lat}_{l_lat}@{clean_dom}", "{first}_{last}", max(10, 50 - penalty))
                    # 10. {last}-{f}@domain
                    add_cand(f"{l_lat}-{f_init}@{clean_dom}", "{last}-{f}", max(10, 48 - penalty))
                    # 11. {first}-{last}@domain
                    add_cand(f"{f_lat}-{l_lat}@{clean_dom}", "{first}-{last}", max(10, 45 - penalty))

                    if m_init:
                        # 12. {last}.{f}.{m}@domain (ФИО через точки)
                        add_cand(f"{l_lat}.{f_init}.{m_init}@{clean_dom}", "{last}.{f}.{m}", max(10, 42 - penalty))
                        # 13. {f}.{m}.{last}@domain
                        add_cand(f"{f_init}.{m_init}.{l_lat}@{clean_dom}", "{f}.{m}.{last}", max(10, 38 - penalty))
                        # 14. {f}{m}{last}@domain
                        add_cand(f"{f_init}{m_init}{l_lat}@{clean_dom}", "{f}{m}{last}", max(10, 35 - penalty))
                elif l_lat:
                    # Только фамилия
                    add_cand(f"{l_lat}@{clean_dom}", "{last}", max(10, 70 - penalty))
                elif f_lat:
                    # Только имя
                    add_cand(f"{f_lat}@{clean_dom}", "{first}", max(10, 65 - penalty))

    # Сортировка: кандидаты с наибольшей вероятностью первыми
    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates


def generate_department_emails(domain: str) -> List[Dict[str, str]]:
    """
    Генерирует стандартные адреса корпоративных отделов компании для резервной связи.
    """
    clean_dom = clean_domain(domain)
    if not clean_dom:
        return []

    dept_prefixes = [
        ("info", "Общая приемная / секретарь"),
        ("office", "Офис компании"),
        ("sales", "Отдел продаж"),
        ("b2b", "Отдел корпоративных клиентов"),
        ("tender", "Тендерный отдел / закупки"),
        ("zakupki", "Отдел снабжения и закупок"),
        ("director", "Приемная генерального директора"),
        ("ceo", "Руководство / CEO"),
        ("pr", "Пресс-служба / PR-департамент"),
        ("hr", "Отдел кадров / HR"),
        ("contact", "Контакты организации")
    ]

    return [
        {"email": f"{prefix}@{clean_dom}", "title": desc, "type": "department"}
        for prefix, desc in dept_prefixes
    ]
