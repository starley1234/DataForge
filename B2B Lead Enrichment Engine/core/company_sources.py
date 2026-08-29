"""
Обратная совместимость: импорт из пакета sources.company_registry.
"""
from sources.company_registry import DaDataClient, CompanyRegistry, MockCompanyRegistry

__all__ = ["DaDataClient", "CompanyRegistry", "MockCompanyRegistry"]
