import re
from typing import Tuple, List, Optional, Dict, Set

# Основная таблица транслитерации (ГОСТ 7.79-2000 / B2B)
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

# Англоязычные эквиваленты и уменьшительные формы для корпоративных email
NAME_ALIASES: Dict[str, List[str]] = {
    "александр": ["alex", "alexander", "sasha"],
    "александра": ["alex", "alexandra", "sasha"],
    "алексей": ["alex", "alexey", "alexei"],
    "анатолий": ["anatoly", "anatoliy"],
    "андрей": ["andrey", "andrei", "andrew"],
    "антон": ["anton"],
    "артем": ["artem", "artyom"],
    "артём": ["artem", "artyom"],
    "борис": ["boris", "bob"],
    "вадим": ["vadim"],
    "валентин": ["valentin"],
    "валерий": ["valery", "valeriy"],
    "василий": ["vasily", "vasiliy", "vasil"],
    "виктор": ["viktor", "victor"],
    "виталий": ["vitaly", "vitaliy"],
    "владимир": ["vladimir", "vlad", "volodya"],
    "владислав": ["vladislav", "vlad"],
    "вячеслав": ["vyacheslav", "slava"],
    "геннадий": ["gennady", "gennadiy", "gena"],
    "георгий": ["georgy", "georgiy", "george"],
    "григорий": ["grigory", "grigoriy", "grisha"],
    "даниил": ["daniil", "danila", "daniel"],
    "денис": ["denis", "den"],
    "дмитрий": ["dmitry", "dmitriy", "dima"],
    "евгений": ["evgeny", "evgeniy", "eugene", "zhenya"],
    "евгения": ["evgeniya", "eugenia", "zhenya"],
    "егор": ["egor"],
    "иван": ["ivan", "vano"],
    "игорь": ["igor"],
    "илья": ["ilya", "ilia"],
    "кирилл": ["kirill", "cyril"],
    "константин": ["konstantin", "kostya"],
    "лев": ["lev", "leo"],
    "леонид": ["leonid", "leo"],
    "максим": ["maxim", "maksim", "max"],
    "михаил": ["mikhail", "michael", "misha"],
    "никита": ["nikita", "nick"],
    "николай": ["nikolay", "nikolai", "nick"],
    "олег": ["oleg"],
    "павел": ["pavel", "paul", "pasha"],
    "петр": ["petr", "peter", "pyotr"],
    "пётр": ["petr", "peter", "pyotr"],
    "роман": ["roman", "roma"],
    "ростислав": ["rostislav"],
    "руслан": ["ruslan"],
    "сергей": ["sergey", "sergei", "serge"],
    "станислав": ["stanislav", "stas"],
    "степан": ["stepan", "stephen"],
    "тимофей": ["timofey", "tim"],
    "тимур": ["timur", "tim"],
    "федор": ["fedor", "fyodor"],
    "фёдор": ["fedor", "fyodor"],
    "юрий": ["yury", "yuriy", "yuri"],
    "ярослав": ["yaroslav"],
    # Женские
    "алена": ["alena", "elena"],
    "алёна": ["alena", "elena"],
    "алина": ["alina"],
    "анастасия": ["anastasia", "nastya"],
    "анна": ["anna", "ann", "anya"],
    "валерия": ["valeria", "valeriya", "lera"],
    "вектория": ["victoria", "viktoria", "vika"],
    "виктория": ["victoria", "viktoria", "vika"],
    "дарья": ["daria", "dariya", "dasha"],
    "евгения": ["evgenia", "evgeniya"],
    "екатерина": ["ekaterina", "kate", "katya"],
    "елена": ["elena", "helen", "lena"],
    "ирина": ["irina", "ira"],
    "ксения": ["ksenia", "kseniya", "ksenia"],
    "марина": ["marina"],
    "мария": ["maria", "mary", "masha"],
    "надежда": ["nadezhda", "nadia"],
    "наталья": ["natalia", "nataliya", "natasha"],
    "оксана": ["oksana"],
    "ольга": ["olga", "olya"],
    "полина": ["polina"],
    "светлана": ["svetlana", "sveta"],
    "татьяна": ["tatiana", "tatyana", "tanya"],
    "юлия": ["yulia", "yuliya"]
}

