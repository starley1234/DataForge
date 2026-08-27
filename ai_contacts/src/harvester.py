import argparse
import csv
import io
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Set, Tuple
import pypdf
import requests

ARXIV_API_URL = "http://export.arxiv.org/api/query"

# Категории ИИ на arXiv:
# cs.AI: Artificial Intelligence
# cs.LG: Machine Learning
# cs.CL: Computation and Language (NLP / LLM)
# cs.CV: Computer Vision
# cs.RO: Robotics
# cs.NE: Neural and Evolutionary Computing
AI_CATEGORIES = [
    "cat:cs.AI",
    "cat:cs.LG",
    "cat:cs.CL",
    "cat:cs.CV",
    "cat:cs.RO"
]


def init_db(db_path: str = "data/ai_contacts.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            author_name TEXT,
            domain TEXT,
            organization TEXT,
            category TEXT,
            paper_title TEXT,
            paper_url TEXT,
            pdf_url TEXT,
            published_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_email ON contacts(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_domain ON contacts(domain)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_category ON contacts(category)")
    conn.commit()
    return conn


def clean_email(raw: str) -> Optional[str]:
    raw = raw.strip().strip(".,;:()<>[]\"'{}").lower()
    # Проверка на валидный email
    if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", raw):
        # Исключаем ложные срабатывания (расширения файлов, общие заглушки)
        if not raw.endswith((".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ai", ".svg", ".eps", ".tar", ".gz")):
            if not any(x in raw for x in ["example.com", "your.email", "name@domain", "author@", "email@"]):
                return raw
    return None


def extract_emails_from_pdf(pdf_url: str) -> Set[str]:
    headers = {"User-Agent": "AI-Researcher-Harvester/1.0"}
    found_emails = set()
    try:
        resp = requests.get(pdf_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            # Читаем первые 2 страницы (титульный лист и контакты авторов)
            text = ""
            for page in reader.pages[:2]:
                text += (page.extract_text() or "") + "\n"
            
            # 1. Прямой поиск regex
            matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
            for m in matches:
                em = clean_email(m)
                if em:
                    found_emails.add(em)
            
            # 2. Поиск вида {user1, user2}@domain.edu
            brace_matches = re.findall(r"\{([a-zA-Z0-9_,.\s+-]+)\}@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text)
            for users_str, domain in brace_matches:
                for u in re.split(r"[,;\s]+", users_str):
                    em = clean_email(f"{u}@{domain}")
                    if em:
                        found_emails.add(em)
    except Exception:
        pass
    return found_emails


def guess_org_from_domain(domain: str) -> str:
    domain_map = {
        "google.com": "Google / DeepMind",
        "deepmind.com": "Google DeepMind",
        "meta.com": "Meta AI",
        "fb.com": "Meta AI",
        "microsoft.com": "Microsoft Research",
        "apple.com": "Apple AI/ML",
        "amazon.com": "Amazon AI",
        "nvidia.com": "NVIDIA",
        "openai.com": "OpenAI",
        "anthropic.com": "Anthropic",
        "mit.edu": "MIT",
        "stanford.edu": "Stanford University",
        "cmu.edu": "Carnegie Mellon University",
        "berkeley.edu": "UC Berkeley",
        "ox.ac.uk": "University of Oxford",
        "cam.ac.uk": "University of Cambridge",
        "ethz.ch": "ETH Zurich",
        "tsinghua.edu.cn": "Tsinghua University",
        "pku.edu.cn": "Peking University",
        "ntu.edu.sg": "Nanyang Technological University",
        "nus.edu.sg": "National University of Singapore",
        "uw.edu": "University of Washington",
        "cornell.edu": "Cornell University",
        "princeton.edu": "Princeton University",
        "harvard.edu": "Harvard University"
    }
    for k, v in domain_map.items():
        if domain.endswith(k):
            return v
    # Если это edu/ac
    if ".edu" in domain or ".ac." in domain:
        parts = domain.split(".")
        return f"University ({parts[-2].upper() if len(parts) >= 2 else domain})"
    return domain


def harvest_arxiv_ai(
    query: Optional[str] = None,
    max_papers: int = 50,
    db_path: str = "data/ai_contacts.db",
    csv_path: str = "data/ai_contacts.csv"
) -> Tuple[int, int]:
    """
    Сбор научных препринтов и извлечение email авторов.
    Возвращает (кол-во обработанных статей, кол-во найденных уникальных email).
    """
    if not query:
        query = " OR ".join(AI_CATEGORIES)

    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_papers,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    headers = {"User-Agent": "AI-Researcher-Harvester/1.0"}

    print(f"[*] Запрос к arXiv API (запрос: {query}, лимит: {max_papers} статей)...")
    resp = requests.get(ARXIV_API_URL, params=params, headers=headers, timeout=25)
    if resp.status_code != 200:
        print(f"[!] Ошибка API: {resp.status_code}")
        return 0, 0

    root = ET.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    conn = init_db(db_path)
    cur = conn.cursor()

    entries = root.findall("atom:entry", ns)
    print(f"[+] Получено {len(entries)} статей. Начинаем извлечение контактов...")

    saved_contacts_count = 0
    papers_processed = 0

    for idx, entry in enumerate(entries, 1):
        paper_id = entry.find("atom:id", ns).text.strip()
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        published = entry.find("atom:published", ns).text.strip()[:10]
        
        authors = [a.find("atom:name", ns).text.strip() for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
        authors_str = ", ".join(authors)

        # Категория статьи
        primary_cat_elem = entry.find("arxiv:primary_category", ns)
        category = primary_cat_elem.attrib.get("term", "cs.AI") if primary_cat_elem is not None else "cs.AI"

        # Ссылка на PDF
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break
        if not pdf_url:
            pdf_url = paper_id.replace("/abs/", "/pdf/") + ".pdf"

        # Извлекаем email авторов из PDF
        emails = extract_emails_from_pdf(pdf_url)
        papers_processed += 1

        if emails:
            print(f"  [{idx}/{len(entries)}] ✓ {title[:50]}... -> {len(emails)} email(s): {', '.join(emails)}")
            for em in emails:
                domain = em.split("@")[-1]
                org = guess_org_from_domain(domain)
                rec_id = f"{paper_id}_{em}"
                cur.execute(
                    """
                    INSERT OR REPLACE INTO contacts 
                    (id, email, author_name, domain, organization, category, paper_title, paper_url, pdf_url, published_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (rec_id, em, authors_str, domain, org, category, title, paper_id, pdf_url, published)
                )
                saved_contacts_count += 1
            conn.commit()
        else:
            print(f"  [{idx}/{len(entries)}] - {title[:50]}... (email не найден в шапке)")

        time.sleep(0.3)  # Вежливая задержка к arXiv

    # Экспорт в CSV
    cur.execute("SELECT email, author_name, domain, organization, category, paper_title, published_date, paper_url, pdf_url FROM contacts ORDER BY published_date DESC")
    rows = cur.fetchall()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["email", "authors", "domain", "organization", "category", "paper_title", "published_date", "paper_url", "pdf_url"])
        writer.writerows(rows)

    conn.close()
    print(f"\n[✓] Сбор завершен! Всего сохранено в БД контактов: {len(rows)}")
    return papers_processed, saved_contacts_count


def main():
    parser = argparse.ArgumentParser(description="Сборщик действующих email-адресов специалистов по ИИ")
    parser.add_argument("--query", type=str, default=None, help="Поисковый запрос arXiv (по умолчанию все категории cs.AI, cs.LG, cs.CL, cs.CV, cs.RO)")
    parser.add_argument("--limit", type=int, default=50, help="Количество статей для анализа")
    parser.add_argument("--db", type=str, default="data/ai_contacts.db", help="Путь к файлу SQLite базы")
    parser.add_argument("--csv", type=str, default="data/ai_contacts.csv", help="Путь к файлу CSV")
    args = parser.parse_args()

    harvest_arxiv_ai(
        query=args.query,
        max_papers=args.limit,
        db_path=args.db,
        csv_path=args.csv
    )


if __name__ == "__main__":
    main()
