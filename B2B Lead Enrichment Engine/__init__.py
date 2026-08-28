"""
B2B Lead Enrichment & Intelligence Engine (Enterprise Edition)
"""

from core import (
    settings,
    Settings,
    Company,
    DecisionMaker,
    CompanyUpdate,
    DecisionMakerUpdate,
    CompanyORM,
    DecisionMakerORM,
    BatchTaskORM,
    BatchTaskStatus,
    init_db,
    transliterate,
    split_russian_name,
    get_salutation,
    generate_email_permutations,
    verify_email_full,
    normalize_phone,
    analyze_domain_deliverability,
    find_domain_by_query,
    WebsiteScraper,
    EnrichmentEngine,
    UniversalB2BHarvester,
    BatchProcessor,
    export_to_excel,
    export_to_csv,
    export_to_amocrm_csv,
    export_to_bitrix24_csv,
    export_to_hubspot_csv,
    export_to_vcard,
    export_to_json,
    generate_outreach_email,
    generate_cold_calling_script
)

__version__ = "2.2.0-prod"
