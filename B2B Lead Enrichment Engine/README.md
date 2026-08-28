# B2B Lead Enrichment & Intelligence Engine (Enterprise Edition)

**B2B Lead Enrichment Engine** — комплексная производственная платформа корпоративного уровня для автоматического поиска, сбора, обогащения, скоринга, генерации и валидации контактных данных лиц, принимающих решения (ЛПР: Генеральные директора, Президенты, Учредители, Коммерческие, Технические, Финансовые директора, C-Level) предприятий Российской Федерации.

Платформа решает ключевую задачу B2B-продаж, маркетинга и скоринга контрагентов: **получение прямых, верифицированных корпоративных контактов ЛПР без ручного поиска и без зависимости от дорогостоящих зарубежных сервисов** (ZoomInfo, Apollo, Cognism), адаптируя все алгоритмы под российскую специфику (ЕГРЮЛ/ЕГРИП ФНС, HeadHunter API, Реестр МСП 209-ФЗ, стандарты транслитерации ГОСТ/ICAO, домены .RU/.РФ, мобильные DEF-коды РФ, часовые пояса MSK-1..MSK+9 и аудит доставляемости).

---

## Архитектура системы и структура проекта

```
B2B Lead Enrichment Engine/
├── sources/                      # Модульные сборщики данных и интеграции с реестрами
│   ├── fns_egrul.py              # Официальный ЕГРЮЛ/ЕГРИП ФНС РФ (JSON + выписки PDF)
│   ├── headhunter.py             # HeadHunter API: вакансии, рост штата, отраслевые теги
│   ├── msp_registry.py           # Реестр субъектов МСП (209-ФЗ: Микро, Малое, Среднее)
│   ├── tech_stack.py             # Детектор стека, CMS (1С-Битрикс, Tilda, WP) и CRM (amoCRM, Bitrix24)
│   ├── financial_scoring.py      # Скоринг надежности (Solvency Score 0-100) и оценка рисков
│   └── company_registry.py       # Эталонный B2B реестр предприятий РФ и DaData интеграция
│
├── scripts/                      # Готовые автономные CLI-скрипты для продакшена
│   ├── enrich_inn.py             # Обогащение по ИНН/ОГРН напрямую из реестров
│   ├── enrich_domain.py          # Краулинг сайта, извлечение команды и детекция CMS/CRM
│   ├── harvest_industry.py       # Сбор лидов по отраслям, городам и открытым вакансиям
│   ├── batch_enrich.py           # Высокоскоростной batch-процессинг файлов Excel/CSV
│   ├── audit_deliverability.py   # Аудит безопасности домена (MX, SPF, DMARC, DKIM, RBL)
│   └── generate_sales_pack.py    # Генерация полного B2B Sales Pack (8 писем, скрипт звонка, vCard)
│
├── engine.py                     # Центральный движок оркестрации обогащения
├── harvester.py                  # Универсальный комбайн параллельного сбора B2B-лидов
├── models.py                     # SQLAlchemy ORM + Pydantic v2 схемы данных + миграции
├── translit.py                   # Транслитерация ГОСТ/ICAO, парсер ФИО, определение пола
├── email_generator.py            # Корпоративные email по 20+ формулам + Pattern Learning
├── validator.py                  # Валидация Email/Phone, кэш DNS MX, таймзоны и Calling Window
├── deliverability.py             # Аудит MX, SPF, DMARC, DKIM, RBL спам-баз и Catch-All
├── domain_finder.py              # Автоматический поиск корпоративного веб-сайта
├── scraper.py                    # Глубокий краулер сайтов, страниц руководства и соцсетей
├── batch_processor.py            # Асинхронный диспетчер пакетных задач с метриками скорости
├── exporter.py                   # Экспорт: Excel (.xlsx), CSV (BOM), amoCRM, Битрикс24, HubSpot, vCard
├── cli.py                        # Интерактивная консольная утилита с таблицами Rich
├── web_app.py                    # FastAPI сервер + REST API + Prometheus + Web Dashboard
├── config.py                     # Настройки окружения (Pydantic BaseSettings)
├── docker-compose.yml            # Продакшн-развертывание (App + PostgreSQL 16)
└── tests/                        # Полный набор автотестов Pytest (67 тестов)
```

---

## Ключевые возможности платформы

1. **Прямая интеграция с официальным ЕГРЮЛ / ЕГРИП ФНС РФ (`sources/fns_egrul.py`)**:
   - Автоматический поиск по ИНН юридических лиц (10 знаков) и ИП (12 знаков), ОГРН/ОГРНИП или наименованию.
   - Извлечение состава первого лица (Генеральный директор, Президент, Предприниматель) напрямую из JSON-реестра и выписок PDF без платных API-ключей.
   - Определение основного ОКВЭД, региона, официального юридического адреса и статуса деятельности.

