"""
Celery tasks for background email processing.
"""

import asyncio
import logging
from typing import Any, Dict, List

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="email_reminders.persist_pipeline_results",
    max_retries=3,
)
def persist_pipeline_results_task(
    self: Any,
    email: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Persist processed email results in a separate worker task."""
    try:
        from app.agent.pipeline import persist_pipeline_results

        persist_pipeline_results(email, results)
        return {
            "email": email,
            "persisted_result_count": len(results),
        }
    except Exception as exc:
        logger.exception(
            "persist_pipeline_results_task_failed",
            extra={
                "email": email,
                "result_count": len(results),
                "retry_count": self.request.retries,
            },
        )
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(
    bind=True,
    name="email_reminders.process_gmail_notification",
    max_retries=3,
)
def process_gmail_notification_task(
    self: Any,
    notification: Dict[str, str],
) -> Dict[str, Any]:
    """Process one Gmail Pub/Sub notification in a worker process."""
    try:
        from app.service.gmail_push import process_gmail_notification

        return asyncio.run(process_gmail_notification(notification))
    except Exception as exc:
        logger.exception(
            "process_gmail_notification_task_failed",
            extra={
                "email": notification.get("emailAddress"),
                "history_id": notification.get("historyId"),
                "retry_count": self.request.retries,
            },
        )
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    bind=True,
    name="email_reminders.run_pipeline_for_message_ids",
    max_retries=3,
)
def run_pipeline_for_message_ids_task(
    self: Any,
    email: str,
    message_ids: List[str],
) -> Dict[str, Any]:
    """Run the email processing pipeline for exact Gmail message IDs."""
    try:
        from app.agent.pipeline import run_pipeline_for_message_ids

        return asyncio.run(run_pipeline_for_message_ids(email, message_ids))
    except Exception as exc:
        logger.exception(
            "run_pipeline_for_message_ids_task_failed",
            extra={
                "email": email,
                "message_ids": message_ids,
                "retry_count": self.request.retries,
            },
        )
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="email_reminders.renew_gmail_watches")
def renew_gmail_watches_task() -> Dict[str, Any]:
    """Renew the Gmail Pub/Sub watch for every connected account.

    Gmail watches expire exactly 7 days after they are registered, with no
    way to request a longer TTL, and Gmail never renews one on its own. This
    runs on a schedule (see celery_app.py beat_schedule) well inside that
    window so no connected account's watch is ever allowed to lapse.
    """
    from app.core.database import list_connected_gmail_emails
    from app.service.gmail_push import start_gmail_watch

    renewed: List[str] = []
    failed: List[Dict[str, str]] = []
    for email in list_connected_gmail_emails():
        try:
            asyncio.run(start_gmail_watch(email))
            renewed.append(email)
        except Exception as exc:
            logger.exception(
                "gmail_watch_renewal_failed",
                extra={"email": email},
            )
            failed.append({"email": email, "error": str(exc)})

    if failed:
        logger.warning(
            "gmail_watch_renewal_completed_with_failures",
            extra={"renewed_count": len(renewed), "failed_count": len(failed)},
        )

    return {"renewed": renewed, "failed": failed}
