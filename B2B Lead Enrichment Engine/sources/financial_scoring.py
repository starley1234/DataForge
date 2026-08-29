from typing import Optional, Dict, Any, Tuple, List
from core.models import Company


class FinancialScoringEngine:
    """
    Анализатор финансовой устойчивости, кредитоспособности и B2B скоринга контрагентов:
    - Расчет индекса надежности (Solvency Score 0 - 100)
    - Определение уровня риска (LOW, MEDIUM, HIGH)
    - Оценка годовой выручки, штата и коммерческого потенциала для сделки
    """

    @staticmethod
    def calculate_solvency(comp: Company) -> Tuple[int, str, List[str]]:
        """
        Возвращает: (score: int, risk_level: str, factors: List[str])
        """
        score = 60
        factors = []

        if comp.status == "ACTIVE":
            score += 15
            factors.append("+15: Действующее юридическое лицо / ИП")
        elif comp.status in ("LIQUIDATING", "BANKRUPT"):
            score -= 50
            factors.append("-50: Процесс ликвидации или банкротства")

        if comp.revenue_rub:
            if comp.revenue_rub >= 10_000_000_000:
                score += 15
                factors.append("+15: Федеральный масштаб выручки (> 10 млрд ₽)")
            elif comp.revenue_rub >= 1_000_000_000:
                score += 12
                factors.append("+12: Крупный бизнес (> 1 млрд ₽)")
            elif comp.revenue_rub >= 100_000_000:
                score += 8
                factors.append("+8: Средний бизнес (> 100 млн ₽)")
            elif comp.revenue_rub >= 10_000_000:
                score += 4
                factors.append("+4: Малый бизнес (> 10 млн ₽)")

        if comp.employees_count:
            if comp.employees_count >= 500:
                score += 10
                factors.append("+10: Штат свыше 500 сотрудников")
            elif comp.employees_count >= 50:
                score += 6
                factors.append("+6: Штат свыше 50 сотрудников")
            elif comp.employees_count >= 10:
                score += 3
                factors.append("+3: Штат свыше 10 сотрудников")

        if comp.domain or comp.website:
            score += 5
            factors.append("+5: Наличие действующего веб-сайта")

        if comp.general_email:
            score += 5
            factors.append("+5: Наличие официального email в реестре")

        final_score = min(100, max(10, score))
        if final_score >= 70:
            risk = "LOW"
        elif final_score >= 45:
            risk = "MEDIUM"
        else:
            risk = "HIGH"

        return final_score, risk, factors
