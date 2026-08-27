from typing import List, Dict
from translit import split_russian_name, transliterate


def generate_email_permutations(full_name: str, domain: str) -> List[Dict[str, str]]:
    """
    Генерирует список вероятных корпоративных email по популярным корпоративным шаблонам.
    Возвращает список словарей: [{"email": "...", "pattern": "..."}]
    """
    if not full_name or not domain:
        return []
    
    # Очистка домена (удаление http://, https://, www., путей)
    domain = domain.lower().replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0].strip()
    if not domain:
        return []

    last, first, middle = split_russian_name(full_name)
    if not last:
        return []

    l_lat = transliterate(last)
    f_lat = transliterate(first) if first else ""
    m_lat = transliterate(middle) if middle else ""

    f_init = f_lat[0] if f_lat else ""
    m_init = m_lat[0] if m_lat else ""
    l_init = l_lat[0] if l_lat else ""

    candidates = []

    if f_lat and l_lat:
        # {f}.{last}@domain.ru (самый популярный в РФ)
        candidates.append({"email": f"{f_init}.{l_lat}@{domain}", "pattern": "{f}.{last}", "confidence": 90})
        # {last}.{f}@domain.ru
        candidates.append({"email": f"{l_lat}.{f_init}@{domain}", "pattern": "{last}.{f}", "confidence": 85})
        # {first}.{last}@domain.ru
        candidates.append({"email": f"{f_lat}.{l_lat}@{domain}", "pattern": "{first}.{last}", "confidence": 80})
        # {last}@domain.ru
        candidates.append({"email": f"{l_lat}@{domain}", "pattern": "{last}", "confidence": 75})
        # {first}@domain.ru (для топ-менеджеров/основателей)
        candidates.append({"email": f"{f_lat}@{domain}", "pattern": "{first}", "confidence": 70})
        # {f}{last}@domain.ru
        candidates.append({"email": f"{f_init}{l_lat}@{domain}", "pattern": "{f}{last}", "confidence": 65})
        # {last}{f}@domain.ru
        candidates.append({"email": f"{l_lat}{f_init}@{domain}", "pattern": "{last}{f}", "confidence": 60})
        # {last}_{f}@domain.ru
        candidates.append({"email": f"{l_lat}_{f_init}@{domain}", "pattern": "{last}_{f}", "confidence": 55})
        # {first}_{last}@domain.ru
        candidates.append({"email": f"{f_lat}_{l_lat}@{domain}", "pattern": "{first}_{last}", "confidence": 50})
        
        if m_init:
            # {last}.{f}.{m}@domain.ru
            candidates.append({"email": f"{l_lat}.{f_init}.{m_init}@{domain}", "pattern": "{last}.{f}.{m}", "confidence": 45})
            # {f}{m}{last}@domain.ru
            candidates.append({"email": f"{f_init}{m_init}{l_lat}@{domain}", "pattern": "{f}{m}{last}", "confidence": 40})
    else:
        # Только фамилия
        candidates.append({"email": f"{l_lat}@{domain}", "pattern": "{last}", "confidence": 70})

    return candidates
