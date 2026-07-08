"""
Celery application configuration for background task workers.

Run a worker:
    celery -A celery_app worker --loglevel=info

Run the beat scheduler:
    celery -A celery_app beat --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from config import settings

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app: Celery = Celery("tradeforge")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=1500,
    result_expires=86400,
    beat_schedule={
        "daily-market-ingest": {
            "task": "tasks.market_data.daily_ingest",
            "schedule": 60 * 60 * 6,  # every 6 hours
        },
        "generate-signals-every-minute": {
            "task": "tasks.execution.generate_signals",
            "schedule": 60,  # every 60 seconds
        },
        "run-auto-training": {
            "task": "tasks.training.run_training_cycle",
            "schedule": settings.TRAINING_INTERVAL_MINUTES * 60,  # default 20 min
        },
    },
)

# Auto-discover tasks from the tasks package.
celery_app.autodiscover_tasks(["tasks"])
