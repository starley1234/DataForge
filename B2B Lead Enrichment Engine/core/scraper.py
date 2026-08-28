import re
import warnings
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
import urllib3
from core.validator import normalize_phone, validate_email_syntax, is_role_based_email
from core.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache"
}

ROLE_LEVEL_MAPPINGS = [
    # C-Level
    (["генеральный директор", "президент", "председатель правления", "управляющий директор",
      "ceo", "founder", "основатель", "владелец", "сооснователь", "гендиректор"], "C-Level"),
    # Director
    (["коммерческий директор", "технический директор", "финансовый директор",
      "операционный директор", "директор по маркетингу", "директор по развитию",
      "директор по продажам", "директор по логистике", "директор по закупкам",
      "директор по персоналу", "hr-директор", "it-директор", "cto", "cfo", "cmo", "coo", "cio", "ciso"], "Director"),
    # Head / Руководитель
    (["руководитель отдела", "начальник управления", "главный бухгалтер",
      "главный инженер", "заместитель директора", "руководитель проектов",
      "head of", "тимлид", "ведущий специалист"], "Head")
]

CONTACT_PAGE_KEYWORDS = [
    "contacts", "contact", "about", "team", "management", "leadership",
    "o-nas", "komanda", "kontakty", "rukovodstvo", "board", "o-kompanii",
    "o-predpriyatii", "rekvizity", "requisites", "people", "staff"
]

IGNORE_EMAIL_SUBSTRINGS = [
    "example.com", "domain.com", "email.com", "yourdomain", "test.com",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    "sentry.io", "wixpress.com", "wordpress.org"
]

STOP_NAME_WORDS = {
    "главная", "россия", "москва", "контакты", "политика", "компания",
    "новости", "услуги", "продукция", "каталог", "вакансии", "отзывы",
    "проекты", "наши", "партнеры", "информация", "реквизиты", "адрес",
    "телефон", "схема", "проезда", "время", "работы", "режим", "сертификат"
}


