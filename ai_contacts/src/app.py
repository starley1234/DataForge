import os
import sys
import sqlite3
import threading
from typing import Any, Dict, List
from flask import Flask, jsonify, render_template, request, send_file

# Добавляем корень проекта в sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.harvester import harvest_arxiv_ai

BASE_DIR = PROJECT_ROOT
DB_PATH = os.path.join(BASE_DIR, "data", "ai_contacts.db")
CSV_PATH = os.path.join(BASE_DIR, "data", "ai_contacts.csv")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "web", "templates"),
    static_folder=os.path.join(BASE_DIR, "web", "static")
)

# Состояние фонового сбора
collection_state = {
    "is_running": False,
    "last_status": "Ожидание запуска",
    "papers_processed": 0,
    "contacts_found": 0
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    """Статистика базы данных."""
    if not os.path.exists(DB_PATH):
        return jsonify({
            "total_contacts": 0,
            "unique_domains": 0,
            "top_orgs": [],
            "top_domains": [],
            "categories": [],
            "collection_state": collection_state
        })

    conn = get_db_connection()
    cur = conn.cursor()

    total_contacts = cur.execute("SELECT COUNT(DISTINCT email) FROM contacts").fetchone()[0]
    unique_domains = cur.execute("SELECT COUNT(DISTINCT domain) FROM contacts").fetchone()[0]

    top_orgs = cur.execute(
        """
        SELECT organization, COUNT(*) as count 
        FROM contacts 
        GROUP BY organization 
        ORDER BY count DESC 
        LIMIT 7
        """
    ).fetchall()

    top_domains = cur.execute(
        """
        SELECT domain, COUNT(*) as count 
        FROM contacts 
        GROUP BY domain 
        ORDER BY count DESC 
        LIMIT 7
        """
    ).fetchall()

    categories = cur.execute(
        """
        SELECT category, COUNT(*) as count 
        FROM contacts 
        GROUP BY category 
        ORDER BY count DESC
        """
    ).fetchall()

    conn.close()

    return jsonify({
        "total_contacts": total_contacts,
        "unique_domains": unique_domains,
        "top_orgs": [{"name": r["organization"], "count": r["count"]} for r in top_orgs],
        "top_domains": [{"domain": r["domain"], "count": r["count"]} for r in top_domains],
        "categories": [{"cat": r["category"], "count": r["count"]} for r in categories],
        "collection_state": collection_state
    })


@app.route("/api/contacts")
def api_contacts():
    """Получение списка контактов с поиском, фильтрами и пагинацией."""
    if not os.path.exists(DB_PATH):
        return jsonify({"contacts": [], "total": 0})

    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    conn = get_db_connection()
    cur = conn.cursor()

    query_parts = ["1=1"]
    params = []

    if search:
        query_parts.append("(email LIKE ? OR author_name LIKE ? OR organization LIKE ? OR domain LIKE ? OR paper_title LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param, search_param, search_param])

    if category:
        query_parts.append("category = ?")
        params.append(category)

    where_clause = " AND ".join(query_parts)

    total = cur.execute(f"SELECT COUNT(*) FROM contacts WHERE {where_clause}", params).fetchone()[0]

    sql = f"""
        SELECT id, email, author_name, domain, organization, category, paper_title, paper_url, pdf_url, published_date
        FROM contacts
        WHERE {where_clause}
        ORDER BY published_date DESC, id DESC
        LIMIT ? OFFSET ?
    """
    rows = cur.execute(sql, params + [limit, offset]).fetchall()
    conn.close()

    contacts = [dict(r) for r in rows]
    return jsonify({"contacts": contacts, "total": total})


def run_background_harvest(limit: int, query: str):
    global collection_state
    collection_state["is_running"] = True
    collection_state["last_status"] = f"Сбор {limit} статей по запросу: {query or 'Все разделы ИИ'}..."
    try:
        papers, found = harvest_arxiv_ai(query=query if query else None, max_papers=limit, db_path=DB_PATH, csv_path=CSV_PATH)
        collection_state["papers_processed"] += papers
        collection_state["contacts_found"] += found
        collection_state["last_status"] = f"Успешно завершено! Обработано {papers} статей, найдено {found} email."
    except Exception as e:
        collection_state["last_status"] = f"Ошибка: {e}"
    finally:
        collection_state["is_running"] = False


@app.route("/api/harvest", methods=["POST"])
def api_harvest():
    """Запуск сбора новых данных в фоне."""
    global collection_state
    if collection_state["is_running"]:
        return jsonify({"success": False, "message": "Сбор уже запущен и выполняется в фоне."}), 400

    data = request.get_json() or {}
    limit = int(data.get("limit", 30))
    query = data.get("query", "").strip()

    t = threading.Thread(target=run_background_harvest, args=(limit, query))
    t.daemon = True
    t.start()

    return jsonify({"success": True, "message": "Процесс сбора успешно запущен в фоновом режиме!"})


@app.route("/api/export/csv")
def api_export_csv():
    """Выгрузка базы данных в CSV."""
    if os.path.exists(CSV_PATH):
        return send_file(CSV_PATH, as_attachment=True, download_name="ai_contacts_export.csv")
    return jsonify({"error": "Файл CSV пока не сгенерирован"}), 404


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False)
