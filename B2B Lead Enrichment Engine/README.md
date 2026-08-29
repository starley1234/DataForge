# B2B Lead Enrichment & Intelligence Engine (Enterprise Edition)

[![CI Tests](https://img.shields.io/badge/pytest-71%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Production%20Ready-009688.svg)]()
[![License](https://img.shields.io/badge/license-Enterprise%20Proprietary-orange.svg)]()

**B2B Lead Enrichment Engine** — комплексная производственная платформа корпоративного уровня для автоматического поиска, сбора, обогащения, скоринга, генерации и валидации контактных данных лиц, принимающих решения (ЛПР: Генеральные директора, Президенты, Учредители, Коммерческие, Технические, Финансовые директора, C-Level) предприятий Российской Федерации.

Платформа решает ключевую задачу B2B-продаж, маркетинга и скоринга контрагентов: **получение прямых, верифицированных корпоративных контактов ЛПР без ручного поиска и без зависимости от зарубежных сервисов**, адаптируя все алгоритмы под российскую специфику (ЕГРЮЛ/ЕГРИП ФНС, HeadHunter API, Реестр МСП 209-ФЗ, стандарты транслитерации ГОСТ/ICAO, домены .RU/.РФ, мобильные DEF-коды РФ, часовые пояса MSK-1..MSK+9 и аудит доставляемости).

---

## Архитектура системы и структура проекта

```
B2B Lead Enrichment Engine/
├── core/                         # Ядро системы (движок, валидаторы, скоринг, генераторы)
│   ├── __init__.py
│   ├── config.py                 # Настройки и переменные окружения
│   ├── models.py                 # Pydantic v2 & SQLAlchemy схемы
│   ├── engine.py                 # Главный оркестратор обогащения
│   ├── nationwide_harvester.py   # Непрерывный сборщик всех предприятий РФ (89 регионов)
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
│   ├── __init__.py
│   ├── fns_egrul.py              # Официальный ЕГРЮЛ/ЕГРИП ФНС РФ (JSON + PDF)
│   ├── headhunter.py             # HeadHunter API (вакансии, темпы роста)
│   ├── msp_registry.py           # Реестр МСП 209-ФЗ (микро, малое, среднее)
│   ├── tech_stack.py             # Детектор CMS (Битрикс, Tilda) и CRM (amo, b24)
│   ├── financial_scoring.py      # Скоринг надежности (0-100) и оценка рисков
│   ├── company_registry.py       # Реестр предприятий РФ и DaData
│   └── industry_crawler.py       # Отраслевой сборщик предприятий
│
├── scripts/                      # Готовые автономные CLI-скрипты
│   ├── __init__.py
│   ├── enrich_inn.py             # Обогащение по ИНН/ОГРН
│   ├── enrich_domain.py          # Обогащение по домену/сайту
│   ├── harvest_industry.py       # Сбор лидов по отраслям и городам
│   ├── batch_enrich.py           # Пакетная обработка файлов Excel/CSV
│   ├── audit_deliverability.py   # Аудит доставляемости домена
│   └── generate_sales_pack.py    # Генерация B2B Sales Pack (8 писем, звонок, vCard)
│
├── tests/                        # 71 модульный и интеграционный тест
│   ├── test_api.py
│   ├── test_batch_processor.py
│   ├── test_company_sources.py
│   ├── test_deliverability.py
│   ├── test_domain_finder.py
│   ├── test_email_generator.py
│   ├── test_engine.py
│   ├── test_exporter.py
│   ├── test_fns.py
│   ├── test_harvester.py
│   ├── test_nationwide_harvester.py
│   ├── test_scraper.py
│   ├── test_scripts.py
│   ├── test_sources.py
│   ├── test_translit.py
│   └── test_validator.py
│
├── web_app.py                    # Web UI Dashboard & REST API
├── mass_harvester.py             # Консольный live-сборщик всех организаций России
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

## Ключевые возможности платформы

1. **Непрерывный автопоиск предприятий по всей России (`Nationwide Harvester`)**:
   - Охват всех 89 субъектов Российской Федерации и 13 ключевых секторов экономики.
   - Фоновый сбор в 1 клик с живой аналитикой в Web UI и CLI.
   - Автоматическая верификация корпоративных Email, номеров телефонов с часовыми поясами (MSK-1..MSK+9) и финансового скоринга.

2. **Прямая интеграция с официальным ЕГРЮЛ / ЕГРИП ФНС РФ (`sources/fns_egrul.py`)**:
   - Автоматический поиск по ИНН юридических лиц (10 знаков) и ИП (12 знаков), ОГРН/ОГРНИП или наименованию.
   - Извлечение состава первого лица (Генеральный директор, Президент, Предприниматель) напрямую из JSON-реестра и выписок PDF без платных API-ключей.
   - Определение основного ОКВЭД, региона, официального юридического адреса и статуса деятельности.

3. **HeadHunter Employer & Growth Intelligence (`sources/headhunter.py`)**:
   - Сбор информации об открытых вакансиях и динамике найма через открытое API HeadHunter.
   - Определение растущих компаний с высоким бюджетом на персонал и сопутствующие B2B-решения.

4. **Классификатор Реестра МСП ФНС (`sources/msp_registry.py`)**:
   - Автоматическая категоризация бизнеса по критериям Федерального закона № 209-ФЗ (Микропредприятие, Малое предприятие, Среднее предприятие, Крупный бизнес).
   - Оценка лимитов годовой выручки и численности персонала.

5. **Детектор технологического стека, CMS и CRM (`sources/tech_stack.py`)**:
   - Определение используемых CMS (1С-Битрикс, Tilda, WordPress, OpenCart, InSales).
   - Детекция установленных CRM и B2B-виджетов (amoCRM, Bitrix24, JivoSite, Carrot quest, Roistat, Calltouch).
   - Аналитика и инфраструктура (Yandex Metrika, Google Analytics, Cloudflare, DDoS-Guard).

6. **Финансовый скоринг и оценка благонадежности (`sources/financial_scoring.py`)**:
   - Расчет Solvency Score (0 - 100) и уровня коммерческого риска (LOW, MEDIUM, HIGH).
   - Скоринг масштаба выручки, размера штата и статуса регистрации.

7. **Генератор корпоративных Email (`email_generator.py`) и Транслитерация (`translit.py`)**:
   - Поддержка 20+ корпоративных формул (`{f}.{last}`, `{last}.{f}`, `{first}.{last}`, `{last}`, `{first}`, `{last}_{f}`, `{f}_{last}`, `{last}.{first}`, `{last}.{f}.{m}`, `{f}.{m}.{last}` и др.).
   - Двойная транслитерация (ГОСТ 7.79-2000 Система Б + международный ICAO).
   - **Pattern Learning**: автоматическое определение почтового шаблона организации по уже известным адресам и приоритизация до 98% уверенности.

8. **Phone Intelligence & Timezone Engine (`validator.py`)**:
   - Нормализация номеров к стандарту E.164 (`+79991234567`) и национальному формату (`+7 (999) 123-45-67`).
   - Определение операторов связи РФ и часового пояса (MSK-1..MSK+9).
   - **Calling Window Checker**: расчет текущего местного времени абонента и индикация доступности для звонка в рабочие часы (09:00 - 18:00).

9. **Аудит безопасности домена и доставляемости (`deliverability.py`, `scripts/audit_deliverability.py`)**:
   - Проверка почтового провайдера, MX, SPF, DMARC, DKIM, RBL.
   - Детекция Catch-All серверов для защиты от спам-блокировок.

10. **B2B Cold Outreach & Cold Calling Suite (`exporter.py`, `scripts/generate_sales_pack.py`)**:
   - 8 специализированных шаблонов холодных B2B-писем и генератор сценариев звонка.

11. **Многоформатный Экспорт и CRM-интеграции (`exporter.py`)**:
   - Excel (.xlsx), CSV (UTF-8 BOM), amoCRM, Битрикс24, HubSpot, vCard (.vcf 3.0).

---

py -m venv .venv
.venv\Scripts\activate

## Быстрый старт

### 1. Установка зависимостей

```bash
cd "B2B Lead Enrichment Engine"
pip install -r requirements.txt
```

### 2. Запуск автоматических тестов (71 тест)

```bash
pytest -v
```

### 3. Запуск веб-сервера и SPA панели

```bash
python3 web_app.py
```

### 4. Автопоиск всех предприятий России через CLI

```bash
# Непрерывный автопоиск по 89 регионам РФ с живым дашбордом
python3 mass_harvester.py --limit 500

# Или через единый интерфейс
python3 cli.py --harvest-all-russia --limit 100 --region "Москва"
```

---

## Лицензия

Проект предназначен для коммерческого и корпоративного использования при соблюдении регламентов обработки общедоступных данных РФ (ФЗ № 152-ФЗ, ст. 8).
