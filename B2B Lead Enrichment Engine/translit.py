import re
from typing import Tuple

# Таблицы транслитерации ГОСТ 7.79-2000 (система Б) и общепринятая B2B (ICAO/ISO 9)
TRANSLIT_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def transliterate(text: str) -> str:
    """Транслитерация кириллицы в латиницу для email-адресов."""
    if not text:
        return ""
    text = text.lower().strip()
    result = []
    for char in text:
        result.append(TRANSLIT_TABLE.get(char, char))
    # Удаляем любые недопустимые для имени email символы
    cleaned = re.sub(r'[^a-z0-9]', '', ''.join(result))
    return cleaned


def split_russian_name(full_name: str) -> Tuple[str, str, str]:
    """
    Разбирает ФИО вида 'Иванов Иван Иванович' или 'Иван Иванов'
    Возвращает (Фамилия, Имя, Отчество)
    """
    if not full_name:
        return "", "", ""
    
    parts = [p.strip() for p in full_name.split() if p.strip()]
    if not parts:
        return "", "", ""
    
    if len(parts) == 1:
        return parts[0], "", ""
    elif len(parts) == 2:
        # Проверяем суффиксы для определения порядка (Иван Иванов vs Иванов Иван)
        p1, p2 = parts[0], parts[1]
        last_name_suffixes = ('ов', 'ев', 'ин', 'ын', 'ский', 'цкий', 'ова', 'ева', 'ина', 'ына', 'ская', 'цкая', 'ко')
        if p1.lower().endswith(last_name_suffixes) and not p2.lower().endswith(last_name_suffixes):
            return p1, p2, ""
        elif p2.lower().endswith(last_name_suffixes):
            return p2, p1, ""
        return parts[0], parts[1], ""
    else:
        # Обычно 3 части: Фамилия Имя Отчество
        # Проверяем, если 3-е слово - отчество (ович, евич, овна, евна, ич, ична)
        if parts[2].lower().endswith(('ович', 'евич', 'ич', 'овна', 'евна', 'ична')):
            return parts[0], parts[1], parts[2]
        return parts[0], parts[1], parts[2]
