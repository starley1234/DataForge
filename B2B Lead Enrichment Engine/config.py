import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Конфигурация B2B Lead Enrichment Engine."""
    APP_TITLE: str = "B2B Lead Enrichment Engine"
    APP_VERSION: str = "2.1.0"
    APP_DESCRIPTION: str = "Корпоративная платформа поиска, обогащения и валидации контактов ЛПР предприятий РФ"
    
    # База данных: по умолчанию локальный SQLite, в продакшене PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///leads_b2b.db")
    
    # Внешние API (опционально)
    DADATA_API_KEY: str = os.getenv("DADATA_API_KEY", "")
    
    # Таймауты сетевых запросов (в секундах)
    EGRUL_TIMEOUT: float = float(os.getenv("EGRUL_TIMEOUT", "15.0"))
    SCRAPER_TIMEOUT: float = float(os.getenv("SCRAPER_TIMEOUT", "8.0"))
    SCRAPER_MAX_PAGES: int = int(os.getenv("SCRAPER_MAX_PAGES", "6"))
    
    # Валидация контактов
    ENABLE_DNS_CACHE: bool = os.getenv("ENABLE_DNS_CACHE", "true").lower() in ("true", "1", "yes")
    DNS_CACHE_TTL_SECONDS: int = int(os.getenv("DNS_CACHE_TTL_SECONDS", "3600"))
    CHECK_SMTP: bool = os.getenv("CHECK_SMTP", "false").lower() in ("true", "1", "yes")
    SMTP_TIMEOUT: float = float(os.getenv("SMTP_TIMEOUT", "3.0"))
    
    # Сервер
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Пакетная обработка
    BATCH_CONCURRENCY: int = int(os.getenv("BATCH_CONCURRENCY", "3"))


settings = Settings()
