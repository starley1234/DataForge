import pytest
from engine import EnrichmentEngine
from models import Company, DecisionMaker


@pytest.fixture
def test_engine(tmp_path):
    db_file = str(tmp_path / "test_leads.db")
    return EnrichmentEngine(db_url=f"sqlite:///{db_file}")


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
    ok = test_engine.update_lead(lead_id, {"lead_status": "QUALIFIED", "notes": "Заинтересован"})
    assert ok is True
    updated = test_engine.get_lead_by_id(lead_id)
    assert updated["lead_status"] == "QUALIFIED"
    assert updated["notes"] == "Заинтересован"

    # Удаление
    del_ok = test_engine.delete_lead(lead_id)
    assert del_ok is True
    assert test_engine.get_lead_by_id(lead_id) is None


def test_engine_dashboard_stats(test_engine):
    stats = test_engine.get_dashboard_stats()
    assert "total_companies" in stats
    assert "total_dms" in stats
    assert "roles_breakdown" in stats
