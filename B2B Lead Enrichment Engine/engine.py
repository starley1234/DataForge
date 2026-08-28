import logging
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse
from datetime import datetime
from sqlalchemy import desc, func

from models import init_db, CompanyORM, DecisionMakerORM, Company, DecisionMaker
from translit import split_russian_name
from email_generator import generate_email_permutations, detect_pattern_from_sample, clean_domain
from validator import verify_email_full, normalize_phone, check_domain_mx
from scraper import WebsiteScraper
from domain_finder import DomainFinder
from company_sources import DaDataClient, MockCompanyRegistry
from fns_source import FNSEgrulClient
from config import settings

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("b2b_engine")


class EnrichmentEngine:
    def __init__(self, db_url: Optional[str] = None, dadata_api_key: Optional[str] = None):
        db_path = db_url or settings.DATABASE_URL
        self.engine, self.SessionFactory = init_db(db_path)
        self.fns = FNSEgrulClient(timeout=settings.EGRUL_TIMEOUT)
        self.dadata = DaDataClient(api_key=dadata_api_key or settings.DADATA_API_KEY)
        self.mock_registry = MockCompanyRegistry()
        self.scraper = WebsiteScraper()
        self.domain_finder = DomainFinder()

    def fetch_and_enrich(
        self,
        query: str,
        scrape_web: bool = True,
        verify_emails: bool = True
    ) -> Optional[Company]:
        """
        Универсальный метод поиска и обогащения:
        Принимает ИНН, ОГРН или наименование компании.
        1. Ищет в ЕГРЮЛ ФНС РФ.
        2. При отсутствии пробует DaData.
        3. При отсутствии ищет в эталонной базе.
        4. Запускает обогащение контактами и краулинг.
        """
        clean_q = query.strip()
        logger.info(f"Запрос на поиск компании: '{clean_q}'")

        # 1. Поиск в официальном ЕГРЮЛ
        comp = self.fns.fetch_company(clean_q)

        # 2. Если не найдено и есть DaData
        if not comp and self.dadata.api_key:
            comp = self.dadata.find_by_inn_or_ogrn(clean_q)

        # 3. Fallback на реестр эталонных данных
        if not comp:
            comp = self.mock_registry.find_by_query(clean_q)

        if not comp:
            logger.warning(f"Организация '{clean_q}' не найдена в источниках данных.")
            return None

        return self.enrich_company_and_dms(comp, scrape_web=scrape_web, verify_emails=verify_emails)

    def fetch_and_enrich_by_inn(self, inn: str, scrape_web: bool = True, verify_emails: bool = True) -> Optional[Company]:
        """Совместимость со старым API по ИНН."""
        return self.fetch_and_enrich(inn, scrape_web=scrape_web, verify_emails=verify_emails)

    def enrich_by_domain(self, raw_domain: str, verify_emails: bool = True) -> Optional[Company]:
        """
        Прямое обогащение организации по сайту / домену.
        Краулит сайт, извлекает реквизиты (ИНН/ОГРН) и команду.
        """
        clean_dom = clean_domain(raw_domain)
        if not clean_dom:
            return None

        logger.info(f"Обогащение организации по домену: {clean_dom}")
        scraped = self.scraper.scrape_website(clean_dom)

        inn = scraped.get("requisites", {}).get("inn") or f"DOM-{abs(hash(clean_dom)) % 10000000000:010d}"
        comp_name = clean_dom.split(".")[0].upper()

        dms: List[DecisionMaker] = []
        for p in scraped.get("persons", []):
            dms.append(DecisionMaker(
                company_inn=inn,
                company_name=comp_name,
                full_name=p["full_name"],
                title=p["title"],
                role_level=p.get("role_level", "Director"),
                email=p.get("email"),
                phone=p.get("phone"),
                source=p.get("source", "website")
            ))

        comp = Company(
            inn=inn,
            name=comp_name,
            short_name=comp_name,
            website=clean_dom,
            domain=clean_dom,
            general_email=scraped["emails"][0] if scraped.get("emails") else None,
            general_phone=scraped["phones"][0]["formatted"] if scraped.get("phones") else None,
            telegram=scraped["socials"]["telegram"][0] if scraped.get("socials", {}).get("telegram") else None,
            vk=scraped["socials"]["vk"][0] if scraped.get("socials", {}).get("vk") else None,
            decision_makers=dms,
            source="website_crawler"
        )

        return self.enrich_company_and_dms(comp, scrape_web=False, verify_emails=verify_emails)

    def enrich_company_and_dms(
        self,
        company: Company,
        scrape_web: bool = True,
        verify_emails: bool = True
    ) -> Company:
        """
        Полный производственный цикл обогащения:
        1. Определение или поиск официального корпоративного домена (DomainFinder).
        2. Краулинг сайта (телефоны, почты, страницы команды, соцсети, реквизиты).
        3. Обучение паттерну email (Pattern Learning).
        4. Генерация корпоративных адресов для всех найденных ЛПР.
        5. Валидация контактов (DNS MX + Phone E.164 + Ролевые фильтры).
        6. Расчет скоринга доверия.
        7. Сохранение в базу данных с дедупликацией.
        """
        logger.info(f"Обогащение данных: {company.name} (ИНН: {company.inn})")

        # 1. Поиск домена, если он не указан
        domain = company.domain
        if not domain and company.website:
            domain = clean_domain(company.website)
            company.domain = domain

        if not domain:
            # Интеллектуальный поиск домена через DomainFinder
            found_domain = self.domain_finder.find_domain(company.name, city=company.city or company.region, inn=company.inn)
            if found_domain:
                domain = found_domain
                company.domain = domain
                company.website = domain
                logger.info(f"Найден корпоративный домен: {domain}")

        # 2. Краулинг веб-ресурса компании
        known_email_pattern = None
        scraped_data = None
        if scrape_web and domain:
            try:
                logger.info(f"Сбор контактных данных с сайта: {domain}")
                scraped_data = self.scraper.scrape_website(domain)

                if not company.general_email and scraped_data.get("emails"):
                    company.general_email = scraped_data["emails"][0]

                if not company.general_phone and scraped_data.get("phones"):
                    company.general_phone = scraped_data["phones"][0]["formatted"]

                if not company.telegram and scraped_data.get("socials", {}).get("telegram"):
                    company.telegram = scraped_data["socials"]["telegram"][0]

                if not company.vk and scraped_data.get("socials", {}).get("vk"):
                    company.vk = scraped_data["socials"]["vk"][0]

                # Добавляем новых руководителей, обнаруженных на страницах сайта
                existing_names = {dm.full_name.lower().strip() for dm in company.decision_makers}
                for p in scraped_data.get("persons", []):
                    clean_pname = p["full_name"].strip()
                    if clean_pname.lower() not in existing_names:
                        company.decision_makers.append(DecisionMaker(
                            company_inn=company.inn,
                            company_name=company.name,
                            full_name=clean_pname,
                            title=p["title"],
                            role_level=p.get("role_level", "Director"),
                            email=p.get("email"),
                            phone=p.get("phone"),
                            source=p.get("source", "website_team")
                        ))
                        existing_names.add(clean_pname.lower())

                # 3. Детекция корпоративного шаблона email компании
                # Если на сайте есть email сотрудника и его имя, определяем шаблон
                for dm in company.decision_makers:
                    if dm.email:
                        pat = detect_pattern_from_sample(dm.email, dm.full_name, domain)
                        if pat:
                            known_email_pattern = pat
                            logger.info(f"Определен корпоративный шаблон email: {pat}")
                            break
            except Exception as e:
                logger.warning(f"Ошибка при краулинге сайта {domain}: {e}")

        # 4. Генерация и валидация контактов для каждого ЛПР
        for dm in company.decision_makers:
            last, first, middle = split_russian_name(dm.full_name)
            dm.last_name = last
            dm.first_name = first
            dm.middle_name = middle

            # Если email не задан, генерируем по вероятностным шаблонам
            if not dm.email and domain:
                perms = generate_email_permutations(dm.full_name, domain, known_pattern=known_email_pattern)
                if perms:
                    best_cand = perms[0]
                    dm.email = best_cand["email"]
                    dm.email_pattern = best_cand["pattern"]
                    dm.email_status = "generated"
                    dm.confidence_score = best_cand["confidence"]

            # Валидация email через DNS MX и синтаксис
            if dm.email and verify_emails:
                v_res = verify_email_full(dm.email)
                dm.email_status = v_res["status"]
                if not v_res["is_valid"]:
                    dm.confidence_score = max(10, dm.confidence_score - 40)
                else:
                    dm.confidence_score = min(98, max(dm.confidence_score, v_res["confidence"]))

            # Если телефон ЛПР отсутствует, подставляем общий телефон компании
            if not dm.phone and company.general_phone:
                dm.phone = company.general_phone
                dm.phone_type = "reception"

            # Валидация и нормализация телефона
            if dm.phone:
                p_res = normalize_phone(dm.phone)
                if p_res["valid"]:
                    dm.phone = p_res["formatted"]
                    if not dm.phone_type or dm.phone_type == "other":
                        dm.phone_type = p_res["type"]

        # 5. Сохранение в БД
        self.save_company_to_db(company)
        return company

    def save_company_to_db(self, comp: Company):
        """Потокобезопасное сохранение компании и связанных ЛПР в БД."""
        session = self.SessionFactory()
        try:
            db_comp = session.query(CompanyORM).filter_by(inn=comp.inn).first()
            now = datetime.utcnow()

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
                    telegram=comp.telegram,
                    vk=comp.vk,
                    source=comp.source or "egrul",
                    tags=comp.tags,
                    notes=comp.notes,
                    status=comp.status,
                    created_at=now,
                    updated_at=now
                )
                session.add(db_comp)
                session.flush()
            else:
                db_comp.name = comp.name
                if comp.short_name:
                    db_comp.short_name = comp.short_name
                if comp.website:
                    db_comp.website = comp.website
                if comp.domain:
                    db_comp.domain = comp.domain
                if comp.general_email:
                    db_comp.general_email = comp.general_email
                if comp.general_phone:
                    db_comp.general_phone = comp.general_phone
                if comp.telegram:
                    db_comp.telegram = comp.telegram
                if comp.vk:
                    db_comp.vk = comp.vk
                if comp.tags:
                    db_comp.tags = comp.tags
                db_comp.updated_at = now

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
                        gender=dm.gender,
                        title=dm.title,
                        role_level=dm.role_level or "C-Level",
                        email=dm.email,
                        email_status=dm.email_status,
                        email_pattern=dm.email_pattern,
                        phone=dm.phone,
                        phone_type=dm.phone_type,
                        telegram=dm.telegram,
                        profile_url=dm.profile_url,
                        source=dm.source,
                        confidence_score=dm.confidence_score,
                        lead_status=dm.lead_status or "NEW",
                        notes=dm.notes,
                        created_at=now,
                        updated_at=now
                    )
                    session.add(db_dm)
                else:
                    if dm.email:
                        db_dm.email = dm.email
                        db_dm.email_status = dm.email_status
                    if dm.phone:
                        db_dm.phone = dm.phone
                        db_dm.phone_type = dm.phone_type
                    if dm.title:
                        db_dm.title = dm.title
                    db_dm.confidence_score = dm.confidence_score
                    db_dm.updated_at = now

            session.commit()
            logger.info(f"Сохранены данные в БД: {comp.name}")
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения в БД: {e}")
        finally:
            session.close()

    def get_all_leads(
        self,
        query: Optional[str] = None,
        region: Optional[str] = None,
        role_level: Optional[str] = None,
        email_status: Optional[str] = None,
        lead_status: Optional[str] = None,
        min_confidence: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Возвращает плоский список контактов ЛПР с поддержкой комплексной фильтрации.
        """
        session = self.SessionFactory()
        leads: List[Dict[str, Any]] = []
        try:
            q = session.query(DecisionMakerORM).join(CompanyORM)

            if query:
                clean_q = f"%{query.strip()}%"
                q = q.filter(
                    (DecisionMakerORM.full_name.ilike(clean_q)) |
                    (CompanyORM.name.ilike(clean_q)) |
                    (CompanyORM.inn.ilike(clean_q)) |
                    (DecisionMakerORM.email.ilike(clean_q)) |
                    (DecisionMakerORM.phone.ilike(clean_q)) |
                    (DecisionMakerORM.title.ilike(clean_q))
                )

            if region:
                q = q.filter(CompanyORM.region.ilike(f"%{region.strip()}%"))

            if role_level:
                q = q.filter(DecisionMakerORM.role_level == role_level)

            if email_status:
                q = q.filter(DecisionMakerORM.email_status == email_status)

            if lead_status:
                q = q.filter(DecisionMakerORM.lead_status == lead_status)

            if min_confidence is not None:
                q = q.filter(DecisionMakerORM.confidence_score >= min_confidence)

            q = q.order_by(desc(DecisionMakerORM.id))
            dms = q.all()

            for dm in dms:
                c = dm.company
                leads.append({
                    "id": dm.id,
                    "company_id": c.id,
                    "inn": c.inn,
                    "ogrn": c.ogrn,
                    "company_name": c.name,
                    "short_name": c.short_name,
                    "okved": c.okved,
                    "okved_name": c.okved_name,
                    "revenue_rub": c.revenue_rub,
                    "website": c.website or c.domain,
                    "domain": c.domain,
                    "region": c.region or c.city,
                    "address": c.address,
                    "general_phone": c.general_phone,
                    "general_email": c.general_email,
                    "telegram_company": c.telegram,
                    "vk_company": c.vk,
                    "dm_full_name": dm.full_name,
                    "dm_first_name": dm.first_name,
                    "dm_last_name": dm.last_name,
                    "dm_middle_name": dm.middle_name,
                    "dm_title": dm.title,
                    "dm_role_level": dm.role_level,
                    "dm_email": dm.email,
                    "email_status": dm.email_status,
                    "email_pattern": dm.email_pattern,
                    "dm_phone": dm.phone,
                    "dm_phone_type": dm.phone_type,
                    "dm_telegram": dm.telegram,
                    "dm_profile_url": dm.profile_url,
                    "source": dm.source,
                    "confidence_score": dm.confidence_score,
                    "lead_status": dm.lead_status or "NEW",
                    "notes": dm.notes,
                    "created_at": dm.created_at.isoformat() if dm.created_at else None
                })
        finally:
            session.close()
        return leads

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает детальную карточку конкретного ЛПР."""
        session = self.SessionFactory()
        try:
            dm = session.query(DecisionMakerORM).filter_by(id=lead_id).first()
            if not dm:
                return None
            c = dm.company
            return {
                "id": dm.id,
                "company_id": c.id,
                "inn": c.inn,
                "ogrn": c.ogrn,
                "company_name": c.name,
                "short_name": c.short_name,
                "okved": c.okved,
                "okved_name": c.okved_name,
                "revenue_rub": c.revenue_rub,
                "website": c.website or c.domain,
                "domain": c.domain,
                "region": c.region or c.city,
                "address": c.address,
                "general_phone": c.general_phone,
                "general_email": c.general_email,
                "dm_full_name": dm.full_name,
                "dm_title": dm.title,
                "dm_role_level": dm.role_level,
                "dm_email": dm.email,
                "email_status": dm.email_status,
                "email_pattern": dm.email_pattern,
                "dm_phone": dm.phone,
                "dm_phone_type": dm.phone_type,
                "dm_telegram": dm.telegram,
                "dm_profile_url": dm.profile_url,
                "source": dm.source,
                "confidence_score": dm.confidence_score,
                "lead_status": dm.lead_status or "NEW",
                "notes": dm.notes,
                "created_at": dm.created_at.isoformat() if dm.created_at else None
            }
        finally:
            session.close()

    def update_lead(self, lead_id: int, updates: Dict[str, Any]) -> bool:
        """Обновляет поля контакта ЛПР (статус в CRM, телефон, email, заметки)."""
        session = self.SessionFactory()
        try:
            dm = session.query(DecisionMakerORM).filter_by(id=lead_id).first()
            if not dm:
                return False

            for k, v in updates.items():
                if hasattr(dm, k) and v is not None:
                    setattr(dm, k, v)

            dm.updated_at = datetime.utcnow()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка обновления лида {lead_id}: {e}")
            return False
        finally:
            session.close()

    def delete_lead(self, lead_id: int) -> bool:
        """Удаляет контакт ЛПР из базы данных."""
        session = self.SessionFactory()
        try:
            dm = session.query(DecisionMakerORM).filter_by(id=lead_id).first()
            if not dm:
                return False
            session.delete(dm)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка удаления лида {lead_id}: {e}")
            return False
        finally:
            session.close()

    def reverify_all_emails(self) -> int:
        """Пакетная повторная валидация всех почтовых ящиков в базе."""
        session = self.SessionFactory()
        updated_count = 0
        try:
            dms = session.query(DecisionMakerORM).filter(DecisionMakerORM.email.isnot(None)).all()
            for dm in dms:
                v_res = verify_email_full(dm.email)
                dm.email_status = v_res["status"]
                if v_res["is_valid"]:
                    dm.confidence_score = min(98, max(dm.confidence_score, v_res["confidence"]))
                else:
                    dm.confidence_score = max(10, dm.confidence_score - 30)
                dm.updated_at = datetime.utcnow()
                updated_count += 1
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка повторной валидации email: {e}")
        finally:
            session.close()
        return updated_count

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Формирует развернутую аналитику по всей собранной базе."""
        session = self.SessionFactory()
        try:
            total_companies = session.query(func.count(CompanyORM.id)).scalar() or 0
            total_dms = session.query(func.count(DecisionMakerORM.id)).scalar() or 0

            # Статусы email
            valid_mx_count = session.query(func.count(DecisionMakerORM.id)).filter(
                DecisionMakerORM.email_status.in_(["valid_mx", "verified"])
            ).scalar() or 0

            generated_count = session.query(func.count(DecisionMakerORM.id)).filter(
                DecisionMakerORM.email_status == "generated"
            ).scalar() or 0

            # Типы телефонов
            mobile_phones = session.query(func.count(DecisionMakerORM.id)).filter(
                DecisionMakerORM.phone_type == "mobile"
            ).scalar() or 0

            office_phones = session.query(func.count(DecisionMakerORM.id)).filter(
                DecisionMakerORM.phone_type.in_(["office", "reception", "8800"])
            ).scalar() or 0

            # Распределение по уровням ЛПР
            role_stats = session.query(
                DecisionMakerORM.role_level, func.count(DecisionMakerORM.id)
            ).group_by(DecisionMakerORM.role_level).all()

            roles_dict = {r[0] or "Другое": r[1] for r in role_stats}

            # Топ регионов
            region_stats = session.query(
                CompanyORM.region, func.count(CompanyORM.id)
            ).filter(CompanyORM.region.isnot(None)).group_by(CompanyORM.region).order_by(desc(func.count(CompanyORM.id))).limit(6).all()

            regions_list = [{"region": r[0], "count": r[1]} for r in region_stats if r[0]]

            # Топ отраслей
            okved_stats = session.query(
                CompanyORM.okved_name, func.count(CompanyORM.id)
            ).filter(CompanyORM.okved_name.isnot(None)).group_by(CompanyORM.okved_name).order_by(desc(func.count(CompanyORM.id))).limit(5).all()

            okved_list = [{"industry": (o[0][:32] + "...") if len(o[0] or "") > 32 else o[0], "count": o[1]} for o in okved_stats if o[0]]

            return {
                "total_companies": total_companies,
                "total_dms": total_dms,
                "valid_emails_count": valid_mx_count,
                "generated_emails_count": generated_count,
                "mobile_phones_count": mobile_phones,
                "office_phones_count": office_phones,
                "roles_breakdown": roles_dict,
                "top_regions": regions_list,
                "top_industries": okved_list
            }
        finally:
            session.close()
