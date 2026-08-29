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


def test_industry_crawler():
    from sources.industry_crawler import IndustryCrawler
    from sources.company_registry import CompanyRegistry

    crawler = IndustryCrawler()
    comps = crawler.harvest_industry_companies(count_per_sector=2)
    assert len(comps) >= 16
    assert all(c.inn and c.name and c.okved for c in comps)

    registry = CompanyRegistry()
    all_known = registry.get_all()
    assert len(all_known) >= 50

