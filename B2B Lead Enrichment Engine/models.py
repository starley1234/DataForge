import os
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session

Base = declarative_base()


class CompanyORM(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inn = Column(String(12), unique=True, index=True, nullable=False)
    kpp = Column(String(9), nullable=True)
    ogrn = Column(String(15), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    short_name = Column(String(255), nullable=True)
    okved = Column(String(20), nullable=True, index=True)
    okved_name = Column(String(255), nullable=True)
    revenue_rub = Column(BigInteger, nullable=True)
    employees_count = Column(Integer, nullable=True)
    website = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    region = Column(String(100), nullable=True, index=True)
    city = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    general_email = Column(String(255), nullable=True)
    general_phone = Column(String(50), nullable=True)
    telegram = Column(String(255), nullable=True)
    vk = Column(String(255), nullable=True)
    source = Column(String(100), default="egrul")
    tags = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    decision_makers = relationship(
        "DecisionMakerORM",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="joined"
    )


class DecisionMakerORM(Base):
    __tablename__ = "decision_makers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    gender = Column(String(20), nullable=True)
    title = Column(String(255), nullable=True)
    role_level = Column(String(50), nullable=True, default="C-Level")  # C-Level, Director, Head, Founder, Manager
    email = Column(String(255), nullable=True, index=True)
    email_status = Column(String(50), default="unverified")  # verified, valid_mx, generated, invalid, catch_all
    email_pattern = Column(String(50), nullable=True)  # {f}.{last}, {last}.{f}, etc.
    phone = Column(String(50), nullable=True)
    phone_type = Column(String(50), nullable=True)  # mobile, office, 8800, reception
    telegram = Column(String(100), nullable=True)
    profile_url = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True)  # egrul, website, tenchat, linkedin, pattern
    confidence_score = Column(Integer, default=50)  # 0 - 100
    lead_status = Column(String(50), default="NEW")  # NEW, CONTACTED, QUALIFIED, CONVERTED, REJECTED
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("CompanyORM", back_populates="decision_makers")


class BatchTaskORM(Base):
    __tablename__ = "batch_tasks"

    id = Column(String(36), primary_key=True)
    task_type = Column(String(50), default="inn")
    status = Column(String(50), default="queued")  # queued, running, completed, failed
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    success_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error_log = Column(Text, nullable=True)


# Pydantic Schemas for validation and API exchange
class DecisionMaker(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    company_id: Optional[int] = None
    company_inn: Optional[str] = None
    company_name: Optional[str] = None
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    gender: Optional[str] = None
    title: Optional[str] = "Генеральный директор"
    role_level: Optional[str] = "C-Level"
    email: Optional[str] = None
    email_status: Optional[str] = "unverified"
    email_pattern: Optional[str] = None
    phone: Optional[str] = None
    phone_type: Optional[str] = None
    telegram: Optional[str] = None
    profile_url: Optional[str] = None
    source: Optional[str] = "egrul"
    confidence_score: int = 50
    lead_status: Optional[str] = "NEW"
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DecisionMakerUpdate(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = None
    role_level: Optional[str] = None
    email: Optional[str] = None
    email_status: Optional[str] = None
    phone: Optional[str] = None
    phone_type: Optional[str] = None
    telegram: Optional[str] = None
    lead_status: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: Optional[int] = None


class Company(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    inn: str
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    name: str
    short_name: Optional[str] = None
    okved: Optional[str] = None
    okved_name: Optional[str] = None
    revenue_rub: Optional[int] = None
    employees_count: Optional[int] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    general_email: Optional[str] = None
    general_phone: Optional[str] = None
    telegram: Optional[str] = None
    vk: Optional[str] = None
    source: Optional[str] = "egrul"
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    decision_makers: List[DecisionMaker] = Field(default_factory=list)


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    general_email: Optional[str] = None
    general_phone: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class BatchTaskStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_type: str
    status: str
    total_items: int
    processed_items: int
    success_items: int
    failed_items: int
    progress_percent: float = 0.0
    created_at: datetime
    finished_at: Optional[datetime] = None
    error_log: Optional[str] = None


class BatchCreateRequest(BaseModel):
    items: List[str]
    task_type: str = "inn"  # inn, name, domain
    scrape_web: bool = True
    verify_emails: bool = True


class EnrichmentRequest(BaseModel):
    query: str  # INN, OGRN or Company Name
    scrape_web: bool = True
    verify_emails: bool = True


class VerifyEmailRequest(BaseModel):
    email: str
    check_smtp: bool = False


class VerifyPhoneRequest(BaseModel):
    phone: str
    default_region: str = "RU"


class PermutationRequest(BaseModel):
    full_name: str
    domain: str
    known_pattern: Optional[str] = None


class OutreachTemplateRequest(BaseModel):
    lead_id: int
    offer_type: str = "partnership"  # partnership, sales, demo, service


def _migrate_db(engine):
    """Автоматическая миграция недостающих колонок для существующих баз данных."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Проверяем тип базы данных
        is_sqlite = engine.dialect.name == "sqlite"
        if is_sqlite:
            # Колонки для companies
            res = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
            existing_comp_cols = {row[1] for row in res}
            comp_additions = [
                ("telegram", "VARCHAR(255)"),
                ("vk", "VARCHAR(255)"),
                ("source", "VARCHAR(100) DEFAULT 'egrul'"),
                ("tags", "VARCHAR(255)"),
                ("notes", "TEXT"),
                ("updated_at", "DATETIME")
            ]
            for col_name, col_type in comp_additions:
                if col_name not in existing_comp_cols:
                    conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}"))

            # Колонки для decision_makers
            res = conn.execute(text("PRAGMA table_info(decision_makers)")).fetchall()
            existing_dm_cols = {row[1] for row in res}
            dm_additions = [
                ("gender", "VARCHAR(20)"),
                ("email_pattern", "VARCHAR(50)"),
                ("lead_status", "VARCHAR(50) DEFAULT 'NEW'"),
                ("notes", "TEXT"),
                ("updated_at", "DATETIME")
            ]
            for col_name, col_type in dm_additions:
                if col_name not in existing_dm_cols:
                    conn.execute(text(f"ALTER TABLE decision_makers ADD COLUMN {col_name} {col_type}"))
            
            conn.commit()


def init_db(db_path: str = "sqlite:///leads_b2b.db"):
    """
    Инициализирует подключение к базе данных.
    Поддерживает SQLite и PostgreSQL с автоматической миграцией.
    """
    connect_args = {}
    if db_path.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        db_path,
        connect_args=connect_args,
        echo=False,
        pool_pre_ping=True
    )
    Base.metadata.create_all(engine)
    _migrate_db(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Session = scoped_session(session_factory)
    return engine, Session
