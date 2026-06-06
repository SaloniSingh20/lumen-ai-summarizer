"""Celery application factory."""
from celery import Celery
from ..app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "video_summarizer",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["worker.tasks"],
)

import ssl as _ssl
_ssl_opts = {"ssl_cert_reqs": _ssl.CERT_NONE}

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_use_ssl=_ssl_opts,
    redis_backend_use_ssl=_ssl_opts,
)
