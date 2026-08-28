import io
import json
import uuid
import logging
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import pandas as pd
from models import BatchTaskORM, init_db
from config import settings

logger = logging.getLogger("batch_processor")


class BatchProcessor:
    def __init__(self, engine_instance):
        self.engine = engine_instance
        self.executor = ThreadPoolExecutor(max_workers=settings.BATCH_CONCURRENCY)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cancelled_tasks = set()

    def parse_file_to_items(self, file_bytes: bytes, filename: str) -> List[str]:
        """Извлекает список ИНН или поисковых запросов из загруженного CSV или Excel."""
        items: List[str] = []
        try:
            if filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
                except Exception:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding="cp1251")

            target_col = None
            for col in df.columns:
                c_clean = str(col).lower().strip()
                if any(k in c_clean for k in ["инн", "inn", "огрн", "ogrn", "организация", "компания", "наименование", "домен", "domain", "сайт"]):
                    target_col = col
                    break

            if target_col is not None:
                series = df[target_col].dropna().astype(str)
                items = [s.strip() for s in series if s.strip() and s.strip().lower() != "nan"]
            else:
                first_col = df.columns[0]
                series = df[first_col].dropna().astype(str)
                items = [s.strip() for s in series if s.strip() and s.strip().lower() != "nan"]
        except Exception as e:
            logger.error(f"Ошибка парсинга файла {filename}: {e}")

        return items[:settings.BATCH_MAX_ITEMS]

    def cancel_task(self, task_id: str) -> bool:
        """Отмена выполнения задачи."""
        with self._lock:
            if task_id in self.tasks:
                self._cancelled_tasks.add(task_id)
                self.tasks[task_id]["status"] = "cancelled"
                return True
        return False

    def start_batch_enrichment(
        self,
        items: List[str],
        task_type: str = "inn",
        scrape_web: bool = True,
        verify_emails: bool = True
    ) -> str:
        """Создает задачу пакетного обогащения и запускает ее в фоне."""
        task_id = str(uuid.uuid4())
        clean_items = list(dict.fromkeys([it.strip() for it in items if it and it.strip()]))[:settings.BATCH_MAX_ITEMS]

        task_info = {
            "id": task_id,
            "task_type": task_type,
            "status": "running",
            "total_items": len(clean_items),
            "processed_items": 0,
            "success_items": 0,
            "failed_items": 0,
            "progress_percent": 0.0,
            "speed_per_sec": 0.0,
            "created_at": datetime.utcnow(),
            "finished_at": None,
            "error_log": None,
            "results": []
        }

        with self._lock:
            self.tasks[task_id] = task_info

        session = self.engine.SessionFactory()
        try:
            db_task = BatchTaskORM(
                id=task_id,
                task_type=task_type,
                status="running",
                total_items=len(clean_items),
                processed_items=0,
                success_items=0,
                failed_items=0,
                progress_percent=0.0,
                created_at=datetime.utcnow()
            )
            session.add(db_task)
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения задачи {task_id} в БД: {e}")
        finally:
            session.close()

        self.executor.submit(
            self._process_batch_job,
            task_id,
            clean_items,
            task_type,
            scrape_web,
            verify_emails
        )

        return task_id

    def _process_batch_job(
        self,
        task_id: str,
        items: List[str],
        task_type: str,
        scrape_web: bool,
        verify_emails: bool
    ):
        logger.info(f"Старт пакетной обработки задачи {task_id}: {len(items)} элементов")
        errors = []
        start_time = time.time()

        for idx, item in enumerate(items, start=1):
            with self._lock:
                if task_id in self._cancelled_tasks:
                    logger.info(f"Задача {task_id} была отменена пользователем.")
                    break

            success = False
            try:
                if task_type == "domain":
                    comp = self.engine.enrich_by_domain(item, verify_emails=verify_emails)
                else:
                    comp = self.engine.fetch_and_enrich(item, scrape_web=scrape_web, verify_emails=verify_emails)

                if comp:
                    success = True
                    with self._lock:
                        self.tasks[task_id]["results"].append({
                            "query": item,
                            "company_name": comp.name,
                            "inn": comp.inn,
                            "dms_count": len(comp.decision_makers),
                            "solvency_score": comp.solvency_score
                        })
                else:
                    errors.append(f"Не найдено: {item}")
            except Exception as e:
                err_msg = f"Ошибка при обработке {item}: {e}"
                logger.warning(err_msg)
                errors.append(err_msg)

            elapsed = max(0.1, time.time() - start_time)
            speed = round(idx / elapsed, 2)

            with self._lock:
                task = self.tasks[task_id]
                task["processed_items"] = idx
                if success:
                    task["success_items"] += 1
                else:
                    task["failed_items"] += 1
                task["progress_percent"] = round((idx / len(items)) * 100, 1)
                task["speed_per_sec"] = speed

        now = datetime.utcnow()
        with self._lock:
            task = self.tasks[task_id]
            if task["status"] != "cancelled":
                task["status"] = "completed"
            task["finished_at"] = now
            task["error_log"] = "\n".join(errors) if errors else None

        session = self.engine.SessionFactory()
        try:
            db_task = session.query(BatchTaskORM).filter_by(id=task_id).first()
            if db_task:
                db_task.status = task["status"]
                db_task.processed_items = task["processed_items"]
                db_task.success_items = task["success_items"]
                db_task.failed_items = task["failed_items"]
                db_task.progress_percent = task["progress_percent"]
                db_task.finished_at = now
                db_task.error_log = task["error_log"]
                db_task.results_summary = json.dumps(task["results"][:50], ensure_ascii=False)
                session.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления статуса задачи в БД: {e}")
        finally:
            session.close()

        logger.info(f"Завершена пакетная обработка задачи {task_id}: {task['success_items']} успешно, {task['failed_items']} ошибок")

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает статус выполнения задачи из оперативной памяти или БД."""
        with self._lock:
            if task_id in self.tasks:
                return dict(self.tasks[task_id])

        session = self.engine.SessionFactory()
        try:
            db_task = session.query(BatchTaskORM).filter_by(id=task_id).first()
            if db_task:
                progress = db_task.progress_percent or 0.0
                if db_task.total_items > 0 and progress == 0.0:
                    progress = round((db_task.processed_items / db_task.total_items) * 100, 1)
                return {
                    "id": db_task.id,
                    "task_type": db_task.task_type,
                    "status": db_task.status,
                    "total_items": db_task.total_items,
                    "processed_items": db_task.processed_items,
                    "success_items": db_task.success_items,
                    "failed_items": db_task.failed_items,
                    "progress_percent": progress,
                    "created_at": db_task.created_at,
                    "finished_at": db_task.finished_at,
                    "error_log": db_task.error_log,
                    "results": []
                }
        finally:
            session.close()
        return None
