import pytest
from validator import (
    validate_email_syntax,
    is_role_based_email,
    check_domain_mx,
    verify_email_full,
    normalize_phone,
    detect_timezone_offset,
    is_calling_window_open
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
    assert is_role_based_email("tender@company.ru") is True
    assert is_role_based_email("i.ivanov@company.ru") is False


def test_disposable_email_detection():
    res = verify_email_full("test@mailinator.com")
    assert res["is_valid"] is False
    assert res["status"] == "disposable"


def test_normalize_phone():
    # Мобильный РФ (МТС / DEF 916)
    m_res = normalize_phone("+7 (916) 123-45-67")
    assert m_res["valid"] is True
    assert m_res["formatted"] == "+79161234567"
    assert m_res["type"] == "mobile"
    assert m_res["carrier"] is not None
    assert m_res["whatsapp_link"] == "https://wa.me/79161234567"

    # Офисный городской (Москва 495)
    o_res = normalize_phone("8 (495) 739-70-00")
    assert o_res["valid"] is True
    assert o_res["formatted"] == "+74957397000"
    assert o_res["type"] == "office"
    assert o_res["timezone"] is not None

    # 8-800
    t_res = normalize_phone("8-800-200-00-00")
    assert t_res["valid"] is True
    assert t_res["type"] == "8800"

    # Некорректный номер
    b_res = normalize_phone("12345")
    assert b_res["valid"] is False


def test_russian_timezone_detection():
    off_msk, label_msk = detect_timezone_offset("г. Москва")
    assert off_msk == 3
    assert "MSK" in label_msk

    off_ekb, label_ekb = detect_timezone_offset("Свердловская область, г. Екатеринбург")
    assert off_ekb == 5
    assert "MSK+2" in label_ekb

    off_nsk, label_nsk = detect_timezone_offset("Новосибирская обл., г. Новосибирск")
    assert off_nsk == 7
    assert "MSK+4" in label_nsk

    off_vld, label_vld = detect_timezone_offset("Приморский край, г. Владивосток")
    assert off_vld == 10
    assert "MSK+7" in label_vld


def test_calling_window_check():
    is_open, loc_time = is_calling_window_open(3)
    assert isinstance(is_open, bool)
    assert len(loc_time) == 5 and ":" in loc_time
