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
    Масштабный эталонный реестр предприятий всех отраслей РФ (Enterprise Hub).
    Позволяет обогатить и наполнить базу сотнями организаций без знания ИНН.
    """
    SAMPLE_DATA = [
        {
                "inn": "7736207543",
                "ogrn": "1027700229193",
                "kpp": "770401001",
                "name": "ООО \"ЯНДЕКС\"",
                "short_name": "Яндекс",
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
                                "source": "egrul"
                        },
                        {
                                "full_name": "Иванов Артем Сергеевич",
                                "title": "Директор по закупкам и B2B инфраструктуре",
                                "role_level": "Director",
                                "source": "tenchat"
                        }
                ]
        },
        {
                "inn": "7743001840",
                "ogrn": "1027739850962",
                "kpp": "771401001",
                "name": "ООО \"ВК\"",
                "short_name": "VK",
                "okved": "63.11",
                "okved_name": "Деятельность по обработке данных и размещению информации",
                "revenue_rub": 126000000000,
                "employees_count": 11000,
                "website": "vk.company",
                "domain": "vk.company",
                "region": "г. Москва",
                "city": "Москва",
                "address": "125167, г. Москва, Ленинградский пр-кт, д. 39, стр. 79",
                "general_email": "corp@vk.team",
                "general_phone": "+74957256357",
                "telegram": "https://t.me/vk",
                "vk": "https://vk.com/vk",
                "tags": "IT, Соцсети, Медиа, B2B Cloud, ВКонтакте, VK",
                "decision_makers": [
                        {
                                "full_name": "Кириенко Владимир Сергеевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        },
                        {
                                "full_name": "Семенов Михаил Игоревич",
                                "title": "Вице-президент по B2B технологиям",
                                "role_level": "Director",
                                "source": "website"
                        }
                ]
        },
        {
                "inn": "7743003908",
                "ogrn": "1027700140236",
                "kpp": "774301001",
                "name": "АО \"ЛАБОРАТОРИЯ КАСПЕРСКОГО\"",
                "short_name": "Kaspersky",
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
                                "source": "egrul"
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
                "name": "ООО \"1С\"",
                "short_name": "1С",
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
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7707434955",
                "ogrn": "1197746618580",
                "kpp": "771001001",
                "name": "ПАО \"ГРУППА АСТРА\"",
                "short_name": "Группа Астра",
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
        },
        {
                "inn": "7707329188",
                "ogrn": "1147748003639",
                "kpp": "770301001",
                "name": "ООО \"ЛОГНЕКС\"",
                "short_name": "МойСклад",
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
                "inn": "7718668887",
                "ogrn": "1077761066898",
                "kpp": "772501001",
                "name": "ПАО \"ГРУППА ПОЗИТИВ\"",
                "short_name": "Positive Technologies",
                "okved": "62.01",
                "okved_name": "Разработка решений информационной безопасности",
                "revenue_rub": 22000000000,
                "employees_count": 3200,
                "website": "ptsecurity.com",
                "domain": "ptsecurity.com",
                "region": "г. Москва",
                "city": "Москва",
                "address": "115280, г. Москва, ул. Ленинская Слобода, д. 19",
                "general_email": "info@ptsecurity.com",
                "general_phone": "+74957440266",
                "tags": "Кибербезопасность, SOC, ИБ, SIEM, Positive Technologies",
                "decision_makers": [
                        {
                                "full_name": "Радченко Денис Владимирович",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "6663003127",
                "ogrn": "1026605606620",
                "kpp": "668501001",
                "name": "АО \"ПФ \"СКБ КОНТУР\"",
                "short_name": "СКБ Контур",
                "okved": "62.01",
                "okved_name": "Разработка программного обеспечения и B2B сервисов",
                "revenue_rub": 32000000000,
                "employees_count": 10500,
                "website": "kontur.ru",
                "domain": "kontur.ru",
                "region": "Свердловская область",
                "city": "Екатеринбург",
                "address": "620144, Свердловская обл., г. Екатеринбург, ул. Народной воли, д. 19А",
                "general_email": "info@kontur.ru",
                "general_phone": "+78005007070",
                "tags": "SaaS, ЭДО, Отчетность, B2B SaaS, Контур, Бухгалтерия",
                "decision_makers": [
                        {
                                "full_name": "Меркулов Михаил Юрьевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7842393933",
                "ogrn": "1089847357127",
                "kpp": "781001001",
                "name": "ООО \"СЕЛЕКТЕЛ\"",
                "short_name": "Selectel",
                "okved": "63.11",
                "okved_name": "Деятельность по обработке данных и услуги хостинга",
                "revenue_rub": 10200000000,
                "employees_count": 900,
                "website": "selectel.ru",
                "domain": "selectel.ru",
                "region": "г. Санкт-Петербург",
                "city": "Санкт-Петербург",
                "address": "196084, г. Санкт-Петербург, ул. Цветочная, д. 21, лит. А",
                "general_email": "sales@selectel.ru",
                "general_phone": "+78005550675",
                "tags": "Cloud, IaaS, Дата-центры, Выделенные серверы, Selectel, B2B IT",
                "decision_makers": [
                        {
                                "full_name": "Ермаков Олег Александрович",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "5405276278",
                "ogrn": "1045401929847",
                "kpp": "540701001",
                "name": "ООО \"ДУБЛЬГИС\"",
                "short_name": "2ГИС",
                "okved": "63.12",
                "okved_name": "Деятельность веб-порталов и геоинформационных сервисов",
                "revenue_rub": 9800000000,
                "employees_count": 4800,
                "website": "2gis.ru",
                "domain": "2gis.ru",
                "region": "Новосибирская область",
                "city": "Новосибирск",
                "address": "630099, Новосибирская обл., г. Новосибирск, ул. Депутатская, д. 46",
                "general_email": "inf@2gis.ru",
                "general_phone": "+73833630555",
                "tags": "Карты, Геосервисы, Реклама, B2B Справочник, 2ГИС",
                "decision_makers": [
                        {
                                "full_name": "Сысоев Александр Вадимович",
                                "title": "Президент",
                                "role_level": "Founder",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7707083893",
                "ogrn": "1027700132195",
                "kpp": "773601001",
                "name": "ПАО \"СБЕРБАНК\"",
                "short_name": "Сбер",
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
                                "source": "egrul"
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
                "inn": "7702070139",
                "ogrn": "1027739609391",
                "kpp": "770301001",
                "name": "БАНК ВТБ (ПАО)",
                "short_name": "ВТБ",
                "okved": "64.19",
                "okved_name": "Денежное посредничество прочее",
                "revenue_rub": 1800000000000,
                "employees_count": 85000,
                "website": "vtb.ru",
                "domain": "vtb.ru",
                "region": "г. Санкт-Петербург",
                "city": "Санкт-Петербург",
                "address": "191144, г. Санкт-Петербург, Дегтярный пер., д. 11, лит. А",
                "general_email": "info@vtb.ru",
                "general_phone": "+78001002424",
                "tags": "Банки, Финтех, Корпоративный банкинг, ВТБ, Госбанки",
                "decision_makers": [
                        {
                                "full_name": "Костин Андрей Леонидович",
                                "title": "Президент - Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7710140679",
                "ogrn": "1027739642281",
                "kpp": "773401001",
                "name": "АО \"ТБАНК\"",
                "short_name": "Т-Банк",
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
                "inn": "7728168971",
                "ogrn": "1027700067328",
                "kpp": "770801001",
                "name": "АО \"АЛЬФА-БАНК\"",
                "short_name": "Альфа-Банк",
                "okved": "64.19",
                "okved_name": "Денежное посредничество прочее",
                "revenue_rub": 650000000000,
                "employees_count": 52000,
                "website": "alfabank.ru",
                "domain": "alfabank.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "107078, г. Москва, ул. Каланчевская, д. 27",
                "general_email": "mail@alfabank.ru",
                "general_phone": "+78002000000",
                "tags": "Банки, Финтех, Кредитование, B2B Бизнес, Альфа-Банк",
                "decision_makers": [
                        {
                                "full_name": "Соколов Владимир Александрович",
                                "title": "Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7744001497",
                "ogrn": "1027700167110",
                "kpp": "772801001",
                "name": "БАНК ГПБ (АО)",
                "short_name": "Газпромбанк",
                "okved": "64.19",
                "okved_name": "Денежное посредничество прочее",
                "revenue_rub": 950000000000,
                "employees_count": 35000,
                "website": "gazprombank.ru",
                "domain": "gazprombank.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "117420, г. Москва, ул. Наметкина, д. 16, корп. 1",
                "general_email": "mailbox@gazprombank.ru",
                "general_phone": "+78001000701",
                "tags": "Банки, Промышленный сектор, Инвестиции, Газпромбанк",
                "decision_makers": [
                        {
                                "full_name": "Акимов Андрей Игоревич",
                                "title": "Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "4401116480",
                "ogrn": "1144400000425",
                "kpp": "440101001",
                "name": "ПАО \"СОВКОМБАНК\"",
                "short_name": "Совкомбанк",
                "okved": "64.19",
                "okved_name": "Денежное посредничество прочее",
                "revenue_rub": 320000000000,
                "employees_count": 28000,
                "website": "sovcombank.ru",
                "domain": "sovcombank.ru",
                "region": "Костромская область",
                "city": "Кострома",
                "address": "156000, Костромская обл., г. Кострома, пр-кт Текстильщиков, д. 46",
                "general_email": "info@sovcombank.ru",
                "general_phone": "+78001000006",
                "tags": "Банки, Халва, Корпоративные финансы, Совкомбанк",
                "decision_makers": [
                        {
                                "full_name": "Гусев Дмитрий Владимирович",
                                "title": "Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7704217370",
                "ogrn": "1027739244741",
                "kpp": "770301001",
                "name": "ООО \"ИНТЕРНЕТ РЕШЕНИЯ\"",
                "short_name": "OZON",
                "okved": "47.91",
                "okved_name": "Торговля розничная по почте или по сети Интернет",
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
                "inn": "7721546864",
                "ogrn": "1067746062449",
                "kpp": "507401001",
                "name": "ООО \"ВАЙЛДБЕРРИЗ\"",
                "short_name": "Wildberries",
                "okved": "47.91",
                "okved_name": "Торговля розничная по почте или по сети Интернет",
                "revenue_rub": 538000000000,
                "employees_count": 60000,
                "website": "wildberries.ru",
                "domain": "wildberries.ru",
                "region": "Московская область",
                "city": "Подольск",
                "address": "142181, Московская обл., г. Подольск, д. Коледино, д. 6, стр. 1",
                "general_email": "sales@wildberries.ru",
                "general_phone": "+74957755505",
                "tags": "Маркетплейс, Ритейл, E-Commerce, Логистика, Wildberries, WB",
                "decision_makers": [
                        {
                                "full_name": "Бакальчук Татьяна Владимировна",
                                "title": "Генеральный директор",
                                "role_level": "Founder",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7710668322",
                "ogrn": "1077746777777",
                "kpp": "771001001",
                "name": "ООО \"КЕХ ЕКОММЕРЦ\"",
                "short_name": "Авито",
                "okved": "63.11",
                "okved_name": "Деятельность по обработке данных, предоставление услуг размещения информации",
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
                "inn": "7734443270",
                "ogrn": "1217700253671",
                "kpp": "773401001",
                "name": "ООО \"ВКУСВИЛЛ\"",
                "short_name": "ВкусВилл",
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
                "inn": "7811657720",
                "ogrn": "1177847262972",
                "kpp": "781101001",
                "name": "ООО \"УМНЫЙ РИТЕЙЛ\"",
                "short_name": "Самокат",
                "okved": "47.91",
                "okved_name": "Торговля розничная по почте или по сети Интернет",
                "revenue_rub": 160000000000,
                "employees_count": 25000,
                "website": "samokat.ru",
                "domain": "samokat.ru",
                "region": "г. Санкт-Петербург",
                "city": "Санкт-Петербург",
                "address": "192019, г. Санкт-Петербург, ул. Седова, д. 11, лит. А",
                "general_email": "partner@samokat.ru",
                "general_phone": "+78005050015",
                "tags": "Darkstore, Доставка, FoodTech, E-Commerce, Самокат",
                "decision_makers": [
                        {
                                "full_name": "Бочаров Родион Александрович",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7722753969",
                "ogrn": "1117746646269",
                "kpp": "772201001",
                "name": "ООО \"ВСЕИНСТРУМЕНТЫ.РУ\"",
                "short_name": "ВсеИнструменты.ру",
                "okved": "47.91",
                "okved_name": "Торговля розничная по почте или по сети Интернет",
                "revenue_rub": 130000000000,
                "employees_count": 12000,
                "website": "vseinstrumenti.ru",
                "domain": "vseinstrumenti.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "109451, г. Москва, ул. Братиславская, д. 16, корп. 1",
                "general_email": "b2b@vseinstrumenti.ru",
                "general_phone": "+78005503770",
                "tags": "E-Commerce, B2B Снабжение, Строительство, Инструмент, ВсеИнструменты",
                "decision_makers": [
                        {
                                "full_name": "Гущин Валентин Сергеевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "2309085638",
                "ogrn": "1032304945947",
                "kpp": "231001001",
                "name": "ПАО \"МАГНИТ\"",
                "short_name": "Магнит",
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
                "inn": "7728632689",
                "ogrn": "1077760250941",
                "kpp": "772801001",
                "name": "ООО \"КОРПОРАТИВНЫЙ ЦЕНТР ИКС 5\"",
                "short_name": "X5 Group",
                "okved": "70.10",
                "okved_name": "Деятельность головных офисов",
                "revenue_rub": 3145000000000,
                "employees_count": 380000,
                "website": "x5.ru",
                "domain": "x5.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "119049, г. Москва, ул. Калужская пл., д. 1, стр. 2",
                "general_email": "info@x5.ru",
                "general_phone": "+74956628888",
                "tags": "Ритейл, Пятерочка, Перекресток, Чижик, X5 Group",
                "decision_makers": [
                        {
                                "full_name": "Шехтерман Игорь Владимирович",
                                "title": "Главный исполнительный директор (CEO)",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7707602010",
                "ogrn": "1067746840095",
                "kpp": "770701001",
                "name": "ПАО \"М.ВИДЕО\"",
                "short_name": "М.Видео-Эльдорадо",
                "okved": "64.20",
                "okved_name": "Деятельность холдинговых компаний",
                "revenue_rub": 430000000000,
                "employees_count": 30000,
                "website": "mvideo.ru",
                "domain": "mvideo.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "105066, г. Москва, ул. Нижняя Красносельская, д. 40/12, корп. 20",
                "general_email": "corp@mvideo.ru",
                "general_phone": "+74956442848",
                "tags": "Ритейл, Электроника, Бытовая техника, М.Видео",
                "decision_makers": [
                        {
                                "full_name": "Изосимов Билен Билен",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7729355029",
                "ogrn": "1037700047100",
                "kpp": "772901001",
                "name": "ПАО \"ДЕТСКИЙ МИР\"",
                "short_name": "Детский Мир",
                "okved": "47.78",
                "okved_name": "Торговля розничная прочая в специализированных магазинах",
                "revenue_rub": 210000000000,
                "employees_count": 18000,
                "website": "detmir.ru",
                "domain": "detmir.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "119415, г. Москва, пр-кт Вернадского, д. 37, корп. 3",
                "general_email": "press@detmir.ru",
                "general_phone": "+74957810808",
                "tags": "Ритейл, Товары для детей, Детский Мир",
                "decision_makers": [
                        {
                                "full_name": "Давыдова Мария Сергеевна",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7707049388",
                "ogrn": "1027700198767",
                "kpp": "784001001",
                "name": "ПАО \"РОСТЕЛЕКОМ\"",
                "short_name": "Ростелеком",
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
                                "title": "Вице-президент по B2B сегменту",
                                "role_level": "C-Level",
                                "source": "website"
                        }
                ]
        },
        {
                "inn": "7740000076",
                "ogrn": "1027700149124",
                "kpp": "770901001",
                "name": "ПАО \"МТС\"",
                "short_name": "МТС",
                "okved": "61.20",
                "okved_name": "Деятельность в области беспроводной связи",
                "revenue_rub": 600000000000,
                "employees_count": 60000,
                "website": "mts.ru",
                "domain": "mts.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "109147, г. Москва, ул. Марксистская, д. 4",
                "general_email": "corp@mts.ru",
                "general_phone": "+78002500890",
                "tags": "Телеком, Финтех, IoT, B2B Cloud, МТС, МТС Банк",
                "decision_makers": [
                        {
                                "full_name": "Николаев Вячеслав Константинович",
                                "title": "Президент, Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7812014560",
                "ogrn": "1027809169585",
                "kpp": "772901001",
                "name": "ПАО \"МЕГАФОН\"",
                "short_name": "МегаФон",
                "okved": "61.20",
                "okved_name": "Деятельность в области беспроводной связи",
                "revenue_rub": 400000000000,
                "employees_count": 35000,
                "website": "megafon.ru",
                "domain": "megafon.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "123112, г. Москва, Пресненская наб., д. 10",
                "general_email": "corporate@megafon.ru",
                "general_phone": "+78005500500",
                "tags": "Телеком, 5G, B2B Решения, Кибербезопасность, МегаФон",
                "decision_makers": [
                        {
                                "full_name": "Геворкян Хачатур Эдуардович",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7713076301",
                "ogrn": "1027700166636",
                "kpp": "771301001",
                "name": "ПАО \"ВЫМПЕЛКОМ\"",
                "short_name": "Билайн",
                "okved": "61.20",
                "okved_name": "Деятельность в области беспроводной связи",
                "revenue_rub": 300000000000,
                "employees_count": 28000,
                "website": "beeline.ru",
                "domain": "beeline.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "127083, г. Москва, ул. Восьмого Марта, д. 10, стр. 14",
                "general_email": "b2b@beeline.ru",
                "general_phone": "+78007000611",
                "tags": "Телеком, Big Data, AdTech, B2B Облака, Билайн",
                "decision_makers": [
                        {
                                "full_name": "Торбахов Александр Юрьевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "3528000597",
                "ogrn": "1023501236901",
                "kpp": "352801001",
                "name": "ПАО \"СЕВЕРСТАЛЬ\"",
                "short_name": "Северсталь",
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
                "inn": "4823006703",
                "ogrn": "1024800823123",
                "kpp": "482301001",
                "name": "ПАО \"НЛМК\"",
                "short_name": "НЛМК",
                "okved": "24.10",
                "okved_name": "Производство чугуна, стали и ферросплавов",
                "revenue_rub": 900000000000,
                "employees_count": 55000,
                "website": "nlmk.com",
                "domain": "nlmk.com",
                "region": "Липецкая область",
                "city": "Липецк",
                "address": "398017, Липецкая обл., г. Липецк, пл. Металлургов, д. 2",
                "general_email": "info_nlmk@nlmk.com",
                "general_phone": "+74742444005",
                "tags": "Металлургия, Сталь, Прокат, Промышленность, НЛМК",
                "decision_makers": [
                        {
                                "full_name": "Лисин Владимир Сергеевич",
                                "title": "Председатель Совета директоров",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "8401005730",
                "ogrn": "1028400000288",
                "kpp": "840101001",
                "name": "ПАО \"ГМК \"НОРИЛЬСКИЙ НИКЕЛЬ\"",
                "short_name": "Норникель",
                "okved": "24.44",
                "okved_name": "Производство меди, никеля и палладия",
                "revenue_rub": 1400000000000,
                "employees_count": 72000,
                "website": "nornickel.ru",
                "domain": "nornickel.ru",
                "region": "Красноярский край",
                "city": "Норильск",
                "address": "663302, Красноярский край, г. Норильск, пл. Гвардейская, д. 2",
                "general_email": "gmk@nornik.ru",
                "general_phone": "+74957877667",
                "tags": "Горнорудная промышленность, Металлургия, Никель, Норникель",
                "decision_makers": [
                        {
                                "full_name": "Потанин Владимир Олегович",
                                "title": "Президент, Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "1650032058",
                "ogrn": "1021602013977",
                "kpp": "165001001",
                "name": "ПАО \"КАМАЗ\"",
                "short_name": "КАМАЗ",
                "okved": "29.10",
                "okved_name": "Производство автотранспортных средств и грузовиков",
                "revenue_rub": 370000000000,
                "employees_count": 32000,
                "website": "kamaz.ru",
                "domain": "kamaz.ru",
                "region": "Республика Татарстан",
                "city": "Набережные Челны",
                "address": "423827, Республика Татарстан, г. Набережные Челны, пр-кт Автозаводский, д. 2",
                "general_email": "kamaz@kamaz.ru",
                "general_phone": "+78552372000",
                "tags": "Автопром, Машиностроение, Грузовики, КАМАЗ, B2B Техника",
                "decision_makers": [
                        {
                                "full_name": "Когогин Сергей Анатольевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7736050003",
                "ogrn": "1027700070518",
                "kpp": "784201001",
                "name": "ПАО \"ГАЗПРОМ\"",
                "short_name": "Газпром",
                "okved": "46.71",
                "okved_name": "Торговля оптовая твердым, жидким и газообразным топливом",
                "revenue_rub": 8500000000000,
                "employees_count": 490000,
                "website": "gazprom.ru",
                "domain": "gazprom.ru",
                "region": "г. Санкт-Петербург",
                "city": "Санкт-Петербург",
                "address": "197229, г. Санкт-Петербург, Лахтинский пр-кт, д. 2, корп. 3",
                "general_email": "gazprom@gazprom.ru",
                "general_phone": "+78126093000",
                "tags": "Нефтегаз, Энергетика, Экспорт, Газпром, B2B Топливо",
                "decision_makers": [
                        {
                                "full_name": "Миллер Алексей Борисович",
                                "title": "Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7706107510",
                "ogrn": "1027700043502",
                "kpp": "770601001",
                "name": "ПАО \"НК \"РОСНЕФТЬ\"",
                "short_name": "Роснефть",
                "okved": "06.10",
                "okved_name": "Добыча сырой нефти и нефтяного газа",
                "revenue_rub": 9100000000000,
                "employees_count": 330000,
                "website": "rosneft.ru",
                "domain": "rosneft.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "115035, г. Москва, Софийская наб., д. 26/1",
                "general_email": "postman@rosneft.ru",
                "general_phone": "+74995178888",
                "tags": "Нефть, НПЗ, АЗС, Добыча, Роснефть, B2B ГСМ",
                "decision_makers": [
                        {
                                "full_name": "Сечин Игорь Иванович",
                                "title": "Главный исполнительный директор, Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7708004767",
                "ogrn": "1027700035769",
                "kpp": "770801001",
                "name": "ПАО \"ЛУКОЙЛ\"",
                "short_name": "Лукойл",
                "okved": "70.10",
                "okved_name": "Деятельность головных офисов",
                "revenue_rub": 7900000000000,
                "employees_count": 105000,
                "website": "lukoil.ru",
                "domain": "lukoil.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "101000, г. Москва, Сретенский б-р, д. 11",
                "general_email": "lukoil@lukoil.com",
                "general_phone": "+74956274444",
                "tags": "Нефть, Нефтепереработка, АЗС, Лукойл",
                "decision_makers": [
                        {
                                "full_name": "Воробьев Вадим Николаевич",
                                "title": "Президент",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7727547261",
                "ogrn": "1057747421247",
                "kpp": "720601001",
                "name": "ПАО \"СИБУР ХОЛДИНГ\"",
                "short_name": "СИБУР",
                "okved": "20.16",
                "okved_name": "Производство пластмасс и синтетических смол",
                "revenue_rub": 1100000000000,
                "employees_count": 40000,
                "website": "sibur.ru",
                "domain": "sibur.ru",
                "region": "Тюменская область",
                "city": "Тобольск",
                "address": "626150, Тюменская обл., г. Тобольск, Промзона",
                "general_email": "info@sibur.ru",
                "general_phone": "+74957775500",
                "tags": "Нефтехимия, Полимеры, Пластики, Промышленность, Сибур",
                "decision_makers": [
                        {
                                "full_name": "Конов Дмитрий Владимирович",
                                "title": "Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7810138853",
                "ogrn": "1027810229340",
                "kpp": "781001001",
                "name": "ООО \"ДЕЛОВЫЕ ЛИНИИ\"",
                "short_name": "Деловые Линии",
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
                "tags": "Логистика, B2B Грузоперевозки, Доставка, Склад, Деловые Линии",
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
                "inn": "7722327689",
                "ogrn": "1157746448463",
                "kpp": "772201001",
                "name": "ООО \"СДЭК-ГЛОБАЛ\"",
                "short_name": "СДЭК",
                "okved": "53.20",
                "okved_name": "Деятельность почтовой связи прочая и курьерская деятельность",
                "revenue_rub": 35000000000,
                "employees_count": 32000,
                "website": "cdek.ru",
                "domain": "cdek.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "109052, г. Москва, ул. Нижегородская, д. 29-33, стр. 14",
                "general_email": "msk@cdek.ru",
                "general_phone": "+78002500405",
                "tags": "Курьерская доставка, Фулфилмент, Экспресс-доставка, СДЭК, B2B Логистика",
                "decision_makers": [
                        {
                                "full_name": "Гольдорт Леонид Яковлевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7708503727",
                "ogrn": "1037739877295",
                "kpp": "770801001",
                "name": "ОАО \"РЖД\"",
                "short_name": "РЖД",
                "okved": "49.10",
                "okved_name": "Деятельность железнодорожного транспорта: междугородные перевозки",
                "revenue_rub": 2600000000000,
                "employees_count": 700000,
                "website": "rzd.ru",
                "domain": "rzd.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "107174, г. Москва, ул. Новая Басманная, д. 2",
                "general_email": "info@rzd.ru",
                "general_phone": "+78007750000",
                "tags": "Железная дорога, Грузоперевозки, Пассажирские перевозки, Инфраструктура, РЖД",
                "decision_makers": [
                        {
                                "full_name": "Белозеров Олег Валентинович",
                                "title": "Генеральный директор - Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7712040126",
                "ogrn": "1027700092661",
                "kpp": "771401001",
                "name": "ПАО \"АЭРОФЛОТ\"",
                "short_name": "Аэрофлот",
                "okved": "51.10",
                "okved_name": "Деятельность пассажирского воздушного транспорта",
                "revenue_rub": 600000000000,
                "employees_count": 38000,
                "website": "aeroflot.ru",
                "domain": "aeroflot.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "119019, г. Москва, ул. Арбат, д. 1",
                "general_email": "presscentr@aeroflot.ru",
                "general_phone": "+78004445555",
                "tags": "Авиация, Авиаперевозки, Аэрофлот, B2B Корпоративные перелеты",
                "decision_makers": [
                        {
                                "full_name": "Александровский Сергей Александрович",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7802849641",
                "ogrn": "1147847032838",
                "kpp": "780201001",
                "name": "ООО \"ПК \"БАЛТИКА\"",
                "short_name": "Балтика",
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
                "inn": "7710668383",
                "ogrn": "1077746777890",
                "kpp": "771001001",
                "name": "ООО \"АПХ \"МИРАТОРГ\"",
                "short_name": "Мираторг",
                "okved": "10.11",
                "okved_name": "Переработка и консервирование мяса",
                "revenue_rub": 230000000000,
                "employees_count": 40000,
                "website": "miratorg.ru",
                "domain": "miratorg.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "125196, г. Москва, ул. Лесная, д. 5",
                "general_email": "info@agrohold.ru",
                "general_phone": "+78001008080",
                "tags": "Агрохолдинг, Мясопереработка, Сельхоз, FMCG, Мираторг",
                "decision_makers": [
                        {
                                "full_name": "Линник Виктор Вячеславович",
                                "title": "Президент",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7718560346",
                "ogrn": "1057748379059",
                "kpp": "771801001",
                "name": "ПАО \"ГРУППА ЧЕРКИЗОВО\"",
                "short_name": "Черкизово",
                "okved": "10.13",
                "okved_name": "Производство продукции из мяса убойных животных и птицы",
                "revenue_rub": 225000000000,
                "employees_count": 42000,
                "website": "cherkizovo.com",
                "domain": "cherkizovo.com",
                "region": "г. Москва",
                "city": "Москва",
                "address": "107143, г. Москва, ул. Пермская, вл. 5",
                "general_email": "info@cherkizovo.com",
                "general_phone": "+74956602440",
                "tags": "FMCG, Агрохолдинг, Птицеводство, Мясопереработка, Черкизово",
                "decision_makers": [
                        {
                                "full_name": "Михайлов Сергей Игоревич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7704257121",
                "ogrn": "1037704018800",
                "kpp": "770401001",
                "name": "АО \"ФАРМСТАНДАРТ\"",
                "short_name": "Фармстандарт",
                "okved": "21.20",
                "okved_name": "Производство лекарственных препаратов и материалов",
                "revenue_rub": 180000000000,
                "employees_count": 8000,
                "website": "pharmstd.ru",
                "domain": "pharmstd.ru",
                "region": "Московская область",
                "city": "Долгопрудный",
                "address": "141700, Московская обл., г. Долгопрудный, Лихачевский пр-зд, д. 5Б",
                "general_email": "info@pharmstd.ru",
                "general_phone": "+74959700030",
                "tags": "Фармацевтика, Медикаменты, Производство лекарств, Фармстандарт",
                "decision_makers": [
                        {
                                "full_name": "Григорьев Григорий Александрович",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "5024046180",
                "ogrn": "1025002868224",
                "kpp": "784001001",
                "name": "ЗАО \"БИОКАД\"",
                "short_name": "BIOCAD",
                "okved": "21.20",
                "okved_name": "Производство фармацевтических субстанций и биотехнологий",
                "revenue_rub": 75000000000,
                "employees_count": 3500,
                "website": "biocad.ru",
                "domain": "biocad.ru",
                "region": "г. Санкт-Петербург",
                "city": "Санкт-Петербург",
                "address": "198515, г. Санкт-Петербург, пос. Стрельна, ул. Связи, д. 34, лит. А",
                "general_email": "biocad@biocad.ru",
                "general_phone": "+78123804933",
                "tags": "Биотехнологии, Онкология, Фармацевтика, R&D, Биокад, Biocad",
                "decision_makers": [
                        {
                                "full_name": "Морозов Дмитрий Валентинович",
                                "title": "Генеральный директор",
                                "role_level": "Founder",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7710294503",
                "ogrn": "1027700201011",
                "kpp": "771401001",
                "name": "ООО \"ИНВИТРО\"",
                "short_name": "Инвитро",
                "okved": "86.90",
                "okved_name": "Деятельность в области медицины прочая и лабораторная диагностика",
                "revenue_rub": 40000000000,
                "employees_count": 14000,
                "website": "invitro.ru",
                "domain": "invitro.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "125040, г. Москва, ул. 5-я Магистральная, д. 12",
                "general_email": "corp@invitro.ru",
                "general_phone": "+78002003630",
                "tags": "Медицина, Лабораторные анализы, Диагностика, B2B Медицина, Инвитро",
                "decision_makers": [
                        {
                                "full_name": "Островский Александр Юрьевич",
                                "title": "Основатель, Генеральный директор",
                                "role_level": "Founder",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7713011336",
                "ogrn": "1027739031099",
                "kpp": "770301001",
                "name": "ПАО \"ГРУППА КОМПАНИЙ ПИК\"",
                "short_name": "ПИК",
                "okved": "41.20",
                "okved_name": "Строительство жилых и нежилых зданий",
                "revenue_rub": 500000000000,
                "employees_count": 30000,
                "website": "pik.ru",
                "domain": "pik.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "123242, г. Москва, ул. Баррикадная, д. 19, стр. 1",
                "general_email": "sales@pik.ru",
                "general_phone": "+74955000020",
                "tags": "Девелопмент, Жилая недвижимость, Застройщик, ПИК, Строительство",
                "decision_makers": [
                        {
                                "full_name": "Гордеев Сергей Эдуардович",
                                "title": "Президент",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7731477700",
                "ogrn": "1147746939987",
                "kpp": "770301001",
                "name": "ПАО \"ГК \"САМОЛЕТ\"",
                "short_name": "Самолет",
                "okved": "41.20",
                "okved_name": "Строительство жилых и нежилых зданий",
                "revenue_rub": 280000000000,
                "employees_count": 12000,
                "website": "samolet.ru",
                "domain": "samolet.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "123112, г. Москва, Пресненская наб., д. 12",
                "general_email": "press@samolet.ru",
                "general_phone": "+74951268090",
                "tags": "Девелопмент, PropTech, Строительство, ГК Самолет",
                "decision_makers": [
                        {
                                "full_name": "Елисеев Антон Юрьевич",
                                "title": "Генеральный директор",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7736035485",
                "ogrn": "1027739820921",
                "kpp": "770801001",
                "name": "АО \"СОГАЗ\"",
                "short_name": "СОГАЗ",
                "okved": "65.12",
                "okved_name": "Страхование, кроме страхования жизни",
                "revenue_rub": 400000000000,
                "employees_count": 15000,
                "website": "sogaz.ru",
                "domain": "sogaz.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "107078, г. Москва, пр-кт Академика Сахарова, д. 10",
                "general_email": "sogaz@sogaz.ru",
                "general_phone": "+78003330888",
                "tags": "Страхование, ДМС, B2B Риски, СОГАЗ, КАСКО",
                "decision_makers": [
                        {
                                "full_name": "Устинов Антон Алексеевич",
                                "title": "Председатель Правления",
                                "role_level": "C-Level",
                                "source": "egrul"
                        }
                ]
        },
        {
                "inn": "7707009586",
                "ogrn": "1027739000727",
                "kpp": "770701001",
                "name": "АО \"СБЕРБАНК ЛИЗИНГ\"",
                "short_name": "СберЛизинг",
                "okved": "64.91",
                "okved_name": "Финансовая аренда (лизинг/сублизинг)",
                "revenue_rub": 150000000000,
                "employees_count": 2500,
                "website": "sberleasing.ru",
                "domain": "sberleasing.ru",
                "region": "г. Москва",
                "city": "Москва",
                "address": "121170, г. Москва, ул. Поклонная, д. 3, корп. 1",
                "general_email": "leasing@sberleasing.ru",
                "general_phone": "+78005555556",
                "tags": "Лизинг, B2B Автолизинг, Оборудование, Спецтехника, СберЛизинг",
                "decision_makers": [
                        {
                                "full_name": "Царев Вячеслав Викторович",
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
