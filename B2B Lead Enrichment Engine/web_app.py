import os
import tempfile
import io
import time
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Request, Query, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.engine import EnrichmentEngine
from core.email_generator import generate_email_permutations
from core.validator import verify_email_full, normalize_phone
from core.deliverability import analyze_domain_deliverability
from core.exporter import (
    export_to_csv, export_to_excel, export_to_amocrm_csv,
    export_to_bitrix24_csv, export_to_hubspot_csv, export_to_vcard,
    export_to_json, generate_outreach_email, generate_cold_calling_script
)
from core.batch_processor import BatchProcessor
from core.config import settings

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = EnrichmentEngine()
batch_processor = BatchProcessor(engine)


# Middleware: тайминг выполнения запросов и request ID
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time-Sec"] = f"{process_time:.4f}"
    return response


# Pydantic Schemas for Requests
class LeadUpdateRequest(BaseModel):
    dm_full_name: Optional[str] = None
    dm_title: Optional[str] = None
    dm_role_level: Optional[str] = None
    dm_email: Optional[str] = None
    email_status: Optional[str] = None
    dm_phone: Optional[str] = None
    dm_phone_type: Optional[str] = None
    phone_carrier: Optional[str] = None
    phone_timezone: Optional[str] = None
    dm_telegram: Optional[str] = None
    dm_vk: Optional[str] = None
    dm_tenchat: Optional[str] = None
    lead_status: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: Optional[int] = None


class ManualLeadCreateRequest(BaseModel):
    inn: str
    company_name: str
    website: Optional[str] = None
    region: Optional[str] = None
    okved_name: Optional[str] = None
    dm_full_name: str
    dm_title: Optional[str] = "Генеральный директор"
    dm_role_level: Optional[str] = "C-Level"
    dm_email: Optional[str] = None
    dm_phone: Optional[str] = None
    notes: Optional[str] = None


class BulkStatusRequest(BaseModel):
    lead_ids: List[int]
    status: str


class BulkDeleteRequest(BaseModel):
    lead_ids: List[int]


class PermutationReq(BaseModel):
    full_name: str
    domain: str
    known_pattern: Optional[str] = None


class VerifyEmailReq(BaseModel):
    email: str
    check_smtp: bool = False


class VerifyPhoneReq(BaseModel):
    phone: str
    default_region: str = "RU"


class DeliverabilityReq(BaseModel):
    domain: str


class OutreachReq(BaseModel):
    lead_id: int
    offer_type: str = "partnership"
    sender_name: Optional[str] = "[Ваше Имя]"
    sender_company: Optional[str] = "[Ваша Компания]"
    sender_title: Optional[str] = "[Ваша Должность]"
    sender_phone: Optional[str] = "[Ваш Телефон]"


class ColdCallScriptReq(BaseModel):
    lead_id: int


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
        "database": "connected",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    """Prometheus-совместимый эндпоинт метрик системы."""
    stats = engine.get_dashboard_stats()
    metrics = [
        f"# HELP b2b_total_companies Total companies stored in database",
        f"# TYPE b2b_total_companies gauge",
        f"b2b_total_companies {stats['total_companies']}",
        f"# HELP b2b_total_leads Total decision makers stored in database",
        f"# TYPE b2b_total_leads gauge",
        f"b2b_total_leads {stats['total_dms']}",
        f"# HELP b2b_valid_emails Total verified MX emails",
        f"# TYPE b2b_valid_emails gauge",
        f"b2b_valid_emails {stats['valid_emails_count']}",
        f"# HELP b2b_direct_mobiles Total mobile numbers",
        f"# TYPE b2b_direct_mobiles gauge",
        f"b2b_direct_mobiles {stats['mobile_phones_count']}"
    ]
    return "\n".join(metrics) + "\n"


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


@app.post("/api/leads/manual")
def create_manual_lead(req: ManualLeadCreateRequest):
    """Ручное создание организации и контакта ЛПР с автоматическим скорингом."""
    from core.models import Company, DecisionMaker
    
    dm = DecisionMaker(
        company_inn=req.inn.strip(),
        company_name=req.company_name.strip(),
        full_name=req.dm_full_name.strip(),
        title=req.dm_title or "Генеральный директор",
        role_level=req.dm_role_level or "C-Level",
        email=req.dm_email,
        phone=req.dm_phone,
        notes=req.notes,
        source="manual_entry"
    )

    comp = Company(
        inn=req.inn.strip(),
        name=req.company_name.strip(),
        website=req.website,
        domain=req.website,
        region=req.region,
        okved_name=req.okved_name,
        decision_makers=[dm],
        source="manual"
    )

    saved_comp = engine.enrich_company_and_dms(comp, scrape_web=False, verify_emails=True)
    return {"status": "ok", "message": "Организация и ЛПР успешно созданы", "company_inn": saved_comp.inn}


