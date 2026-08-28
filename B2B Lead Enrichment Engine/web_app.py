import os
import io
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Request, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import EnrichmentEngine
from email_generator import generate_email_permutations
from validator import verify_email_full, normalize_phone
from exporter import (
    export_to_csv, export_to_excel, export_to_amocrm_csv,
    export_to_bitrix24_csv, export_to_json, generate_outreach_email
)
from batch_processor import BatchProcessor
from config import settings

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Разрешаем CORS для веб-интерфейса и внешних интеграций
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = EnrichmentEngine()
batch_processor = BatchProcessor(engine)


# Pydantic schemas for API requests
class LeadUpdateRequest(BaseModel):
    dm_full_name: Optional[str] = None
    dm_title: Optional[str] = None
    dm_role_level: Optional[str] = None
    dm_email: Optional[str] = None
    email_status: Optional[str] = None
    dm_phone: Optional[str] = None
    dm_phone_type: Optional[str] = None
    dm_telegram: Optional[str] = None
    lead_status: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: Optional[int] = None


class ManualLeadCreateRequest(BaseModel):
    inn: str
    company_name: str
    website: Optional[str] = None
    region: Optional[str] = None
    dm_full_name: str
    dm_title: Optional[str] = "Генеральный директор"
    dm_role_level: Optional[str] = "C-Level"
    dm_email: Optional[str] = None
    dm_phone: Optional[str] = None
    notes: Optional[str] = None


class PermutationReq(BaseModel):
    full_name: str
    domain: str
    known_pattern: Optional[str] = None


class VerifyEmailReq(BaseModel):
    email: str
    check_smtp: bool = False


class VerifyPhoneReq(BaseModel):
    phone: str


class OutreachReq(BaseModel):
    lead_id: int
    offer_type: str = "partnership"


class BatchStartReq(BaseModel):
    items: List[str]
    task_type: str = "inn"
    scrape_web: bool = True
    verify_emails: bool = True


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/stats")
def get_stats():
    return engine.get_dashboard_stats()


@app.get("/api/leads")
def get_leads(
    q: Optional[str] = Query(None, description="Поисковая строка"),
    region: Optional[str] = Query(None, description="Фильтр по региону"),
    role_level: Optional[str] = Query(None, description="Уровень ЛПР"),
    email_status: Optional[str] = Query(None, description="Статус Email"),
    lead_status: Optional[str] = Query(None, description="Статус CRM"),
    min_confidence: Optional[int] = Query(None, description="Минимальный скоринг доверия"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    leads = engine.get_all_leads(
        query=q,
        region=region,
        role_level=role_level,
        email_status=email_status,
        lead_status=lead_status,
        min_confidence=min_confidence
    )

    total_count = len(leads)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = leads[start_idx:end_idx]

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total_count + page_size - 1) // page_size),
        "items": paginated
    }


@app.get("/api/leads/{lead_id}")
def get_lead_detail(lead_id: int):
    lead = engine.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Контакт с ID {lead_id} не найден")
    return lead


@app.put("/api/leads/{lead_id}")
def update_lead(lead_id: int, req: LeadUpdateRequest):
    updates = req.model_dump(exclude_unset=True)
    # Маппинг ключей API к модели ORM
    field_map = {
        "dm_full_name": "full_name",
        "dm_title": "title",
        "dm_role_level": "role_level",
        "dm_email": "email",
        "email_status": "email_status",
        "dm_phone": "phone",
        "dm_phone_type": "phone_type",
        "dm_telegram": "telegram",
        "lead_status": "lead_status",
        "notes": "notes",
        "confidence_score": "confidence_score"
    }
    orm_updates = {}
    for k, v in updates.items():
        orm_key = field_map.get(k, k)
        orm_updates[orm_key] = v

    success = engine.update_lead(lead_id, orm_updates)
    if not success:
        raise HTTPException(status_code=404, detail="Не удалось обновить контакт")
    return {"status": "ok", "message": "Контакт успешно обновлен"}


@app.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: int):
    success = engine.delete_lead(lead_id)
    if not success:
        raise HTTPException(status_code=404, detail="Контакт не найден")
    return {"status": "ok", "message": "Контакт удален"}


@app.post("/api/enrich/real")
def enrich_real(inn: str = Query(..., description="ИНН, ОГРН или наименование организации")):
    clean_inn = inn.strip()
    comp = engine.fetch_and_enrich(clean_inn, scrape_web=True, verify_emails=True)
    if comp:
        return {
            "status": "ok",
            "company_name": comp.name,
            "inn": comp.inn,
            "domain": comp.domain or comp.website,
            "dms_count": len(comp.decision_makers),
            "dms": [
                {
                    "full_name": dm.full_name,
                    "title": dm.title,
                    "role_level": dm.role_level,
                    "email": dm.email,
                    "email_status": dm.email_status,
                    "phone": dm.phone,
                    "confidence": dm.confidence_score
                }
                for dm in comp.decision_makers
            ]
        }
    return {"status": "error", "message": f"Организация '{clean_inn}' не найдена в ЕГРЮЛ ФНС РФ и реестрах"}


@app.post("/api/enrich/domain")
def enrich_domain(domain: str = Query(..., description="Корпоративный домен компании")):
    comp = engine.enrich_by_domain(domain.strip(), verify_emails=True)
    if comp:
        return {
            "status": "ok",
            "company_name": comp.name,
            "inn": comp.inn,
            "domain": comp.domain,
            "dms_count": len(comp.decision_makers)
        }
    return {"status": "error", "message": f"Не удалось извлечь данные с сайта {domain}"}


@app.post("/api/batch/start")
def batch_start(req: BatchStartReq):
    if not req.items:
        raise HTTPException(status_code=400, detail="Список элементов для обработки пуст")
    task_id = batch_processor.start_batch_enrichment(
        items=req.items,
        task_type=req.task_type,
        scrape_web=req.scrape_web,
        verify_emails=req.verify_emails
    )
    return {"status": "ok", "task_id": task_id}


