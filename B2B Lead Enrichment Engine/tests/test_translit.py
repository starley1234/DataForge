import pytest
from translit import (
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


def test_transliterate_variants():
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


def test_split_russian_name_female():
    last, first, middle = split_russian_name("Смирнова Анна Сергеевна")
    assert last == "Смирнова"
    assert first == "Анна"
    assert middle == "Сергеевна"


def test_split_russian_name_hyphenated():
    last, first, middle = split_russian_name("Мамин-Сибиряк Дмитрий Наркисович")
    assert "Мамин" in last
    assert first == "Дмитрий"
    assert middle == "Наркисович"


def test_detect_gender():
    assert detect_gender("Иванов", "Иван", "Иванович") == "male"
    assert detect_gender("Иванова", "Анна", "Сергеевна") == "female"
    assert detect_gender("", "Ольга", "") == "female"
    assert detect_gender("", "Михаил", "") == "male"


def test_get_salutation():
    assert "Иван Иванович" in get_salutation("Иванов Иван Иванович", formal=True)
    assert "Анна Сергеевна" in get_salutation("Иванова Анна Сергеевна", formal=True)
    assert "Уважаемая" in get_salutation("Иванова Анна Сергеевна", formal=True)
    assert "Уважаемый" in get_salutation("Иванов Иван Иванович", formal=True)
    assert get_salutation("Иван", formal=False) == "Здравствуйте, Иван!"
