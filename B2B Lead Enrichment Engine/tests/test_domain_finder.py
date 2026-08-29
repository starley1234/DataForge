import pytest
from core.domain_finder import DomainFinder, clean_company_name_for_search


def test_clean_company_name():
    assert clean_company_name_for_search('ООО "ЯНДЕКС"') == "ЯНДЕКС"
    assert clean_company_name_for_search('ПАО "Сбербанк"') == "Сбербанк"
    assert clean_company_name_for_search('АО "Лаборатория Касперского"') == "Лаборатория Касперского"
    assert clean_company_name_for_search('ИП Иванов И.И.') == "Иванов И.И."


def test_domain_finder_heuristics():
    finder = DomainFinder()
    assert finder._is_valid_corporate_domain("yandex.ru") is False  # поисковик в исключениях
    assert finder._is_valid_corporate_domain("company-test.ru") is True
    assert finder._is_valid_corporate_domain("spark-interfax.ru") is False  # агрегатор в исключениях
