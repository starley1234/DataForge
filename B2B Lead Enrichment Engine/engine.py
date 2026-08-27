import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from models import init_db, CompanyORM, DecisionMakerORM, Company, DecisionMaker
from translit import split_russian_name
from email_generator import generate_email_permutations
from validator import verify_email_full, normalize_phone, check_domain_mx
from scraper import WebsiteScraper
from company_sources import DaDataClient, MockCompanyRegistry
from fns_source import FNSEgrulClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("b2b_enrichment")


class EnrichmentEngine:
    def __init__(self, db_url: str = "sqlite:///leads_b2b.db", dadata_api_key: Optional[str] = None):
        self.engine, self.SessionFactory = init_db(db_url)
        self.fns = FNSEgrulClient()
        self.dadata = DaDataClient(api_key=dadata_api_key)
        self.mock_registry = MockCompanyRegistry()
        self.scraper = WebsiteScraper()

    def fetch_and_enrich_by_inn(self, inn: str, scrape_web: bool = True, verify_emails: bool = True) -> Optional[Company]:
        """
        Ищет реальную компанию по ИНН в официальном ЕГРЮЛ ФНС РФ (или DaData),
        обогащает контактами, сайтом и ЛПР и сохраняет в БД.
        """
        logger.info(f"Поиск реальной компании по ИНН {inn} в ЕГРЮЛ ФНС РФ...")
        comp = self.fns.fetch_company_by_inn(inn)
        
        # Если в ЕГРЮЛ не найдено, пробуем DaData
        if not comp and self.dadata.api_key:
            comp = self.dadata.find_by_inn(inn)
            
        # Fallback на тестовую базу
        if not comp:
            comp = self.mock_registry.find_by_inn(inn)

        if not comp:
            logger.warning(f"Компания с ИНН {inn} не найдена в источниках.")
            return None

        return self.enrich_company_and_dms(comp, scrape_web=scrape_web, verify_emails=verify_emails)

    def enrich_company_and_dms(self, company: Company, scrape_web: bool = True, verify_emails: bool = True) -> Company:
        """
        Полный цикл обогащения:
        1. Определение домена компании
        2. Краулинг сайта (телефоны, почты, страницы команды, соцсети)
        3. Генерация корпоративных email для всех найденных ЛПР
        4. Валидация контактов
        5. Сохранение в БД
        """
        logger.info(f"Обогащение данных для компании: {company.name} (ИНН: {company.inn})")

        # 1. Домен
        domain = company.domain
        if not domain and company.website:
            domain = company.website.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0].strip()
            company.domain = domain

        # 2. Скрейпинг сайта
        scraped_data = None
        if scrape_web and domain:
            try:
                logger.info(f"Сбор данных с сайта: {domain}")
                scraped_data = self.scraper.scrape_website(domain)
                
                # Если у компании не было контактов, берем с сайта
                if not company.general_email and scraped_data.get("emails"):
                    company.general_email = scraped_data["emails"][0]
                
                if not company.general_phone and scraped_data.get("phones"):
                    company.general_phone = scraped_data["phones"][0]["formatted"]

                # Добавляем найденных на сайте руководителей
                existing_names = {dm.full_name.lower() for dm in company.decision_makers}
                for p in scraped_data.get("persons", []):
                    if p["full_name"].lower() not in existing_names:
                        company.decision_makers.append(DecisionMaker(
                            company_inn=company.inn,
                            company_name=company.name,
                            full_name=p["full_name"],
                            title=p["title"],
                            role_level="Director",
                            source="website_team"
                        ))
                        existing_names.add(p["full_name"].lower())
            except Exception as e:
                logger.warning(f"Ошибка при скрейпинге {domain}: {e}")

        # 3. Генерация и обогащение ЛПР контактами
        for dm in company.decision_makers:
            last, first, middle = split_russian_name(dm.full_name)
            dm.last_name = last
            dm.first_name = first
            dm.middle_name = middle

            # Если email не задан, генерируем по корпоративному шаблону
            if not dm.email and domain:
                perms = generate_email_permutations(dm.full_name, domain)
                if perms:
                    # Выбираем наиболее вероятный паттерн (первый в списке)
                    best_candidate = perms[0]["email"]
                    dm.email = best_candidate
                    dm.email_status = "generated"
                    dm.confidence_score = perms[0]["confidence"]

            # Валидация email
            if dm.email and verify_emails:
                v_res = verify_email_full(dm.email)
                dm.email_status = v_res["status"]
                if not v_res["is_valid"]:
                    dm.confidence_score = max(10, dm.confidence_score - 40)
                else:
                    dm.confidence_score = min(98, dm.confidence_score + 10)

            # Если телефон ЛПР не задан, но есть общий телефон компании
            if not dm.phone and company.general_phone:
                dm.phone = company.general_phone
                dm.phone_type = "reception"

        # 4. Сохранение в SQLite/PostgreSQL
        self.save_company_to_db(company)
        return company

    def save_company_to_db(self, comp: Company):
        session = self.SessionFactory()
        try:
            db_comp = session.query(CompanyORM).filter_by(inn=comp.inn).first()
            if not db_comp:
                db_comp = CompanyORM(
                    inn=comp.inn,
                    kpp=comp.kpp,
                    ogrn=comp.ogrn,
                    name=comp.name,
                    short_name=comp.short_name,
                    okved=comp.okved,
                    okved_name=comp.okved_name,
                    revenue_rub=comp.revenue_rub,
                    employees_count=comp.employees_count,
                    website=comp.website,
                    domain=comp.domain,
                    region=comp.region,
                    city=comp.city,
                    address=comp.address,
                    general_email=comp.general_email,
                    general_phone=comp.general_phone,
                    status=comp.status
                )
                session.add(db_comp)
                session.flush()
            else:
                db_comp.name = comp.name
                db_comp.website = comp.website
                db_comp.domain = comp.domain
                db_comp.general_email = comp.general_email
                db_comp.general_phone = comp.general_phone

            for dm in comp.decision_makers:
                db_dm = session.query(DecisionMakerORM).filter_by(
                    company_id=db_comp.id,
                    full_name=dm.full_name
                ).first()

                if not db_dm:
                    db_dm = DecisionMakerORM(
                        company_id=db_comp.id,
                        full_name=dm.full_name,
                        first_name=dm.first_name,
                        last_name=dm.last_name,
                        middle_name=dm.middle_name,
                        title=dm.title,
                        role_level=dm.role_level,
                        email=dm.email,
                        email_status=dm.email_status,
                        phone=dm.phone,
                        phone_type=dm.phone_type,
                        telegram=dm.telegram,
                        profile_url=dm.profile_url,
                        source=dm.source,
                        confidence_score=dm.confidence_score
                    )
                    session.add(db_dm)
                else:
                    db_dm.email = dm.email
                    db_dm.email_status = dm.email_status
                    db_dm.phone = dm.phone
                    db_dm.confidence_score = dm.confidence_score

            session.commit()
            logger.info(f"Успешно сохранены данные в БД для {comp.name}")
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения в БД: {e}")
        finally:
            session.close()

    def get_all_leads(self) -> List[Dict[str, Any]]:
        """Возвращает плоский список всех обогащенных контактов ЛПР для экспорта."""
        session = self.SessionFactory()
        leads = []
        try:
            dms = session.query(DecisionMakerORM).all()
            for dm in dms:
                c = dm.company
                leads.append({
                    "inn": c.inn,
                    "company_name": c.name,
                    "okved": c.okved,
                    "okved_name": c.okved_name,
                    "revenue_rub": c.revenue_rub,
                    "website": c.website or c.domain,
                    "region": c.region or c.city,
                    "general_phone": c.general_phone,
                    "general_email": c.general_email,
                    "dm_full_name": dm.full_name,
                    "dm_title": dm.title,
                    "dm_role_level": dm.role_level,
                    "dm_email": dm.email,
                    "email_status": dm.email_status,
                    "dm_phone": dm.phone,
                    "dm_phone_type": dm.phone_type,
                    "dm_profile_url": dm.profile_url,
                    "source": dm.source,
                    "confidence_score": dm.confidence_score
                })
        finally:
            session.close()
        return leads
