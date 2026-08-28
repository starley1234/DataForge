import pytest
from fastapi.testclient import TestClient
from web_app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["database"] == "connected"


def test_metrics_endpoint():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "b2b_total_companies" in resp.text
    assert "b2b_total_leads" in resp.text
    assert "b2b_valid_emails" in resp.text


def test_stats_endpoint():
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_companies" in data
    assert "total_dms" in data
    assert "roles_breakdown" in data
    assert "crm_funnel" in data


def test_leads_list_and_filters():
    resp = client.get("/api/leads?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1


def test_tools_generate_email():
    resp = client.post("/api/tools/generate-email", json={
        "full_name": "Иванов Иван",
        "domain": "company.ru"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["permutations"]) > 0


def test_tools_verify_phone():
    resp = client.post("/api/tools/verify-phone", json={
        "phone": "+7 (495) 739-70-00"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["valid"] is True
    assert data["result"]["formatted"] == "+74957397000"
    assert data["result"]["timezone"] is not None


def test_tools_deliverability():
    resp = client.post("/api/tools/deliverability", json={
        "domain": "yandex.ru"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["valid"] is True
    assert "provider" in data["result"]
    assert "deliverability_score" in data["result"]


def test_manual_lead_create_and_flow():
    payload = {
        "inn": "7799001122",
        "company_name": 'ООО "ТестСервис API"',
        "website": "test-service.ru",
        "region": "г. Москва",
        "dm_full_name": "Николаев Сергей Михайлович",
        "dm_title": "Генеральный директор",
        "dm_role_level": "C-Level",
        "dm_email": "s.nikolaev@test-service.ru",
        "dm_phone": "+7 916 555-44-33"
    }
    resp = client.post("/api/leads/manual", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Проверяем появление в списке
    resp2 = client.get("/api/leads?q=7799001122")
    items = resp2.json()["items"]
    assert len(items) >= 1
    lead_id = items[0]["id"]

    # Проверка получения карточки
    resp_detail = client.get(f"/api/leads/{lead_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["dm_full_name"] == "Николаев Сергей Михайлович"

    # Проверка vCard для лида
    resp_vcf = client.get(f"/api/leads/{lead_id}/vcard")
    assert resp_vcf.status_code == 200
    assert "BEGIN:VCARD" in resp_vcf.text

    # Проверка обновления статуса
    resp_up = client.put(f"/api/leads/{lead_id}", json={
        "lead_status": "QUALIFIED",
        "notes": "Проведен демо-показ"
    })
    assert resp_up.status_code == 200

    # Проверка генерации драфта холодного письма
    resp_draft = client.post("/api/tools/outreach-draft", json={
        "lead_id": lead_id,
        "offer_type": "sales"
    })
    assert resp_draft.status_code == 200
    assert "Николаев" in resp_draft.json()["draft"]["body"] or "Сергей" in resp_draft.json()["draft"]["body"]

    # Проверка генерации скрипта холодного звонка
    resp_script = client.post("/api/tools/call-script", json={
        "lead_id": lead_id
    })
    assert resp_script.status_code == 200
    assert "gatekeeper_script" in resp_script.json()["script"]

    # Массовый статус
    resp_bulk = client.post("/api/leads/bulk-status", json={
        "lead_ids": [lead_id],
        "status": "MEETING_SCHEDULED"
    })
    assert resp_bulk.status_code == 200
    assert resp_bulk.json()["updated_count"] >= 1

    # Удаление
    resp_del = client.delete(f"/api/leads/{lead_id}")
    assert resp_del.status_code == 200


def test_export_endpoints():
    r_csv = client.get("/api/export/csv")
    assert r_csv.status_code == 200

    r_xlsx = client.get("/api/export/excel")
    assert r_xlsx.status_code == 200

    r_amo = client.get("/api/export/amocrm")
    assert r_amo.status_code == 200

    r_b24 = client.get("/api/export/bitrix24")
    assert r_b24.status_code == 200

    r_hub = client.get("/api/export/hubspot")
    assert r_hub.status_code == 200

    r_vcf = client.get("/api/export/vcard")
    assert r_vcf.status_code == 200

    r_json = client.get("/api/export/json")
    assert r_json.status_code == 200