@app.post("/api/batch/upload")
async def batch_upload(file: UploadFile = File(...)):
    contents = await file.read()
    items = batch_processor.parse_file_to_items(contents, file.filename or "leads.csv")
    if not items:
        raise HTTPException(status_code=400, detail="В загруженном файле не найдено колонок с ИНН или названиями компаний")

    task_id = batch_processor.start_batch_enrichment(items=items, task_type="inn")
    return {
        "status": "ok",
        "task_id": task_id,
        "filename": file.filename,
        "items_count": len(items)
    }


@app.get("/api/batch/status/{task_id}")
def batch_status(task_id: str):
    info = batch_processor.get_task_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return info


@app.post("/api/tools/generate-email")
def tool_generate_email(req: PermutationReq):
    perms = generate_email_permutations(req.full_name, req.domain, known_pattern=req.known_pattern)
    return {"status": "ok", "permutations": perms}


@app.post("/api/tools/verify-email")
def tool_verify_email(req: VerifyEmailReq):
    res = verify_email_full(req.email, check_smtp=req.check_smtp)
    return {"status": "ok", "result": res}


@app.post("/api/tools/verify-phone")
def tool_verify_phone(req: VerifyPhoneReq):
    res = normalize_phone(req.phone)
    return {"status": "ok", "result": res}


