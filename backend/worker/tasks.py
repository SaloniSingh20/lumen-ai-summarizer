"""Celery tasks — use absolute imports (top-level packages from backend/)."""
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# Read config before creating the app so env vars are loaded
import os
_broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "video_summarizer",
    broker=_broker,
    backend=_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@celery_app.task(bind=True, name="worker.tasks.process_video_task", max_retries=1)
def process_video_task(self, job_id: str, video_id: str):
    """Main Celery task: run the full video processing pipeline."""
    from app.database import SessionLocal
    from app.pipeline.runner import run_pipeline

    db = SessionLocal()
    try:
        logger.info(f"Starting pipeline for job {job_id}, video {video_id}")
        run_pipeline(job_id, video_id, db)
        logger.info(f"Pipeline complete for job {job_id}")
    except Exception as exc:
        logger.exception(f"Pipeline task failed for job {job_id}: {exc}")
        raise
    finally:
        db.close()
