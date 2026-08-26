from celery import Celery
from app.config import get_settings

settings = get_settings()

# creating celery app
# 1st arg: name of curr module- for autonaming tasks

celery_app = Celery(
    "incident_whisperer",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_pool="solo",  # ← add this
)

# tell celery where to find tasks
celery_app.autodiscover_tasks([
    "app.workers.tasks",
])