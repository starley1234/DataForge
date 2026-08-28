import os
from typing import List, Dict, Any, Optional
import httpx
from core.models import Company, DecisionMaker
from core.validator import normalize_phone
from core.config import settings


class DaDataClient:
    """Интеграция с API DaData.ru для поиска и стандартизации контрагентов."""
    BASE_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DADATA_API_KEY

    def find_by_inn_or_ogrn(self, query: str) -> Optional[Company]:
        if not self.api_key or not query:
            return None

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self.api_key}"
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(self.BASE_URL, json={"query": query.strip()}, headers=headers)
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
                            source="dadata_egrul",
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
                        inn=d.get("inn", ""),
                        kpp=d.get("kpp"),
                        ogrn=d.get("ogrn"),
                        name=item.get("value", ""),
                        short_name=d.get("name", {}).get("short_with_opf"),
                        okved=d.get("okved"),
                        okved_name=d.get("okved_type"),
                        region=d.get("address", {}).get("data", {}).get("region_with_type"),
                        city=d.get("address", {}).get("data", {}).get("city_with_type"),
                        address=d.get("address", {}).get("value"),
                        status=d.get("state", {}).get("status", "ACTIVE"),
                        general_phone=gen_phone,
                        general_email=gen_email,
                        decision_makers=decision_makers,
                        source="dadata"
                    )
                    return comp
        except Exception:
            return None
        return None


