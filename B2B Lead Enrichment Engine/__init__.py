"""
B2B Lead Generation & Decision Maker Enrichment Engine for Russian Enterprises.

Modules:
- models.py: Data models and database schemas (SQLite / SQLAlchemy)
- translit.py: Russian Cyrillic to Latin transliteration for email generation
- company_sources.py: Fetching company data (DaData / Rusprofile / open registries)
- email_generator.py: Generating email patterns based on full name and domain
- validator.py: Validating emails (syntax, MX DNS, disposable check) and phones (E.164)
- scraper.py: Scraping website contacts, leadership and social links
- engine.py: Main pipeline orchestrator
- cli.py: Command line interface and export to CSV / Excel / JSON
- web_app.py: Web dashboard with FastAPI / HTML UI
"""