2. **HeadHunter Employer & Growth Intelligence (`sources/headhunter.py`)**:
   - Сбор информации об открытых вакансиях и динамике найма через открытое API HeadHunter.
   - Определение растущих компаний с высоким бюджетом на персонал и сопутствующие B2B-решения.

3. **Классификатор Реестра МСП ФНС (`sources/msp_registry.py`)**:
   - Автоматическая категоризация бизнеса по критериям Федерального закона № 209-ФЗ (Микропредприятие, Малое предприятие, Среднее предприятие, Крупный бизнес).
   - Оценка лимитов годовой выручки и численности персонала.

4. **Детектор технологического стека, CMS и CRM (`sources/tech_stack.py`)**:
   - Определение используемых CMS (1С-Битрикс, Tilda, WordPress, OpenCart, InSales).
   - Детекция установленных CRM и B2B-виджетов (amoCRM, Bitrix24, JivoSite, Carrot quest, Roistat, Calltouch).
   - Аналитика и инфраструктура (Yandex Metrika, Google Analytics, Cloudflare, DDoS-Guard).

5. **Финансовый скоринг и оценка благонадежности (`sources/financial_scoring.py`)**:
   - Расчет Solvency Score (0 - 100) и уровня коммерческого риска (LOW, MEDIUM, HIGH).
   - Скоринг масштаба выручки, размера штата и статуса регистрации.

6. **Генератор корпоративных Email (`email_generator.py`) и Транслитерация (`translit.py`)**:
   - Поддержка 20+ корпоративных формул (`{f}.{last}`, `{last}.{f}`, `{first}.{last}`, `{last}`, `{first}`, `{last}_{f}`, `{f}_{last}`, `{last}.{first}`, `{last}.{f}.{m}`, `{f}.{m}.{last}` и др.).
   - Двойная транслитерация (ГОСТ 7.79-2000 Система Б + международный ICAO) и поддержка уменьшительных/англоязычных форм (Александр -> Alex, Sasha; Дмитрий -> Dmitry, Dima; Екатерина -> Kate, Katya).
   - **Pattern Learning**: автоматическое определение почтового шаблона организации по уже известным адресам и приоритизация до 98% уверенности.
   - Определение пола и генерация персонализированных обращений ("Уважаемый Иван Иванович!", "Иван Иванович, добрый день!").

7. **Phone Intelligence & Timezone Engine (`validator.py`)**:
   - Нормализация номеров к стандарту E.164 (`+79991234567`) и национальному формату (`+7 (999) 123-45-67`).
   - Определение операторов связи РФ (МТС, МегаФон, Билайн, Tele2/T2, Ростелеком, Yota, Т-Банк Мобайл, СберМобайл).
   - Определение часового пояса (MSK-1 Калининград, MSK Москва/СПб, MSK+1 Самара, MSK+2 Екатеринбург, MSK+4 Новосибирск, MSK+7 Владивосток и др.).
   - **Calling Window Checker**: расчет текущего местного времени абонента и индикация доступности для звонка в рабочие часы (09:00 - 18:00).
   - Генерация прямой ссылки для начала чата в WhatsApp.

8. **Аудит безопасности домена и доставляемости (`deliverability.py`, `scripts/audit_deliverability.py`)**:
   - Определение почтового провайдера (Яндекс 360, VK WorkSpace / Mail.ru, Google Workspace, Microsoft 365, On-Premise).
   - Проверка наличия и строгости SPF-записи (`-all`, `~all`, `?all`).
   - Проверка DMARC-политики (`p=reject`, `p=quarantine`, `p=none`).
   - Проверка наличия DKIM-селекторов.
   - Проверка наличия домена в спам-листах (RBL / DNSBL).
   - Детекция Catch-All серверов (приема любых входящих писем) для предотвращения спам-блокировок.
   - Расчет Deliverability Score (0 - 100) и рекомендации для аутрич-инженера.

9. **B2B Cold Outreach & Cold Calling Suite (`exporter.py`, `scripts/generate_sales_pack.py`)**:
   - 8 специализированных шаблонов холодных B2B-писем (Партнерство, B2B Продажи, Демо-доступ, Закупки и снабжение, Импортозамещение, Приглашение на круглый стол, Follow-up 1, Breakup Email).
   - Генератор персонализированных сценариев холодного звонка: преодоление секретаря (Gatekeeper bypass), 30-секундный Hook с ЛПР, отработка 5 типовых возражений, закрытие на онлайн-встречу.