FEMALE_FIRST_NAMES: Set[str] = {
    "анна", "елена", "ольга", "татьяна", "екатерина", "мария", "наталья", "наталия",
    "светлана", "юлия", "анастасия", "ирина", "оксана", "дарья", "марина", "людмила",
    "галина", "надежда", "евгения", "алена", "алёна", "полина", "валерия", "кристина",
    "виктория", "вера", "любовь", "алина", "диана", "ксеня", "ксения", "инна", "кира",
    "лариса", "любовь", "нина", "тамара", "ярослава", "жанна", "антонина", "снежана"
}

MALE_FIRST_NAMES: Set[str] = {
    "иван", "алексей", "сергей", "александр", "дмитрий", "михаил", "андрей", "владимир",
    "роман", "артем", "артём", "максим", "евгений", "дени", "денис", "илья", "павел",
    "константин", "николай", "виктор", "игорь", "григорий", "тигран", "герман", "лев",
    "олег", "вячеслав", "станислав", "артур", "руслан", "виталий", "тимур", "рустам", "кирилл",
    "борис", "вадим", "валентин", "василий", "геннадий", "георгий", "даниил", "данила", "егор",
    "леонид", "матвей", "никита", "петр", "пётр", "ростислав", "семен", "семён", "степан",
    "тимофей", "федор", "фёдор", "юрий", "ярослав", "эдуард", "ян", "арсений", "владлен"
}

PREFIX_CLEANUP = re.compile(
    r'\b(д\.т\.н\.|к\.т\.н\.|к\.э\.н\.|д\.э\.н\.|д\.ю\.н\.|к\.ю\.н\.|г-н|г-жа|проф\.|доц\.|'
    r'директор|генеральный|президент|руководитель|ип|учредитель|советник|зам\.|заместитель)\b',
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
    cleaned = re.sub(r'[^a-z0-9\-_]', '', joined)
    return cleaned


def transliterate_variants(text: str) -> List[str]:
    """
    Возвращает список уникальных вариантов транслитерации
    (основной ГОСТ/B2B, альтернативный ICAO и англоязычные алиасы).
    """
    if not text:
        return [""]
    text_clean = text.lower().strip()
    v1 = transliterate(text_clean, use_alt=False)
    v2 = transliterate(text_clean, use_alt=True)
    
    res = [v1] if v1 else []
    if v2 and v2 not in res:
        res.append(v2)

    # Проверяем алиасы (например, для Александр -> alex, sasha)
    if text_clean in NAME_ALIASES:
        for alias in NAME_ALIASES[text_clean]:
            if alias not in res:
                res.append(alias)

    return res if res else [""]


def split_russian_name(full_name: str) -> Tuple[str, str, str]:
    """
    Интеллектуальный парсер ФИО:
    Разбирает форматы:
    - 'Иванов Иван Иванович' (Фамилия Имя Отчество)
    - 'Иван Иванов' (Имя Фамилия)
    - 'Иванов Иван' (Фамилия Имя)
    - 'Мамин-Сибиряк Дмитрий Наркисович' (Составная фамилия)
    - 'Иванова Анна Сергеевна'
    Возвращает кортеж: (Фамилия, Имя, Отчество)
    """
    if not full_name:
        return "", "", ""
    
    cleaned = PREFIX_CLEANUP.sub("", full_name)
    cleaned = re.sub(r'[\(\)\[\]"\'«»]', '', cleaned)
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
        'ская', 'цкая', 'ко', 'ых', 'их', 'дзе', 'швили', 'ян', 'янц', 'ич', 'ук', 'юк'
    )
    patronymic_suffixes = (
        'ович', 'евич', 'ич', 'овна', 'евна', 'ична', 'кызы', 'оглы', 'улы'
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
        if m_lower.endswith(('ович', 'евич', 'ич', 'оглы', 'улы')):
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


def get_salutation(full_name: str, formal: bool = True, style: str = "business") -> str:
    """
    Формирует корректное и вежливое русское деловое приветствие для B2B cold outreach:
    - formal / business: 'Уважаемый Иван Иванович!' / 'Уважаемая Анна Сергеевна!'
    - direct / modern: 'Здравствуйте, Иван!' / 'Добрый день, Иван!'
    - executive: 'Иван Иванович, добрый день!'
    """
    last, first, middle = split_russian_name(full_name)
    gender = detect_gender(last, first, middle)

    if style == "executive" and first and middle:
        return f"{first} {middle}, добрый день!"
    elif style == "direct" and first:
        return f"Добрый день, {first}!"

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
