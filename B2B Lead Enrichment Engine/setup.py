from setuptools import setup, find_packages

setup(
    name="b2b-lead-enrichment-engine",
    version="2.2.0",
    description="Enterprise B2B Lead Finder, Enrichment, Scoring & Decision Maker Intelligence Platform for Russian Markets",
    author="B2B Lead Intelligence Team",
    packages=find_packages(),
    py_modules=[
        "config", "models", "translit", "validator", "deliverability",
        "email_generator", "scraper", "domain_finder", "fns_source",
        "company_sources", "engine", "batch_processor", "exporter", "web_app", "cli"
    ],
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.28.0",
        "pydantic>=2.6.0",
        "sqlalchemy>=2.0.28",
        "pandas>=2.2.0",
        "openpyxl>=3.1.2",
        "phonenumbers>=8.13.0",
        "dnspython>=2.6.0",
        "httpx>=0.27.0",
        "beautifulsoup4>=4.12.0",
        "requests>=2.31.0",
        "pypdf>=4.1.0",
        "rich>=13.7.0",
        "python-multipart>=0.0.9"
    ],
    entry_points={
        "console_scripts": [
            "b2b-engine=cli:main",
        ],
    },
    python_requires=">=3.10",
)
