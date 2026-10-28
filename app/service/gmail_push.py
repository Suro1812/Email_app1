import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from app.service.get_messages import filter_primary_inbox_message_ids, get_gmail_service

logger = logging.getLogger(__name__)


class GmailPubSubNotification(TypedDict):
    emailAddress: str
    historyId: str


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _topic_name(topic_name: Optional[str] = None) -> str:
    resolved = topic_name or os.getenv("GMAIL_PUBSUB_TOPIC", "")
    if not resolved:
        raise RuntimeError("Missing GMAIL_PUBSUB_TOPIC environment variable.")
    return resolved


def _pubsub_audience() -> str:
    audience = os.getenv("GMAIL_PUBSUB_AUDIENCE", os.getenv("PUBSUB_AUDIENCE", ""))
    if not audience:
        raise RuntimeError("Missing GMAIL_PUBSUB_AUDIENCE environment variable.")
    return audience


def _verify_google_id_token(token: str, audience: str) -> Dict[str, Any]:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, Request(), audience)


def verify_pubsub_push_token(authorization_header: Optional[str]) -> Dict[str, Any]:
    if not _env_flag("GMAIL_PUBSUB_VERIFY_TOKEN", default=True):
        return {}

    if not authorization_header:
        raise ValueError("Missing Authorization header.")

    prefix = "Bearer "
    if not authorization_header.startswith(prefix):
        raise ValueError("Authorization header must be a Bearer token.")

    token = authorization_header[len(prefix):].strip()
    if not token:
        raise ValueError("Authorization Bearer token is empty.")

    claims = _verify_google_id_token(token, _pubsub_audience())
    issuer = claims.get("iss")
    if issuer not in {"https://accounts.google.com", "accounts.google.com"}:
        raise ValueError("Pub/Sub token has an invalid issuer.")

    allowed_email = os.getenv("GMAIL_PUBSUB_SERVICE_ACCOUNT", "")
    if allowed_email and claims.get("email") != allowed_email:
        raise ValueError("Pub/Sub token service account is not allowed.")

    if allowed_email and claims.get("email_verified") is not True:
        raise ValueError("Pub/Sub token service account email is not verified.")

    return claims


def decode_pubsub_push(payload: Dict[str, Any]) -> GmailPubSubNotification:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Pub/Sub push payload must include a message object.")

    encoded_data = message.get("data")
    if not encoded_data:
        raise ValueError("Pub/Sub message must include base64 data.")

    try:
        raw_data = base64.b64decode(encoded_data).decode("utf-8")
        decoded = json.loads(raw_data)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Pub/Sub message data must be base64-encoded JSON.") from exc

    email = decoded.get("emailAddress")
    history_id = decoded.get("historyId")
    if not email or not history_id:
        raise ValueError("Gmail notification must include emailAddress and historyId.")

    return {"emailAddress": str(email), "historyId": str(history_id)}


def _expiration_from_millis(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def save_gmail_watch_state(
    email: str,
    history_id: Optional[str],
    expiration: Any = None,
) -> None:
    from app.core.database import GmailUser, SessionLocal

    db = SessionLocal()
    try:
        user = db.query(GmailUser).filter(GmailUser.email == email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {email}")

        if history_id:
            user.gmail_history_id = str(history_id)
        parsed_expiration = _expiration_from_millis(expiration)
        if parsed_expiration:
            user.gmail_watch_expiration = parsed_expiration
        user.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_last_gmail_history_id(email: str) -> Optional[str]:
    from app.core.database import GmailUser, SessionLocal

    db = SessionLocal()
    try:
        user = db.query(GmailUser).filter(GmailUser.email == email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {email}")
        if not user.gmail_history_id:
            raise ValueError(f"No active Gmail watch found for {email}")
        return user.gmail_history_id
    finally:
        db.close()


async def start_gmail_watch(
    email: str,
    topic_name: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    service = await get_gmail_service(email=email)
    body = {
        "topicName": _topic_name(topic_name),
        "labelIds": label_ids or ["INBOX"],
    }

    response = await asyncio.to_thread(
        service.users().watch(userId="me", body=body).execute
    )
    save_gmail_watch_state(
        email=email,
        history_id=response.get("historyId"),
        expiration=response.get("expiration"),
    )
    return response


async def list_changed_message_ids(email: str, start_history_id: str) -> List[str]:
    service = await get_gmail_service(email=email)
    message_ids = set()
    page_token = None

    while True:
        request = service.users().history().list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],
            labelId="INBOX",
            pageToken=page_token,
        )
        response = await asyncio.to_thread(request.execute)

        for history in response.get("history", []):
            for added in history.get("messagesAdded", []):
                message = added.get("message", {})
                message_id = message.get("id")
                if message_id:
                    message_ids.add(str(message_id))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return list(message_ids)


async def process_gmail_notification(notification: GmailPubSubNotification) -> Dict[str, Any]:
    email = notification["emailAddress"]
    history_id = notification["historyId"]
    try:
        previous_history_id = get_last_gmail_history_id(email)
    except ValueError as exc:
        if "No active Gmail watch" not in str(exc):
            raise

        save_gmail_watch_state(email=email, history_id=history_id)
        logger.warning(
            "gmail_notification_missing_watch_baseline_established",
            extra={"email": email, "history_id": history_id},
        )
        return {
            "email": email,
            "history_id": history_id,
            "previous_history_id": None,
            "changed_message_ids": [],
            "analysis": {
                "status": "baseline_established",
                "processed_message_count": 0,
                "reason": str(exc),
            },
        }

    changed_message_ids: List[str] = []
    if previous_history_id:
        changed_message_ids = await list_changed_message_ids(email, previous_history_id)
        changed_message_ids = await filter_primary_inbox_message_ids(email, changed_message_ids)

    if changed_message_ids:
        from app.core.database import mark_messages_analysis_queued

        mark_messages_analysis_queued(email, changed_message_ids)

    from app.agent.pipeline import run_pipeline_for_message_ids

    result = await run_pipeline_for_message_ids(email, changed_message_ids)
    save_gmail_watch_state(email=email, history_id=history_id)

    return {
        "email": email,
        "history_id": history_id,
        "previous_history_id": previous_history_id,
        "changed_message_ids": changed_message_ids,
        "analysis": result,
    }
