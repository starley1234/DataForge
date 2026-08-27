import os
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from models import Company, DecisionMaker
from validator import normalize_phone
from fns_source import FNSEgrulClient


class DaDataClient:
    """Интеграция с официальным API DaData.ru для поиска компаний по ИНН/названию."""
    BASE_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DADATA_API_KEY", "")

    def find_by_inn(self, inn: str) -> Optional[Company]:
        if not self.api_key:
            return None

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self.api_key}"
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.BASE_URL, json={"query": inn}, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    suggestions = data.get("suggestions", [])
                    if not suggestions:
                        return None
                    
                    item = suggestions[0]
                    d = item.get("data", {})
                    
                    management = d.get("management", {})
                    ceo_name = management.get("name")
                    ceo_post = management.get("post", "Генеральный директор")

                    decision_makers = []
                    if ceo_name:
                        decision_makers.append(DecisionMaker(
                            company_inn=d.get("inn"),
                            company_name=item.get("value"),
                            full_name=ceo_name,
                            title=ceo_post,
                            role_level="C-Level",
                            source="egrul_dadata",
                            confidence_score=95
                        ))

                    phones = d.get("phones") or []
                    gen_phone = None
                    if phones:
                        norm = normalize_phone(phones[0].get("value", ""))
                        gen_phone = norm["formatted"] if norm["valid"] else phones[0].get("value")

                    emails = d.get("emails") or []
                    gen_email = emails[0].get("value") if emails else None

                    comp = Company(
                        inn=d.get("inn"),
                        kpp=d.get("kpp"),
                        ogrn=d.get("ogrn"),
                        name=item.get("value"),
                        short_name=d.get("name", {}).get("short_with_opf"),
                        okved=d.get("okved"),
                        okved_name=d.get("okved_type"),
                        region=d.get("address", {}).get("data", {}).get("region_with_type"),
                        city=d.get("address", {}).get("data", {}).get("city_with_type"),
                        address=d.get("address", {}).get("value"),
                        status=d.get("state", {}).get("status", "ACTIVE"),
                        general_phone=gen_phone,
                        general_email=gen_email,
                        decision_makers=decision_makers
                    )
                    return comp
        except Exception:
            return None
        return None


class MockCompanyRegistry:
    """
    Встроенная база эталонных тестовых предприятий для быстрой демонстрации.
    """
    SAMPLE_DATA = [
        {
            "inn": "7736207543",
            "ogrn": "1027700229193",
            "name": 'ООО "ЯНДЕКС"',
            "short_name": 'Яндекс',
            "okved": "62.01",
            "okved_name": "Разработка компьютерного программного обеспечения",
            "revenue_rub": 800000000000,
            "employees_count": 20000,
            "website": "yandex.ru",
            "domain": "yandex.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "119021, г. Москва, ул. Льва Толстого, д. 16",
            "general_email": "pr@yandex-team.ru",
            "general_phone": "+74957397000",
            "decision_makers": [
                {
                    "full_name": "Худавердян Тигран Оганесович",
                    "title": "Управляющий директор",
                    "role_level": "C-Level",
                    "source": "egrul",
                    "profile_url": "https://ru.linkedin.com/in/tigran-khudaverdyan"
                },
                {
                    "full_name": "Иванов Артем Сергеевич",
                    "title": "Директор по закупкам и B2B инфраструктуре",
                    "role_level": "Director",
                    "source": "tenchat",
                    "profile_url": "https://tenchat.ru/artem_ivanov"
                }
            ]
        },
        {
            "inn": "7707083893",
            "ogrn": "1027700132195",
            "name": 'ПАО "СБЕРБАНК"',
            "short_name": 'Сбер',
            "okved": "64.19",
            "okved_name": "Денежное посредничество прочее",
            "revenue_rub": 3000000000000,
            "employees_count": 210000,
            "website": "sberbank.ru",
            "domain": "sberbank.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "117312, г. Москва, ул. Вавилова, д. 19",
            "general_email": "sberbank@sberbank.ru",
            "general_phone": "+74955005550",
            "decision_makers": [
                {
                    "full_name": "Греф Герман Оскарович",
                    "title": "Президент, Председатель Правления",
                    "role_level": "C-Level",
                    "source": "egrul",
                    "profile_url": "https://sberbank.ru/about/management"
                },
                {
                    "full_name": "Хасис Лев Аронович",
                    "title": "Первый заместитель Председателя Правления",
                    "role_level": "C-Level",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7802849641",
            "ogrn": "1147847032838",
            "name": 'ООО "ПК "БАЛТИКА"',
            "short_name": 'Балтика',
            "okved": "11.05",
            "okved_name": "Производство пива",
            "revenue_rub": 109000000000,
            "employees_count": 8400,
            "website": "corporate.baltika.ru",
            "domain": "baltika.ru",
            "region": "г. Санкт-Петербург",
            "city": "Санкт-Петербург",
            "address": "194292, г. Санкт-Петербург, 6-й Верхний пер., д. 3",
            "general_email": "ru_post@baltika.com",
            "general_phone": "+78123299100",
            "decision_makers": [
                {
                    "full_name": "Визир Дмитрий Михайлович",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                }
            ]
        }
    ]

    def get_all(self) -> List[Company]:
        comps = []
        for d in self.SAMPLE_DATA:
            dms = [DecisionMaker(**dm, company_inn=d["inn"], company_name=d["name"]) for dm in d["decision_makers"]]
            c_dict = {k: v for k, v in d.items() if k != "decision_makers"}
            comps.append(Company(**c_dict, decision_makers=dms))
        return comps

    def find_by_inn(self, inn: str) -> Optional[Company]:
        for d in self.SAMPLE_DATA:
            if d["inn"] == inn:
                dms = [DecisionMaker(**dm, company_inn=d["inn"], company_name=d["name"]) for dm in d["decision_makers"]]
                c_dict = {k: v for k, v in d.items() if k != "decision_makers"}
                return Company(**c_dict, decision_makers=dms)
        return None
