import pytest
from validator import (
    validate_email_syntax,
    is_role_based_email,
    check_domain_mx,
    verify_email_full,
    normalize_phone
)


def test_validate_email_syntax():
    assert validate_email_syntax("user@example.com") is True
    assert validate_email_syntax("first.last@company.ru") is True
    assert validate_email_syntax("bad-email") is False
    assert validate_email_syntax("bad@domain") is False
    assert validate_email_syntax("spaces in@email.com") is False


def test_is_role_based_email():
    assert is_role_based_email("info@company.ru") is True
    assert is_role_based_email("sales@company.ru") is True
    assert is_role_based_email("support@company.ru") is True
    assert is_role_based_email("i.ivanov@company.ru") is False


def test_disposable_email_detection():
    res = verify_email_full("test@mailinator.com")
    assert res["is_valid"] is False
    assert res["status"] == "disposable"


def test_normalize_phone():
    # Мобильный РФ
    m_res = normalize_phone("+7 (916) 123-45-67")
    assert m_res["valid"] is True
    assert m_res["formatted"] == "+79161234567"
    assert m_res["type"] == "mobile"

    # Офисный городской (Москва 495)
    o_res = normalize_phone("8 (495) 739-70-00")
    assert o_res["valid"] is True
    assert o_res["formatted"] == "+74957397000"
    assert o_res["type"] == "office"

    # 8-800
    t_res = normalize_phone("8-800-200-00-00")
    assert t_res["valid"] is True
    assert t_res["type"] == "8800"

    # Некорректный номер
    bad = normalize_phone("12345")
    assert bad["valid"] is False
