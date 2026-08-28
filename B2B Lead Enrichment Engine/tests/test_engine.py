import pytest
from engine import EnrichmentEngine, calculate_company_solvency_score
from models import Company, DecisionMaker


@pytest.fixture
def test_engine(tmp_path):
    db_file = str(tmp_path / "test_leads.db")
    return EnrichmentEngine(db_url=f"sqlite:///{db_file}")


def test_calculate_company_solvency_score():
    comp = Company(
        inn="7707083893",
        name='ПАО "СБЕРБАНК"',
        revenue_rub=3000000000000,
        employees_count=210000,
        website="sberbank.ru",
        status="ACTIVE"
    )
    score, risk = calculate_company_solvency_score(comp)
    assert score >= 85
    assert risk == "LOW"


def test_engine_save_and_retrieve(test_engine):
    comp = Company(
        inn="7700000001",
        name='ООО "ТестХолдинг"',
        website="test-holding.ru",
        domain="test-holding.ru",
        decision_makers=[
            DecisionMaker(
                full_name="Иванов Алексей Петрович",
                title="Генеральный директор",
                email="a.ivanov@test-holding.ru",
                email_status="valid_mx",
                confidence_score=90
            )
        ]
    )
    test_engine.save_company_to_db(comp)
    leads = test_engine.get_all_leads()
    assert len(leads) == 1
    assert leads[0]["inn"] == "7700000001"
    assert leads[0]["dm_full_name"] == "Иванов Алексей Петрович"


def test_engine_update_and_delete_lead(test_engine):
    comp = Company(
        inn="7700000002",
        name='ООО "Инновации"',
        decision_makers=[
            DecisionMaker(
                full_name="Петров Иван Сергеевич",
                title="Директор",
                lead_status="NEW"
            )
        ]
    )
    test_engine.save_company_to_db(comp)
    leads = test_engine.get_all_leads(query="7700000002")
    assert len(leads) == 1
    lead_id = leads[0]["id"]

    # Обновление
    ok = test_engine.update_lead(lead_id, {"lead_status": "QUALIFIED", "notes": "Звонок 15:00"})
    assert ok is True
    updated = test_engine.get_lead_by_id(lead_id)
    assert updated["lead_status"] == "QUALIFIED"

    # Удаление
    deleted = test_engine.delete_lead(lead_id)
    assert deleted is True
    assert test_engine.get_lead_by_id(lead_id) is None


def test_engine_bulk_operations(test_engine):
    comp = Company(
        inn="7700000003",
        name='ООО "Массовый Тест"',
        decision_makers=[
            DecisionMaker(full_name="Сидоров Сидор", title="CEO", lead_status="NEW"),
            DecisionMaker(full_name="Кузнецов Петр", title="CTO", lead_status="NEW")
        ]
    )
    test_engine.save_company_to_db(comp)
    leads = test_engine.get_all_leads(query="7700000003")
    assert len(leads) == 2

    ids = [l["id"] for l in leads]
    test_engine.bulk_update_lead_status(ids, "IN_PROGRESS")
    leads_after = test_engine.get_all_leads(query="7700000003")
    assert all(l["lead_status"] == "IN_PROGRESS" for l in leads_after)

    del_cnt = test_engine.bulk_delete_leads(ids)
    assert del_cnt == 2
    assert len(test_engine.get_all_leads(query="7700000003")) == 0


def test_mock_registry_search():
    engine = EnrichmentEngine()
    c1 = engine.mock_registry.find_by_query("Яндекс")
    assert c1 is not None
    assert c1.inn == "7736207543"

    c2 = engine.mock_registry.find_by_inn("7707083893")
    assert c2 is not None
    assert "СБЕРБАНК" in c2.name
