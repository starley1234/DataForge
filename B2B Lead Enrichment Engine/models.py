import re
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class CompanyORM(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inn = Column(String(12), unique=True, index=True, nullable=False)
    kpp = Column(String(9), nullable=True)
    ogrn = Column(String(15), nullable=True)
    name = Column(String(255), nullable=False)
    short_name = Column(String(255), nullable=True)
    okved = Column(String(20), nullable=True)
    okved_name = Column(String(255), nullable=True)
    revenue_rub = Column(BigInteger, nullable=True)
    employees_count = Column(Integer, nullable=True)
    website = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    general_email = Column(String(255), nullable=True)
    general_phone = Column(String(50), nullable=True)
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)

    decision_makers = relationship("DecisionMakerORM", back_populates="company", cascade="all, delete-orphan")


class DecisionMakerORM(Base):
    __tablename__ = "decision_makers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    title = Column(String(255), nullable=True)
    role_level = Column(String(50), nullable=True)  # C-Level, Director, Head, Founder, Manager
    email = Column(String(255), nullable=True, index=True)
    email_status = Column(String(50), default="unverified")  # verified, valid_mx, generated, invalid, catch_all
    phone = Column(String(50), nullable=True)
    phone_type = Column(String(50), nullable=True)  # mobile, office, 8800, reception
    telegram = Column(String(100), nullable=True)
    profile_url = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True)  # egrul, website, tenchat, linkedin, pattern
    confidence_score = Column(Integer, default=50)  # 0 - 100
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("CompanyORM", back_populates="decision_makers")


# Pydantic Schemas for validation and API/CLI exchange
class DecisionMaker(BaseModel):
    id: Optional[int] = None
    company_inn: Optional[str] = None
    company_name: Optional[str] = None
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    title: Optional[str] = "Генеральный директор"
    role_level: Optional[str] = "C-Level"
    email: Optional[str] = None
    email_status: Optional[str] = "unverified"
    phone: Optional[str] = None
    phone_type: Optional[str] = None
    telegram: Optional[str] = None
    profile_url: Optional[str] = None
    source: Optional[str] = "egrul"
    confidence_score: int = 50


class Company(BaseModel):
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
    status: str = "ACTIVE"
    decision_makers: List[DecisionMaker] = Field(default_factory=list)


def init_db(db_path: str = "sqlite:///leads_b2b.db"):
    engine = create_engine(db_path, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
