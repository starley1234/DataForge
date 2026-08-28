# DataForge: B2B Lead Enrichment & Intelligence Engine (Enterprise Edition)

[![CI Tests](https://img.shields.io/badge/pytest-67%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Production%20Ready-009688.svg)]()
[![License](https://img.shields.io/badge/license-Enterprise%20Proprietary-orange.svg)]()

**DataForge B2B Lead Enrichment Engine** — это комплексная производственная платформа для автоматизированного поиска, сбора, обогащения, скоринга и валидации прямых корпоративных контактов лиц, принимающих решения (ЛПР: Генеральные директора, Президенты, Коммерческие и Технические директора, Учредители) предприятий Российской Федерации.

---

## Лаконичная структура проекта

```
B2B Lead Enrichment Engine/
├── core/                         # Ядро системы (движок, валидаторы, скоринг, генераторы)
│   ├── config.py                 # Настройки и переменные окружения
│   ├── models.py                 # Pydantic v2 & SQLAlchemy схемы
│   ├── engine.py                 # Главный оркестратор обогащения
│   ├── harvester.py              # Универсальный B2B комбайн параллельного сбора
│   ├── translit.py               # Транслитерация ГОСТ/ICAO и парсинг имен
│   ├── email_generator.py        # 20+ формул email + Pattern Learning
│   ├── validator.py              # Валидация Email/Phone, таймзоны (MSK-1..MSK+9)
│   ├── deliverability.py         # Аудит MX, SPF, DMARC, DKIM, RBL
│   ├── domain_finder.py          # Интеллектуальный поиск корпоративных сайтов
│   ├── scraper.py                # Веб-краулинг страниц команды и соцсетей
│   ├── batch_processor.py        # Фоновая асинхронная обработка файлов
│   └── exporter.py               # Экспорт (Excel, amoCRM, Bitrix24, vCard, скрипты)
│
├── sources/                      # Модульные сборщики из официальных реестров
│   ├── fns_egrul.py              # Официальный ЕГРЮЛ/ЕГРИП ФНС РФ (JSON + PDF)
│   ├── headhunter.py             # HeadHunter API (вакансии, темпы роста)
│   ├── msp_registry.py           # Реестр МСП 209-ФЗ (микро, малое, среднее)
│   ├── tech_stack.py             # Детектор CMS (Битрикс, Tilda) и CRM (amo, b24)
│   ├── financial_scoring.py      # Скоринг надежности (0-100) и оценка рисков
│   └── company_registry.py       # Реестр предприятий РФ и DaData
│
├── scripts/                      # Готовые автономные CLI-скрипты
│   ├── enrich_inn.py             # Обогащение по ИНН/ОГРН
│   ├── enrich_domain.py          # Обогащение по домену/сайту
│   ├── harvest_industry.py       # Сбор лидов по отраслям и городам
│   ├── batch_enrich.py           # Пакетная обработка файлов Excel/CSV
│   ├── audit_deliverability.py   # Аудит доставляемости домена
│   └── generate_sales_pack.py    # Генерация B2B Sales Pack (8 писем, звонок, vCard)
│
├── data/                         # Данные, база SQLite и примеры экспорта
│   ├── leads_b2b.db              # База данных SQLite
│   ├── leads.csv                 # Экспорт базы (CSV BOM)
│   ├── leads.xlsx                # Экспорт базы (Excel)
│   ├── leads_amocrm.csv          # Экспорт для amoCRM
│   └── leads_bitrix24.csv        # Экспорт для Битрикс24
│
├── tests/                        # 67 модульных и интеграционных тестов Pytest
│
├── web_app.py                    # Web UI Dashboard & REST API
├── cli.py                        # Главный консольный интерфейс
├── docker-compose.yml            # Docker окружение
├── Dockerfile                    # Сборка контейнера
├── pyproject.toml                # Конфигурация проекта и pytest
├── requirements.txt              # Зависимости
├── setup.py                      # Установка пакета
├── .env.example                  # Пример конфигурации
└── README.md                     # Документация
```

---

## Быстрый запуск

```bash
cd "B2B Lead Enrichment Engine"
pip install -r requirements.txt

# Запуск автотестов
pytest -v

# Запуск Web Dashboard
python3 web_app.py

# Или через CLI
python3 cli.py --stats
```

Подробная документация, примеры использования и спецификация REST API находятся в директории [`B2B Lead Enrichment Engine/README.md`](B2B%20Lead%20Enrichment%20Engine/README.md).