10. **Многоформатный Экспорт и CRM-интеграции (`exporter.py`)**:
   - Стилизованный многостраничный **Excel (.xlsx)** с цветовым кодированием, автофильтрами и листом аналитики.
   - **CSV** с кодировкой UTF-8 с BOM (utf-8-sig) для идеального открытия в Excel на Windows.
   - Готовый экспорт для **amoCRM** (сделки и контакты) и **Битрикс24** (лиды).
   - Экспорт в международный формат **HubSpot / Salesforce**.
   - Экспорт в **vCard (.vcf 3.0)** — добавление контактов в Apple Contacts, Google Контакты, Outlook или смартфон в один клик.

11. **Пакетная фоновая обработка (Batch Processing) (`batch_processor.py`, `scripts/batch_enrich.py`)**:
   - Загрузка списков ИНН из CSV или Excel (.xlsx, .xls) до 10 000 записей.
   - Автоматическое распознавание нужной колонки в файле.
   - Фоновая обработка с расчетом скорости (записей/сек), прогресса, возможностью отмены и скачивания отчета.

---

## Быстрый старт

### 1. Установка зависимостей

```bash
cd "B2B Lead Enrichment Engine"
pip install -r requirements.txt
```

### 2. Конфигурация (.env)

Скопируйте пример настроек:
```bash
cp .env.example .env
```
По умолчанию система работает "из коробки" на локальной БД SQLite с автоматической миграцией схемы данных. Для продакшена доступен PostgreSQL 16.

### 3. Запуск автоматических тестов

Проект полностью покрыт 67 тестами `pytest`:
```bash
pytest -v
```

---

## Готовые исполняемые скрипты (`scripts/`)

В директории `scripts/` содержатся готовые CLI-инструменты для ежедневной работы специалистов по лидогенерации и продажам:

### 1. Прямое обогащение по ИНН / ОГРН (`scripts/enrich_inn.py`):
```bash
# Обогатить компанию и вывести карточку в терминал
python3 scripts/enrich_inn.py 7736207543

# Обогатить несколько организаций и выгрузить результат в Excel
python3 scripts/enrich_inn.py 7707083893 7802849641 --export-excel leads_enriched.xlsx

# Получить результат в формате JSON для автоматизации
python3 scripts/enrich_inn.py 7743003908 --json
```

### 2. Краулинг корпоративного сайта (`scripts/enrich_domain.py`):
```bash
# Извлечь состав команды, телефоны, email и определить CMS сайта
python3 scripts/enrich_domain.py sberbank.ru
python3 scripts/enrich_domain.py kaspersky.ru --export-excel kaspersky_leads.xlsx
```

### 3. Сбор лидов по отраслям и вакансиям (`scripts/harvest_industry.py`):
```bash
# Сбор ИТ-компаний в Москве с автоматической классификацией МСП
python3 scripts/harvest_industry.py --keyword "ИТ" --city "Москва" --limit 15 --export-excel it_leads.xlsx
```

### 4. Пакетная обработка файлов Excel/CSV (`scripts/batch_enrich.py`):
```bash
# Загрузка необработанного файла с ИНН и экспорт в amoCRM и Excel
python3 scripts/batch_enrich.py raw_inns.xlsx --export-excel enriched.xlsx --export-amocrm amo.csv
```

### 5. Аудит доставляемости и SPF/DMARC (`scripts/audit_deliverability.py`):
```bash
python3 scripts/audit_deliverability.py yandex.ru sberbank.ru ozon.ru
```

### 6. Генерация полного B2B Sales Pack для ЛПР (`scripts/generate_sales_pack.py`):
```bash
# Сгенерировать 8 персонализированных писем, скрипт звонка и vCard
python3 scripts/generate_sales_pack.py --inn 7707083893 --out-dir sales_kit
```

---

## Консольный интерфейс CLI (`cli.py`)

Интерфейс командной строки поддерживает цветные таблицы Rich, панели и прогресс-бары:

### 1. Демонстрационное обогащение эталонной корпоративной базы:
```bash
python3 cli.py --demo
```

### 2. Сводная аналитика текущей базы:
```bash
python3 cli.py --stats
```

### 3. Поиск и обогащение компании по ИНН или названию:
```bash
python3 cli.py --inn 7707083893
python3 cli.py --query "Авито"
```

### 4. Генерация корпоративных вариантов Email:
```bash
python3 cli.py --generate-email "Иванов Иван Иванович" "sberbank.ru"
```

