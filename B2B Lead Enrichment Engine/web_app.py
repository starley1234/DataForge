import os
import re
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
import pandas as pd
from engine import EnrichmentEngine
from email_generator import generate_email_permutations
from validator import verify_email_full, normalize_phone

app = FastAPI(title="B2B Lead Finder & Decision Maker Intelligence", version="2.0.0")
engine = EnrichmentEngine()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B2B Intelligence — База ЛПР предприятий России</title>
    <!-- Google Fonts & Bootstrap Icons -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg-page: #f8fafc;
            --card-border: #e2e8f0;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --success: #10b981;
            --warning: #f59e0b;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-page);
            color: var(--text-main);
            min-height: 100vh;
        }

        .navbar-custom {
            background: #ffffff;
            border-bottom: 1px solid var(--card-border);
            padding: 16px 0;
        }

        .brand-icon {
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            color: #fff;
            width: 38px;
            height: 38px;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
        }

        .stat-card {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 18px 20px;
            transition: all 0.2s ease;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.04);
        }
        .stat-number {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-main);
            line-height: 1.1;
        }

        .search-container-card {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 20px -2px rgba(0,0,0,0.05);
        }

        .input-group-search {
            position: relative;
        }
        .input-group-search .search-icon {
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            color: #94a3b8;
            font-size: 1.2rem;
            z-index: 5;
        }
        .input-group-search input {
            padding-left: 48px;
            height: 52px;
            border-radius: 12px;
            border: 1.5px solid #cbd5e1;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        .input-group-search input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
        }

        .filter-input {
            height: 42px;
            border-radius: 10px;
            border: 1px solid #cbd5e1;
            font-size: 0.9rem;
        }
        .filter-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }

        .table-custom {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
        }
        .table-custom thead th {
            background: #f1f5f9;
            color: #475569;
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            padding: 14px 16px;
            border-bottom: 1px solid var(--card-border);
        }
        .table-custom tbody tr {
            background: #ffffff;
            transition: background 0.15s ease;
        }
        .table-custom tbody tr:hover {
            background: #f8fafc;
        }
        .table-custom tbody td {
            padding: 16px;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: middle;
            font-size: 0.92rem;
        }

        .badge-status {
            font-weight: 600;
            padding: 4px 9px;
            border-radius: 6px;
            font-size: 0.75rem;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .badge-verified { background: #dcfce7; color: #166534; }
        .badge-valid_mx { background: #e0f2fe; color: #075985; }
        .badge-generated { background: #fef3c7; color: #92400e; }
        .badge-unverified { background: #f1f5f9; color: #64748b; }

        .btn-action {
            border-radius: 8px;
            font-weight: 500;
            font-size: 0.85rem;
            padding: 6px 12px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
        }

        .contact-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            font-family: ui-monospace, monospace;
            font-size: 0.86rem;
            color: #334155;
            text-decoration: none;
        }
        .contact-pill:hover {
            background: #f1f5f9;
            color: #0f172a;
        }

        .avatar-circle {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: #e2e8f0;
            color: #475569;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.85rem;
            flex-shrink: 0;
        }
    </style>
</head>
<body>

    <!-- Навбар -->
    <nav class="navbar-custom sticky-top">
        <div class="container-fluid px-lg-5">
            <div class="d-flex justify-content-between align-items-center w-100">
                <div class="d-flex align-items-center gap-3">
                    <div class="brand-icon">
                        <i class="bi bi-briefcase-fill"></i>
                    </div>
                    <div>
                        <h5 class="mb-0 fw-bold">B2B Lead Intelligence</h5>
                        <small class="text-muted">Поиск и прямые контакты ЛПР предприятий России</small>
                    </div>
                </div>
                <div class="d-flex gap-2">
                    <a href="/api/export/csv" class="btn btn-outline-secondary btn-action">
                        <i class="bi bi-filetype-csv"></i> Экспорт CSV
                    </a>
                    <a href="/api/export/excel" class="btn btn-success btn-action">
                        <i class="bi bi-file-earmark-excel"></i> Экспорт Excel
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <div class="container-fluid px-lg-5 py-4">

        <!-- Виджеты статистики -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="stat-card d-flex align-items-center gap-3">
                    <div class="p-3 bg-primary bg-opacity-10 text-primary rounded-3 fs-3">
                        <i class="bi bi-building"></i>
                    </div>
                    <div>
                        <div class="stat-number" id="statCompanies">0</div>
                        <div class="text-muted small fw-medium">Предприятий в базе</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card d-flex align-items-center gap-3">
                    <div class="p-3 bg-indigo bg-opacity-10 text-primary rounded-3 fs-3" style="background:#ede9fe!important; color:#6366f1!important;">
                        <i class="bi bi-person-lines-fill"></i>
                    </div>
                    <div>
                        <div class="stat-number" id="statDMs">0</div>
                        <div class="text-muted small fw-medium">Контактов ЛПР</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card d-flex align-items-center gap-3">
                    <div class="p-3 bg-success bg-opacity-10 text-success rounded-3 fs-3">
                        <i class="bi bi-envelope-check-fill"></i>
                    </div>
                    <div>
                        <div class="stat-number" id="statEmails">0</div>
                        <div class="text-muted small fw-medium">Email с проверкой MX</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card d-flex align-items-center gap-3">
                    <div class="p-3 bg-warning bg-opacity-10 text-warning rounded-3 fs-3">
                        <i class="bi bi-telephone-fill"></i>
                    </div>
                    <div>
                        <div class="stat-number" id="statPhones">0</div>
                        <div class="text-muted small fw-medium">Прямых номеров</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Центральный поисковый блок -->
        <div class="search-container-card mb-4">
            <div class="row g-3">
                <div class="col-lg-8">
                    <label class="form-label fw-bold text-dark small text-uppercase mb-2">
                        <i class="bi bi-cloud-arrow-down text-primary me-1"></i>
                        Сбор и обогащение компании из ЕГРЮЛ ФНС РФ (по ИНН или ОГРН)
                    </label>
                    <div class="input-group-search d-flex gap-2">
                        <i class="bi bi-search search-icon"></i>
                        <input type="text" id="innSearchInput" class="form-control" placeholder="Введите ИНН организации (например: 7707083893, 7802849641, 7736207543, 7702070139)...">
                        <button class="btn btn-primary px-4 fw-semibold d-flex align-items-center gap-2" onclick="enrichRealCompany()" id="btnSearch">
                            <i class="bi bi-search"></i> <span>Найти</span>
                        </button>
                    </div>
                    <div id="searchProgress" class="mt-2 text-muted small" style="min-height: 22px;"></div>
                </div>

                <div class="col-lg-4">
                    <label class="form-label fw-bold text-dark small text-uppercase mb-2">
                        <i class="bi bi-lightning-charge-fill text-warning me-1"></i> Быстрый поиск в сохраненной базе
                    </label>
                    <input type="text" id="filterInput" class="form-control filter-input" placeholder="Фильтр по ФИО, должности, компании, email..." oninput="filterTable()">
                    <div class="d-flex justify-content-between align-items-center mt-2">
                        <small class="text-muted" id="filterCount">Отображено: 0</small>
                        <button class="btn btn-sm btn-link text-decoration-none p-0" onclick="resetFilter()">Сбросить</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Таблица результатов -->
        <div class="card border-0 shadow-sm" style="border-radius: 16px; overflow: hidden;">
            <div class="table-responsive">
                <table class="table table-custom mb-0">
                    <thead>
                        <tr>
                            <th style="width: 25%;">Предприятие / Реквизиты</th>
                            <th style="width: 25%;">Лицо, принимающее решения</th>
                            <th style="width: 22%;">Корпоративный Email</th>
                            <th style="width: 16%;">Телефон</th>
                            <th style="width: 12%; text-align: right;">Профиль / Инфо</th>
                        </tr>
                    </thead>
                    <tbody id="leadsTableBody">
                        <tr>
                            <td colspan="5" class="text-center py-5 text-muted">
                                <div class="spinner-border text-primary spinner-border-sm me-2" role="status"></div>
                                Загрузка базы контактов...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <script>
        let allLeads = [];

        function getInitials(name) {
            if (!name) return 'ЛПР';
            const parts = name.trim().split(/\s+/);
            if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
            return parts[0].slice(0, 2).toUpperCase();
        }

        async function loadLeads() {
            try {
                const res = await fetch('/api/leads');
                allLeads = await res.json();
                updateStats(allLeads);
                renderTable(allLeads);
            } catch (e) {
                console.error("Ошибка загрузки данных:", e);
            }
        }

        function updateStats(leads) {
            const uniqueCompanies = new Set(leads.map(l => l.inn)).size;
            const emailsCount = leads.filter(l => l.dm_email && l.dm_email !== '-').length;
            const phonesCount = leads.filter(l => l.dm_phone && l.dm_phone !== '-').length;

            document.getElementById('statCompanies').innerText = uniqueCompanies;
            document.getElementById('statDMs').innerText = leads.length;
            document.getElementById('statEmails').innerText = emailsCount;
            document.getElementById('statPhones').innerText = phonesCount;
            document.getElementById('filterCount').innerText = `Найдено записей: ${leads.length}`;
        }

        function renderTable(leads) {
            const tbody = document.getElementById('leadsTableBody');
            tbody.innerHTML = '';

            if (leads.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-5 text-muted">
                            <i class="bi bi-inbox fs-1 d-block mb-2 text-secondary"></i>
                            Контакты не найдены. Введите ИНН выше для поиска в реестре.
                        </td>
                    </tr>
                `;
                return;
            }

            leads.forEach(l => {
                let badgeClass = 'badge-unverified';
                let badgeIcon = 'bi-question-circle';
                let statusText = l.email_status || 'не проверен';

                if (l.email_status === 'verified') {
                    badgeClass = 'badge-verified';
                    badgeIcon = 'bi-patch-check-fill';
                    statusText = 'Verified';
                } else if (l.email_status === 'valid_mx') {
                    badgeClass = 'badge-valid_mx';
                    badgeIcon = 'bi-check2-circle';
                    statusText = 'MX активен';
                } else if (l.email_status === 'generated') {
                    badgeClass = 'badge-generated';
                    badgeIcon = 'bi-gear';
                    statusText = 'Паттерн';
                }

                const emailHtml = l.dm_email && l.dm_email !== '-' ? `
                    <div class="d-flex flex-column gap-1">
                        <a href="mailto:${l.dm_email}" class="contact-pill text-truncate" style="max-width: 240px;" title="${l.dm_email}">
                            <i class="bi bi-envelope text-primary"></i> ${l.dm_email}
                        </a>
                        <div>
                            <span class="badge-status ${badgeClass}">
                                <i class="bi ${badgeIcon}"></i> ${statusText}
                            </span>
                        </div>
                    </div>
                ` : '<span class="text-muted small">—</span>';

                const phoneHtml = l.dm_phone && l.dm_phone !== '-' ? `
                    <div class="d-flex flex-column gap-1">
                        <a href="tel:${l.dm_phone}" class="contact-pill text-nowrap">
                            <i class="bi bi-telephone text-success"></i> ${l.dm_phone}
                        </a>
                        <small class="text-muted" style="font-size: 0.75rem;">${l.dm_phone_type === 'reception' ? 'Приемная' : (l.dm_phone_type || 'Прямой')}</small>
                    </div>
                ` : '<span class="text-muted small">—</span>';

                const profileLink = l.dm_profile_url ? `
                    <a href="${l.dm_profile_url}" target="_blank" class="btn btn-sm btn-outline-primary btn-action" title="Открыть профиль">
                        <i class="bi bi-person-badge"></i> Профиль
                    </a>
                ` : (l.website ? `
                    <a href="https://${l.website}" target="_blank" class="btn btn-sm btn-outline-secondary btn-action" title="Сайт организации">
                        <i class="bi bi-globe"></i> Сайт
                    </a>
                ` : '<span class="text-muted small">—</span>');

                tbody.innerHTML += `
                    <tr>
                        <td>
                            <div class="fw-bold text-dark mb-1">${l.company_name}</div>
                            <div class="d-flex align-items-center gap-2 flex-wrap">
                                <span class="badge bg-light text-dark border">ИНН: ${l.inn}</span>
                                ${l.region ? `<span class="text-muted small"><i class="bi bi-geo-alt"></i> ${l.region}</span>` : ''}
                            </div>
                            ${l.okved_name ? `<div class="text-muted small text-truncate mt-1" style="max-width: 280px;" title="${l.okved_name}">${l.okved_name}</div>` : ''}
                        </td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <div class="avatar-circle">${getInitials(l.dm_full_name)}</div>
                                <div>
                                    <div class="fw-semibold text-dark">${l.dm_full_name}</div>
                                    <div class="text-muted small">${l.dm_title || 'Руководитель'}</div>
                                </div>
                            </div>
                        </td>
                        <td>${emailHtml}</td>
                        <td>${phoneHtml}</td>
                        <td style="text-align: right;">${profileLink}</td>
                    </tr>
                `;
            });
        }

        function filterTable() {
            const query = document.getElementById('filterInput').value.toLowerCase().trim();
            if (!query) {
                renderTable(allLeads);
                document.getElementById('filterCount').innerText = `Отображено: ${allLeads.length}`;
                return;
            }

            const filtered = allLeads.filter(l => {
                return (
                    (l.company_name && l.company_name.toLowerCase().includes(query)) ||
                    (l.inn && l.inn.includes(query)) ||
                    (l.dm_full_name && l.dm_full_name.toLowerCase().includes(query)) ||
                    (l.dm_title && l.dm_title.toLowerCase().includes(query)) ||
                    (l.dm_email && l.dm_email.toLowerCase().includes(query)) ||
                    (l.dm_phone && l.dm_phone.includes(query)) ||
                    (l.region && l.region.toLowerCase().includes(query))
                );
            });

            renderTable(filtered);
            document.getElementById('filterCount').innerText = `Найдено: ${filtered.length} из ${allLeads.length}`;
        }

        function resetFilter() {
            document.getElementById('filterInput').value = '';
            filterTable();
        }

        async function enrichRealCompany() {
            const input = document.getElementById('innSearchInput');
            const btn = document.getElementById('btnSearch');
            const progress = document.getElementById('searchProgress');
            const inn = input.value.trim();

            if (!inn) {
                input.focus();
                return;
            }

            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> <span>Поиск...</span>`;
            progress.innerHTML = `<span class="text-primary"><i class="bi bi-hourglass-split"></i> Запрос в официальный реестр ЕГРЮЛ ФНС РФ, получение выписки и поиск контактов...</span>`;

            try {
                const res = await fetch(`/api/enrich/real?inn=${encodeURIComponent(inn)}`, { method: 'POST' });
                const data = await res.json();

                if (data.status === 'ok') {
                    progress.innerHTML = `<span class="text-success fw-semibold"><i class="bi bi-check-circle-fill"></i> Успешно найдено и добавлено: ${data.company_name}</span>`;
                    input.value = '';
                    await loadLeads();
                } else {
                    progress.innerHTML = `<span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> ${data.message || 'Организация не найдена в реестре'}</span>`;
                }
            } catch (e) {
                progress.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle-fill"></i> Ошибка соединения с реестром. Повторите попытку.</span>`;
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i class="bi bi-search"></i> <span>Найти</span>`;
            }
        }

        // Поиск по нажатию Enter
        document.getElementById('innSearchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                enrichRealCompany();
            }
        });

        // Запуск при старте
        loadLeads();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE


@app.get("/api/leads")
def get_leads():
    return engine.get_all_leads()


@app.post("/api/enrich/real")
def enrich_real(inn: str):
    comp = engine.fetch_and_enrich_by_inn(inn.strip(), scrape_web=True, verify_emails=True)
    if comp:
        return {"status": "ok", "company_name": comp.name, "inn": comp.inn, "dms_count": len(comp.decision_makers)}
    return {"status": "error", "message": f"Организация с ИНН {inn} не найдена в ЕГРЮЛ ФНС РФ"}


@app.get("/api/export/csv")
def export_csv():
    leads = engine.get_all_leads()
    df = pd.DataFrame(leads)
    csv_file = "/tmp/leads_export.csv"
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    return FileResponse(csv_file, filename="leads_export.csv", media_type="text/csv")


@app.get("/api/export/excel")
def export_excel():
    leads = engine.get_all_leads()
    df = pd.DataFrame(leads)
    xlsx_file = "/tmp/leads_export.xlsx"
    df.to_excel(xlsx_file, index=False)
    return FileResponse(xlsx_file, filename="leads_export.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
