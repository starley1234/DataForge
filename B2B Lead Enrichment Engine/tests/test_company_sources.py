import pytest
from core.company_sources import MockCompanyRegistry, DaDataClient


def test_mock_registry_completeness():
    reg = MockCompanyRegistry()
    comps = reg.get_all()
    assert len(comps) >= 15
    for c in comps:
        assert len(c.inn) in (10, 12)
        assert c.name is not None
        assert len(c.decision_makers) >= 1
        assert c.decision_makers[0].full_name is not None


def test_mock_registry_find_by_inn():
    reg = MockCompanyRegistry()
    comp = reg.find_by_inn("7736207543")
    assert comp is not None
    assert comp.name == 'ООО "ЯНДЕКС"'
    assert comp.domain == "yandex.ru"


def test_mock_registry_find_by_query_stemming():
    reg = MockCompanyRegistry()
    comp = reg.find_by_query("касперский")
    assert comp is not None
    assert "КАСПЕРСКОГО" in comp.name


def test_dadata_client_init():
    dadata = DaDataClient(api_key="test_token")
    assert dadata.api_key == "test_token"