@app.post("/api/tools/outreach-draft")
def tool_outreach_draft(req: OutreachReq):
    lead = engine.get_lead_by_id(req.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    draft = generate_outreach_email(lead, offer_type=req.offer_type)
    return {"status": "ok", "draft": draft}


@app.post("/api/leads/reverify")
def reverify_leads():
    cnt = engine.reverify_all_emails()
    return {"status": "ok", "reverified_count": cnt}


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@app.get("/api/export/csv")
def api_export_csv():
    leads = engine.get_all_leads()
    path = "/tmp/leads_export.csv"
    export_to_csv(leads, path)
    return FileResponse(path, filename="leads_b2b.csv", media_type="text/csv")


@app.get("/api/export/excel")
def api_export_excel():
    leads = engine.get_all_leads()
    path = "/tmp/leads_export.xlsx"
    export_to_excel(leads, path)
    return FileResponse(path, filename="leads_b2b.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/export/amocrm")
def api_export_amocrm():
    leads = engine.get_all_leads()
    path = "/tmp/leads_amocrm.csv"
    export_to_amocrm_csv(leads, path)
    return FileResponse(path, filename="leads_amocrm.csv", media_type="text/csv")


@app.get("/api/export/bitrix24")
def api_export_bitrix24():
    leads = engine.get_all_leads()
    path = "/tmp/leads_bitrix24.csv"
    export_to_bitrix24_csv(leads, path)
    return FileResponse(path, filename="leads_bitrix24.csv", media_type="text/csv")


@app.get("/api/export/json")
def api_export_json():
    leads = engine.get_all_leads()
    path = "/tmp/leads_export.json"
    export_to_json(leads, path)
    return FileResponse(path, filename="leads_b2b.json", media_type="application/json")


# ============================================================================
# HTML SPA DASHBOARD TEMPLATE
# ============================================================================

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B2B Lead Intelligence — База ЛПР предприятий России</title>
    <!-- Fonts & Icons -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

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
            padding: 14px 0;
        }

        .brand-icon {
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            color: #fff;
            width: 42px;
            height: 42px;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.35rem;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
        }

        .nav-tabs-custom {
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 24px;
        }
        .nav-tabs-custom .nav-link {
            border: none;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.95rem;
            padding: 12px 20px;
            border-bottom: 3px solid transparent;
            border-radius: 0;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .nav-tabs-custom .nav-link:hover {
            color: var(--primary);
        }
        .nav-tabs-custom .nav-link.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
            background: transparent;
        }

        .stat-card {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 20px;
            transition: all 0.2s ease;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        }
        .stat-number {
            font-size: 1.85rem;
            font-weight: 700;
            color: var(--text-main);
            line-height: 1.1;
        }

        .card-custom {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 20px -2px rgba(0,0,0,0.03);
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
            height: 50px;
            border-radius: 12px;
            border: 1.5px solid #cbd5e1;
            font-size: 0.95rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        .input-group-search input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
        }

        .filter-select {
            height: 42px;
            border-radius: 10px;
            border: 1px solid #cbd5e1;
            font-size: 0.88rem;
            font-weight: 500;
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
            font-size: 0.78rem;
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
        .badge-invalid { background: #fee2e2; color: #991b1b; }

        .btn-action {
            border-radius: 8px;
            font-weight: 500;
            font-size: 0.85rem;
            padding: 6px 12px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
            cursor: pointer;
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
            font-size: 0.85rem;
            color: #334155;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.15s;
        }
        .contact-pill:hover {
            background: #e2e8f0;
            color: #0f172a;
        }

        .avatar-circle {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: #e2e8f0;
            color: #475569;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
            flex-shrink: 0;
        }

        .dropzone-box {
            border: 2px dashed #cbd5e1;
            border-radius: 14px;
            padding: 40px 20px;
            text-align: center;
            background: #fafafa;
            cursor: pointer;
            transition: all 0.2s;
        }
        .dropzone-box:hover {
            border-color: var(--primary);
            background: #eff6ff;
        }

        .toast-copy {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
            background: #0f172a;
            color: #fff;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 0.88rem;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            display: none;
            animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
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
                        <div class="d-flex align-items-center gap-2">
                            <h5 class="mb-0 fw-bold">B2B Lead Enrichment Engine</h5>
                            <span class="badge bg-primary bg-opacity-10 text-primary">v2.1 Enterprise</span>
                        </div>
                        <small class="text-muted">Поиск, обогащение и валидация контактов ЛПР предприятий России</small>
                    </div>
                </div>
                <div class="d-flex gap-2">
                    <div class="dropdown">
                        <button class="btn btn-outline-secondary btn-action dropdown-toggle" type="button" data-bs-toggle="dropdown">
                            <i class="bi bi-download"></i> Экспорт базы
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end shadow-sm border-0 rounded-3">
                            <li><a class="dropdown-item py-2" href="/api/export/excel"><i class="bi bi-file-earmark-excel text-success me-2"></i> Экспорт Excel (.xlsx)</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/csv"><i class="bi bi-filetype-csv text-primary me-2"></i> Экспорт CSV (UTF-8-BOM)</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item py-2" href="/api/export/amocrm"><i class="bi bi-cloud-arrow-up text-warning me-2"></i> Формат для amoCRM</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/bitrix24"><i class="bi bi-boxes text-info me-2"></i> Формат для Битрикс24</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/json"><i class="bi bi-filetype-json text-secondary me-2"></i> Экспорт JSON</a></li>
                        </ul>
                    </div>
                    <a href="/docs" target="_blank" class="btn btn-outline-primary btn-action" title="OpenAPI Swagger документация">
                        <i class="bi bi-journal-code"></i> API Docs
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <div class="container-fluid px-lg-5 py-4">

        <!-- Вкладки приложения -->
        <ul class="nav nav-tabs nav-tabs-custom" id="mainTab" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="crm-tab" data-bs-toggle="tab" data-bs-target="#crmPane" type="button" role="tab">
                    <i class="bi bi-people-fill"></i> База контактов (CRM)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="analytics-tab" data-bs-toggle="tab" data-bs-target="#analyticsPane" type="button" role="tab" onclick="loadAnalytics()">
                    <i class="bi bi-bar-chart-line-fill"></i> Аналитика и KPI
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="search-tab" data-bs-toggle="tab" data-bs-target="#searchPane" type="button" role="tab">
                    <i class="bi bi-search"></i> Поиск и Обогащение
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="batch-tab" data-bs-toggle="tab" data-bs-target="#batchPane" type="button" role="tab">
                    <i class="bi bi-layers-fill"></i> Пакетная обработка (Batch)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tools-tab" data-bs-toggle="tab" data-bs-target="#toolsPane" type="button" role="tab">
                    <i class="bi bi-tools"></i> Инструменты валидации
                </button>
            </li>
        </ul>

        <!-- Содержимое вкладок -->
        <div class="tab-content" id="mainTabContent">

            <!-- Вкладка 1: CRM База контактов -->
            <div class="tab-pane fade show active" id="crmPane" role="tabpanel">

                <!-- Карточки быстрой статистики -->
                <div class="row g-3 mb-4">
                    <div class="col-xl-3 col-md-6">
                        <div class="stat-card d-flex align-items-center gap-3">
                            <div class="p-3 bg-primary bg-opacity-10 text-primary rounded-3 fs-3">
                                <i class="bi bi-building"></i>
                            </div>
                            <div>
                                <div class="stat-number" id="statCompanies">0</div>
                                <div class="text-muted small fw-medium">Предприятий в реестре</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-xl-3 col-md-6">
                        <div class="stat-card d-flex align-items-center gap-3">
                            <div class="p-3 bg-opacity-10 rounded-3 fs-3" style="background:#ede9fe; color:#6366f1;">
                                <i class="bi bi-person-lines-fill"></i>
                            </div>
                            <div>
                                <div class="stat-number" id="statDMs">0</div>
                                <div class="text-muted small fw-medium">Контактов ЛПР</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-xl-3 col-md-6">
                        <div class="stat-card d-flex align-items-center gap-3">
                            <div class="p-3 bg-success bg-opacity-10 text-success rounded-3 fs-3">
                                <i class="bi bi-patch-check-fill"></i>
                            </div>
                            <div>
                                <div class="stat-number" id="statEmails">0</div>
                                <div class="text-muted small fw-medium">Email с проверкой MX</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-xl-3 col-md-6">
                        <div class="stat-card d-flex align-items-center gap-3">
                            <div class="p-3 bg-warning bg-opacity-10 text-warning rounded-3 fs-3">
                                <i class="bi bi-telephone-fill"></i>
                            </div>
                            <div>
                                <div class="stat-number" id="statPhones">0</div>
                                <div class="text-muted small fw-medium">Прямых телефонов</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Блок поиска и фильтрации -->
                <div class="card-custom mb-4">
                    <div class="row g-3 align-items-end">
                        <div class="col-lg-4">
                            <label class="form-label fw-bold text-dark small text-uppercase mb-1">
                                <i class="bi bi-search me-1"></i> Поиск по базе
                            </label>
                            <div class="input-group-search">
                                <i class="bi bi-search search-icon"></i>
                                <input type="text" id="filterQuery" class="form-control" placeholder="Поиск по ФИО, компании, ИНН, email, телефону..." oninput="applyFilters()">
                            </div>
                        </div>
                        <div class="col-lg-2 col-md-4">
                            <label class="form-label fw-bold text-dark small text-uppercase mb-1">Регион</label>
                            <select id="filterRegion" class="form-select filter-select" onchange="applyFilters()">
                                <option value="">Все регионы</option>
                                <option value="Москва">г. Москва</option>
                                <option value="Санкт-Петербург">г. Санкт-Петербург</option>
                                <option value="Московская">Московская обл.</option>
                                <option value="Вологодская">Вологодская обл.</option>
                                <option value="Краснодарский">Краснодарский край</option>
                            </select>
                        </div>
                        <div class="col-lg-2 col-md-4">
                            <label class="form-label fw-bold text-dark small text-uppercase mb-1">Уровень ЛПР</label>
                            <select id="filterRole" class="form-select filter-select" onchange="applyFilters()">
                                <option value="">Все роли</option>
                                <option value="C-Level">C-Level (Гендиректор, Президент)</option>
                                <option value="Director">Директор (Коммерч., Технич.)</option>
                                <option value="Head">Руководитель отдела / Главный</option>
                                <option value="Founder">Основатель / Владелец</option>
                            </select>
                        </div>
                        <div class="col-lg-2 col-md-4">
                            <label class="form-label fw-bold text-dark small text-uppercase mb-1">Статус Email</label>
                            <select id="filterEmailStatus" class="form-select filter-select" onchange="applyFilters()">
                                <option value="">Любой статус</option>
                                <option value="valid_mx">Активный MX</option>
                                <option value="verified">Verified (проверен)</option>
                                <option value="generated">Паттерн</option>
                            </select>
                        </div>
                        <div class="col-lg-2">
                            <div class="d-flex gap-2">
                                <button class="btn btn-outline-secondary w-100 btn-action" style="height: 42px;" onclick="resetFilters()">
                                    <i class="bi bi-arrow-counterclockwise"></i> Сбросить
                                </button>
                                <button class="btn btn-outline-primary btn-action" style="height: 42px;" onclick="reverifyAll()" title="Перепроверить все MX DNS">
                                    <i class="bi bi-shield-check"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Таблица лидов -->
                <div class="card border-0 shadow-sm" style="border-radius: 16px; overflow: hidden;">
                    <div class="table-responsive">
                        <table class="table table-custom mb-0">
                            <thead>
                                <tr>
                                    <th style="width: 26%;">Организация / Реквизиты</th>
                                    <th style="width: 24%;">ЛПР (Лицо, принимающее решения)</th>
                                    <th style="width: 22%;">Корпоративный Email</th>
                                    <th style="width: 16%;">Телефон</th>
                                    <th style="width: 12%; text-align: right;">Действия</th>
                                </tr>
                            </thead>
                            <tbody id="leadsTableBody">
                                <tr>
                                    <td colspan="5" class="text-center py-5 text-muted">
                                        <div class="spinner-border text-primary spinner-border-sm me-2"></div>
                                        Загрузка контактов...
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>

            <!-- Вкладка 2: Аналитика (Dashboard) -->
            <div class="tab-pane fade" id="analyticsPane" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h6 class="fw-bold mb-3"><i class="bi bi-pie-chart-fill text-primary me-2"></i> Распределение по уровням ЛПР</h6>
                            <div style="height: 280px; position: relative;">
                                <canvas id="chartRoles"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h6 class="fw-bold mb-3"><i class="bi bi-bar-chart-fill text-success me-2"></i> Топ регионов предприятий</h6>
                            <div style="height: 280px; position: relative;">
                                <canvas id="chartRegions"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-12">
                        <div class="card-custom">
                            <h6 class="fw-bold mb-3"><i class="bi bi-diagram-3-fill text-warning me-2"></i> Отраслевая структура базы (ОКВЭД)</h6>
                            <div style="height: 260px; position: relative;">
                                <canvas id="chartIndustries"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Вкладка 3: Поиск и Обогащение -->
            <div class="tab-pane fade" id="searchPane" role="tabpanel">
                <div class="row justify-content-center">
                    <div class="col-lg-8">
                        <div class="card-custom mb-4">
                            <h5 class="fw-bold mb-2"><i class="bi bi-cloud-arrow-down-fill text-primary me-2"></i> Обогащение компании из ЕГРЮЛ ФНС РФ</h5>
                            <p class="text-muted small">Введите ИНН (10 или 12 цифр), ОГРН или наименование предприятия. Система найдет карточку в официальном реестре, определит первого лица, найдет сайт, соберет контакты и сгенерирует корпоративные адреса.</p>

                            <div class="input-group-search d-flex gap-2 mb-3">
                                <i class="bi bi-search search-icon"></i>
                                <input type="text" id="enrichQueryInput" class="form-control" placeholder="Например: 7707083893, 7736207543, Лаборатория Касперского, Балтика, Озон...">
                                <button class="btn btn-primary px-4 fw-semibold d-flex align-items-center gap-2" id="btnEnrich" onclick="startSingleEnrichment()">
                                    <i class="bi bi-search"></i> <span>Найти</span>
                                </button>
                            </div>

                            <!-- Индикатор прогресса -->
                            <div id="enrichProgressArea" style="display: none;">
                                <div class="progress mb-2" style="height: 8px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" id="enrichBar" style="width: 100%;"></div>
                                </div>
                                <div id="enrichStatusText" class="text-primary small fw-medium"></div>
                            </div>
                        </div>

                        <!-- Карточка результата -->
                        <div id="enrichResultCard" class="card-custom" style="display: none;">
                            <h6 class="fw-bold text-success mb-3"><i class="bi bi-check-circle-fill me-2"></i> Результат обогащения</h6>
                            <div id="enrichResultContent"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Вкладка 4: Пакетная обработка (Batch) -->
            <div class="tab-pane fade" id="batchPane" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-2"><i class="bi bi-file-earmark-arrow-up-fill text-primary me-2"></i> Загрузка файла реестра</h5>
                            <p class="text-muted small">Загрузите файл Excel (.xlsx) или CSV со списком ИНН организаций. Система автоматически распознает колонку с ИНН и запустит конвейер обогащения в фоновом режиме.</p>

                            <div class="dropzone-box" onclick="document.getElementById('fileUploadInput').click()">
                                <i class="bi bi-cloud-arrow-up fs-1 text-primary mb-2 d-block"></i>
                                <div class="fw-semibold">Нажмите для выбора файла или перетащите сюда</div>
                                <div class="text-muted small mt-1">Поддерживаются .xlsx, .xls, .csv</div>
                                <input type="file" id="fileUploadInput" accept=".xlsx,.xls,.csv" style="display: none;" onchange="uploadBatchFile(this.files[0])">
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-2"><i class="bi bi-card-text text-warning me-2"></i> Ввод списка ИНН вручную</h5>
                            <p class="text-muted small">Вставьте список ИНН или сайтов (по одному на строку):</p>
                            <textarea id="batchTextarea" class="form-control mb-3" rows="5" placeholder="7707083893&#10;7736207543&#10;7802849641&#10;7743003908&#10;3528000597"></textarea>
                            <button class="btn btn-primary btn-action" onclick="startBatchFromText()">
                                <i class="bi bi-play-fill"></i> Запустить пакетное обогащение
                            </button>
                        </div>
                    </div>

                    <!-- Монитор активной задачи -->
                    <div class="col-12" id="batchMonitorCard" style="display: none;">
                        <div class="card-custom">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold mb-0"><i class="bi bi-cpu-fill text-primary me-2"></i> Статус фонового конвейера</h6>
                                <span class="badge bg-primary" id="batchBadgeStatus">В процессе</span>
                            </div>
                            <div class="progress mb-2" style="height: 12px; border-radius: 6px;">
                                <div class="progress-bar progress-bar-striped progress-bar-animated bg-success" id="batchProgressBar" style="width: 0%;"></div>
                            </div>
                            <div class="d-flex justify-content-between small text-muted">
                                <span id="batchProgressDetails">Обработано: 0 из 0</span>
                                <span id="batchPercent">0%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Вкладка 5: Инструменты валидации -->
            <div class="tab-pane fade" id="toolsPane" role="tabpanel">
                <div class="row g-4">
                    <!-- Генератор email -->
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-3"><i class="bi bi-envelope-at-fill text-primary me-2"></i> Генератор корпоративных email</h5>
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label small fw-semibold">ФИО сотрудника</label>
                                    <input type="text" id="toolNameInput" class="form-control" placeholder="Иванов Иван Иванович" value="Иванов Иван Иванович">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small fw-semibold">Корпоративный домен</label>
                                    <input type="text" id="toolDomainInput" class="form-control" placeholder="company.ru" value="yandex.ru">
                                </div>
                            </div>
                            <button class="btn btn-primary btn-action mb-3" onclick="runEmailPermutations()">
                                <i class="bi bi-lightning-charge"></i> Сгенерировать варианты
                            </button>
                            <div id="permutationsResult"></div>
                        </div>
                    </div>

                    <!-- Валидатор контактов -->
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-3"><i class="bi bi-shield-check text-success me-2"></i> Валидатор телефона и Email</h5>
                            
                            <div class="mb-3">
                                <label class="form-label small fw-semibold">Проверка Email (DNS MX + Синтаксис)</label>
                                <div class="input-group">
                                    <input type="email" id="toolEmailInput" class="form-control" placeholder="pr@yandex-team.ru" value="pr@yandex-team.ru">
                                    <button class="btn btn-outline-primary" onclick="runEmailValidation()">Проверить</button>
                                </div>
                                <div id="emailVerifyResult" class="mt-2 small"></div>
                            </div>

                            <hr>

                            <div class="mb-3">
                                <label class="form-label small fw-semibold">Проверка телефона (E.164 + Регион + Оператор)</label>
                                <div class="input-group">
                                    <input type="text" id="toolPhoneInput" class="form-control" placeholder="+7 916 123 45 67" value="+7 (495) 739-70-00">
                                    <button class="btn btn-outline-success" onclick="runPhoneValidation()">Проверить</button>
                                </div>
                                <div id="phoneVerifyResult" class="mt-2 small"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </div>

    </div>

    <!-- Модальное окно деталей лида и генератора холодного письма -->
    <div class="modal fade" id="leadModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content border-0 shadow-lg" style="border-radius: 16px;">
                <div class="modal-header border-bottom-0 pb-0">
                    <h5 class="modal-title fw-bold" id="modalLeadTitle">Карточка ЛПР</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="row g-3 mb-4">
                        <div class="col-md-6">
                            <label class="form-label small text-muted mb-1">ФИО руководителя</label>
                            <input type="text" id="modalFio" class="form-control fw-bold">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small text-muted mb-1">Должность</label>
                            <input type="text" id="modalPost" class="form-control">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small text-muted mb-1">Email</label>
                            <input type="text" id="modalEmail" class="form-control">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small text-muted mb-1">Телефон</label>
                            <input type="text" id="modalPhone" class="form-control">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small text-muted mb-1">Статус в CRM</label>
                            <select id="modalStatus" class="form-select">
                                <option value="NEW">Новый контакт (NEW)</option>
                                <option value="CONTACTED">Связались (CONTACTED)</option>
                                <option value="QUALIFIED">Квалифицирован (QUALIFIED)</option>
                                <option value="CONVERTED">Сделка (CONVERTED)</option>
                                <option value="REJECTED">Отказ (REJECTED)</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small text-muted mb-1">Заметки / История контакта</label>
                            <input type="text" id="modalNotes" class="form-control" placeholder="Комментарии менеджера...">
                        </div>
                    </div>

                    <!-- Генератор холодного письма -->
                    <div class="p-3 bg-light rounded-3 mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="fw-bold text-dark small text-uppercase">
                                <i class="bi bi-envelope-paper-heart-fill text-primary me-1"></i>
                                Генератор B2B холодного письма
                            </span>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-secondary" onclick="generateOutreach('partnership')">Партнерство</button>
                                <button class="btn btn-outline-secondary" onclick="generateOutreach('sales')">Продажи</button>
                                <button class="btn btn-outline-secondary" onclick="generateOutreach('demo')">Демо-доступ</button>
                            </div>
                        </div>
                        <div id="outreachSubject" class="fw-bold text-primary small mb-1"></div>
                        <textarea id="outreachBody" class="form-control form-control-sm font-monospace" rows="6" readonly></textarea>
                        <button class="btn btn-sm btn-outline-primary mt-2" onclick="copyOutreachText()">
                            <i class="bi bi-clipboard"></i> Скопировать текст письма
                        </button>
                    </div>
                </div>
                <div class="modal-footer border-top-0 pt-0">
                    <button type="button" class="btn btn-outline-danger btn-sm" onclick="deleteCurrentLead()">Удалить контакт</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Закрыть</button>
                    <button type="button" class="btn btn-primary btn-sm px-3" onclick="saveLeadChanges()">Сохранить изменения</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Уведомление о копировании -->
    <div id="copyToast" class="toast-copy">
        <i class="bi bi-clipboard-check text-success me-2"></i> Скопировано в буфер обмена
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        let allLeads = [];
        let activeLeadId = null;
        let chartRolesInstance = null;
        let chartRegionsInstance = null;
        let chartIndustriesInstance = null;

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Скопировано: ' + text);
            });
        }

        function showToast(msg) {
            const t = document.getElementById('copyToast');
            t.innerHTML = `<i class="bi bi-clipboard-check text-success me-2"></i> ${msg}`;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 2200);
        }

        function getInitials(name) {
            if (!name) return 'ЛПР';
            const parts = name.trim().split(/\s+/);
            if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
            return parts[0].slice(0, 2).toUpperCase();
        }

        async function loadLeads() {
            try {
                const res = await fetch('/api/leads?page_size=300');
                const data = await res.json();
                allLeads = data.items || [];
                updateStats();
                renderTable(allLeads);
            } catch (e) {
                console.error("Ошибка загрузки данных:", e);
            }
        }

        async function updateStats() {
            try {
                const res = await fetch('/api/stats');
                const s = await res.json();
                document.getElementById('statCompanies').innerText = s.total_companies;
                document.getElementById('statDMs').innerText = s.total_dms;
                document.getElementById('statEmails').innerText = s.valid_emails_count;
                document.getElementById('statPhones').innerText = s.mobile_phones_count + s.office_phones_count;
            } catch (e) {
                console.error(e);
            }
        }

        function renderTable(leads) {
            const tbody = document.getElementById('leadsTableBody');
            tbody.innerHTML = '';

            if (leads.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-5 text-muted">
                            <i class="bi bi-inbox fs-1 d-block mb-2 text-secondary"></i>
                            Контакты не найдены. Воспользуйтесь вкладкой «Поиск и Обогащение» для добавления.
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
                } else if (l.email_status === 'disposable' || l.email_status === 'no_mx') {
                    badgeClass = 'badge-invalid';
                    badgeIcon = 'bi-x-circle';
                    statusText = 'Не валиден';
                }

                const emailHtml = l.dm_email ? `
                    <div class="d-flex flex-column gap-1">
                        <div class="contact-pill text-truncate" style="max-width: 230px;" title="Кликните для копирования" onclick="copyToClipboard('${l.dm_email}')">
                            <i class="bi bi-envelope text-primary"></i> ${l.dm_email}
                        </div>
                        <div>
                            <span class="badge-status ${badgeClass}">
                                <i class="bi ${badgeIcon}"></i> ${statusText}
                            </span>
                        </div>
                    </div>
                ` : '<span class="text-muted small">—</span>';

                const phoneHtml = l.dm_phone ? `
                    <div class="d-flex flex-column gap-1">
                        <div class="contact-pill text-nowrap" title="Кликните для копирования" onclick="copyToClipboard('${l.dm_phone}')">
                            <i class="bi bi-telephone text-success"></i> ${l.dm_phone}
                        </div>
                        <small class="text-muted" style="font-size: 0.72rem;">${l.dm_phone_type === 'mobile' ? 'Прямой мобильный' : (l.dm_phone_type === '8800' ? 'Горячая линия' : 'Приемная / Офис')}</small>
                    </div>
                ` : '<span class="text-muted small">—</span>';

                tbody.innerHTML += `
                    <tr>
                        <td>
                            <div class="fw-bold text-dark mb-1">${l.company_name}</div>
                            <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                                <span class="badge bg-light text-dark border">ИНН: ${l.inn}</span>
                                ${l.region ? `<span class="text-muted small"><i class="bi bi-geo-alt"></i> ${l.region}</span>` : ''}
                            </div>
                            ${l.okved_name ? `<div class="text-muted small text-truncate" style="max-width: 260px;" title="${l.okved_name}">${l.okved_name}</div>` : ''}
                        </td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <div class="avatar-circle">${getInitials(l.dm_full_name)}</div>
                                <div>
                                    <div class="fw-semibold text-dark">${l.dm_full_name}</div>
                                    <div class="text-muted small">${l.dm_title || 'Руководитель'}</div>
                                    <span class="badge bg-secondary bg-opacity-10 text-secondary" style="font-size: 0.7rem;">${l.dm_role_level || 'C-Level'}</span>
                                </div>
                            </div>
                        </td>
                        <td>${emailHtml}</td>
                        <td>${phoneHtml}</td>
                        <td style="text-align: right;">
                            <div class="d-flex gap-1 justify-content-end">
                                <button class="btn btn-sm btn-outline-primary btn-action" onclick="openLeadModal(${l.id})" title="Карточка ЛПР и холодное письмо">
                                    <i class="bi bi-pencil-square"></i>
                                </button>
                                ${l.website ? `<a href="https://${l.website}" target="_blank" class="btn btn-sm btn-outline-secondary btn-action" title="Сайт"><i class="bi bi-globe"></i></a>` : ''}
                            </div>
                        </td>
                    </tr>
                `;
            });
        }

        function applyFilters() {
            const q = document.getElementById('filterQuery').value.toLowerCase().trim();
            const region = document.getElementById('filterRegion').value.toLowerCase();
            const role = document.getElementById('filterRole').value;
            const emailStatus = document.getElementById('filterEmailStatus').value;

            const filtered = allLeads.filter(l => {
                if (q) {
                    const matchQ = (
                        (l.company_name && l.company_name.toLowerCase().includes(q)) ||
                        (l.inn && l.inn.includes(q)) ||
                        (l.dm_full_name && l.dm_full_name.toLowerCase().includes(q)) ||
                        (l.dm_title && l.dm_title.toLowerCase().includes(q)) ||
                        (l.dm_email && l.dm_email.toLowerCase().includes(q)) ||
                        (l.dm_phone && l.dm_phone.includes(q))
                    );
                    if (!matchQ) return false;
                }
                if (region && (!l.region || !l.region.toLowerCase().includes(region))) return false;
                if (role && l.dm_role_level !== role) return false;
                if (emailStatus && l.email_status !== emailStatus) return false;
                return true;
            });

            renderTable(filtered);
        }

        function resetFilters() {
            document.getElementById('filterQuery').value = '';
            document.getElementById('filterRegion').value = '';
            document.getElementById('filterRole').value = '';
            document.getElementById('filterEmailStatus').value = '';
            renderTable(allLeads);
        }

        async function openLeadModal(leadId) {
            activeLeadId = leadId;
            const res = await fetch(`/api/leads/${leadId}`);
            const lead = await res.json();

            document.getElementById('modalLeadTitle').innerText = `${lead.company_name} — ${lead.dm_full_name}`;
            document.getElementById('modalFio').value = lead.dm_full_name || '';
            document.getElementById('modalPost').value = lead.dm_title || '';
            document.getElementById('modalEmail').value = lead.dm_email || '';
            document.getElementById('modalPhone').value = lead.dm_phone || '';
            document.getElementById('modalStatus').value = lead.lead_status || 'NEW';
            document.getElementById('modalNotes').value = lead.notes || '';

            // Генерируем драфт письма по умолчанию
            await generateOutreach('partnership');

            const modal = new bootstrap.Modal(document.getElementById('leadModal'));
            modal.show();
        }

        async function generateOutreach(offerType) {
            if (!activeLeadId) return;
            try {
                const res = await fetch('/api/tools/outreach-draft', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ lead_id: activeLeadId, offer_type: offerType })
                });
                const data = await res.json();
                if (data.draft) {
                    document.getElementById('outreachSubject').innerText = `Тема: ${data.draft.subject}`;
                    document.getElementById('outreachBody').value = data.draft.body;
                }
            } catch (e) {
                console.error(e);
            }
        }

        function copyOutreachText() {
            const body = document.getElementById('outreachBody').value;
            copyToClipboard(body);
        }

        async function saveLeadChanges() {
            if (!activeLeadId) return;
            const payload = {
                dm_full_name: document.getElementById('modalFio').value,
                dm_title: document.getElementById('modalPost').value,
                dm_email: document.getElementById('modalEmail').value,
                dm_phone: document.getElementById('modalPhone').value,
                lead_status: document.getElementById('modalStatus').value,
                notes: document.getElementById('modalNotes').value
            };

            await fetch(`/api/leads/${activeLeadId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            bootstrap.Modal.getInstance(document.getElementById('leadModal')).hide();
            showToast('Изменения сохранены');
            await loadLeads();
        }

        async function deleteCurrentLead() {
            if (!activeLeadId || !confirm("Удалить этот контакт из базы?")) return;
            await fetch(`/api/leads/${activeLeadId}`, { method: 'DELETE' });
            bootstrap.Modal.getInstance(document.getElementById('leadModal')).hide();
            showToast('Контакт удален');
            await loadLeads();
        }

        async function reverifyAll() {
            showToast('Запущена повторная проверка MX DNS...');
            const res = await fetch('/api/leads/reverify', { method: 'POST' });
            const d = await res.json();
            showToast(`Перепроверено записей: ${d.reverified_count}`);
            await loadLeads();
        }

        // ====================================================================
        // ОБОГАЩЕНИЕ ОДНОЙ ОРГАНИЗАЦИИ
        // ====================================================================
        async function startSingleEnrichment() {
            const input = document.getElementById('enrichQueryInput');
            const q = input.value.trim();
            if (!q) { input.focus(); return; }

            const btn = document.getElementById('btnEnrich');
            const pArea = document.getElementById('enrichProgressArea');
            const pText = document.getElementById('enrichStatusText');
            const resCard = document.getElementById('enrichResultCard');
            const resContent = document.getElementById('enrichResultContent');

            btn.disabled = true;
            pArea.style.display = 'block';
            resCard.style.display = 'none';
            pText.innerText = 'Запрос в ЕГРЮЛ ФНС РФ, краулинг сайта и генерация контактов...';

            try {
                const res = await fetch(`/api/enrich/real?inn=${encodeURIComponent(q)}`, { method: 'POST' });
                const data = await res.json();

                if (data.status === 'ok') {
                    resCard.style.display = 'block';
                    resContent.innerHTML = `
                        <div class="fw-bold fs-5 text-dark mb-1">${data.company_name}</div>
                        <div class="text-muted small mb-3">ИНН: <b>${data.inn}</b> | Домен: <b>${data.domain || 'Не указан'}</b> | Найдено ЛПР: <b>${data.dms_count}</b></div>
                        <div class="list-group">
                            ${data.dms.map(dm => `
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div>
                                        <div class="fw-semibold">${dm.full_name}</div>
                                        <small class="text-muted">${dm.title} (${dm.role_level})</small>
                                    </div>
                                    <div class="text-end">
                                        <div class="fw-bold text-primary font-monospace">${dm.email || '—'}</div>
                                        <small class="badge bg-light text-dark border">${dm.email_status}</small>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                    input.value = '';
                    await loadLeads();
                } else {
                    resCard.style.display = 'block';
                    resContent.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i> ${data.message}</div>`;
                }
            } catch (e) {
                resCard.style.display = 'block';
                resContent.innerHTML = `<div class="text-danger"><i class="bi bi-x-circle-fill me-2"></i> Ошибка сетевого запроса к серверу</div>`;
            } finally {
                btn.disabled = false;
                pArea.style.display = 'none';
            }
        }

        // ====================================================================
        // ПАКЕТНАЯ ОБРАБОТКА (BATCH)
        // ====================================================================
        async function uploadBatchFile(file) {
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);

            showToast(`Загрузка файла ${file.name}...`);
            try {
                const res = await fetch('/api/batch/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.task_id) {
                    trackBatchTask(data.task_id);
                } else {
                    alert(data.detail || 'Ошибка загрузки');
                }
            } catch (e) {
                alert('Ошибка загрузки файла');
            }
        }

        async function startBatchFromText() {
            const text = document.getElementById('batchTextarea').value;
            const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            if (lines.length === 0) {
                alert('Введите хотя бы один ИНН или домен');
                return;
            }

            const res = await fetch('/api/batch/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ items: lines, task_type: 'inn' })
            });
            const data = await res.json();
            if (data.task_id) {
                trackBatchTask(data.task_id);
            }
        }

        function trackBatchTask(taskId) {
            const monitor = document.getElementById('batchMonitorCard');
            const pBar = document.getElementById('batchProgressBar');
            const pDetails = document.getElementById('batchProgressDetails');
            const pPercent = document.getElementById('batchPercent');
            const badge = document.getElementById('batchBadgeStatus');

            monitor.style.display = 'block';
            badge.innerText = 'В процессе';
            badge.className = 'badge bg-primary';

            const interval = setInterval(async () => {
                const res = await fetch(`/api/batch/status/${taskId}`);
                const status = await res.json();

                pBar.style.width = `${status.progress_percent}%`;
                pPercent.innerText = `${status.progress_percent}%`;
                pDetails.innerText = `Обработано: ${status.processed_items} из ${status.total_items} (Успешно: ${status.success_items}, Ошибок: ${status.failed_items})`;

                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(interval);
                    badge.innerText = status.status === 'completed' ? 'Завершено' : 'Ошибка';
                    badge.className = status.status === 'completed' ? 'badge bg-success' : 'badge bg-danger';
                    await loadLeads();
                }
            }, 1200);
        }

        // ====================================================================
        // ИНСТРУМЕНТЫ ВАЛИДАЦИИ
        // ====================================================================
        async function runEmailPermutations() {
            const name = document.getElementById('toolNameInput').value;
            const domain = document.getElementById('toolDomainInput').value;
            const resDiv = document.getElementById('permutationsResult');

            resDiv.innerHTML = '<div class="spinner-border spinner-border-sm text-primary"></div> Генерация...';
            const res = await fetch('/api/tools/generate-email', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ full_name: name, domain: domain })
            });
            const d = await res.json();

            resDiv.innerHTML = `
                <div class="table-responsive" style="max-height: 280px; overflow-y: auto;">
                    <table class="table table-sm table-hover small mb-0">
                        <thead>
                            <tr><th>Email</th><th>Паттерн</th><th>Вероятность</th></tr>
                        </thead>
                        <tbody>
                            ${d.permutations.map(p => `
                                <tr>
                                    <td><a href="javascript:void(0)" onclick="copyToClipboard('${p.email}')" class="font-monospace">${p.email}</a></td>
                                    <td><code>${p.pattern}</code></td>
                                    <td><span class="badge bg-success bg-opacity-10 text-success">${p.confidence}%</span></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        async function runEmailValidation() {
            const em = document.getElementById('toolEmailInput').value;
            const div = document.getElementById('emailVerifyResult');
            div.innerHTML = '<div class="spinner-border spinner-border-sm text-primary"></div> Проверка...';

            const res = await fetch('/api/tools/verify-email', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email: em, check_smtp: false })
            });
            const d = await res.json();
            const r = d.result;

            div.innerHTML = `
                <div class="alert ${r.is_valid ? 'alert-success' : 'alert-danger'} py-2 mb-0">
                    <div><b>Статус:</b> ${r.status} (${r.reason})</div>
                    <div><b>Корпоративный:</b> ${r.is_corporate ? 'Да' : 'Нет'} | <b>MX сервер:</b> ${r.mx_host || '—'}</div>
                </div>
            `;
        }

        async function runPhoneValidation() {
            const ph = document.getElementById('toolPhoneInput').value;
            const div = document.getElementById('phoneVerifyResult');
            div.innerHTML = '<div class="spinner-border spinner-border-sm text-success"></div> Валидация...';

            const res = await fetch('/api/tools/verify-phone', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ phone: ph })
            });
            const d = await res.json();
            const r = d.result;

            if (r.valid) {
                div.innerHTML = `
                    <div class="alert alert-success py-2 mb-0">
                        <div><b>E.164:</b> <code>${r.formatted}</code> | <b>Национальный:</b> <code>${r.national}</code></div>
                        <div><b>Тип:</b> ${r.type} | <b>Регион:</b> ${r.region || 'РФ'} | <b>Оператор:</b> ${r.carrier || 'Определен'}</div>
                    </div>
                `;
            } else {
                div.innerHTML = `<div class="alert alert-danger py-2 mb-0">Некорректный номер телефона</div>`;
            }
        }

        // ====================================================================
        // АНАЛИТИКА И ГРАФИКИ (CHART.JS)
        // ====================================================================
        async function loadAnalytics() {
            const res = await fetch('/api/stats');
            const stats = await res.json();

            // 1. Roles Chart
            const rolesLabels = Object.keys(stats.roles_breakdown);
            const rolesData = Object.values(stats.roles_breakdown);

            if (chartRolesInstance) chartRolesInstance.destroy();
            const ctxRoles = document.getElementById('chartRoles').getContext('2d');
            chartRolesInstance = new Chart(ctxRoles, {
                type: 'doughnut',
                data: {
                    labels: rolesLabels,
                    datasets: [{
                        data: rolesData,
                        backgroundColor: ['#2563eb', '#6366f1', '#10b981', '#f59e0b', '#ec4899']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 2. Regions Chart
            const regLabels = stats.top_regions.map(r => r.region);
            const regData = stats.top_regions.map(r => r.count);

            if (chartRegionsInstance) chartRegionsInstance.destroy();
            const ctxRegions = document.getElementById('chartRegions').getContext('2d');
            chartRegionsInstance = new Chart(ctxRegions, {
                type: 'bar',
                data: {
                    labels: regLabels,
                    datasets: [{
                        label: 'Предприятий',
                        data: regData,
                        backgroundColor: '#3b82f6'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 3. Industries Chart
            const indLabels = stats.top_industries.map(i => i.industry);
            const indData = stats.top_industries.map(i => i.count);

            if (chartIndustriesInstance) chartIndustriesInstance.destroy();
            const ctxInd = document.getElementById('chartIndustries').getContext('2d');
            chartIndustriesInstance = new Chart(ctxInd, {
                type: 'bar',
                data: {
                    labels: indLabels,
                    datasets: [{
                        label: 'Компаний по ОКВЭД',
                        data: indData,
                        backgroundColor: '#10b981'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y'
                }
            });
        }

        // Запуск при загрузке страницы
        loadLeads();
    </script>
</body>
</html>
"""


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_TEMPLATE, status_code=200)
