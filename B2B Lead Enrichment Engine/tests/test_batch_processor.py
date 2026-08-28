import pytest
import time
from batch_processor import BatchProcessor
from engine import EnrichmentEngine


@pytest.fixture
def batch_proc(tmp_path):
    db_file = str(tmp_path / "test_batch.db")
    eng = EnrichmentEngine(db_url=f"sqlite:///{db_file}")
    return BatchProcessor(eng)


def test_parse_csv_content(batch_proc):
    csv_bytes = b"inn,company_name\n7707083893,Sberbank\n7736207543,Yandex\n"
    items = batch_proc.parse_file_to_items(csv_bytes, "leads.csv")
    assert len(items) == 2
    assert "7707083893" in items
    assert "7736207543" in items


def test_batch_enrichment_execution(batch_proc):
    items = ["7707083893", "7736207543"]
    task_id = batch_proc.start_batch_enrichment(items, task_type="inn", scrape_web=False, verify_emails=False)
    assert task_id is not None

    # Ожидаем завершения фоновой задачи
    time.sleep(1.0)
    status = batch_proc.get_task_status(task_id)
    assert status is not None
    assert status["total_items"] == 2
    assert status["status"] in ("running", "completed")


def test_batch_cancel(batch_proc):
    items = ["7707083893", "7736207543", "7802849641"]
    task_id = batch_proc.start_batch_enrichment(items, task_type="inn", scrape_web=False, verify_emails=False)
    res = batch_proc.cancel_task(task_id)
    assert res is True
    status = batch_proc.get_task_status(task_id)
    assert status["status"] == "cancelled"
