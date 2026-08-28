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


def test_stats_endpoint():
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_companies" in data
    assert "total_dms" in data


def test_leads_list_endpoint():
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


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
        "phone": "+7 495 739-70-00"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["valid"] is True


def test_tools_verify_email():
    resp = client.post("/api/tools/verify-email", json={
        "email": "test@mailinator.com"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["is_valid"] is False
