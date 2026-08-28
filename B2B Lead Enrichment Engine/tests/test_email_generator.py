import pytest
from email_generator import (
    generate_email_permutations,
    detect_pattern_from_sample,
    generate_department_emails,
    clean_domain
)


def test_clean_domain():
    assert clean_domain("https://www.company.ru/about") == "company.ru"
    assert clean_domain("http://yandex.ru") == "yandex.ru"
    assert clean_domain("sberbank.ru:8080") == "sberbank.ru"


def test_generate_email_permutations():
    perms = generate_email_permutations("Иванов Иван Иванович", "company.ru")
    assert len(perms) >= 10
    emails = [p["email"] for p in perms]
    assert "i.ivanov@company.ru" in emails
    assert "ivanov.i@company.ru" in emails
    assert "ivan.ivanov@company.ru" in emails
    assert "ivanov@company.ru" in emails


def test_known_pattern_boosting():
    perms = generate_email_permutations(
        "Петров Сергей Николаевич",
        "company.ru",
        known_pattern="{last}.{f}"
    )
    assert perms[0]["pattern"] == "{last}.{f}"
    assert perms[0]["email"] == "petrov.s@company.ru"
    assert perms[0]["confidence"] == 98


def test_detect_pattern_from_sample():
    pat1 = detect_pattern_from_sample("a.ivanov@domain.ru", "Иванов Алексей", "domain.ru")
    assert pat1 == "{f}.{last}"

    pat2 = detect_pattern_from_sample("ivanov.a@domain.ru", "Иванов Алексей", "domain.ru")
    assert pat2 == "{last}.{f}"

    pat3 = detect_pattern_from_sample("aleksey.ivanov@domain.ru", "Иванов Алексей", "domain.ru")
    assert pat3 == "{first}.{last}"


def test_generate_department_emails():
    depts = generate_department_emails("company.ru")
    assert len(depts) >= 5
    dept_emails = [d["email"] for d in depts]
    assert "info@company.ru" in dept_emails
    assert "sales@company.ru" in dept_emails
    assert "pr@company.ru" in dept_emails