@app.put("/api/leads/{lead_id}")
def update_lead(lead_id: int, req: LeadUpdateRequest):
    updates = req.model_dump(exclude_unset=True)
    field_map = {
        "dm_full_name": "full_name",
        "dm_title": "title",
        "dm_role_level": "role_level",
        "dm_email": "email",
        "email_status": "email_status",
        "dm_phone": "phone",
        "dm_phone_type": "phone_type",
        "phone_carrier": "phone_carrier",
        "phone_timezone": "phone_timezone",
        "dm_telegram": "telegram",
        "dm_vk": "vk",
        "dm_tenchat": "tenchat",
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


@app.post("/api/leads/bulk-status")
def bulk_status(req: BulkStatusRequest):
    updated = engine.bulk_update_lead_status(req.lead_ids, req.status)
    return {"status": "ok", "updated_count": updated}


@app.post("/api/leads/bulk-delete")
def bulk_delete(req: BulkDeleteRequest):
    deleted = engine.bulk_delete_leads(req.lead_ids)
    return {"status": "ok", "deleted_count": deleted}


@app.post("/api/enrich/real")
def enrich_real(inn: str = Query(..., description="ИНН, ОГРН или наименование организации")):
    clean_inn = inn.strip()
    comp = engine.fetch_and_enrich(clean_inn, scrape_web=True, verify_emails=True)
    if comp:
        leads = engine.get_all_leads(query=comp.inn)
        return {
            "status": "ok",
            "company_name": comp.name,
            "short_name": comp.short_name,
            "inn": comp.inn,
            "ogrn": comp.ogrn,
            "kpp": comp.kpp,
            "domain": comp.domain or comp.website,
            "website": comp.website,
            "region": comp.region,
            "city": comp.city,
            "address": comp.address,
            "okved": comp.okved,
            "okved_name": comp.okved_name,
            "revenue_rub": comp.revenue_rub,
            "employees_count": comp.employees_count,
            "solvency_score": comp.solvency_score,
            "risk_level": comp.risk_level,
            "tags": comp.tags,
            "dms_count": len(comp.decision_makers),
            "leads": leads,
            "dms": [
                {
                    "full_name": dm.full_name,
                    "title": dm.title,
                    "role_level": dm.role_level,
                    "email": dm.email,
                    "email_status": dm.email_status,
                    "phone": dm.phone,
                    "phone_carrier": dm.phone_carrier,
                    "phone_timezone": dm.phone_timezone,
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


@app.post("/api/batch/cancel/{task_id}")
def batch_cancel(task_id: str):
    res = batch_processor.cancel_task(task_id)
    return {"status": "ok" if res else "error", "cancelled": res}


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
    res = normalize_phone(req.phone, default_region=req.default_region)
    return {"status": "ok", "result": res}


@app.post("/api/tools/deliverability")
def tool_deliverability(req: DeliverabilityReq):
    res = analyze_domain_deliverability(req.domain)
    return {"status": "ok", "result": res}


@app.post("/api/tools/outreach-draft")
def tool_outreach_draft(req: OutreachReq):
    lead = engine.get_lead_by_id(req.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    draft = generate_outreach_email(
        lead,
        offer_type=req.offer_type,
        sender_name=req.sender_name or "[Ваше Имя]",
        sender_company=req.sender_company or "[Ваша Компания]",
        sender_title=req.sender_title or "[Ваша Должность]",
        sender_phone=req.sender_phone or "[Ваш Телефон]"
    )
    return {"status": "ok", "draft": draft}


@app.post("/api/tools/call-script")
def tool_call_script(req: ColdCallScriptReq):
    lead = engine.get_lead_by_id(req.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    script = generate_cold_calling_script(lead)
    return {"status": "ok", "script": script}


@app.post("/api/leads/reverify")
def reverify_leads():
    cnt = engine.reverify_all_emails()
    return {"status": "ok", "reverified_count": cnt}


@app.post("/api/enrich/auto-all")
def enrich_auto_all():
    """
    Автоматический сбор и обогащение всех организаций РФ и их руководящего состава.
    Пользователю не нужно знать ИНН — система сама собирает и актуализирует всю базу!
    """
    enriched_comps = engine.enrich_all_known_companies(scrape_web=False, verify_emails=True)
    leads = engine.get_all_leads()
    return {
        "status": "ok",
        "message": f"Успешно собрано и обогащено {len(enriched_comps)} предприятий и {len(leads)} контактов ЛПР!",
        "companies_count": len(enriched_comps),
        "leads_count": len(leads),
        "leads": leads
    }


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@app.get("/api/export/csv")
def api_export_csv():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_export.csv")
    export_to_csv(leads, path)
    return FileResponse(path, filename="leads_b2b.csv", media_type="text/csv")


@app.get("/api/export/excel")
def api_export_excel():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_export.xlsx")
    export_to_excel(leads, path)
    return FileResponse(path, filename="leads_b2b.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/export/amocrm")
def api_export_amocrm():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_amocrm.csv")
    export_to_amocrm_csv(leads, path)
    return FileResponse(path, filename="leads_amocrm.csv", media_type="text/csv")


@app.get("/api/export/bitrix24")
def api_export_bitrix24():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_bitrix24.csv")
    export_to_bitrix24_csv(leads, path)
    return FileResponse(path, filename="leads_bitrix24.csv", media_type="text/csv")


@app.get("/api/export/hubspot")
def api_export_hubspot():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_hubspot.csv")
    export_to_hubspot_csv(leads, path)
    return FileResponse(path, filename="leads_hubspot.csv", media_type="text/csv")


@app.get("/api/export/vcard")
def api_export_vcard():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_all.vcf")
    export_to_vcard(leads, path)
    return FileResponse(path, filename="leads_b2b_contacts.vcf", media_type="text/vcard")


@app.get("/api/leads/{lead_id}/vcard")
def api_export_single_vcard(lead_id: int):
    lead = engine.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Контакт не найден")
    path = os.path.join(tempfile.gettempdir(), f"lead_{lead_id}.vcf")
    export_to_vcard([lead], path)
    return FileResponse(path, filename=f"contact_{lead_id}.vcf", media_type="text/vcard")


@app.get("/api/export/json")
def api_export_json():
    leads = engine.get_all_leads()
    path = os.path.join(tempfile.gettempdir(), "leads_export.json")
    export_to_json(leads, path)
    return FileResponse(path, filename="leads_b2b.json", media_type="application/json")


# ============================================================================
# HTML SPA DASHBOARD TEMPLATE (ENTERPRISE EDITION)
# ============================================================================

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B2B Lead Intelligence Enterprise — База ЛПР предприятий России</title>
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
            --danger: #ef4444;
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
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
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
            height: 48px;
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
            height: 44px;
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
        .badge-catch_all { background: #fef9c3; color: #854d0e; }
        .badge-unverified { background: #f1f5f9; color: #64748b; }
        .badge-invalid { background: #fee2e2; color: #991b1b; }

        .badge-crm {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 6px;
        }

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
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #e2e8f0, #cbd5e1);
            color: #334155;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.88rem;
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
            padding: 12px 20px;
            border-radius: 10px;
            font-size: 0.9rem;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            display: none;
            animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .enrich-hero-card {
            background: linear-gradient(135deg, #ffffff 0%, #f0f7ff 100%);
            border: 1px solid #bfdbfe;
            border-radius: 20px;
            padding: 24px 28px;
            box-shadow: 0 10px 30px rgba(37, 99, 235, 0.08);
            position: relative;
            overflow: hidden;
            margin-bottom: 24px;
        }
        .enrich-hero-card::before {
            content: '';
            position: absolute;
            top: -60px;
            right: -60px;
            width: 180px;
            height: 180px;
            background: radial-gradient(circle, rgba(37, 99, 235, 0.12) 0%, transparent 70%);
            border-radius: 50%;
            pointer-events: none;
        }
        .enrich-input-container {
            position: relative;
        }
        .enrich-input-container .form-control {
            border-radius: 14px 0 0 14px;
            font-size: 1.05rem;
            padding: 14px 18px;
            border-color: #cbd5e1;
        }
        .enrich-input-container .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
        }
        .enrich-btn-gradient {
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            border: none;
            border-radius: 0 14px 14px 0;
            padding: 12px 28px;
            font-size: 1.05rem;
            font-weight: 700;
            color: #ffffff;
            transition: all 0.25s ease;
            box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);
        }
        .enrich-btn-gradient:hover {
            background: linear-gradient(135deg, #1d4ed8, #4338ca);
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
            color: #ffffff;
        }
        .sample-chip {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 20px;
            padding: 5px 13px;
            font-size: 0.83rem;
            font-weight: 600;
            color: #334155;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .sample-chip:hover {
            background: #eff6ff;
            border-color: #3b82f6;
            color: #1d4ed8;
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.15);
        }
        .spin {
            animation: spinAnim 1s linear infinite;
        }
        @keyframes spinAnim {
            100% { transform: rotate(360deg); }
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
                            <span class="badge bg-primary bg-opacity-10 text-primary">v2.2 Enterprise</span>
                        </div>
                        <small class="text-muted">Поиск, скоринг, обогащение и валидация контактов ЛПР предприятий РФ</small>
                    </div>
                </div>
                <div class="d-flex gap-2 align-items-center">
                    <button class="btn btn-primary px-3 shadow-sm d-flex align-items-center gap-2 fw-bold enrich-btn-gradient" style="border-radius: 10px; font-size: 0.92rem; padding: 8px 16px;" onclick="focusQuickEnrichment()">
                        <i class="bi bi-stars"></i> ✨ Обогатить данные
                    </button>
                    <button class="btn btn-outline-primary btn-action" onclick="openManualCreateModal()">
                        <i class="bi bi-plus-circle"></i> Добавить контакт
                    </button>
                    <div class="dropdown">
                        <button class="btn btn-outline-secondary btn-action dropdown-toggle" type="button" data-bs-toggle="dropdown">
                            <i class="bi bi-download"></i> Экспорт базы
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end shadow-sm border-0 rounded-3">
                            <li><a class="dropdown-item py-2" href="/api/export/excel"><i class="bi bi-file-earmark-excel text-success me-2"></i> Экспорт Excel (.xlsx)</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/csv"><i class="bi bi-filetype-csv text-primary me-2"></i> Экспорт CSV (UTF-8-BOM)</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/vcard"><i class="bi bi-person-vcard text-info me-2"></i> Экспорт vCard (.vcf для iPhone/Android)</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item py-2" href="/api/export/amocrm"><i class="bi bi-cloud-arrow-up text-warning me-2"></i> Формат amoCRM</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/bitrix24"><i class="bi bi-boxes text-info me-2"></i> Формат Битрикс24</a></li>
                            <li><a class="dropdown-item py-2" href="/api/export/hubspot"><i class="bi bi-globe text-primary me-2"></i> Формат HubSpot / Salesforce</a></li>
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
                    <i class="bi bi-tools"></i> Студия валидации и Outreach
                </button>
            </li>
        </ul>

        <!-- Содержимое вкладок -->
        <div class="tab-content" id="mainTabContent">

            <!-- Вкладка 1: CRM База контактов -->
            <div class="tab-pane fade show active" id="crmPane" role="tabpanel">

                <!-- ГЛАВНЫЙ БЛОК БЫСТРОГО ОБОГАЩЕНИЯ В 1 КЛИК -->
                <div class="enrich-hero-card" id="quickEnrichHeroCard">
                    <div class="row align-items-center mb-3">
                        <div class="col-lg-8">
                            <div class="d-flex align-items-center gap-2 mb-2">
                                <span class="badge bg-primary px-3 py-1 text-white rounded-pill shadow-sm"><i class="bi bi-lightning-charge-fill me-1"></i> 1-CLICK ENRICHMENT</span>
                                <span class="text-muted small fw-medium">Официальный ЕГРЮЛ ФНС • Реестр МСП • Краулинг • Email Permutations • Phone Intel</span>
                            </div>
                            <h4 class="fw-bold mb-1 text-dark">Быстрое обогащение организации и поиск ЛПР</h4>
                            <p class="text-secondary small mb-0">Введите ИНН организации (10 или 12 цифр), название компании или сайт. Нажмите <b>«Обогатить данные»</b> для автоматического сбора реквизитов, состава топ-менеджмента, корпоративной почты и скоринга надежности.</p>
                        </div>
                        <div class="col-lg-4 text-lg-end mt-3 mt-lg-0 d-flex flex-wrap gap-2 justify-content-lg-end">
                            <button class="btn btn-warning btn-sm fw-bold shadow-sm text-dark rounded-pill px-3" id="btnAutoEnrichHero" onclick="startAutoEnrichAll()">
                                <i class="bi bi-rocket-takeoff-fill me-1"></i> 🚀 Собрать все организации
                            </button>
                            <button class="btn btn-sm btn-outline-primary rounded-pill px-3 shadow-sm" onclick="applyRandomSample()">
                                <i class="bi bi-shuffle me-1"></i> Случайный пример
                            </button>
                        </div>
                    </div>

                    <!-- Поисковая строка и Главная Кнопка Обогащения -->
                    <div class="enrich-input-container">
                        <div class="input-group input-group-lg shadow-sm">
                            <span class="input-group-text bg-white border-end-0 ps-3">
                                <i class="bi bi-search text-primary fs-5"></i>
                            </span>
                            <input type="text" id="heroEnrichInput" class="form-control border-start-0 ps-2" placeholder="Введите ИНН (например, 7707083893), название компании (Яндекс, Авито) или сайт..." onkeypress="handleHeroEnrichKey(event)">
                            <button class="btn btn-primary px-4 fw-bold d-flex align-items-center gap-2 enrich-btn-gradient" id="btnHeroEnrich" onclick="startHeroEnrichment()">
                                <i class="bi bi-stars fs-5"></i> <span>Обогатить данные</span>
                            </button>
                        </div>
                    </div>

                    <!-- Быстрый выбор примеров в 1 клик -->
                    <div class="d-flex flex-wrap align-items-center gap-2 mt-3 pt-1">
                        <span class="text-muted small fw-semibold me-1"><i class="bi bi-cursor-fill text-primary"></i> Быстрый выбор:</span>
                        <button class="sample-chip" onclick="applySample('7736207543')">🏢 Яндекс</button>
                        <button class="sample-chip" onclick="applySample('7707083893')">🏦 Сбербанк</button>
                        <button class="sample-chip" onclick="applySample('7704217370')">📦 Ozon</button>
                        <button class="sample-chip" onclick="applySample('7734443270')">🥑 ВкусВилл</button>
                        <button class="sample-chip" onclick="applySample('7710668322')">🛍️ Авито</button>
                        <button class="sample-chip" onclick="applySample('7710140679')">💳 Т-Банк</button>
                        <button class="sample-chip" onclick="applySample('7743003908')">🛡️ Касперский</button>
                        <button class="sample-chip" onclick="applySample('7714595571')">💻 1С</button>
                        <button class="sample-chip" onclick="applySample('3528000597')">🏗️ Северсталь</button>
                        <button class="sample-chip" onclick="applySample('7802849641')">🍺 Балтика</button>
                        <button class="sample-chip" onclick="applySample('7707329188')">☁️ МойСклад</button>
                        <button class="sample-chip" onclick="applySample('7810138853')">🚚 Деловые Линии</button>
                    </div>

                    <!-- Индикатор прогресса -->
                    <div id="heroEnrichProgress" class="mt-3 pt-2" style="display: none;">
                        <div class="progress mb-2" style="height: 10px; border-radius: 6px;">
                            <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" id="heroEnrichBar" style="width: 100%;"></div>
                        </div>
                        <div class="d-flex justify-content-between align-items-center">
                            <div id="heroEnrichStatusText" class="text-primary small fw-semibold">
                                <i class="bi bi-arrow-repeat spin me-1"></i> Запрос в ЕГРЮЛ ФНС РФ, краулинг сайта и генерация контактов...
                            </div>
                            <span class="badge bg-light text-muted border">Сбор live-данных</span>
                        </div>
                    </div>

                    <!-- Карточка мгновенного результата обогащения -->
                    <div id="heroEnrichResultCard" class="mt-3 p-3 rounded-3 border bg-white shadow-sm" style="display: none;">
                        <div id="heroEnrichResultContent"></div>
                    </div>
                </div>

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
                                <div class="text-muted small fw-medium">Прямых номеров / Часовые пояса</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Блок поиска и фильтрации -->
                <div class="card-custom mb-4">
                    <div class="row g-3 align-items-end">
                        <div class="col-lg-3">
                            <label class="form-label fw-bold text-dark small text-uppercase mb-1">
                                <i class="bi bi-search me-1"></i> Поиск по всей базе
                            </label>
                            <div class="input-group-search">
                                <i class="bi bi-search search-icon"></i>
                                <input type="text" id="filterQuery" class="form-control" placeholder="ФИО, компания, ИНН, email, телефон..." oninput="applyFilters()">
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
                            <label class="form-label fw-bold text-dark small text-uppercase mb-1">Статус CRM</label>
                            <select id="filterLeadStatus" class="form-select filter-select" onchange="applyFilters()">
                                <option value="">Все статусы CRM</option>
                                <option value="NEW">Новый (NEW)</option>
                                <option value="CONTACTED">Связались (CONTACTED)</option>
                                <option value="IN_PROGRESS">В работе (IN_PROGRESS)</option>
                                <option value="QUALIFIED">Квалифицирован (QUALIFIED)</option>
                                <option value="MEETING_SCHEDULED">Назначена встреча</option>
                                <option value="WON">Сделка (WON)</option>
                                <option value="REJECTED">Отказ (REJECTED)</option>
                            </select>
                        </div>
                        <div class="col-lg-3">
                            <div class="d-flex gap-2">
                                <button class="btn btn-outline-secondary w-100 btn-action" style="height: 44px;" onclick="resetFilters()">
                                    <i class="bi bi-arrow-counterclockwise"></i> Сброс
                                </button>
                                <button class="btn btn-outline-primary btn-action" style="height: 44px;" onclick="reverifyAll()" title="Перепроверить все MX DNS">
                                    <i class="bi bi-shield-check"></i> Ревалидация
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Панель массовых действий -->
                    <div id="bulkActionsBar" class="mt-3 pt-3 border-top d-flex align-items-center justify-content-between" style="display: none !important;">
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-primary fs-6" id="bulkSelectedCount">0</span>
                            <span class="small fw-semibold text-dark">контактов выбрано</span>
                        </div>
                        <div class="d-flex gap-2">
                            <select id="bulkStatusSelect" class="form-select form-select-sm" style="width: 170px;">
                                <option value="CONTACTED">Статус: Связались</option>
                                <option value="IN_PROGRESS">Статус: В работе</option>
                                <option value="QUALIFIED">Статус: Квалифицирован</option>
                                <option value="MEETING_SCHEDULED">Статус: Встреча</option>
                                <option value="WON">Статус: Сделка</option>
                                <option value="REJECTED">Статус: Отказ</option>
                            </select>
                            <button class="btn btn-sm btn-primary" onclick="applyBulkStatus()">Применить статус</button>
                            <button class="btn btn-sm btn-outline-danger" onclick="applyBulkDelete()">Удалить выбранные</button>
                        </div>
                    </div>
                </div>

                <!-- Таблица лидов -->
                <div class="card border-0 shadow-sm" style="border-radius: 16px; overflow: hidden;">
                    <div class="table-responsive">
                        <table class="table table-custom mb-0">
                            <thead>
                                <tr>
                                    <th style="width: 4%;"><input type="checkbox" id="selectAllCheckbox" onchange="toggleSelectAll(this)"></th>
                                    <th style="width: 25%;">Организация / Реквизиты</th>
                                    <th style="width: 23%;">ЛПР (Лицо, принимающее решения)</th>
                                    <th style="width: 20%;">Корпоративный Email</th>
                                    <th style="width: 18%;">Телефон и Время</th>
                                    <th style="width: 10%; text-align: right;">Действия</th>
                                </tr>
                            </thead>
                            <tbody id="leadsTableBody">
                                <tr>
                                    <td colspan="6" class="text-center py-5 text-muted">
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
                            <h6 class="fw-bold mb-3"><i class="bi bi-bar-chart-fill text-success me-2"></i> Воронка статусов в CRM</h6>
                            <div style="height: 280px; position: relative;">
                                <canvas id="chartCRM"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h6 class="fw-bold mb-3"><i class="bi bi-geo-alt-fill text-info me-2"></i> Топ регионов предприятий</h6>
                            <div style="height: 260px; position: relative;">
                                <canvas id="chartRegions"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
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
                            <p class="text-muted small">Введите ИНН (10 или 12 цифр), ОГРН или наименование предприятия. Платформа найдет карточку в реестре, определит состав руководства, найдет официальный домен, соберет контакты и рассчитает скоринг.</p>

                            <div class="input-group-search d-flex gap-2 mb-3">
                                <i class="bi bi-search search-icon"></i>
                                <input type="text" id="enrichQueryInput" class="form-control" placeholder="Например: 7707083893, 7736207543, Авито, МойСклад, ВкусВилл...">
                                <button class="btn btn-primary px-4 fw-semibold d-flex align-items-center gap-2" id="btnEnrich" onclick="startSingleEnrichment()">
                                    <i class="bi bi-search"></i> <span>Найти</span>
                                </button>
                            </div>

                            <div id="enrichProgressArea" style="display: none;">
                                <div class="progress mb-2" style="height: 8px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" id="enrichBar" style="width: 100%;"></div>
                                </div>
                                <div id="enrichStatusText" class="text-primary small fw-medium"></div>
                            </div>
                        </div>

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
                            <p class="text-muted small">Загрузите реестр Excel (.xlsx, .xls) или CSV со списком ИНН организаций. Система автоматически найдет нужную колонку и запустит конвейер в фоне.</p>

                            <div class="dropzone-box" onclick="document.getElementById('fileUploadInput').click()">
                                <i class="bi bi-cloud-arrow-up fs-1 text-primary mb-2 d-block"></i>
                                <div class="fw-semibold">Нажмите для выбора файла или перетащите сюда</div>
                                <div class="text-muted small mt-1">Поддерживаются .xlsx, .xls, .csv до 10 000 строк</div>
                                <input type="file" id="fileUploadInput" accept=".xlsx,.xls,.csv" style="display: none;" onchange="uploadBatchFile(this.files[0])">
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-2"><i class="bi bi-card-text text-warning me-2"></i> Ввод списка ИНН вручную</h5>
                            <p class="text-muted small">Вставьте список ИНН или сайтов (по одному на строку):</p>
                            <textarea id="batchTextarea" class="form-control mb-3 font-monospace" rows="5" placeholder="7707083893&#10;7736207543&#10;7802849641&#10;7743003908&#10;7710668322"></textarea>
                            <button class="btn btn-primary btn-action" onclick="startBatchFromText()">
                                <i class="bi bi-play-fill"></i> Запустить пакетное обогащение
                            </button>
                        </div>
                    </div>

                    <div class="col-12" id="batchMonitorCard" style="display: none;">
                        <div class="card-custom">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold mb-0"><i class="bi bi-cpu-fill text-primary me-2"></i> Фоновый конвейер обработки</h6>
                                <div class="d-flex gap-2">
                                    <span class="badge bg-primary" id="batchBadgeStatus">В процессе</span>
                                    <button class="btn btn-sm btn-outline-danger" id="btnCancelBatch" onclick="cancelActiveBatch()">Отменить</button>
                                </div>
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

            <!-- Вкладка 5: Инструменты валидации и Outreach -->
            <div class="tab-pane fade" id="toolsPane" role="tabpanel">
                <div class="row g-4">
                    <!-- Генератор email -->
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-3"><i class="bi bi-envelope-at-fill text-primary me-2"></i> Генератор корпоративных email (20+ формул)</h5>
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label small fw-semibold">ФИО сотрудника</label>
                                    <input type="text" id="toolNameInput" class="form-control" placeholder="Иванов Иван Иванович" value="Иванов Иван Иванович">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small fw-semibold">Корпоративный домен</label>
                                    <input type="text" id="toolDomainInput" class="form-control" placeholder="company.ru" value="sberbank.ru">
                                </div>
                            </div>
                            <button class="btn btn-primary btn-action mb-3" onclick="runEmailPermutations()">
                                <i class="bi bi-lightning-charge"></i> Сгенерировать варианты
                            </button>
                            <div id="permutationsResult"></div>
                        </div>
                    </div>

                    <!-- Валидатор контактов & Доставляемость -->
                    <div class="col-lg-6">
                        <div class="card-custom h-100">
                            <h5 class="fw-bold mb-3"><i class="bi bi-shield-check text-success me-2"></i> Аудит домена, Email и Телефонов</h5>
                            
                            <div class="mb-3">
                                <label class="form-label small fw-semibold">Аудит безопасности домена (MX, SPF, DMARC, DKIM)</label>
                                <div class="input-group">
                                    <input type="text" id="toolDeliverDomain" class="form-control" placeholder="yandex.ru" value="yandex.ru">
                                    <button class="btn btn-outline-primary" onclick="runDeliverabilityAudit()">Аудит домена</button>
                                </div>
                                <div id="deliverAuditResult" class="mt-2 small"></div>
                            </div>

                            <hr>

                            <div class="mb-3">
                                <label class="form-label small fw-semibold">Проверка телефона (Часовой пояс + Окно звонка + Оператор)</label>
                                <div class="input-group">
                                    <input type="text" id="toolPhoneInput" class="form-control" placeholder="+7 916 123 45 67" value="+7 (495) 739-70-00">
                                    <button class="btn btn-outline-success" onclick="runPhoneValidation()">Проверить телефон</button>
                                </div>
                                <div id="phoneVerifyResult" class="mt-2 small"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </div>

    </div>

    <!-- Модальное окно деталей лида и генератора холодного письма / звонка -->
    <div class="modal fade" id="leadModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content border-0 shadow-lg" style="border-radius: 16px;">
                <div class="modal-header border-bottom-0 pb-0">
                    <div>
                        <h5 class="modal-title fw-bold" id="modalLeadTitle">Досье ЛПР</h5>
                        <small class="text-muted" id="modalCompanySub">Карточка предприятия и руководителя</small>
                    </div>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    
                    <ul class="nav nav-pills mb-3" id="modalTabs" role="tablist">
                        <li class="nav-item"><button class="nav-link active" data-bs-toggle="pill" data-bs-target="#tabLeadInfo">Контактные данные</button></li>
                        <li class="nav-item"><button class="nav-link" data-bs-toggle="pill" data-bs-target="#tabOutreach">Cold Email Studio</button></li>
                        <li class="nav-item"><button class="nav-link" data-bs-toggle="pill" data-bs-target="#tabCallScript">Сценарий звонка (Cold Call)</button></li>
                    </ul>

                    <div class="tab-content">
                        <!-- Вкладка Контакт -->
                        <div class="tab-pane fade show active" id="tabLeadInfo">
                            <div class="row g-3 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label small text-muted mb-1">ФИО руководителя</label>
                                    <input type="text" id="modalFio" class="form-control fw-bold">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small text-muted mb-1">Должность</label>
                                    <input type="text" id="modalPost" class="form-control">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small text-muted mb-1">Корпоративный Email</label>
                                    <input type="text" id="modalEmail" class="form-control font-monospace">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small text-muted mb-1">Телефон</label>
                                    <input type="text" id="modalPhone" class="form-control font-monospace">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small text-muted mb-1">Статус в CRM</label>
                                    <select id="modalStatus" class="form-select">
                                        <option value="NEW">Новый контакт (NEW)</option>
                                        <option value="CONTACTED">Связались (CONTACTED)</option>
                                        <option value="IN_PROGRESS">В работе (IN_PROGRESS)</option>
                                        <option value="QUALIFIED">Квалифицирован (QUALIFIED)</option>
                                        <option value="MEETING_SCHEDULED">Назначена встреча</option>
                                        <option value="WON">Сделка (WON)</option>
                                        <option value="REJECTED">Отказ (REJECTED)</option>
                                    </select>
                                </div>
                                <div class="col-12">
                                    <label class="form-label small text-muted mb-1">Заметки и история взаимодействия</label>
                                    <textarea id="modalNotes" class="form-control" rows="2" placeholder="Комментарии менеджера по продажам..."></textarea>
                                </div>
                            </div>
                        </div>

                        <!-- Вкладка Outreach Email -->
                        <div class="tab-pane fade" id="tabOutreach">
                            <div class="p-3 bg-light rounded-3 mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
                                    <span class="fw-bold text-dark small text-uppercase">
                                        <i class="bi bi-envelope-paper-heart-fill text-primary me-1"></i>
                                        Шаблоны B2B холодного письма
                                    </span>
                                    <div class="btn-group btn-group-sm">
                                        <button class="btn btn-outline-primary" onclick="generateOutreach('partnership')">Партнерство</button>
                                        <button class="btn btn-outline-primary" onclick="generateOutreach('sales')">Продажи</button>
                                        <button class="btn btn-outline-primary" onclick="generateOutreach('demo')">Демо-доступ</button>
                                        <button class="btn btn-outline-primary" onclick="generateOutreach('procurement')">Закупки</button>
                                        <button class="btn btn-outline-primary" onclick="generateOutreach('substitution')">Импортозамещение</button>
                                        <button class="btn btn-outline-secondary" onclick="generateOutreach('followup1')">Follow-up 1</button>
                                    </div>
                                </div>
                                <div id="outreachSubject" class="fw-bold text-primary small mb-1"></div>
                                <textarea id="outreachBody" class="form-control form-control-sm font-monospace" rows="8" readonly></textarea>
                                <button class="btn btn-sm btn-outline-primary mt-2" onclick="copyOutreachText()">
                                    <i class="bi bi-clipboard"></i> Скопировать текст письма
                                </button>
                            </div>
                        </div>

                        <!-- Вкладка Сценарий звонка -->
                        <div class="tab-pane fade" id="tabCallScript">
                            <div class="p-3 bg-light rounded-3 mb-3" id="callScriptContainer">
                                <div class="spinner-border spinner-border-sm text-primary"></div> Загрузка скрипта...
                            </div>
                        </div>
                    </div>

                </div>
                <div class="modal-footer border-top-0 pt-0">
                    <button type="button" class="btn btn-outline-danger btn-sm" onclick="deleteCurrentLead()">Удалить контакт</button>
                    <a id="modalVcardBtn" href="#" class="btn btn-outline-info btn-sm"><i class="bi bi-person-vcard"></i> vCard</a>
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Закрыть</button>
                    <button type="button" class="btn btn-primary btn-sm px-3" onclick="saveLeadChanges()">Сохранить изменения</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно ручного добавления -->
    <div class="modal fade" id="manualCreateModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content border-0 shadow-lg" style="border-radius: 16px;">
                <div class="modal-header border-bottom-0 pb-0">
                    <h5 class="modal-title fw-bold">Добавить организацию и ЛПР</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-2">
                        <label class="form-label small text-muted mb-1">ИНН организации *</label>
                        <input type="text" id="manualInn" class="form-control" placeholder="7707083893" required>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small text-muted mb-1">Наименование организации *</label>
                        <input type="text" id="manualCompName" class="form-control" placeholder="ООО 'Пример'" required>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small text-muted mb-1">ФИО руководителя / ЛПР *</label>
                        <input type="text" id="manualFio" class="form-control" placeholder="Иванов Иван Иванович" required>
                    </div>
                    <div class="row g-2 mb-2">
                        <div class="col-6">
                            <label class="form-label small text-muted mb-1">Должность</label>
                            <input type="text" id="manualTitle" class="form-control" placeholder="Генеральный директор" value="Генеральный директор">
                        </div>
                        <div class="col-6">
                            <label class="form-label small text-muted mb-1">Уровень</label>
                            <select id="manualRole" class="form-select">
                                <option value="C-Level">C-Level</option>
                                <option value="Director">Director</option>
                                <option value="Head">Head</option>
                                <option value="Founder">Founder</option>
                            </select>
                        </div>
                    </div>
                    <div class="row g-2 mb-2">
                        <div class="col-6">
                            <label class="form-label small text-muted mb-1">Email</label>
                            <input type="email" id="manualEmail" class="form-control" placeholder="ceo@company.ru">
                        </div>
                        <div class="col-6">
                            <label class="form-label small text-muted mb-1">Телефон</label>
                            <input type="text" id="manualPhone" class="form-control" placeholder="+7 999 123-45-67">
                        </div>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small text-muted mb-1">Сайт</label>
                        <input type="text" id="manualWebsite" class="form-control" placeholder="company.ru">
                    </div>
                </div>
                <div class="modal-footer border-top-0 pt-0">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Отмена</button>
                    <button type="button" class="btn btn-primary btn-sm px-4" onclick="submitManualLead()">Создать</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Уведомление о действиях -->
    <div id="copyToast" class="toast-copy">
        <i class="bi bi-clipboard-check text-success me-2"></i> Скопировано в буфер обмена
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        let allLeads = [];
        let selectedLeadIds = new Set();
        let activeLeadId = null;
        let activeBatchTaskId = null;
        let chartRolesInstance = null;
        let chartCRMInstance = null;
        let chartRegionsInstance = null;
        let chartIndustriesInstance = null;

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Скопировано: ' + text);
            });
        }

        function showToast(msg) {
            const t = document.getElementById('copyToast');
            t.innerHTML = `<i class="bi bi-check-circle-fill text-success me-2"></i> ${msg}`;
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
                selectedLeadIds.clear();
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
                        <td colspan="6" class="text-center py-5 text-muted">
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
                } else if (l.email_status === 'catch_all') {
                    badgeClass = 'badge-catch_all';
                    badgeIcon = 'bi-envelope-exclamation';
                    statusText = 'Catch-All';
                } else if (l.email_status === 'generated') {
                    badgeClass = 'badge-generated';
                    badgeIcon = 'bi-gear';
                    statusText = 'Паттерн';
                } else if (l.email_status === 'disposable' || l.email_status === 'no_mx' || l.email_status === 'syntax_invalid') {
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

                let phoneBadge = '';
                if (l.phone_timezone) {
                    phoneBadge = `<span class="badge bg-light text-dark border" style="font-size: 0.68rem;"><i class="bi bi-clock"></i> ${l.phone_timezone}</span>`;
                }

                const phoneHtml = l.dm_phone ? `
                    <div class="d-flex flex-column gap-1">
                        <div class="contact-pill text-nowrap" title="Кликните для копирования" onclick="copyToClipboard('${l.dm_phone}')">
                            <i class="bi bi-telephone text-success"></i> ${l.dm_phone}
                        </div>
                        <div class="d-flex align-items-center gap-1 flex-wrap">
                            <small class="text-muted" style="font-size: 0.72rem;">${l.phone_carrier || (l.dm_phone_type === 'mobile' ? 'Мобильный' : 'Офис')}</small>
                            ${phoneBadge}
                        </div>
                    </div>
                ` : '<span class="text-muted small">—</span>';

                const isChecked = selectedLeadIds.has(l.id) ? 'checked' : '';

                let crmBadgeColor = 'bg-secondary';
                if (l.lead_status === 'QUALIFIED') crmBadgeColor = 'bg-primary';
                else if (l.lead_status === 'MEETING_SCHEDULED') crmBadgeColor = 'bg-info text-dark';
                else if (l.lead_status === 'WON') crmBadgeColor = 'bg-success';
                else if (l.lead_status === 'REJECTED') crmBadgeColor = 'bg-danger';

                tbody.innerHTML += `
                    <tr>
                        <td>
                            <input type="checkbox" class="lead-checkbox" data-id="${l.id}" ${isChecked} onchange="toggleLeadSelect(${l.id}, this)">
                        </td>
                        <td>
                            <div class="fw-bold text-dark mb-1">${l.company_name}</div>
                            <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                                <span class="badge bg-light text-dark border">ИНН: ${l.inn}</span>
                                ${l.region ? `<span class="text-muted small"><i class="bi bi-geo-alt"></i> ${l.region}</span>` : ''}
                                ${l.solvency_score ? `<span class="badge bg-success bg-opacity-10 text-success border-0" title="Надежность">${l.solvency_score}/100</span>` : ''}
                            </div>
                            ${l.okved_name ? `<div class="text-muted small text-truncate" style="max-width: 260px;" title="${l.okved_name}">${l.okved_name}</div>` : ''}
                        </td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <div class="avatar-circle">${getInitials(l.dm_full_name)}</div>
                                <div>
                                    <div class="fw-semibold text-dark">${l.dm_full_name}</div>
                                    <div class="text-muted small">${l.dm_title || 'Руководитель'}</div>
                                    <div class="d-flex gap-1 mt-1">
                                        <span class="badge bg-secondary bg-opacity-10 text-secondary" style="font-size: 0.7rem;">${l.dm_role_level || 'C-Level'}</span>
                                        <span class="badge ${crmBadgeColor} badge-crm">${l.lead_status || 'NEW'}</span>
                                    </div>
                                </div>
                            </div>
                        </td>
                        <td>${emailHtml}</td>
                        <td>${phoneHtml}</td>
                        <td style="text-align: right;">
                            <div class="d-flex gap-1 justify-content-end">
                                <button class="btn btn-sm btn-outline-primary btn-action" onclick="openLeadModal(${l.id})" title="Досье ЛПР и генератор Outreach">
                                    <i class="bi bi-person-lines-fill"></i>
                                </button>
                                ${l.website ? `<a href="https://${l.website}" target="_blank" class="btn btn-sm btn-outline-secondary btn-action" title="Сайт"><i class="bi bi-globe"></i></a>` : ''}
                            </div>
                        </td>
                    </tr>
                `;
            });
            updateBulkToolbar();
        }

        function toggleLeadSelect(id, cb) {
            if (cb.checked) selectedLeadIds.add(id);
            else selectedLeadIds.delete(id);
            updateBulkToolbar();
        }

        function toggleSelectAll(masterCb) {
            const cbs = document.querySelectorAll('.lead-checkbox');
            cbs.forEach(cb => {
                cb.checked = masterCb.checked;
                const id = parseInt(cb.getAttribute('data-id'));
                if (masterCb.checked) selectedLeadIds.add(id);
                else selectedLeadIds.delete(id);
            });
            updateBulkToolbar();
        }

        function updateBulkToolbar() {
            const bar = document.getElementById('bulkActionsBar');
            const cnt = document.getElementById('bulkSelectedCount');
            if (selectedLeadIds.size > 0) {
                bar.style.setProperty('display', 'flex', 'important');
                cnt.innerText = selectedLeadIds.size;
            } else {
                bar.style.setProperty('display', 'none', 'important');
            }
        }

        async function applyBulkStatus() {
            const status = document.getElementById('bulkStatusSelect').value;
            const ids = Array.from(selectedLeadIds);
            if (ids.length === 0) return;

            await fetch('/api/leads/bulk-status', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ lead_ids: ids, status: status })
            });
            showToast(`Обновлен статус для ${ids.length} контактов`);
            await loadLeads();
        }

        async function applyBulkDelete() {
            const ids = Array.from(selectedLeadIds);
            if (ids.length === 0 || !confirm(`Удалить ${ids.length} контактов?`)) return;

            await fetch('/api/leads/bulk-delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ lead_ids: ids })
            });
            showToast(`Удалено ${ids.length} контактов`);
            await loadLeads();
        }

        function applyFilters() {
            const q = document.getElementById('filterQuery').value.toLowerCase().trim();
            const region = document.getElementById('filterRegion').value.toLowerCase();
            const role = document.getElementById('filterRole').value;
            const leadStatus = document.getElementById('filterLeadStatus').value;

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
                if (leadStatus && l.lead_status !== leadStatus) return false;
                return true;
            });

            renderTable(filtered);
        }

        function resetFilters() {
            document.getElementById('filterQuery').value = '';
            document.getElementById('filterRegion').value = '';
            document.getElementById('filterRole').value = '';
            document.getElementById('filterLeadStatus').value = '';
            renderTable(allLeads);
        }

        async function openLeadModal(leadId) {
            activeLeadId = leadId;
            const res = await fetch(`/api/leads/${leadId}`);
            const lead = await res.json();

            document.getElementById('modalLeadTitle').innerText = `${lead.company_name} — ${lead.dm_full_name}`;
            document.getElementById('modalCompanySub').innerText = `ИНН: ${lead.inn} | Регион: ${lead.region || 'РФ'} | Скоринг: ${lead.confidence_score}%`;
            document.getElementById('modalFio').value = lead.dm_full_name || '';
            document.getElementById('modalPost').value = lead.dm_title || '';
            document.getElementById('modalEmail').value = lead.dm_email || '';
            document.getElementById('modalPhone').value = lead.dm_phone || '';
            document.getElementById('modalStatus').value = lead.lead_status || 'NEW';
            document.getElementById('modalNotes').value = lead.notes || '';
            document.getElementById('modalVcardBtn').href = `/api/leads/${leadId}/vcard`;

            await generateOutreach('partnership');
            await loadCallScript(leadId);

            const modal = new bootstrap.Modal(document.getElementById('leadModal'));
            modal.show();
        }

        function openManualCreateModal() {
            const modal = new bootstrap.Modal(document.getElementById('manualCreateModal'));
            modal.show();
        }

        async function submitManualLead() {
            const inn = document.getElementById('manualInn').value.trim();
            const comp = document.getElementById('manualCompName').value.trim();
            const fio = document.getElementById('manualFio').value.trim();
            if (!inn || !comp || !fio) {
                alert('Пожалуйста, заполните обязательные поля: ИНН, Название, ФИО');
                return;
            }

            const payload = {
                inn: inn,
                company_name: comp,
                dm_full_name: fio,
                dm_title: document.getElementById('manualTitle').value,
                dm_role_level: document.getElementById('manualRole').value,
                dm_email: document.getElementById('manualEmail').value,
                dm_phone: document.getElementById('manualPhone').value,
                website: document.getElementById('manualWebsite').value
            };

            await fetch('/api/leads/manual', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            bootstrap.Modal.getInstance(document.getElementById('manualCreateModal')).hide();
            showToast('Контакт успешно создан');
            await loadLeads();
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

        async function loadCallScript(leadId) {
            const cont = document.getElementById('callScriptContainer');
            try {
                const res = await fetch('/api/tools/call-script', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ lead_id: leadId })
                });
                const data = await res.json();
                const s = data.script;

                cont.innerHTML = `
                    <div class="mb-3">
                        <span class="badge bg-warning text-dark mb-1">1. Секретарский барьер (Gatekeeper bypass)</span>
                        <div class="p-2 bg-white rounded border small">${s.gatekeeper_script}</div>
                    </div>
                    <div class="mb-3">
                        <span class="badge bg-primary mb-1">2. Открытие разговора с ЛПР (30-сек Hook)</span>
                        <div class="p-2 bg-white rounded border small">${s.intro_pitch}</div>
                    </div>
                    <div class="mb-3">
                        <span class="badge bg-secondary mb-1">3. Отработка возражений</span>
                        <div class="accordion" id="accObjections">
                            ${s.objections.map((obj, i) => `
                                <div class="accordion-item">
                                    <h2 class="accordion-header">
                                        <button class="accordion-button collapsed py-2 small" type="button" data-bs-toggle="collapse" data-bs-target="#obj${i}">
                                            ${obj.objection}
                                        </button>
                                    </h2>
                                    <div id="obj${i}" class="accordion-collapse collapse" data-bs-parent="#accObjections">
                                        <div class="accordion-body small text-muted">${obj.answer}</div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div>
                        <span class="badge bg-success mb-1">4. Закрытие на онлайн-встречу / Демо</span>
                        <div class="p-2 bg-white rounded border small">${s.closing}</div>
                    </div>
                `;
            } catch (e) {
                cont.innerHTML = `<div class="text-danger small">Ошибка генерации сценария звонка</div>`;
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
            showToast('Запущена проверка MX DNS...');
            const res = await fetch('/api/leads/reverify', { method: 'POST' });
            const d = await res.json();
            showToast(`Перепроверено записей: ${d.reverified_count}`);
            await loadLeads();
        }

        // ====================================================================
        // БЫСТРОЕ ОБОГАЩЕНИЕ ДАННЫХ В 1 КЛИК (HERO WIDGET)
        // ====================================================================
        const SAMPLE_INNS = [
            '7736207543', '7707083893', '7704217370', '7734443270',
            '7710668322', '7710140679', '7743003908', '7714595571',
            '3528000597', '7802849641', '7707329188', '7810138853'
        ];

        async function startAutoEnrichAll() {
            const btn = document.getElementById('btnAutoEnrichHero');
            const pArea = document.getElementById('heroEnrichProgress');
            const pText = document.getElementById('heroEnrichStatusText');
            const resCard = document.getElementById('heroEnrichResultCard');
            const resContent = document.getElementById('heroEnrichResultContent');

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Авто-сбор...';
            }
            pArea.style.display = 'block';
            resCard.style.display = 'none';

            const stages = [
                '🚀 Запуск авто-сбора: перебор отраслей РФ...',
                '🏢 Сбор ИТ, Финтех, Ритейл, Производство, FMCG...',
                '🌐 Определение корпоративных сайтов и CMS/CRM...',
                '👥 Извлечение топ-менеджмента и C-Level директоров...',
                '✉️ Генерация корпоративной почты и MX DNS аудит...',
                '📊 Финансовый скоринг, расчет надежности и запись в CRM...'
            ];
            let sIdx = 0;
            pText.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i> ' + stages[0];
            const timer = setInterval(() => {
                sIdx = (sIdx + 1) % stages.length;
                pText.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i> ' + stages[sIdx];
            }, 600);

            try {
                const res = await fetch('/api/enrich/auto-all', { method: 'POST' });
                clearInterval(timer);
                const data = await res.json();

                if (data.status === 'ok') {
                    resCard.style.display = 'block';
                    resContent.innerHTML = '<div class="alert alert-success d-flex align-items-center justify-content-between mb-0">' +
                        '<div>' +
                            '<h6 class="fw-bold mb-1"><i class="bi bi-check-circle-fill me-2"></i>' + data.message + '</h6>' +
                            '<div class="small">Все организации, топ-менеджеры, корпоративные Email и телефоны успешно занесены в реестр CRM.</div>' +
                        '</div>' +
                        '<div class="d-flex gap-2">' +
                            '<a href="/api/export/excel" class="btn btn-success btn-sm text-white"><i class="bi bi-file-earmark-excel me-1"></i> Excel</a>' +
                            '<a href="/api/export/vcard" class="btn btn-primary btn-sm"><i class="bi bi-person-vcard me-1"></i> vCard</a>' +
                        '</div>' +
                    '</div>';

                    showToast(data.message);
                    await loadLeads();
                    await loadAnalytics();
                } else {
                    resCard.style.display = 'block';
                    resContent.innerHTML = '<div class="alert alert-danger mb-0"><i class="bi bi-x-circle me-1"></i> ' + (data.detail || 'Ошибка авто-сбора') + '</div>';
                }
            } catch (e) {
                clearInterval(timer);
                resCard.style.display = 'block';
                resContent.innerHTML = '<div class="alert alert-danger mb-0">Ошибка связи с сервером при авто-сборе</div>';
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-rocket-takeoff-fill me-1"></i> 🚀 Собрать все организации';
                }
                pArea.style.display = 'none';
            }
        }

        function applyRandomSample() {
            const rand = SAMPLE_INNS[Math.floor(Math.random() * SAMPLE_INNS.length)];
            applySample(rand);
        }

        function focusQuickEnrichment() {
            const el = document.getElementById('heroEnrichInput');
            if (el) {
                const crmTab = document.getElementById('crm-tab');
                if (crmTab) crmTab.click();
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.focus();
            }
        }

        function handleHeroEnrichKey(event) {
            if (event.key === 'Enter') {
                startHeroEnrichment();
            }
        }

        function applySample(query) {
            const input = document.getElementById('heroEnrichInput');
            if (input) {
                input.value = query;
                startHeroEnrichment();
            }
        }

        async function startHeroEnrichment() {
            const input = document.getElementById('heroEnrichInput');
            const q = input.value.trim();
            if (!q) { input.focus(); return; }

            const btn = document.getElementById('btnHeroEnrich');
            const pArea = document.getElementById('heroEnrichProgress');
            const pText = document.getElementById('heroEnrichStatusText');
            const resCard = document.getElementById('heroEnrichResultCard');
            const resContent = document.getElementById('heroEnrichResultContent');

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Обогащение...';
            pArea.style.display = 'block';
            resCard.style.display = 'none';

            const stages = [
                '🔍 Запрос в реестр ЕГРЮЛ/ЕГРИП ФНС РФ...',
                '🌐 Краулинг корпоративного сайта и анализ структуры...',
                '👥 Извлечение состава руководства и директоров...',
                '✉️ Генерация корпоративных Email и проверка MX DNS...',
                '📞 Определение операторов РФ, таймзоны и доступности...',
                '📊 Расчет скоринга надежности (Solvency Score)...'
            ];
            let sIdx = 0;
            pText.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i> ' + stages[0];
            const timer = setInterval(() => {
                sIdx = (sIdx + 1) % stages.length;
                pText.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i> ' + stages[sIdx];
            }, 500);

            try {
                const res = await fetch('/api/enrich/real?inn=' + encodeURIComponent(q), { method: 'POST' });
                clearInterval(timer);
                const data = await res.json();

                if (data.status === 'ok') {
                    resCard.style.display = 'block';

                    const riskBadgeClass = data.risk_level === 'LOW' ? 'bg-success' : (data.risk_level === 'MEDIUM' ? 'bg-warning text-dark' : 'bg-danger');

                    const leadsList = data.leads && data.leads.length > 0 ? data.leads : data.dms.map(d => ({
                        id: null,
                        dm_full_name: d.full_name,
                        dm_title: d.title,
                        dm_role_level: d.role_level,
                        dm_email: d.email,
                        email_status: d.email_status,
                        dm_phone: d.phone,
                        phone_timezone: d.phone_timezone,
                        confidence_score: d.confidence
                    }));

                    let rowsHtml = '';
                    for (const l of leadsList) {
                        const emailBtn = l.dm_email ? '<button class="btn btn-link btn-sm p-0 text-muted" title="Копировать" onclick="copyToClipboard(\'' + l.dm_email + '\')"><i class="bi bi-clipboard"></i></button>' : '';
                        const waBtn = l.dm_phone ? '<a href="https://wa.me/' + l.dm_phone.replace(/[^0-9]/g, '') + '" target="_blank" class="btn btn-link btn-sm p-0 text-success" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>' : '';
                        const actionBtns = l.id ? '<button class="btn btn-outline-primary btn-sm" title="Письмо ЛПР (8 шаблонов)" onclick="openOutreachForLead(' + l.id + ')"><i class="bi bi-envelope-fill"></i></button><button class="btn btn-outline-warning text-dark btn-sm ms-1" title="Скрипт звонка" onclick="openCallScriptForLead(' + l.id + ')"><i class="bi bi-telephone-fill"></i></button><a href="/api/leads/' + l.id + '/vcard" class="btn btn-outline-secondary btn-sm ms-1" title="Скачать vCard (.vcf)"><i class="bi bi-person-vcard"></i></a>' : '';

                        rowsHtml += '<tr>' +
                            '<td><div class="fw-bold text-dark">' + l.dm_full_name + '</div><span class="badge bg-light text-secondary border" style="font-size:0.72rem;">' + (l.dm_role_level || 'C-Level') + '</span></td>' +
                            '<td class="small text-muted">' + (l.dm_title || 'Руководитель') + '</td>' +
                            '<td><div class="d-flex align-items-center gap-1"><span class="font-monospace fw-semibold text-primary">' + (l.dm_email || '—') + '</span> ' + emailBtn + '</div><small class="badge bg-light text-dark border" style="font-size:0.7rem;">' + (l.email_status || 'valid_mx') + '</small></td>' +
                            '<td><div class="d-flex align-items-center gap-1 font-monospace"><span>' + (l.dm_phone || '—') + '</span> ' + waBtn + '</div><small class="text-muted" style="font-size:0.72rem;">' + (l.phone_timezone || 'MSK') + '</small></td>' +
                            '<td><span class="badge bg-success bg-opacity-10 text-success fw-bold">' + (l.confidence_score || 92) + '%</span></td>' +
                            '<td class="text-end">' + actionBtns + '</td>' +
                        '</tr>';
                    }

                    resContent.innerHTML = '<div class="d-flex flex-wrap justify-content-between align-items-center pb-3 border-bottom mb-3">' +
                        '<div>' +
                            '<div class="d-flex align-items-center gap-2">' +
                                '<h5 class="fw-bold mb-0 text-dark">' + data.company_name + '</h5>' +
                                '<span class="badge ' + riskBadgeClass + '">Надежность: ' + data.solvency_score + '/100 (' + data.risk_level + ')</span>' +
                                '<span class="badge bg-light text-secondary border">ЕГРЮЛ ФНС РФ</span>' +
                            '</div>' +
                            '<div class="text-muted small mt-1">' +
                                'ИНН: <b class="text-dark">' + data.inn + '</b> | ОГРН: ' + (data.ogrn || '—') + ' | ' +
                                'Отрасль: ' + (data.okved_name || '—') + ' | ' +
                                'Регион: ' + (data.region || data.city || 'РФ') + ' | ' +
                                'Сайт: <a href="https://' + (data.domain || 'yandex.ru') + '" target="_blank" class="text-primary fw-semibold">' + (data.domain || '—') + '</a>' +
                            '</div>' +
                        '</div>' +
                        '<div class="d-flex gap-2 mt-2 mt-md-0">' +
                            '<button class="btn btn-sm btn-outline-primary" onclick="filterTableByInn(\'' + data.inn + '\')"><i class="bi bi-funnel me-1"></i> Показать в таблице</button>' +
                            '<a href="/api/export/excel" class="btn btn-sm btn-success text-white"><i class="bi bi-file-earmark-excel me-1"></i> Скачать Excel</a>' +
                        '</div>' +
                    '</div>' +
                    '<div class="mb-2 fw-semibold text-dark small d-flex justify-content-between align-items-center">' +
                        '<span><i class="bi bi-person-lines-fill text-primary me-1"></i> Найденные лица, принимающие решения (ЛПР):</span>' +
                        '<span class="badge bg-primary bg-opacity-10 text-primary">' + leadsList.length + ' контакта(ов)</span>' +
                    '</div>' +
                    '<div class="table-responsive">' +
                        '<table class="table table-sm table-hover align-middle mb-0">' +
                            '<thead class="table-light">' +
                                '<tr>' +
                                    '<th>ФИО ЛПР</th><th>Должность</th><th>Корпоративный Email</th><th>Телефон и таймзона</th><th>Скоринг</th><th class="text-end">Действия</th>' +
                                '</tr>' +
                            '</thead>' +
                            '<tbody>' + rowsHtml + '</tbody>' +
                        '</table>' +
                    '</div>';

                    showToast('Обогащено: ' + data.company_name);
                    await loadLeads();
                    await loadAnalytics();
                } else {
                    clearInterval(timer);
                    resCard.style.display = 'block';
                    resContent.innerHTML = '<div class="alert alert-danger d-flex align-items-center gap-2 mb-0"><i class="bi bi-exclamation-triangle-fill fs-5"></i><div>' + (data.message || 'Организация не найдена') + '</div></div>';
                }
            } catch (e) {
                clearInterval(timer);
                resCard.style.display = 'block';
                resContent.innerHTML = '<div class="alert alert-danger d-flex align-items-center gap-2 mb-0"><i class="bi bi-x-circle-fill fs-5"></i><div>Ошибка сетевого запроса к серверу при обогащении</div></div>';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-stars fs-5"></i> <span>Обогатить данные</span>';
                pArea.style.display = 'none';
            }
        }

        function filterTableByInn(inn) {
            document.getElementById('filterQuery').value = inn;
            filterLeads();
            const tableEl = document.getElementById('leadsTableCard');
            if (tableEl) tableEl.scrollIntoView({ behavior: 'smooth' });
        }

        function openOutreachForLead(leadId) {
            openLeadModal(leadId).then(() => {
                const triggerEl = document.querySelector('#modalTabs button[data-bs-target="#tabOutreach"]');
                if (triggerEl) {
                    const tab = new bootstrap.Tab(triggerEl);
                    tab.show();
                }
            });
        }

        function openCallScriptForLead(leadId) {
            openLeadModal(leadId).then(() => {
                const triggerEl = document.querySelector('#modalTabs button[data-bs-target="#tabCallScript"]');
                if (triggerEl) {
                    const tab = new bootstrap.Tab(triggerEl);
                    tab.show();
                }
            });
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
                        <div class="text-muted small mb-3">ИНН: <b>${data.inn}</b> | Домен: <b>${data.domain || 'Не указан'}</b> | Надежность: <b>${data.solvency_score}/100 (${data.risk_level})</b></div>
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
                    activeBatchTaskId = data.task_id;
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
                activeBatchTaskId = data.task_id;
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

                if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
                    clearInterval(interval);
                    badge.innerText = status.status === 'completed' ? 'Завершено' : (status.status === 'cancelled' ? 'Отменено' : 'Ошибка');
                    badge.className = status.status === 'completed' ? 'badge bg-success' : 'badge bg-danger';
                    await loadLeads();
                }
            }, 1200);
        }

        async function cancelActiveBatch() {
            if (!activeBatchTaskId) return;
            await fetch(`/api/batch/cancel/${activeBatchTaskId}`, { method: 'POST' });
            showToast('Задача отменена');
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

        async function runDeliverabilityAudit() {
            const dom = document.getElementById('toolDeliverDomain').value;
            const div = document.getElementById('deliverAuditResult');
            div.innerHTML = '<div class="spinner-border spinner-border-sm text-primary"></div> Проверка DNS записей...';

            const res = await fetch('/api/tools/deliverability', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ domain: dom })
            });
            const d = await res.json();
            const r = d.result;

            if (!r.valid) {
                div.innerHTML = `<div class="alert alert-danger py-2 mb-0">${r.error || 'Ошибка проверки'}</div>`;
                return;
            }

            div.innerHTML = `
                <div class="alert ${r.deliverability_score >= 70 ? 'alert-success' : 'alert-warning'} py-2 mb-0">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <b>Провайдер:</b> ${r.provider}
                        <span class="badge bg-primary">Score: ${r.deliverability_score}/100</span>
                    </div>
                    <div><b>MX:</b> ${r.has_mx ? '✓ Настроен' : '✗ Отсутствует'} | <b>SPF:</b> ${r.has_spf ? r.spf_qualifier : '✗ Отсутствует'}</div>
                    <div><b>DMARC:</b> ${r.has_dmarc ? r.dmarc_policy : '✗ Отсутствует'} | <b>DKIM:</b> ${r.has_dkim ? '✓ Настроен' : '—'}</div>
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
                        <div><b>E.164:</b> <code>${r.formatted}</code> | <b>Оператор:</b> ${r.carrier || 'Определен'}</div>
                        <div><b>Регион:</b> ${r.region || 'РФ'} | <b>Пояс:</b> ${r.timezone || 'MSK'} (местное: ${r.local_time})</div>
                        <div><b>Окно звонков:</b> ${r.is_calling_window ? '<span class="text-success fw-bold">✓ Рабочее время</span>' : '<span class="text-danger fw-bold">✗ Нерабочие часы</span>'}</div>
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
                        backgroundColor: ['#2563eb', '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 2. CRM Funnel Chart
            const crmLabels = Object.keys(stats.crm_funnel || {});
            const crmData = Object.values(stats.crm_funnel || {});

            if (chartCRMInstance) chartCRMInstance.destroy();
            const ctxCRM = document.getElementById('chartCRM').getContext('2d');
            chartCRMInstance = new Chart(ctxCRM, {
                type: 'bar',
                data: {
                    labels: crmLabels,
                    datasets: [{
                        label: 'Лидов в статусе',
                        data: crmData,
                        backgroundColor: '#6366f1'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 3. Regions Chart
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

            // 4. Industries Chart
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

        loadLeads();
    </script>
</body>
</html>
"""


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_TEMPLATE, status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)

