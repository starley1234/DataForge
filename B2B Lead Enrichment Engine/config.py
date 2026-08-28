import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Конфигурация B2B Lead Enrichment Engine (Enterprise Edition)."""
    APP_TITLE: str = "B2B Lead Enrichment Engine"
    APP_VERSION: str = "2.2.0-prod"
    APP_DESCRIPTION: str = "Корпоративная платформа поиска, обогащения, скоринга и валидации контактов ЛПР предприятий РФ"
    
    # База данных: локальный SQLite по умолчанию, в продакшене PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///leads_b2b.db")
    
    # Внешние API и ключи
    DADATA_API_KEY: str = os.getenv("DADATA_API_KEY", "")
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "")  # Опциональный токен авторизации API
    
    # Сетевые таймауты (в секундах)
    EGRUL_TIMEOUT: float = float(os.getenv("EGRUL_TIMEOUT", "15.0"))
    SCRAPER_TIMEOUT: float = float(os.getenv("SCRAPER_TIMEOUT", "8.0"))
    SCRAPER_MAX_PAGES: int = int(os.getenv("SCRAPER_MAX_PAGES", "6"))
    HTTP_MAX_RETRIES: int = int(os.getenv("HTTP_MAX_RETRIES", "2"))
    
    # Валидация контактов и DNS
    ENABLE_DNS_CACHE: bool = os.getenv("ENABLE_DNS_CACHE", "true").lower() in ("true", "1", "yes")
    DNS_CACHE_TTL_SECONDS: int = int(os.getenv("DNS_CACHE_TTL_SECONDS", "3600"))
    CHECK_SMTP: bool = os.getenv("CHECK_SMTP", "false").lower() in ("true", "1", "yes")
    SMTP_TIMEOUT: float = float(os.getenv("SMTP_TIMEOUT", "3.0"))
    CHECK_CATCH_ALL: bool = os.getenv("CHECK_CATCH_ALL", "true").lower() in ("true", "1", "yes")
    
    # Сервер
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() in ("true", "1", "yes")
    
    # Пакетная обработка
    BATCH_CONCURRENCY: int = int(os.getenv("BATCH_CONCURRENCY", "4"))
    BATCH_MAX_ITEMS: int = int(os.getenv("BATCH_MAX_ITEMS", "10000"))


settings = Settings()
