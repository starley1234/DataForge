import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from validator import normalize_phone, validate_email_syntax

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

LEADERSHIP_KEYWORDS = [
    "директор", "руководитель", "президент", "вице-президент", "генеральный",
    "главный", "коммерческий", "технический", "управляющий", "учредитель",
    "начальник", "founder", "ceo", "cto", "cfo", "cmo", "coo", "director"
]

CONTACT_PAGE_KEYWORDS = ["contacts", "contact", "about", "team", "management", "o-nas", "komanda", "kontakty", "rukovodstvo"]


class WebsiteScraper:
    def __init__(self, timeout: float = 7.0):
        self.timeout = timeout

    def _extract_emails(self, text: str) -> List[str]:
        raw_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        valid = []
        for e in set(raw_emails):
            if validate_email_syntax(e):
                valid.append(e.lower())
        return valid

    def _extract_phones(self, text: str) -> List[Dict[str, Any]]:
        # Паттерны номеров РФ: +7, 8, (xxx)
        phone_patterns = re.findall(r'(?:\+7|8)[\s\-\(]*\d{3,4}[\s\-\)]*\d{2,3}[\s\-]*\d{2}[\s\-]*\d{2}', text)
        results = []
        seen = set()
        for p in phone_patterns:
            norm = normalize_phone(p)
            if norm["valid"] and norm["formatted"] not in seen:
                seen.add(norm["formatted"])
                results.append(norm)
        return results

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        links = {"telegram": [], "vk": [], "linkedin": [], "tenchat": []}
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "t.me/" in href or "telegram.me/" in href:
                links["telegram"].append(href)
            elif "vk.com/" in href:
                links["vk"].append(href)
            elif "linkedin.com/" in href:
                links["linkedin"].append(href)
            elif "tenchat.ru/" in href:
                links["tenchat"].append(href)
        
        for k in links:
            links[k] = list(set(links[k]))
        return links

    def _extract_persons(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Эвристический поиск блоков руководителей / команды на страницах."""
        persons = []
        seen_names = set()

        # Ищем карточки и текстовые блоки с упоминанием должностей
        cards = soup.find_all(["div", "section", "article", "li"], class_=re.compile(r'(team|member|person|leader|staff|about|worker|employee)', re.I))
        
        for card in cards:
            text = card.get_text(" ", strip=True)
            for kw in LEADERSHIP_KEYWORDS:
                if kw in text.lower():
                    # Пытаемся найти ФИО (2-3 русских слова с заглавной буквы)
                    name_matches = re.findall(r'\b([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})\b', text)
                    for name in name_matches:
                        if name not in seen_names and len(name.split()) >= 2:
                            # Проверяем, чтобы это не были служебные слова
                            if not any(sw in name.lower() for sw in ["главная", "россия", "москва", "контакты", "политика"]):
                                seen_names.add(name)
                                persons.append({
                                    "full_name": name,
                                    "title": kw.capitalize(),
                                    "source": "website_team_page"
                                })
                    break

        return persons

    def scrape_website(self, base_url: str) -> Dict[str, Any]:
        """
        Обходит главную страницу и страницы контактов/команды,
        извлекая почты, телефоны, соцсети и упомянутых руководителей.
        """
        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        parsed_url = urlparse(base_url)
        domain = parsed_url.netloc.replace("www.", "")

        results = {
            "domain": domain,
            "emails": [],
            "phones": [],
            "socials": {"telegram": [], "vk": [], "linkedin": [], "tenchat": []},
            "persons": [],
            "pages_visited": []
        }

        pages_to_visit = [base_url]

        with httpx.Client(headers=HEADERS, timeout=self.timeout, follow_redirects=True, verify=False) as client:
            # 1. Загружаем главную
            try:
                resp = client.get(base_url)
                if resp.status_code == 200:
                    results["pages_visited"].append(base_url)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    results["emails"].extend(self._extract_emails(resp.text))
                    results["phones"].extend(self._extract_phones(resp.text))
                    
                    soc = self._extract_social_links(soup)
                    for k in soc:
                        results["socials"][k].extend(soc[k])

                    # Ищем ссылки на контакты / команду
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        full_href = urljoin(base_url, href)
                        parsed_href = urlparse(full_href)
                        
                        if parsed_href.netloc.replace("www.", "") == domain:
                            path_lower = parsed_href.path.lower()
                            if any(k in path_lower for k in CONTACT_PAGE_KEYWORDS):
                                if full_href not in pages_to_visit and len(pages_to_visit) < 5:
                                    pages_to_visit.append(full_href)
            except Exception:
                pass

            # 2. Обходим найденные страницы контактов/команды
            for page_url in pages_to_visit[1:]:
                try:
                    resp = client.get(page_url)
                    if resp.status_code == 200:
                        results["pages_visited"].append(page_url)
                        soup = BeautifulSoup(resp.text, "html.parser")
                        results["emails"].extend(self._extract_emails(resp.text))
                        results["phones"].extend(self._extract_phones(resp.text))
                        results["persons"].extend(self._extract_persons(soup))
                        
                        soc = self._extract_social_links(soup)
                        for k in soc:
                            results["socials"][k].extend(soc[k])
                except Exception:
                    pass

        # Дедупликация
        results["emails"] = list(set(results["emails"]))
        
        unique_phones = []
        seen_phone_nums = set()
        for p in results["phones"]:
            if p["formatted"] not in seen_phone_nums:
                seen_phone_nums.add(p["formatted"])
                unique_phones.append(p)
        results["phones"] = unique_phones

        for k in results["socials"]:
            results["socials"][k] = list(set(results["socials"][k]))

        return results
