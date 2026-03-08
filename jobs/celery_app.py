"""
celery_app.py — Celery application instance for ExamAI.

Start the worker:
    python -m jobs worker
    # or directly:
    celery -A jobs.celery_app worker --pool=threads --concurrency=3 -l info
"""

from celery import Celery
from jobs.config import REDIS_URL

app = Celery(
    "examai",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,            # report STARTED state to backend
    worker_prefetch_multiplier=1,       # fair scheduling across chains
    task_acks_late=True,                # ack after completion (crash safety)
    task_reject_on_worker_lost=True,    # re-queue if worker crashes mid-task

    # Results
    result_expires=86400,               # keep results for 24 hours

    # Task discovery
    imports=["jobs.tasks"],
)
