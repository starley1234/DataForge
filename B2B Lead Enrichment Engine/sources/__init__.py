"""
Пакет источников данных и сборщиков информации для B2B Lead Enrichment Engine.
"""
from sources.fns_egrul import FNSEgrulClient
from sources.headhunter import HeadHunterClient
from sources.msp_registry import MSPRegistryClient
from sources.tech_stack import TechStackDetector
from sources.financial_scoring import FinancialScoringEngine
from sources.company_registry import CompanyRegistry

__all__ = [
    "FNSEgrulClient",
    "HeadHunterClient",
    "MSPRegistryClient",
    "TechStackDetector",
    "FinancialScoringEngine",
    "CompanyRegistry"
]
