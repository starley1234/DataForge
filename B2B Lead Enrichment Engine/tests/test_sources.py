import pytest
from unittest.mock import MagicMock, patch
from sources.msp_registry import MSPRegistryClient
from sources.tech_stack import TechStackDetector
from sources.financial_scoring import FinancialScoringEngine
from sources.headhunter import HeadHunterClient
from core.models import Company


def test_msp_registry_classification():
    client = MSPRegistryClient()

    # Микропредприятие
    micro = client.classify_by_metrics(revenue_rub=50_000_000, employees_count=10)
    assert micro["category_code"] == "MICRO"
    assert micro["is_msp"] is True

    # Малое
    small = client.classify_by_metrics(revenue_rub=400_000_000, employees_count=80)
    assert small["category_code"] == "SMALL"

    # Среднее
    medium = client.classify_by_metrics(revenue_rub=1_500_000_000, employees_count=200)
    assert medium["category_code"] == "MEDIUM"

    # Крупный бизнес
    enterprise = client.classify_by_metrics(revenue_rub=5_000_000_000, employees_count=1000)
    assert enterprise["category_code"] == "LARGE"
    assert enterprise["is_msp"] is False


def test_tech_stack_detection():
    detector = TechStackDetector()
    html_sample = """
    <html>
      <head>
        <script src="https://mc.yandex.ru/metrika/tag.js"></script>
        <script src="https://static.tildacdn.com/js/tilda-scripts-3.0.min.js"></script>
        <script src="https://code.jivosite.com/widget/12345"></script>
      </head>
      <body>
        <div class="tildaBlocks">Hello World</div>
      </body>
    </html>
    """
    techs = detector.detect_technologies(html_sample)
    assert "Tilda" in techs
    assert "Yandex Metrika" in techs
    assert "JivoSite" in techs


def test_financial_scoring():
    comp = Company(
        inn="7736207543",
        name='ООО "ТЕСТ"',
        status="ACTIVE",
        revenue_rub=500_000_000,
        employees_count=120,
        website="test.ru",
        general_email="info@test.ru"
    )
    score, risk, factors = FinancialScoringEngine.calculate_solvency(comp)
    assert score >= 70
    assert risk == "LOW"
    assert len(factors) > 0


def test_headhunter_client_search():
    client = HeadHunterClient()
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [
                    {
                        "id": "123",
                        "name": "Яндекс",
                        "site_url": "https://yandex.ru",
                        "open_vacancies": 450,
                        "alternate_url": "https://hh.ru/employer/123"
                    }
                ]
            }
        )
        res = client.search_employer("Яндекс")
        assert res is not None
        assert res["name"] == "Яндекс"
        assert res["open_vacancies"] == 450
