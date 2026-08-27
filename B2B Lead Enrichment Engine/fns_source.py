import io
import re
import time
import logging
from typing import Optional, List, Dict, Any
import requests
from pypdf import PdfReader
from models import Company, DecisionMaker
from validator import normalize_phone

logger = logging.getLogger("fns_egrul")


class FNSEgrulClient:
    """
    Официальный сборщик данных напрямую из Единого государственного реестра юридических лиц (ЕГРЮЛ ФНС РФ).
    Не требует платных API-ключей.
    
    Извлекает:
    - Официальное полное и краткое наименование
    - ОГРН, ИНН, КПП
    - Юридический адрес и регион
    - Официальный Email организации, указанный при регистрации в ФНС
    - ФИО первого лица (Генеральный директор, Президент, Руководитель)
    - Должность руководителя
    - Основной ОКВЭД
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://egrul.nalog.ru/index.html"
        })

    def search_by_query(self, query: str) -> List[Dict[str, Any]]:
        """Поиск компаний в ЕГРЮЛ по ИНН, ОГРН или наименованию."""
        try:
            r = self.session.post(self.BASE_URL, data={"query": query.strip()}, timeout=self.timeout)
            if r.status_code != 200:
                return []
            
            token = r.json().get("t")
            if not token:
                return []
            
            time.sleep(0.5)
            r2 = self.session.get(f"{self.SEARCH_URL}{token}", timeout=self.timeout)
            if r2.status_code == 200:
                data = r2.json()
                return data.get("rows", [])
        except Exception as e:
            logger.warning(f"Ошибка поиска в ЕГРЮЛ по запросу '{query}': {e}")
        return []

    def fetch_company_by_inn(self, inn: str) -> Optional[Company]:
        """
        Полное извлечение карточки компании и руководителя из официальной выписки ЕГРЮЛ.
        """
        rows = self.search_by_query(inn)
        if not rows:
            return None

        # Ищем точное совпадение по ИНН
        target_row = None
        for row in rows:
            if row.get("i") == inn.strip():
                target_row = row
                break
        if not target_row:
            target_row = rows[0]

        comp_name = target_row.get("c") or target_row.get("n", "")
        full_name_org = target_row.get("n", "")
        ogrn = target_row.get("o")
        kpp = target_row.get("p")
        region = target_row.get("rn")
        token = target_row.get("t")

        ceo_name = None
        ceo_post = "Генеральный директор"
        official_email = None
        domain = None
        okved_code = None
        okved_name = None
        address = None

        # Скачиваем и парсим электронную выписку ЕГРЮЛ (PDF)
        if token:
            try:
                vyp_req = self.session.get(f"{self.VYP_REQ_URL}{token}", timeout=self.timeout)
                vyp_t = vyp_req.json().get("t")
                if vyp_t:
                    # Ожидание готовности выписки
                    ready = False
                    for _ in range(5):
                        time.sleep(1.0)
                        st_resp = self.session.get(f"{self.VYP_STATUS_URL}{vyp_t}", timeout=self.timeout)
                        if st_resp.status_code == 200 and st_resp.json().get("status") == "ready":
                            ready = True
                            break

                    if ready:
                        pdf_resp = self.session.get(f"{self.VYP_DOWNLOAD_URL}{vyp_t}", timeout=self.timeout)
                        if pdf_resp.status_code == 200:
                            reader = PdfReader(io.BytesIO(pdf_resp.content))
                            full_text = "\n".join([page.extract_text() for page in reader.pages])

                            # Извлекаем Email (в ЕГРЮЛ есть поле "Адрес электронной почты E-mail ...")
                            email_match = re.search(r"E-mail\s+([A-Za-z0-9_.+\-\s]+@[A-Za-z0-9.\-\s]+)", full_text, re.IGNORECASE)
                            if email_match:
                                raw_em = email_match.group(1)
                                # Удаляем пробелы и спецсимволы
                                cleaned = re.sub(r"\s+", "", raw_em).lower()
                                # Убираем случайно прилипшие цифры со следующей строки
                                cleaned = re.sub(r"\.([a-z]{2,4})\d+.*$", r".\1", cleaned)
                                official_email = cleaned
                                if "@" in official_email:
                                    domain = official_email.split("@")[1]

                            # Извлекаем ФИО руководителя
                            fio_block = re.search(r"Фамилия\s*\n\s*Имя\s*\n\s*Отчество\s*\n\s*([А-ЯЁ\-]+)\s*\n\s*([А-ЯЁ\-]+)\s*\n\s*([А-ЯЁ\-]+)", full_text)
                            if fio_block:
                                ceo_name = f"{fio_block.group(1).title()} {fio_block.group(2).title()} {fio_block.group(3).title()}"

                            # Должность руководителя
                            post_block = re.search(r"Должность\s+([^\n]+)", full_text)
                            if post_block:
                                ceo_post = post_block.group(1).strip().capitalize()

                            # Адрес
                            addr_block = re.search(r"Адрес юридического лица\s+([^\n]+(?:\n[^\n]+){1,4})", full_text)
                            if addr_block:
                                address = ", ".join([line.strip() for line in addr_block.group(1).split("\n") if line.strip() and not line.startswith("ГРН")])

                            # ОКВЭД
                            okv_match = re.search(r"Сведения об основном виде экономической деятельности.*?(?:Код по ОКВЭД|Код и наименование вида деятельности)\s+([0-9\.]+)\s+([^\n]+)", full_text, re.DOTALL)
                            if okv_match:
                                okved_code = okv_match.group(1).strip()
                                okved_name = okv_match.group(2).strip()
            except Exception as e:
                logger.warning(f"Ошибка парсинга PDF выписки ЕГРЮЛ для {inn}: {e}")

        decision_makers = []
        if ceo_name:
            decision_makers.append(DecisionMaker(
                company_inn=inn,
                company_name=comp_name,
                full_name=ceo_name,
                title=ceo_post,
                role_level="C-Level",
                source="egrul_nalog_ru",
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
            decision_makers=decision_makers
        )
