import re
import logging
from typing import Optional, List, Set
from urllib.parse import urlparse, unquote
import httpx
from bs4 import BeautifulSoup
from translit import transliterate
from validator import check_domain_mx

logger = logging.getLogger("domain_finder")

EXCLUDED_DOMAINS: Set[str] = {
    # Реестры и агрегаторы контрагентов РФ
    "rusprofile.ru", "spark-interfax.ru", "checko.ru", "list-org.com",
    "sbis.ru", "audit-it.ru", "kartoteka.ru", "egrul.nalog.ru", "nalog.ru",
    "nalog.gov.ru", "gosuslugi.ru", "fedresurs.ru", "zakupki.gov.ru",
    "zachestnyibiznes.ru", "synapsenet.ru", "b2b-center.ru", "rostender.info",
    "audit-it.info", "e-disclosure.ru", "cominfo.pro", "reestr-zalogov.ru",
    "vbankcenter.ru", "kontur.ru", "focus.kontur.ru",
    # Справочники, каталоги и карты
    "2gis.ru", "yell.ru", "zoon.ru", "orgpage.ru", "yp.ru", "allinform.ru",
    "flamp.ru", "avito.ru", "cian.ru", "yandex.ru", "ya.ru", "google.com",
    "google.ru", "duckduckgo.com", "bing.com", "mail.ru", "rambler.ru",
    # Поиск работы и карьеры
    "hh.ru", "superjob.ru", "rabota.ru", "zarplata.ru", "career.habr.com",
    # Соцсети, медиа и видео
    "vk.com", "t.me", "telegram.me", "youtube.com", "rutube.ru", "dzen.ru",
    "vc.ru", "rbc.ru", "kommersant.ru", "vedomosti.ru", "ria.ru", "tass.ru",
    "wikipedia.org", "ok.ru", "instagram.com", "facebook.com", "linkedin.com",
    "tenchat.ru", "github.com", "gitlab.com", "habr.com"
}


def clean_company_name_for_search(name: str) -> str:
    """Удаляет организационно-правовые формы, кавычки и шум для чистого поиска."""
    if not name:
        return ""
    cleaned = re.sub(r'\b(ООО|ОАО|ЗАО|ПАО|АО|НКО|ИП|МУП|ГУП|ФГУП|ПК|НПО|ГК)\b', '', name, flags=re.IGNORECASE)
    cleaned = re.sub(r'["«»„“”\']', '', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


class DomainFinder:
    """
    Интеллектуальный поисковик официального корпоративного домена предприятия
    по наименованию, региону и ИНН без обязательных платных API.
    """

    def __init__(self, timeout: float = 7.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def _is_valid_corporate_domain(self, domain: str) -> bool:
        """Проверяет, не является ли домен поисковиком, соцсетью или реестром."""
        if not domain or "." not in domain:
            return False
        domain_lower = domain.lower().strip()
        parts = domain_lower.split(".")
        root_dom = ".".join(parts[-2:]) if len(parts) >= 2 else domain_lower

        if root_dom in EXCLUDED_DOMAINS or domain_lower in EXCLUDED_DOMAINS:
            return False
        return True

    def find_domain(
        self,
        company_name: str,
        city: Optional[str] = None,
        inn: Optional[str] = None
    ) -> Optional[str]:
        """
        Ищет официальный сайт компании через поисковые выдачи и эвристический подбор.
        """
        clean_name = clean_company_name_for_search(company_name)
        if not clean_name:
            return None

        # 1. Поиск через DuckDuckGo HTML
        query_parts = [clean_name, "официальный сайт"]
        if city:
            query_parts.append(city)
        search_query = " ".join(query_parts)

        try:
            url = "https://html.duckduckgo.com/html/"
            with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.post(url, data={"q": search_query})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = soup.find_all("a", class_="result__url")
                    for a in links:
                        raw_href = a.get("href", "").strip()
                        parsed = urlparse(raw_href)
                        dom = parsed.netloc.replace("www.", "").lower()
                        if dom and self._is_valid_corporate_domain(dom):
                            has_mx, _ = check_domain_mx(dom)
                            if has_mx:
                                return dom
        except Exception as e:
            logger.debug(f"DuckDuckGo search error for '{company_name}': {e}")

        # 2. Эвристический подбор по транслитерации наименования
        lat_name = transliterate(clean_name)
        if lat_name and len(lat_name) >= 3:
            for tld in [".ru", ".com", ".рф"]:
                cand = f"{lat_name}{tld}"
                has_mx, _ = check_domain_mx(cand)
                if has_mx:
                    return cand

        return None
