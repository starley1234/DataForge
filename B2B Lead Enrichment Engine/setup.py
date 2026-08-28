from setuptools import setup, find_packages

setup(
    name="b2b-lead-enrichment-engine",
    version="2.1.0",
    packages=find_packages(),
    py_modules=[
        "config",
        "models",
        "translit",
        "email_generator",
        "validator",
        "scraper",
        "domain_finder",
        "fns_source",
        "company_sources",
        "batch_processor",
        "exporter",
        "engine",
        "cli",
        "web_app"
    ],
    entry_points={
        "console_scripts": [
            "b2b-engine=cli:main"
        ]
    }
)
