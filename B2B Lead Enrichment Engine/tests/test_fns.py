import pytest
from fns_source import parse_management_string, FNSEgrulClient


def test_parse_management_string():
    name, post = parse_management_string("Генеральный директор: Иванов Иван Иванович")
    assert name == "Иванов Иван Иванович"
    assert post == "Генеральный директор"

    name2, post2 = parse_management_string("<b>Президент:</b> Петров Петр")
    assert name2 == "Петров Петр"
    assert post2 == "Президент"

    name3, post3 = parse_management_string("Сидоров Сидор Сидорович")
    assert name3 == "Сидоров Сидор Сидорович"
    assert post3 == "Генеральный директор"


def test_fns_client_init():
    client = FNSEgrulClient(timeout=10.0)
    assert client.timeout == 10.0
    assert "User-Agent" in client.session.headers
