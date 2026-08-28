import pytest
import time
from fastapi.testclient import TestClient
from core.engine import EnrichmentEngine
from core.nationwide_harvester import NationwideHarvester, RUSSIAN_REGIONS, RUSSIAN_INDUSTRIES
from web_app import app

client = TestClient(app)


def test_nationwide_constants():
    """Проверка наличия всех 89 субъектов РФ и секторов экономики."""
    assert len(RUSSIAN_REGIONS) >= 89
    assert len(RUSSIAN_INDUSTRIES) >= 10
    region_codes = {r["code"] for r in RUSSIAN_REGIONS}
    assert "77" in region_codes  # Москва
    assert "78" in region_codes  # Санкт-Петербург
    assert "23" in region_codes  # Краснодарский край
    assert "16" in region_codes  # Татарстан
    assert "66" in region_codes  # Свердловская обл.


def test_nationwide_harvester_lifecycle():
    """Проверка старта, сбора организаций, паузы, возобновления и остановки."""
    test_db_path = "/tmp/test_harvester_nw.db"
    import os
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    test_engine = EnrichmentEngine(db_url=f"sqlite:///{test_db_path}")
    harvester = NationwideHarvester(engine=test_engine)

    # 1. Запуск
    started = harvester.start(region_code="77", industry_keyword="Информационные технологии", max_limit=10)
    assert started is True
    assert harvester.is_running is True

    # Ждем сбора хотя бы нескольких компаний
    time.sleep(2)

    status = harvester.get_status()
    assert status["is_running"] is True
    assert status["total_harvested_session"] >= 1
    assert len(status["recent_companies"]) >= 1

    # 2. Пауза
    harvester.pause()
    assert harvester.is_paused is True
    paused_status = harvester.get_status()
    assert paused_status["is_paused"] is True

    # 3. Возобновление
    harvester.resume()
    assert harvester.is_paused is False

    # 4. Остановка
    harvester.stop()
    assert harvester.is_running is False
    final_status = harvester.get_status()
    assert final_status["is_running"] is False


def test_nationwide_api_endpoints():
    """Тестирование REST API эндпоинтов автопоиска по всей РФ."""
    # Получение регионов
    resp_r = client.get("/api/nationwide/regions")
    assert resp_r.status_code == 200
    regions = resp_r.json()
    assert len(regions) >= 89

    # Получение отраслей
    resp_i = client.get("/api/nationwide/industries")
    assert resp_i.status_code == 200
    industries = resp_i.json()
    assert len(industries) >= 10

    # Статус
    resp_s = client.get("/api/nationwide/status")
    assert resp_s.status_code == 200
    status = resp_s.json()
    assert "is_running" in status
    assert "total_harvested_session" in status

    # Запуск
    resp_start = client.post("/api/nationwide/start", json={"region": "77", "industry": "Финансы", "limit": 5})
    assert resp_start.status_code == 200
    assert resp_start.json()["is_running"] is True

    time.sleep(1)

    # Пауза
    resp_pause = client.post("/api/nationwide/pause")
    assert resp_pause.status_code == 200
    assert resp_pause.json()["is_paused"] is True

    # Возобновление
    resp_resume = client.post("/api/nationwide/resume")
    assert resp_resume.status_code == 200
    assert resp_resume.json()["is_paused"] is False

    # Остановка
    resp_stop = client.post("/api/nationwide/stop")
    assert resp_stop.status_code == 200
    assert resp_stop.json()["is_running"] is False
