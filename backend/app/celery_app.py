from celery import Celery
from .config import config

celery_app = Celery(
    "audio_webapp",
    broker=config.celery.broker_url,
    backend=config.celery.result_backend,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Single worker process avoids SQLite write contention
    worker_concurrency=1,
)
