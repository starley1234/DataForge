import pytest
from core.translit import (
    transliterate,
    transliterate_variants,
    split_russian_name,
    detect_gender,
    get_salutation
)


def test_transliterate_basic():
    assert transliterate("Иванов") == "ivanov"
    assert transliterate("Петров") == "petrov"
    assert transliterate("Сидоров") == "sidorov"


def test_transliterate_complex_chars():
    assert "shch" in transliterate("Щербаков")
    assert "zh" in transliterate("Жуков")
    assert "ch" in transliterate("Чехов")
    assert "ya" in transliterate("Яковлев")
    assert "yu" in transliterate("Юдин")


def test_transliterate_variants_and_aliases():
    vars_alex = transliterate_variants("Александр")
    assert "alex" in vars_alex or "alexander" in vars_alex

    vars_dmitry = transliterate_variants("Дмитрий")
    assert "dmitry" in vars_dmitry or "dima" in vars_dmitry

    vars_yulia = transliterate_variants("Юлия")
    assert len(vars_yulia) >= 1
    assert any("yuli" in v or "iuli" in v for v in vars_yulia)


def test_split_russian_name_three_parts():
    last, first, middle = split_russian_name("Иванов Иван Иванович")
    assert last == "Иванов"
    assert first == "Иван"
    assert middle == "Иванович"


def test_split_russian_name_two_parts_last_first():
    last, first, middle = split_russian_name("Иванов Иван")
    assert last == "Иванов"
    assert first == "Иван"
    assert middle == ""


def test_split_russian_name_two_parts_first_last():
    last, first, middle = split_russian_name("Иван Иванов")
    assert last == "Иванов"
    assert first == "Иван"


def test_split_russian_name_compound_and_honorifics():
    last, first, middle = split_russian_name("Генеральный директор Мамин-Сибиряк Дмитрий Наркисович")
    assert "Мамин-сибиряк" in last or "Мамин-Сибиряк" in last
    assert first == "Дмитрий"
    assert middle == "Наркисович"


def test_detect_gender():
    assert detect_gender("Иванов", "Иван", "Иванович") == "male"
    assert detect_gender("Петрова", "Анна", "Сергеевна") == "female"
    assert detect_gender("", "Екатерина", "") == "female"
    assert detect_gender("", "Алексей", "") == "male"


def test_salutation_styles():
    formal = get_salutation("Иванов Иван Иванович", formal=True, style="business")
    assert formal == "Уважаемый Иван Иванович!"

    female_formal = get_salutation("Иванова Анна Сергеевна", formal=True, style="business")
    assert female_formal == "Уважаемая Анна Сергеевна!"

    direct = get_salutation("Иванов Иван Иванович", style="direct")
    assert direct == "Добрый день, Иван!"

    executive = get_salutation("Иванов Иван Иванович", style="executive")
    assert executive == "Иван Иванович, добрый день!"
