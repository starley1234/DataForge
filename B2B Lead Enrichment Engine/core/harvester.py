import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.models import Company, DecisionMaker
from core.engine import EnrichmentEngine
from sources.headhunter import HeadHunterClient
from sources.msp_registry import MSPRegistryClient
from sources.tech_stack import TechStackDetector
from sources.financial_scoring import FinancialScoringEngine
from sources.fns_egrul import FNSEgrulClient
from sources.company_registry import CompanyRegistry
from core.email_generator import clean_domain
from core.config import settings

logger = logging.getLogger("b2b_harvester")


class UniversalB2BHarvester:
    """
    Универсальный комбайн и сборщик актуальных B2B-данных и лидов:
    1. Поиск активно нанимающих компаний через HeadHunter API (индикатор роста)
    2. Обогащение реквизитов и руководства через ЕГРЮЛ ФНС РФ
    3. Определение статуса МСП по критериям 209-ФЗ
    4. Детекция технологического стека, CMS и используемых CRM
    5. Комплексный расчет финансовой устойчивости и риска
    6. Генерация и валидация контактов ЛПР (Email, Phone, Timezone)
    """

    def __init__(self, engine: Optional[EnrichmentEngine] = None):
        self.engine = engine or EnrichmentEngine()
        self.hh = HeadHunterClient()
        self.msp = MSPRegistryClient()
        self.tech_detector = TechStackDetector()
        self.registry = CompanyRegistry()

    def harvest_company(self, query: str, city: Optional[str] = None) -> Optional[Company]:
        """
        Комплексный сбор досье компании по названию, ИНН или домену.
        """
        clean_q = query.strip()
        logger.info(f"Сбор данных для: {clean_q}")

        # 1. Основное обогащение через движок
        comp = self.engine.fetch_and_enrich(clean_q, scrape_web=True, verify_emails=True)
        if not comp:
            return None

        # 2. Дополнительные данные HeadHunter (вакансии и открытые позиции)
        try:
            hh_profile = self.hh.search_employer(comp.name, city=city or comp.city or comp.region)
            if hh_profile:
                if not comp.website and hh_profile.get("domain"):
                    comp.website = hh_profile["domain"]
                    comp.domain = hh_profile["domain"]
                
                # Добавляем отраслевые теги из HH
                if hh_profile.get("industries"):
                    hh_tags = ", ".join(hh_profile["industries"][:3])
                    comp.tags = f"{comp.tags or ''}, {hh_tags}".strip(", ")
        except Exception as e:
            logger.debug(f"HH harvest error: {e}")

        # 3. Классификация МСП (209-ФЗ)
        try:
            msp_info = self.msp.classify_by_metrics(
                revenue_rub=comp.revenue_rub,
                employees_count=comp.employees_count,
                inn=comp.inn
            )
            if not comp.notes:
                comp.notes = f"Категория МСП: {msp_info['category_name']}"
            else:
                comp.notes += f" | МСП: {msp_info['category_name']}"
        except Exception as e:
            logger.debug(f"MSP classify error: {e}")

        # 4. Финансовый скоринг и оценка надежности
        score, risk, factors = FinancialScoringEngine.calculate_solvency(comp)
        comp.solvency_score = score
        comp.risk_level = risk

        # Сохраняем обновленные данные в БД
        self.engine.save_company_to_db(comp)
        return comp

    def harvest_batch(self, queries: List[str], max_workers: int = 4) -> List[Company]:
        """Параллельный сбор данных по перечню запросов."""
        results: List[Company] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_query = {executor.submit(self.harvest_company, q): q for q in queries if q and q.strip()}
            for future in as_completed(future_to_query):
                q = future_to_query[future]
                try:
                    comp = future.result()
                    if comp:
                        results.append(comp)
                except Exception as e:
                    logger.warning(f"Ошибка сбора для {q}: {e}")
        return results
