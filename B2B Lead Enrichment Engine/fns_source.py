import io
import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
import requests
from pypdf import PdfReader
from models import Company, DecisionMaker
from validator import validate_email_syntax

logger = logging.getLogger("fns_egrul")


def parse_management_string(g_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Разбирает строку руководителя из JSON-ответа ЕГРЮЛ (поле 'g').
    Пример: 'Генеральный директор: Иванов Иван Иванович' -> ('Иванов Иван Иванович', 'Генеральный директор')
    """
    if not g_str:
        return None, None

    cleaned = re.sub(r'<[^>]+>', '', g_str).strip()
    if ":" in cleaned:
        parts = cleaned.split(":", 1)
        post = parts[0].strip().capitalize()
        name = parts[1].strip()
        return name, post

    return cleaned, "Генеральный директор"


class FNSEgrulClient:
    """
    Официальный клиент прямого сбора сведений из ЕГРЮЛ / ЕГРИП ФНС РФ (https://egrul.nalog.ru/).
    Поддерживает:
    - Поиск по ИНН (10 знаков для ЮЛ, 12 знаков для ИП)
    - Поиск по ОГРН / ОГРНИП
    - Поиск по наименованию или ФИО предпринимателя
    - Извлечение ФИО первого лица, должности, юридического адреса, выписки PDF, email и ОКВЭД.
    """

    BASE_URL = "https://egrul.nalog.ru/"
    SEARCH_URL = "https://egrul.nalog.ru/search-result/"
    VYP_REQ_URL = "https://egrul.nalog.ru/vyp-request/"
    VYP_STATUS_URL = "https://egrul.nalog.ru/vyp-status/"
    VYP_DOWNLOAD_URL = "https://egrul.nalog.ru/vyp-download/"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://egrul.nalog.ru/index.html"
        })

    def search_by_query(self, query: str) -> List[Dict[str, Any]]:
        """Поиск организаций и ИП в ЕГРЮЛ/ЕГРИП."""
        if not query:
            return []
        clean_query = query.strip()
        try:
            r = self.session.post(self.BASE_URL, data={"query": clean_query}, timeout=self.timeout)
            if r.status_code != 200:
                return []

            token = r.json().get("t")
            if not token:
                return []

            time.sleep(0.35)
            r2 = self.session.get(f"{self.SEARCH_URL}{token}", timeout=self.timeout)
            if r2.status_code == 200:
                data = r2.json()
                return data.get("rows", [])
        except Exception as e:
            logger.warning(f"Ошибка поиска в ЕГРЮЛ по запросу '{clean_query}': {e}")
        return []

    def fetch_company(self, query: str) -> Optional[Company]:
        """
        Полное извлечение карточки компании / ИП и руководителя из ЕГРЮЛ / ЕГРИП.
        """
        rows = self.search_by_query(query)
        if not rows:
            return None

        # Ищем точное совпадение по ИНН / ОГРН, либо берем первую запись
        target_row = None
        q_clean = query.strip()
        for row in rows:
            if row.get("i") == q_clean or row.get("o") == q_clean or row.get("p") == q_clean:
                target_row = row
                break
        if not target_row:
            target_row = rows[0]

        inn = target_row.get("i", "")
        ogrn = target_row.get("o") or target_row.get("ogrn")
        kpp = target_row.get("p")
        comp_name = target_row.get("c") or target_row.get("n", "")
        full_name_org = target_row.get("n", "")
        region = target_row.get("rn")
        address = target_row.get("a")
        token = target_row.get("t")

        # Проверка на ИП (12 знаков ИНН или ОГРНИП 15 знаков)
        is_ip = len(inn) == 12 or (ogrn and len(ogrn) == 15)

        raw_mgmt = target_row.get("g")
        ceo_name, ceo_post = parse_management_string(raw_mgmt)
        if is_ip and not ceo_name:
            ceo_name = full_name_org or comp_name
            ceo_post = "Индивидуальный предприниматель"
        elif not ceo_post:
            ceo_post = "Генеральный директор"

        official_email = None
        domain = None
        okved_code = None
        okved_name = None
        reg_date = target_row.get("d") or target_row.get("r")

        # Скачивание и детальный парсинг выписки ЕГРЮЛ (PDF)
        if token:
            try:
                vyp_req = self.session.get(f"{self.VYP_REQ_URL}{token}", timeout=self.timeout)
                vyp_t = vyp_req.json().get("t")
                if vyp_t:
                    ready = False
                    for _ in range(4):
                        time.sleep(0.7)
                        st_resp = self.session.get(f"{self.VYP_STATUS_URL}{vyp_t}", timeout=self.timeout)
                        if st_resp.status_code == 200 and st_resp.json().get("status") == "ready":
                            ready = True
                            break

                    if ready:
                        pdf_resp = self.session.get(f"{self.VYP_DOWNLOAD_URL}{vyp_t}", timeout=self.timeout)
                        if pdf_resp.status_code == 200:
                            reader = PdfReader(io.BytesIO(pdf_resp.content))
                            full_text = "\n".join([page.extract_text() for page in reader.pages])

                            # Email из ЕГРЮЛ
                            email_match = re.search(
                                r"E-mail\s+([A-Za-z0-9_.+\-\s]+@[A-Za-z0-9.\-\s]+)",
                                full_text,
                                re.IGNORECASE
                            )
                            if email_match:
                                raw_em = email_match.group(1)
                                cleaned = re.sub(r"\s+", "", raw_em).lower()
                                cleaned = re.sub(r"\.([a-z]{2,4})\d+.*$", r".\1", cleaned)
                                if validate_email_syntax(cleaned):
                                    official_email = cleaned
                                    if "@" in official_email:
                                        d_cand = official_email.split("@")[1]
                                        if not any(f in d_cand for f in ["mail.ru", "yandex.ru", "gmail.com"]):
                                            domain = d_cand

                            # Уточнение ФИО руководителя
                            if not ceo_name or is_ip:
                                fio_block = re.search(
                                    r"Фамилия\s*\n\s*Имя\s*\n\s*Отчество\s*\n\s*([А-ЯЁ\-]+)\s*\n\s*([А-ЯЁ\-]+)\s*\n\s*([А-ЯЁ\-]+)",
                                    full_text
                                )
                                if fio_block:
                                    ceo_name = f"{fio_block.group(1).title()} {fio_block.group(2).title()} {fio_block.group(3).title()}"

                            post_block = re.search(r"Должность\s+([^\n]+)", full_text)
                            if post_block:
                                ceo_post = post_block.group(1).strip().capitalize()

                            if not address:
                                addr_block = re.search(r"Адрес юридического лица\s+([^\n]+(?:\n[^\n]+){1,4})", full_text)
                                if addr_block:
                                    address = ", ".join([line.strip() for line in addr_block.group(1).split("\n") if line.strip() and not line.startswith("ГРН")])

                            okv_match = re.search(
                                r"(?:Код по ОКВЭД|Код и наименование вида деятельности)\s+([0-9\.]+)\s+([^\n]+)",
                                full_text
                            )
                            if okv_match:
                                okved_code = okv_match.group(1).strip()
                                okved_name = okv_match.group(2).strip()
            except Exception as e:
                logger.debug(f"Парсинг PDF ЕГРЮЛ: {e}")

        decision_makers = []
        if ceo_name:
            decision_makers.append(DecisionMaker(
                company_inn=inn,
                company_name=comp_name,
                full_name=ceo_name,
                title=ceo_post,
                role_level="Founder" if is_ip else "C-Level",
                source="egrul_fns",
                confidence_score=95
            ))

        return Company(
            inn=inn,
            kpp=kpp,
            ogrn=ogrn,
            name=full_name_org or comp_name,
            short_name=comp_name,
            okved=okved_code,
            okved_name=okved_name,
            region=region,
            address=address,
            website=domain,
            domain=domain,
            general_email=official_email,
            decision_makers=decision_makers,
            source="egrul"
        )
