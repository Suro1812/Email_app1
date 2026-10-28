"""
Celery application for durable background email-processing jobs.
"""

import os

from celery import Celery
from celery.signals import worker_init, worker_ready

from app.logging_config import configure_logging
from app.observability import (
    prepare_multiprocess_dir,
    start_metrics_pusher,
    start_worker_metrics_server,
)


configure_logging()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "email_reminders",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    result_serializer="json",
    task_acks_late=True,
    task_default_queue=os.getenv("CELERY_DEFAULT_QUEUE", "email-processing"),
    task_reject_on_worker_lost=True,
    task_serializer="json",
    task_time_limit=_int_env("CELERY_TASK_TIME_LIMIT", 1800),
    task_soft_time_limit=_int_env("CELERY_TASK_SOFT_TIME_LIMIT", 1500),
    timezone=os.getenv("CELERY_TIMEZONE", "UTC"),
    worker_concurrency=_int_env("CELERY_WORKER_CONCURRENCY", 4),
    worker_hijack_root_logger=False,
    worker_prefetch_multiplier=_int_env("CELERY_WORKER_PREFETCH_MULTIPLIER", 1),
    beat_schedule={
        "renew-gmail-watches": {
            "task": "email_reminders.renew_gmail_watches",
            # Gmail watches expire 7 days after registration with no way to
            # extend that window. Renewing every 24h keeps every connected
            # account's watch from ever getting within days of lapsing.
            "schedule": _int_env("GMAIL_WATCH_RENEWAL_INTERVAL_SECONDS", 24 * 60 * 60),
        },
    },
)


@worker_init.connect
def _prepare_worker_metrics(**_kwargs) -> None:
    """Clear stale mmap files before the prefork pool spawns its children."""
    prepare_multiprocess_dir()


@worker_ready.connect
def _start_worker_metrics(**_kwargs) -> None:
    """Start the exporter after the pool has forked.

    Binding in worker_init instead would leak the listening socket into every
    forked child.
    """
    start_worker_metrics_server()
    # Reads the same multiprocess-aggregated registry as the exporter above,
    # so this is additive, not a replacement — it only does anything when
    # PUSHGATEWAY_URL is set (the ACA-over-ngrok case), and is a no-op here
    # in ordinary local/compose runs where the exporter is already scrapeable.
    start_metrics_pusher("worker")
