# DataForge: B2B Lead Enrichment & Intelligence Engine (Enterprise Edition)

[![CI Tests](https://img.shields.io/badge/pytest-67%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Production%20Ready-009688.svg)]()
[![License](https://img.shields.io/badge/license-Enterprise%20Proprietary-orange.svg)]()

**DataForge B2B Lead Enrichment Engine** — это комплексная производственная платформа для автоматизированного поиска, сбора, обогащения, скоринга и валидации прямых корпоративных контактов лиц, принимающих решения (ЛПР: Генеральные директора, Президенты, Коммерческие и Технические директора, Учредители) предприятий Российской Федерации.

---

## Краткий обзор модулей

- **`B2B Lead Enrichment Engine/sources/`**: Модульные сборщики и харвестеры данных:
  - `fns_egrul.py`: Официальный реестр ЕГРЮЛ/ЕГРИП ФНС РФ (JSON и PDF-выписки).
  - `headhunter.py`: HeadHunter API (открытые вакансии, динамика найма, отраслевые теги).
  - `msp_registry.py`: Реестр МСП по 209-ФЗ (категории Микро, Малое, Среднее).
  - `tech_stack.py`: Детекция CMS (1С-Битрикс, Tilda, WP) и CRM/виджетов (amoCRM, Bitrix24).
  - `financial_scoring.py`: Скоринг надежности (Solvency Score 0-100) и уровни рисков.
  - `company_registry.py`: Эталонный реестр предприятий РФ и DaData интеграция.

- **`B2B Lead Enrichment Engine/scripts/`**: Готовые к работе CLI-скрипты:
  - `enrich_inn.py`: Прямое обогащение по ИНН/ОГРН.
  - `enrich_domain.py`: Краулинг сайта компании, извлечение команды и технологий.
  - `harvest_industry.py`: Массовый сбор лидов по отраслям и вакансиям.
  - `batch_enrich.py`: Высокоскоростная пакетная обработка файлов Excel и CSV.
  - `audit_deliverability.py`: Аудит DNS MX, SPF, DMARC, DKIM и спам-баз (RBL).
  - `generate_sales_pack.py`: Генерация полного B2B Sales Pack (8 писем, скрипт звонка, vCard).

- **`B2B Lead Enrichment Engine/`**:
  - `web_app.py`: Полнофункциональный веб-интерфейс, REST API и Prometheus метрики.
  - `cli.py`: Интерактивный CLI с цветными таблицами Rich.
  - `engine.py` & `harvester.py`: Ядро оркестрации и параллельного сбора данных.
  - `email_generator.py`: 20+ корпоративных формул генерации email + Pattern Learning.
  - `validator.py` & `translit.py`: Валидация контактов, таймзоны (MSK-1..MSK+9), ГОСТ/ICAO.
  - `exporter.py`: Экспорт в Excel (.xlsx), CSV (BOM), amoCRM, Битрикс24, HubSpot, vCard.

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