class CompanyRegistry:
    """
    Встроенный эталонный реестр предприятий РФ для быстрого демонстрационного
    развертывания, тестирования и работы в изолированных контурах.
    """
    SAMPLE_DATA = [
        {
            "inn": "7736207543",
            "ogrn": "1027700229193",
            "kpp": "770401001",
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
            "telegram": "https://t.me/yandex",
            "vk": "https://vk.com/yandex",
            "tags": "IT, Интернет, ИИ, B2B Cloud, Яндекс",
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
            "kpp": "773601001",
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
            "telegram": "https://t.me/sberbank",
            "vk": "https://vk.com/sber",
            "tags": "Банки, Финтех, Экосистема, Инвестиции, Сбербанк",
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
            "kpp": "780201001",
            "name": 'ООО "ПК "БАЛТИКА"',
            "short_name": 'Балтика',
            "okved": "11.05",
            "okved_name": "Производство пива и напитков",
            "revenue_rub": 109000000000,
            "employees_count": 8400,
            "website": "corporate.baltika.ru",
            "domain": "baltika.ru",
            "region": "г. Санкт-Петербург",
            "city": "Санкт-Петербург",
            "address": "194292, г. Санкт-Петербург, 6-й Верхний пер., д. 3",
            "general_email": "ru_post@baltika.com",
            "general_phone": "+78123299100",
            "vk": "https://vk.com/baltika_career",
            "tags": "FMCG, Производство, Пищевая промышленность, Балтика",
            "decision_makers": [
                {
                    "full_name": "Визир Дмитрий Михайлович",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Ковалев Андрей Игоревич",
                    "title": "Коммерческий директор по B2B дистрибуции",
                    "role_level": "Director",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7743003908",
            "ogrn": "1027700140236",
            "kpp": "774301001",
            "name": 'АО "ЛАБОРАТОРИЯ КАСПЕРСКОГО"',
            "short_name": 'Kaspersky',
            "okved": "62.01",
            "okved_name": "Разработка компьютерного ПО и решений кибербезопасности",
            "revenue_rub": 45000000000,
            "employees_count": 4500,
            "website": "kaspersky.ru",
            "domain": "kaspersky.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "125212, г. Москва, Ленинградское шоссе, д. 39А, стр. 3",
            "general_email": "info@kaspersky.ru",
            "general_phone": "+74957978700",
            "telegram": "https://t.me/kasperskylab",
            "vk": "https://vk.com/kaspersky",
            "tags": "Кибербезопасность, IT, B2B Enterprise, Касперский",
            "decision_makers": [
                {
                    "full_name": "Касперский Евгений Валентинович",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul",
                    "profile_url": "https://kaspersky.ru/about/management"
                },
                {
                    "full_name": "Чекунов Михаил Юрьевич",
                    "title": "Технический директор (CTO)",
                    "role_level": "Director",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7714595571",
            "ogrn": "1057746522511",
            "kpp": "771401001",
            "name": 'ООО "1С"',
            "short_name": '1С',
            "okved": "62.02",
            "okved_name": "Деятельность консультативная и работы в области компьютерных технологий",
            "revenue_rub": 60000000000,
            "employees_count": 2200,
            "website": "1c.ru",
            "domain": "1c.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "127473, г. Москва, ул. Селезневская, д. 21",
            "general_email": "1c@1c.ru",
            "general_phone": "+74957379257",
            "telegram": "https://t.me/one_c_official",
            "tags": "ERP, Автоматизация, Бухгалтерия, B2B IT, 1С",
            "decision_makers": [
                {
                    "full_name": "Нуралиев Борис Георгиевич",
                    "title": "Директор",
                    "role_level": "C-Level",
                    "source": "egrul",
                    "profile_url": "https://1c.ru/about"
                }
            ]
        },
        {
            "inn": "3528000597",
            "ogrn": "1023501236901",
            "kpp": "352801001",
            "name": 'ПАО "СЕВЕРСТАЛЬ"',
            "short_name": 'Северсталь',
            "okved": "24.10",
            "okved_name": "Производство чугуна, стали и ферросплавов",
            "revenue_rub": 750000000000,
            "employees_count": 50000,
            "website": "severstal.com",
            "domain": "severstal.com",
            "region": "Вологодская область",
            "city": "Череповец",
            "address": "162608, Вологодская обл., г. Череповец, ул. Мира, д. 30",
            "general_email": "severstal@severstal.com",
            "general_phone": "+78202535300",
            "tags": "Металлургия, Промышленность, Экспорт, B2B сырье, Северсталь",
            "decision_makers": [
                {
                    "full_name": "Шевелев Александр Анатольевич",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Мордашов Алексей Александрович",
                    "title": "Председатель Совета директоров",
                    "role_level": "C-Level",
                    "source": "egrul"
                }
            ]
        },
        {
            "inn": "7704217370",
            "ogrn": "1027739244741",
            "kpp": "770301001",
            "name": 'ООО "ИНТЕРНЕТ РЕШЕНИЯ"',
            "short_name": 'OZON',
            "okved": "47.91",
            "okved_name": "Торговля розничная по почте или по информационно-коммуникационной сети Интернет",
            "revenue_rub": 424000000000,
            "employees_count": 48000,
            "website": "ozon.ru",
            "domain": "ozon.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "123112, г. Москва, Пресненская наб., д. 10, эт. 41",
            "general_email": "b2b@ozon.ru",
            "general_phone": "+74952321000",
            "tags": "E-Commerce, Маркетплейс, Логистика, Ритейл, Озон, Ozon",
            "decision_makers": [
                {
                    "full_name": "Беляков Сергей Юрьевич",
                    "title": "Управляющий директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Шульгин Александр Александрович",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7707049388",
            "ogrn": "1027700198767",
            "kpp": "784001001",
            "name": 'ПАО "РОСТЕЛЕКОМ"',
            "short_name": 'Ростелеком',
            "okved": "61.10",
            "okved_name": "Деятельность в области связи на базе проводных технологий",
            "revenue_rub": 680000000000,
            "employees_count": 125000,
            "website": "company.rt.ru",
            "domain": "rt.ru",
            "region": "г. Санкт-Петербург",
            "city": "Санкт-Петербург",
            "address": "191167, г. Санкт-Петербург, Синопская наб., д. 14, лит. А",
            "general_email": "rostelecom@rt.ru",
            "general_phone": "+78002000033",
            "tags": "Телеком, Облачные сервисы, Дата-центры, B2G/B2B, Ростелеком, RT",
            "decision_makers": [
                {
                    "full_name": "Осеевский Михаил Эдуардович",
                    "title": "Президент",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Анисимов Валерий Сергеевич",
                    "title": "Вице-президент по корпоративному и B2B сегменту",
                    "role_level": "C-Level",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "2309085638",
            "ogrn": "1032304945947",
            "kpp": "231001001",
            "name": 'ПАО "МАГНИТ"',
            "short_name": 'Магнит',
            "okved": "47.11",
            "okved_name": "Торговля розничная преимущественно пищевыми продуктами",
            "revenue_rub": 2500000000000,
            "employees_count": 360000,
            "website": "magnit.com",
            "domain": "magnit.com",
            "region": "Краснодарский край",
            "city": "Краснодар",
            "address": "350072, Краснодарский край, г. Краснодар, ул. Солнечная, д. 15/5",
            "general_email": "info@magnit.ru",
            "general_phone": "+78612109810",
            "tags": "Ритейл, FMCG, Логистика, Магнит",
            "decision_makers": [
                {
                    "full_name": "Дюннинг Ян Гезинус",
                    "title": "Президент, Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Мелешина Анна Юрьевна",
                    "title": "Управляющий директор",
                    "role_level": "C-Level",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7734443270",
            "ogrn": "1217700253671",
            "kpp": "773401001",
            "name": 'ООО "ВКУСВИЛЛ"',
            "short_name": 'ВкусВилл',
            "okved": "47.29",
            "okved_name": "Торговля розничная прочими пищевыми продуктами",
            "revenue_rub": 297000000000,
            "employees_count": 42000,
            "website": "vkusvill.ru",
            "domain": "vkusvill.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "123592, г. Москва, ул. Кулакова, д. 20, корп. 1",
            "general_email": "info@vkusvill.ru",
            "general_phone": "+74956638602",
            "tags": "FoodTech, Ритейл, Экопродукты, ВкусВилл",
            "decision_makers": [
                {
                    "full_name": "Кривенко Андрей Александрович",
                    "title": "Основатель",
                    "role_level": "Founder",
                    "source": "egrul"
                },
                {
                    "full_name": "Фадеева Алена Викторовна",
                    "title": "Управляющая единой концепцией",
                    "role_level": "Director",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7710668322",
            "ogrn": "1077746777777",
            "kpp": "771001001",
            "name": 'ООО "КЕХ ЕКОММЕРЦ"',
            "short_name": 'Авито',
            "okved": "63.11",
            "okved_name": "Деятельность по обработке данных, предоставление услуг по размещению информации",
            "revenue_rub": 100000000000,
            "employees_count": 7000,
            "website": "avito.ru",
            "domain": "avito.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "125196, г. Москва, ул. Лесная, д. 7",
            "general_email": "b2b@avito.ru",
            "general_phone": "+78006000001",
            "telegram": "https://t.me/avitolive",
            "tags": "IT, Классифайд, E-Commerce, B2B Сервисы, Авито",
            "decision_makers": [
                {
                    "full_name": "Правдивый Владимир Анатольевич",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Гришин Иван Сергеевич",
                    "title": "Директор B2B направления",
                    "role_level": "Director",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7710140679",
            "ogrn": "1027739642281",
            "kpp": "773401001",
            "name": 'АО "ТБАНК"',
            "short_name": 'Т-Банк',
            "okved": "64.19",
            "okved_name": "Денежное посредничество прочее",
            "revenue_rub": 450000000000,
            "employees_count": 65000,
            "website": "tbank.ru",
            "domain": "tbank.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "127287, г. Москва, ул. Хуторская 2-я, д. 38А, стр. 26",
            "general_email": "corp@tbank.ru",
            "general_phone": "+78005557778",
            "telegram": "https://t.me/t_bank",
            "tags": "Финтех, Банки, B2B Эквайринг, Т-Банк, Тинькофф",
            "decision_makers": [
                {
                    "full_name": "Близнюк Станислав Евгеньевич",
                    "title": "Председатель Правления",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Пирожков Илья Дмитриевич",
                    "title": "Директор по развитию B2B продуктов",
                    "role_level": "Director",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7707329188",
            "ogrn": "1147748003639",
            "kpp": "770301001",
            "name": 'ООО "ЛОГНЕКС"',
            "short_name": 'МойСклад',
            "okved": "62.01",
            "okved_name": "Разработка компьютерного программного обеспечения",
            "revenue_rub": 2500000000,
            "employees_count": 350,
            "website": "moysklad.ru",
            "domain": "moysklad.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "123112, г. Москва, Пресненская наб., д. 12",
            "general_email": "sales@moysklad.ru",
            "general_phone": "+74952280044",
            "telegram": "https://t.me/moysklad",
            "tags": "SaaS, ERP, Торговля, Склад, B2B Cloud, МойСклад",
            "decision_makers": [
                {
                    "full_name": "Казанцев Олег Игоревич",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                },
                {
                    "full_name": "Батурин Александр Вадимович",
                    "title": "Коммерческий директор",
                    "role_level": "Director",
                    "source": "website"
                }
            ]
        },
        {
            "inn": "7810138853",
            "ogrn": "1027810229340",
            "kpp": "781001001",
            "name": 'ООО "ДЕЛОВЫЕ ЛИНИИ"',
            "short_name": 'Деловые Линии',
            "okved": "49.41",
            "okved_name": "Деятельность автомобильного грузового транспорта",
            "revenue_rub": 60000000000,
            "employees_count": 20000,
            "website": "dellin.ru",
            "domain": "dellin.ru",
            "region": "г. Санкт-Петербург",
            "city": "Санкт-Петербург",
            "address": "196210, г. Санкт-Петербург, ул. Стартовая, д. 8, лит. А",
            "general_email": "pismo@dellin.ru",
            "general_phone": "+78001008000",
            "tags": "Логистика, B2B Грузоперевозки, Доставка, Деловые Линии",
            "decision_makers": [
                {
                    "full_name": "Богатиков Фарид Равильевич",
                    "title": "Генеральный директор",
                    "role_level": "C-Level",
                    "source": "egrul"
                }
            ]
        },
        {
            "inn": "7707434955",
            "ogrn": "1197746618580",
            "kpp": "771001001",
            "name": 'ПАО "ГРУППА АСТРА"',
            "short_name": 'Группа Астра',
            "okved": "62.01",
            "okved_name": "Разработка компьютерного ПО и операционных систем",
            "revenue_rub": 9500000000,
            "employees_count": 2000,
            "website": "astralinux.ru",
            "domain": "astralinux.ru",
            "region": "г. Москва",
            "city": "Москва",
            "address": "125167, г. Москва, Ленинградский пр-кт, д. 37, корп. 9",
            "general_email": "info@astralinux.ru",
            "general_phone": "+74953694816",
            "tags": "Импортозамещение, ОС Astra Linux, IT B2B, Группа Астра",
            "decision_makers": [
                {
                    "full_name": "Сивцев Илья Игоревич",
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
            comps.append(Company(**c_dict, decision_makers=dms, source="sample_registry"))
        return comps

    def find_by_inn(self, inn: str) -> Optional[Company]:
        q = (inn or "").strip()
        for d in self.SAMPLE_DATA:
            if d["inn"] == q or d.get("ogrn") == q or d.get("kpp") == q:
                dms = [DecisionMaker(**dm, company_inn=d["inn"], company_name=d["name"]) for dm in d["decision_makers"]]
                c_dict = {k: v for k, v in d.items() if k != "decision_makers"}
                return Company(**c_dict, decision_makers=dms, source="sample_registry")
        return None

    def find_by_query(self, query: str) -> Optional[Company]:
        q = (query or "").strip().lower()
        if not q:
            return None
        by_inn = self.find_by_inn(q)
        if by_inn:
            return by_inn

        q_words = [w.strip(" \"'«»") for w in q.split() if len(w.strip(" \"'«»")) >= 3]
        for d in self.SAMPLE_DATA:
            full_text = f"{d['name']} {d.get('short_name', '')} {d.get('tags', '')}".lower()
            if q in full_text:
                dms = [DecisionMaker(**dm, company_inn=d["inn"], company_name=d["name"]) for dm in d["decision_makers"]]
                c_dict = {k: v for k, v in d.items() if k != "decision_makers"}
                return Company(**c_dict, decision_makers=dms, source="sample_registry")

            for qw in q_words:
                stem = qw[:-2] if len(qw) > 5 else qw
                if stem in full_text:
                    dms = [DecisionMaker(**dm, company_inn=d["inn"], company_name=d["name"]) for dm in d["decision_makers"]]
                    c_dict = {k: v for k, v in d.items() if k != "decision_makers"}
                    return Company(**c_dict, decision_makers=dms, source="sample_registry")

        return None


# Совместимость со старым именем класса
MockCompanyRegistry = CompanyRegistry
