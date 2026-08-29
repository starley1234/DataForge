import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from web_app import app
from sources.rusprofile_sources import CounterpartyDataAggregator
from core.counterparty_intelligence import CounterpartyIntelligenceEngine
from core.engine import EnrichmentEngine


@pytest.fixture
def aggregator():
    return CounterpartyDataAggregator()


@pytest.fixture
def counterparty_engine():
    engine = EnrichmentEngine()
    return CounterpartyIntelligenceEngine(engine=engine)


@pytest.fixture
def test_client():
    return TestClient(app)


class TestCounterpartyDataAggregator:
    def test_build_dossier_sberbank(self, aggregator):
        data = aggregator.build_full_dossier("7707083893")
        assert data is not None
        assert data["summary"]["inn"] == "7707083893"
        assert "СБЕРБАНК" in data["summary"]["name"].upper() or "ПРЕДПРИЯТИЕ" in data["summary"]["name"].upper()
        assert data["finance"]["revenue_latest"] > 0
        assert data["summary"]["reliability_score"] >= 75
        assert len(data["risk_factors"]["positive"]) > 0
        assert len(data["risk_factors"]["critical"]) == 0

    def test_build_dossier_yandex(self, aggregator):
        data = aggregator.build_full_dossier("7736207543")
        assert data is not None
        assert data["summary"]["inn"] == "7736207543"
        assert data["summary"]["capital_rub"] > 0
        assert len(data["founders"]) > 0
        assert len(data["affiliated_companies"]) > 0

    def test_build_dossier_arbitrary_inn(self, aggregator):
        data = aggregator.build_full_dossier("7712345678")
        assert data is not None
        assert data["summary"]["inn"] == "7712345678"
        assert data["summary"]["ogrn"].startswith("1")
        assert data["summary"]["registration_date"] is not None
        assert data["summary"]["reliability_score"] > 0
        assert data["leadership"]["ceo_name"] is not None

    def test_risk_markers_and_scoring(self, aggregator):
        data = aggregator.build_full_dossier("7707083893")
        assert data["summary"]["reliability_score"] >= 75
        assert any("лет" in m.lower() or "организация" in m.lower() for m in data["risk_factors"]["positive"])
        assert data["procurement"]["in_rnp"] is False


class TestCounterpartyIntelligenceEngine:
    def test_get_full_dossier(self, counterparty_engine):
        dossier = counterparty_engine.get_full_dossier("7707083893")
        assert dossier is not None
        assert "summary" in dossier
        assert "finance" in dossier
        assert "procurement" in dossier
        assert "courts" in dossier
        assert "fssp" in dossier
        assert "risk_factors" in dossier
        assert "founders" in dossier
        assert "affiliated_companies" in dossier
        assert "licenses" in dossier
        assert "trademarks" in dossier
        assert "inspections" in dossier
        assert "leadership" in dossier

        assert dossier["summary"]["inn"] == "7707083893"
        assert dossier["summary"]["reliability_score"] > 50

    def test_generate_markdown_report(self, counterparty_engine):
        dossier = counterparty_engine.get_full_dossier("7736207543")
        md = counterparty_engine.generate_due_diligence_report_md(dossier)
        assert md is not None
        assert "Due Diligence 360°" in md
        assert "7736207543" in md
        assert "ГИР БО ФНС РФ" in md
        assert "Госзакупки" in md
        assert "Итоговая оценка надежности" in md

    def test_export_excel(self, counterparty_engine):
        dossier = counterparty_engine.get_full_dossier("7707083893")
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            temp_path = f.name
        
        try:
            res_path = counterparty_engine.export_due_diligence_excel(dossier, temp_path)
            assert res_path is not None
            assert os.path.exists(res_path)
            assert os.path.getsize(res_path) > 1000
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestCounterpartyApiEndpoints:
    def test_api_dossier(self, test_client):
        res = test_client.get("/api/counterparty/dossier/7707083893")
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["inn"] == "7707083893"
        assert data["summary"]["reliability_score"] > 0
        assert len(data["founders"]) > 0

    def test_api_report_markdown(self, test_client):
        res = test_client.get("/api/counterparty/report-markdown/7736207543")
        assert res.status_code == 200
        assert "Due Diligence 360°" in res.text
        assert "7736207543" in res.text

    def test_api_export_excel(self, test_client):
        res = test_client.get("/api/counterparty/export-excel/7707083893")
        assert res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers["content-type"]
        assert len(res.content) > 1000
