import re
from typing import Tuple, List, Optional

# Основная таблица транслитерации (ГОСТ 7.79-2000 / ICAO / B2B)
TRANSLIT_PRIMARY = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}

# Альтернативная транслитерация (паспортная ICAO / упрощенная)
TRANSLIT_ALT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'iu', 'я': 'ia'
}

FEMALE_FIRST_NAMES = {
    "анна", "елена", "ольга", "татьяна", "екатерина", "мария", "наталья", "наталия",
    "светлана", "юлия", "анастасия", "ирина", "оксана", "дарья", "марина", "людмила",
    "галина", "надежда", "евгения", "алена", "алёна", "полина", "валерия", "кристина",
    "виктория", "вера", "любовь", "алина", "диана", "ксеня", "ксения", "инна", "кира"
}

MALE_FIRST_NAMES = {
    "иван", "алексей", "сергей", "александр", "дмитрий", "михаил", "андрей", "владимир",
    "роман", "артем", "артём", "максим", "евгений", "дени", "денис", "илья", "павел",
    "константин", "николай", "виктор", "игорь", "григорий", "тигран", "герман", "лев",
    "олег", "вячеслав", "станислав", "артур", "руслан", "виталий", "тимур", "рустам", "кирилл"
}

PREFIX_CLEANUP = re.compile(
    r'\b(д\.т\.н\.|к\.т\.н\.|к\.э\.н\.|д\.э\.н\.|г-н|г-жа|проф\.|доц\.|директор|генеральный|президент|руководитель)\b',
    re.IGNORECASE
)


def transliterate(text: str, use_alt: bool = False) -> str:
    """
    Транслитерация кириллицы в латиницу для email-адресов.
    Очищает любые недопустимые для имени email символы.
    """
    if not text:
        return ""
    text = text.lower().strip()
    # Заменяем дефис на временный символ, если это составная фамилия
    text = text.replace("-", "_dash_")
    
    table = TRANSLIT_ALT if use_alt else TRANSLIT_PRIMARY
    result = []
    for char in text:
        result.append(table.get(char, char))
    
    joined = "".join(result).replace("_dash_", "-")
    # Удаляем любые недопустимые для имени email символы (кроме дефиса и подчеркивания)
    cleaned = re.sub(r'[^a-z0-9\-_]', '', joined)
    return cleaned


def transliterate_variants(text: str) -> List[str]:
    """
    Возвращает список уникальных вариантов транслитерации
    (основной ГОСТ/B2B и альтернативный ICAO).
    """
    v1 = transliterate(text, use_alt=False)
    v2 = transliterate(text, use_alt=True)
    res = [v1]
    if v2 and v2 != v1 and v2 not in res:
        res.append(v2)
    return res


def split_russian_name(full_name: str) -> Tuple[str, str, str]:
    """
    Интеллектуальный парсер ФИО:
    Разбирает 'Иванов Иван Иванович', 'Иван Иванов', 'Мамин-Сибиряк Дмитрий', 'Иванова Анна'
    Возвращает кортеж: (Фамилия, Имя, Отчество)
    """
    if not full_name:
        return "", "", ""
    
    cleaned = PREFIX_CLEANUP.sub("", full_name)
    parts = [p.strip().capitalize() for p in cleaned.split() if p.strip()]
    if not parts:
        return "", "", ""

    if len(parts) == 1:
        w_lower = parts[0].lower()
        if w_lower in FEMALE_FIRST_NAMES or w_lower in MALE_FIRST_NAMES:
            return "", parts[0], ""
        return parts[0], "", ""

    last_name_suffixes = (
        'ов', 'ев', 'ин', 'ын', 'ский', 'цкий', 'ова', 'ева', 'ина', 'ына',
        'ская', 'цкая', 'ко', 'ых', 'их', 'дзе', 'швили', 'ян', 'янц', 'ич'
    )
    patronymic_suffixes = (
        'ович', 'евич', 'ич', 'овна', 'евна', 'ична', 'кызы', 'оглы'
    )

    if len(parts) == 2:
        p1, p2 = parts[0], parts[1]
        p1_l = p1.lower()
        p2_l = p2.lower()

        # Проверяем, не является ли p2 отчеством
        if p2_l.endswith(patronymic_suffixes):
            return "", p1, p2

        # Проверяем суффиксы для определения порядка (Иван Иванов vs Иванов Иван)
        if p1_l.endswith(last_name_suffixes) and not p2_l.endswith(last_name_suffixes):
            return p1, p2, ""
        elif p2_l.endswith(last_name_suffixes) and not p1_l.endswith(last_name_suffixes):
            return p2, p1, ""
        elif p1_l in MALE_FIRST_NAMES or p1_l in FEMALE_FIRST_NAMES:
            # Первый элемент — имя (например, Иван Смирнов)
            return p2, p1, ""
        
        # По умолчанию: Фамилия Имя
        return p1, p2, ""

    # Если 3 и более частей
    p1, p2, p3 = parts[0], parts[1], parts[2]
    p1_l, p2_l, p3_l = p1.lower(), p2.lower(), p3.lower()

    # Формат 1: Фамилия Имя Отчество (Иванов Иван Иванович)
    if p3_l.endswith(patronymic_suffixes):
        return p1, p2, p3

    # Формат 2: Имя Отчество Фамилия (Иван Иванович Иванов)
    if p2_l.endswith(patronymic_suffixes):
        return p3, p1, p2

    # Формат 3: Составная фамилия в начале (Мамин-Сибиряк Дмитрий Наркисович)
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])

    return parts[0], parts[1], parts[2]


def detect_gender(last_name: str, first_name: str, middle_name: str) -> str:
    """
    Определяет пол по ФИО: 'male', 'female' или 'unknown'.
    Необходимо для корректного персонализированного обращения в email.
    """
    m_lower = (middle_name or "").lower().strip()
    if m_lower:
        if m_lower.endswith(('ович', 'евич', 'ич', 'оглы')):
            return "male"
        elif m_lower.endswith(('овна', 'евна', 'ична', 'кызы')):
            return "female"

    f_lower = (first_name or "").lower().strip()
    if f_lower in FEMALE_FIRST_NAMES:
        return "female"
    if f_lower in MALE_FIRST_NAMES:
        return "male"

    l_lower = (last_name or "").lower().strip()
    if l_lower in FEMALE_FIRST_NAMES:
        return "female"
    if l_lower in MALE_FIRST_NAMES:
        return "male"
    if l_lower.endswith(('ова', 'ева', 'ина', 'ына', 'ская', 'цкая')):
        return "female"
    if l_lower.endswith(('ов', 'ев', 'ин', 'ын', 'ский', 'цкий')):
        return "male"

    return "unknown"


def get_salutation(full_name: str, formal: bool = True) -> str:
    """
    Формирует корректное и вежливое русское деловое приветствие для B2B cold email:
    'Уважаемый Иван Иванович!' / 'Уважаемая Анна Сергеевна!' / 'Здравствуйте, Иван!'
    """
    last, first, middle = split_russian_name(full_name)
    gender = detect_gender(last, first, middle)

    if formal and first and middle:
        prefix = "Уважаемая" if gender == "female" else "Уважаемый"
        return f"{prefix} {first} {middle}!"
    elif first:
        return f"Здравствуйте, {first}!"
    elif full_name:
        prefix = "Уважаемая" if gender == "female" else "Уважаемый"
        return f"{prefix} {full_name}!"
    else:
        return "Здравствуйте!"
