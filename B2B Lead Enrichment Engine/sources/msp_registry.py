import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("msp_registry")


class MSPRegistryClient:
    """
    Интеллектуальный классификатор и сборщик данных Единого реестра субъектов
    малого и среднего предпринимательства (Реестр МСП ФНС РФ, 209-ФЗ):
    - Определение категории: Микропредприятие, Малое предприятие, Среднее предприятие, Крупный бизнес
    - Оценка пределов численности сотрудников и годовой выручки
    - Оценка государственной поддержки и налоговых льгот
    """

    CATEGORIES = {
        "MICRO": {"title": "Микропредприятие", "max_staff": 15, "max_revenue_rub": 120_000_000},
        "SMALL": {"title": "Малое предприятие", "max_staff": 100, "max_revenue_rub": 800_000_000},
        "MEDIUM": {"title": "Среднее предприятие", "max_staff": 250, "max_revenue_rub": 2_000_000_000},
        "LARGE": {"title": "Крупный бизнес / Холдинг", "max_staff": 100_000, "max_revenue_rub": 1_000_000_000_000}
    }

    def classify_by_metrics(
        self,
        revenue_rub: Optional[int] = None,
        employees_count: Optional[int] = None,
        inn: Optional[str] = None
    ) -> Dict[str, Any]:
        """Классификация предприятия по критериям 209-ФЗ."""
        if revenue_rub and revenue_rub > 2_000_000_000:
            cat_key = "LARGE"
        elif employees_count and employees_count > 250:
            cat_key = "LARGE"
        elif (revenue_rub and revenue_rub > 800_000_000) or (employees_count and employees_count > 100):
            cat_key = "MEDIUM"
        elif (revenue_rub and revenue_rub > 120_000_000) or (employees_count and employees_count > 15):
            cat_key = "SMALL"
        else:
            cat_key = "MICRO"

        meta = self.CATEGORIES[cat_key]

        return {
            "inn": inn,
            "category_code": cat_key,
            "category_name": meta["title"],
            "max_staff_limit": meta["max_staff"],
            "max_revenue_limit_rub": meta["max_revenue_rub"],
            "is_msp": cat_key in ("MICRO", "SMALL", "MEDIUM"),
            "is_sme": cat_key in ("MICRO", "SMALL", "MEDIUM"),
            "is_enterprise": cat_key == "LARGE"
        }
