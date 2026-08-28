import pytest
from core.deliverability import analyze_domain_deliverability


def test_analyze_domain_empty():
    res = analyze_domain_deliverability("")
    assert res["valid"] is False


def test_analyze_domain_valid():
    res = analyze_domain_deliverability("yandex.ru")
    assert res["valid"] is True
    assert res["has_mx"] is True
    assert "provider" in res
    assert res["deliverability_score"] >= 50