### 5. Аудит доставляемости домена и проверка контактов:
```bash
python3 cli.py --deliverability "yandex.ru"
python3 cli.py --check-email "pr@yandex-team.ru"
python3 cli.py --check-phone "+7 (495) 739-70-00"
```

### 6. Генерация текста холодного письма и сценария звонка для ЛПР:
```bash
python3 cli.py --outreach 1
python3 cli.py --call-script 1
```

### 7. Экспорт базы во все форматы:
```bash
python3 cli.py --export-excel leads.xlsx --export-vcard leads.vcf --export-amocrm leads_amo.csv
```

### 8. Запуск Web-сервера через CLI:
```bash
python3 cli.py --serve --port 8080
```

---

## REST API Документация

Интерактивная документация Swagger UI доступна по адресу: `http://localhost:8080/docs`

### Основные эндпоинты:

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/health` | Проверка состояния сервиса (Health check) |
| `GET` | `/metrics` | Prometheus метрики для мониторинга в продакшене |
| `GET` | `/api/stats` | Сводная аналитика, воронка CRM и распределение по ролям |
| `GET` | `/api/leads` | Получение списка лидов с пагинацией и мульти-фильтрами |
| `GET` | `/api/leads/{id}` | Детальная карточка контакта ЛПР и скоринг |
| `POST` | `/api/leads/manual` | Ручное создание организации и контакта ЛПР |
| `PUT` | `/api/leads/{id}` | Обновление статуса в CRM, телефона, email или заметок |
| `DELETE` | `/api/leads/{id}` | Удаление контакта из базы данных |
| `POST` | `/api/leads/bulk-status` | Массовое изменение статуса CRM для выбранных лидов |
| `POST` | `/api/leads/bulk-delete` | Массовое удаление контактов |
| `POST` | `/api/enrich/real` | Поиск и обогащение организации по ИНН / названию |
| `POST` | `/api/enrich/domain` | Прямое обогащение организации по сайту / домену |
| `POST` | `/api/batch/upload` | Загрузка файла CSV/Excel для фонового обогащения |
| `POST` | `/api/batch/start` | Запуск пакетной задачи по перечню ИНН |
| `GET` | `/api/batch/status/{task_id}` | Прогресс, скорость и статус пакетной задачи |
| `POST` | `/api/batch/cancel/{task_id}` | Отмена активной фоновой задачи |
| `POST` | `/api/tools/generate-email`| Генерация корпоративных вариантов почты по 20+ формулам |
| `POST` | `/api/tools/verify-email` | Валидация email (DNS MX, disposable, syntax, catch-all) |
| `POST` | `/api/tools/verify-phone` | E.164, оператор, регион, часовой пояс и окно звонков |
| `POST` | `/api/tools/deliverability`| Комплексный аудит домена (MX, SPF, DMARC, DKIM, RBL) |
| `POST` | `/api/tools/outreach-draft`| Генерация холодного B2B-письма (8 шаблонов) |
| `POST` | `/api/tools/call-script` | Генерация сценария холодного телефонного звонка |
| `POST` | `/api/leads/reverify` | Массовая перепроверка MX всех email в базе |
| `GET` | `/api/export/excel` | Скачивание многостраничного файла Excel (.xlsx) |
| `GET` | `/api/export/csv` | Скачивание CSV файла в кодировке UTF-8 с BOM |
| `GET` | `/api/export/vcard` | Скачивание контактов в формате vCard (.vcf) |
| `GET` | `/api/leads/{id}/vcard` | Скачивание vCard отдельного контакта |
| `GET` | `/api/export/amocrm` | Скачивание файла импорта в amoCRM |
| `GET` | `/api/export/bitrix24` | Скачивание файла импорта в Битрикс24 |
| `GET` | `/api/export/hubspot` | Скачивание файла импорта в HubSpot / Salesforce |

---

## Развертывание в Production (Docker & PostgreSQL)

### Запуск через Docker Compose:

```bash
docker-compose up -d --build
```
Это запустит:
- Контейнер `b2b_enrichment_engine` на базе Python 3.11 с 4 рабочими процессами Uvicorn и сбором Prometheus метрик.
- Контейнер `b2b_postgres` с базой данных PostgreSQL 16 с сохранением данных в Docker Volume.
- Автоматические проверки работоспособности (Healthcheck).

---

## Лицензия

Проект предназначен для коммерческого и корпоративного использования при соблюдении регламентов обработки общедоступных данных РФ (ФЗ № 152-ФЗ, ст. 8).