class WebsiteScraper:
    def __init__(self, timeout: Optional[float] = None, max_pages: Optional[int] = None):
        self.timeout = timeout or settings.SCRAPER_TIMEOUT
        self.max_pages = max_pages or settings.SCRAPER_MAX_PAGES

    def _extract_emails(self, text: str, domain: str) -> List[str]:
        raw_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        valid: List[str] = []
        for e in set(raw_emails):
            e_clean = e.lower().strip().rstrip('.,;:)"\'')
            if any(bad in e_clean for bad in IGNORE_EMAIL_SUBSTRINGS):
                continue
            if validate_email_syntax(e_clean):
                valid.append(e_clean)
        
        valid.sort(key=lambda x: (domain in x if domain else True, not is_role_based_email(x)), reverse=True)
        return list(dict.fromkeys(valid))

    def _extract_phones(self, text: str) -> List[Dict[str, Any]]:
        raw_phones = re.findall(
            r'(?:(?:\+7|8)[\s\-\(]*)?(?:\d{3,4})[\s\-\)]*\d{2,3}[\s\-]*\d{2}[\s\-]*\d{2}',
            text
        )
        results: List[Dict[str, Any]] = []
        seen = set()
        for p in raw_phones:
            norm = normalize_phone(p)
            if norm["valid"] and norm["formatted"] not in seen:
                seen.add(norm["formatted"])
                results.append(norm)
        return results

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        links: Dict[str, List[str]] = {
            "telegram": [],
            "vk": [],
            "tenchat": [],
            "linkedin": [],
            "hh": [],
            "youtube": []
        }
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "t.me/" in href or "telegram.me/" in href:
                if not any(bad in href for bad in ["share", "joinchat/addstickers"]):
                    links["telegram"].append(href)
            elif "vk.com/" in href:
                if not any(bad in href for bad in ["share.php", "widget"]):
                    links["vk"].append(href)
            elif "tenchat.ru/" in href:
                links["tenchat"].append(href)
            elif "linkedin.com/" in href:
                links["linkedin"].append(href)
            elif "hh.ru/employer/" in href:
                links["hh"].append(href)
            elif "youtube.com/" in href or "rutube.ru/" in href:
                links["youtube"].append(href)

        for k in links:
            links[k] = list(set(links[k]))
        return links

    def _extract_requisites(self, text: str) -> Dict[str, Optional[str]]:
        """Поиск ИНН, ОГРН, КПП на страницах сайта для валидации соответствия."""
        reqs = {"inn": None, "ogrn": None, "kpp": None}
        inn_m = re.search(r'\b(?:ИНН|ИНН/КПП)\s*[:№]?\s*(\d{10}|\d{12})\b', text, re.I)
        if inn_m:
            reqs["inn"] = inn_m.group(1)

        ogrn_m = re.search(r'\bОГРН\s*[:№]?\s*(\d{13}|\d{15})\b', text, re.I)
        if ogrn_m:
            reqs["ogrn"] = ogrn_m.group(1)

        kpp_m = re.search(r'\bКПП\s*[:№]?\s*(\d{9})\b', text, re.I)
        if kpp_m:
            reqs["kpp"] = kpp_m.group(1)

        return reqs

    def _extract_persons(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Интеллектуальный поиск карточек руководителей и контактных лиц."""
        persons: List[Dict[str, Any]] = []
        seen_names = set()

        containers = soup.find_all(
            ["div", "section", "article", "li", "tr"],
            class_=re.compile(r'(team|member|person|leader|staff|about|worker|employee|card|profile|management)', re.I)
        )

        for cont in containers:
            text = cont.get_text(" ", strip=True)
            matched_title = None
            matched_role_level = "Director"

            t_lower = text.lower()
            for keywords, role_lvl in ROLE_LEVEL_MAPPINGS:
                for kw in keywords:
                    if kw in t_lower:
                        matched_title = kw.capitalize()
                        matched_role_level = role_lvl
                        break
                if matched_title:
                    break

            if not matched_title:
                continue

            name_matches = re.findall(r'\b([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})\b', text)
            for raw_name in name_matches:
                parts = [p.strip() for p in raw_name.split() if p.strip()]
                if len(parts) < 2 or len(parts) > 3:
                    continue

                if any(p.lower() in STOP_NAME_WORDS for p in parts):
                    continue

                full_name = " ".join(parts)
                if full_name not in seen_names:
                    seen_names.add(full_name)

                    direct_email = None
                    direct_phone = None

                    emails_in_card = self._extract_emails(text, "")
                    if emails_in_card:
                        direct_email = emails_in_card[0]

                    phones_in_card = self._extract_phones(text)
                    if phones_in_card:
                        direct_phone = phones_in_card[0]["formatted"]

                    persons.append({
                        "full_name": full_name,
                        "title": matched_title,
                        "role_level": matched_role_level,
                        "email": direct_email,
                        "phone": direct_phone,
                        "source": f"website_scrape:{urlparse(page_url).path or '/'}"
                    })
                    break

        return persons

    def scrape_website(self, base_url: str) -> Dict[str, Any]:
        """
        Обходит сайт компании, находит страницы контактов и руководства,
        извлекает телефоны, корпоративные email, соцсети, реквизиты и список ЛПР.
        """
        if not base_url:
            return {
                "domain": "",
                "emails": [],
                "phones": [],
                "socials": {"telegram": [], "vk": [], "tenchat": [], "linkedin": [], "hh": [], "youtube": []},
                "requisites": {},
                "persons": [],
                "pages_visited": []
            }

        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        parsed_url = urlparse(base_url)
        domain = parsed_url.netloc.replace("www.", "")

        results: Dict[str, Any] = {
            "domain": domain,
            "emails": [],
            "phones": [],
            "socials": {"telegram": [], "vk": [], "tenchat": [], "linkedin": [], "hh": [], "youtube": []},
            "requisites": {"inn": None, "ogrn": None, "kpp": None},
            "persons": [],
            "pages_visited": []
        }

        pages_to_visit = [base_url]
        visited_urls: Set[str] = set()

        transport = httpx.HTTPTransport(verify=False, retries=1)
        with httpx.Client(headers=HEADERS, timeout=self.timeout, follow_redirects=True, transport=transport) as client:
            idx = 0
            while idx < len(pages_to_visit) and len(visited_urls) < self.max_pages:
                current_url = pages_to_visit[idx]
                idx += 1

                if current_url in visited_urls:
                    continue
                visited_urls.add(current_url)

                try:
                    resp = client.get(current_url)
                    if resp.status_code == 200:
                        results["pages_visited"].append(current_url)
                        html_text = resp.text
                        soup = BeautifulSoup(html_text, "html.parser")

                        results["emails"].extend(self._extract_emails(html_text, domain))
                        results["phones"].extend(self._extract_phones(html_text))

                        soc = self._extract_social_links(soup)
                        for k in soc:
                            results["socials"][k].extend(soc[k])

                        reqs = self._extract_requisites(html_text)
                        for k, v in reqs.items():
                            if v and not results["requisites"].get(k):
                                results["requisites"][k] = v

                        extracted_persons = self._extract_persons(soup, current_url)
                        results["persons"].extend(extracted_persons)

                        # Если это главная страница, ищем ссылки на контакты / команду
                        if idx == 1:
                            for a in soup.find_all("a", href=True):
                                href = a["href"].strip()
                                full_href = urljoin(base_url, href)
                                parsed_href = urlparse(full_href)

                                if parsed_href.netloc.replace("www.", "") == domain:
                                    path_lower = parsed_href.path.lower()
                                    if any(k in path_lower for k in CONTACT_PAGE_KEYWORDS):
                                        if full_href not in pages_to_visit and len(pages_to_visit) < (self.max_pages + 2):
                                            pages_to_visit.append(full_href)
                except Exception:
                    pass

        results["emails"] = list(dict.fromkeys(results["emails"]))

        unique_phones = []
        seen_phones = set()
        for p in results["phones"]:
            if p["formatted"] not in seen_phones:
                seen_phones.add(p["formatted"])
                unique_phones.append(p)
        results["phones"] = unique_phones

        for k in results["socials"]:
            results["socials"][k] = list(set(results["socials"][k]))

        unique_persons = []
        seen_person_names = set()
        for p in results["persons"]:
            if p["full_name"] not in seen_person_names:
                seen_person_names.add(p["full_name"])
                unique_persons.append(p)
        results["persons"] = unique_persons

        return results
