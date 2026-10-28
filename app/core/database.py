"""
Database models for storing user Gmail credentials and analyzed messages.
"""

import json
import os
import re
import secrets
from datetime import date as DateType, datetime, time as TimeType, timedelta
from email.utils import parsedate_to_datetime, parseaddr
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import Boolean
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlmodel import Field, Session, SQLModel, create_engine


Base = SQLModel


def _clean_display_text(value: Any) -> str:
    return re.sub(r"</?external_source>", "", str(value or "")).strip()


class GmailUser(SQLModel, table=True):
    """Store user Gmail credentials in database."""
    __tablename__: ClassVar[str] = "gmail_users"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True))
    email: str = Field(sa_column=Column(String(255), unique=True, nullable=False))
    refresh_token: str = Field(sa_column=Column(Text, nullable=False))  # Store securely (consider encryption)
    access_token: str = Field(sa_column=Column(Text, nullable=False))
    token_expiry: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    gmail_history_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    gmail_watch_expiration: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow))

    def __repr__(self):
        return f"<GmailUser {self.email}>"


class GmailUserSession(SQLModel, table=True):
    """Server-side browser session bound to one Gmail user."""

    __tablename__: ClassVar[str] = "gmail_user_sessions"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True))
    session_id: str = Field(sa_column=Column(String(255), unique=True, nullable=False, index=True))
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("gmail_users.id"), nullable=False, index=True))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow))
    expires_at: datetime = Field(sa_column=Column(DateTime, nullable=False))
    revoked_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))


class EmailMessageReminder(SQLModel, table=True):
    """Store analyzed Gmail message metadata."""

    __tablename__: ClassVar[str] = "email_message_reminders"
    __table_args__: ClassVar[tuple] = (
        UniqueConstraint("user_id", "message_id", name="uq_email_reminder_user_message"),
    )

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True))
    message_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    summarized_subject: str = Field(default="", sa_column=Column(String(500), nullable=False, default=""))
    summarized_body: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    message_date: Optional[DateType] = Field(default=None, sa_column=Column(Date, nullable=True))
    message_time: Optional[TimeType] = Field(default=None, sa_column=Column(Time, nullable=True))
    reply_subject: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    reply_body: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("gmail_users.id"), nullable=False, index=True))
    from_address: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    to_address: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    processing_status: str = Field(default="pending", sa_column=Column(String(50), nullable=False, default="pending"))
    skip_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    detected_intent: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    action_items_json: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    deadline: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    reply_needed: Optional[bool] = Field(default=None, sa_column=Column(Boolean, nullable=True))
    reply_status: str = Field(default="pending", sa_column=Column(String(50), nullable=False, default="pending"))
    suggested_reply: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    llm_summary_tokens_input: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    llm_summary_tokens_output: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    llm_reply_tokens_input: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    llm_reply_tokens_output: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    prompt_cache_hit: Optional[bool] = Field(default=None, sa_column=Column(Boolean, nullable=True))
    calendar_event_detected: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    calendar_event_title: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    calendar_event_start_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    calendar_event_end_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    calendar_event_location: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    calendar_event_source: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    calendar_event_uid: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    calendar_event_organizer: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    calendar_event_status: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    calendar_notification_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    calendar_notification_sent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow))

    def __repr__(self):
        return f"<EmailMessageReminder {self.message_id}>"


def parse_message_datetime(date_value: str) -> Tuple[Optional[DateType], Optional[TimeType]]:
    """Parse Gmail's Date header into separate date and time values."""
    if not date_value:
        return None, None

    try:
        parsed = parsedate_to_datetime(str(date_value))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None, None

    return parsed.date(), parsed.time().replace(tzinfo=None)


def parse_calendar_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _calendar_event_payload(record: EmailMessageReminder) -> Optional[Dict[str, Any]]:
    if not record.calendar_event_detected or not record.calendar_event_start_at:
        return None
    return {
        "title": record.calendar_event_title or record.summarized_subject or "Email event",
        "start_at": record.calendar_event_start_at.isoformat(),
        "end_at": record.calendar_event_end_at.isoformat() if record.calendar_event_end_at else None,
        "location": record.calendar_event_location,
        "event_kind": record.detected_intent or "calendar_event",
        "source": record.calendar_event_source,
        "uid": record.calendar_event_uid,
        "organizer": record.calendar_event_organizer,
        "status": record.calendar_event_status,
        "notification_at": (
            record.calendar_notification_at.isoformat()
            if record.calendar_notification_at
            else None
        ),
        "notification_sent": bool(record.calendar_notification_sent),
    }


def _clear_calendar_event(record: EmailMessageReminder) -> None:
    record.calendar_event_detected = False
    record.calendar_event_title = None
    record.calendar_event_start_at = None
    record.calendar_event_end_at = None
    record.calendar_event_location = None
    record.calendar_event_source = None
    record.calendar_event_uid = None
    record.calendar_event_organizer = None
    record.calendar_event_status = None
    record.calendar_notification_at = None
    record.calendar_notification_sent = False


def _apply_calendar_event(record: EmailMessageReminder, analyzer_result: Dict[str, Any]) -> None:
    event = analyzer_result.get("calendar_event")
    if not isinstance(event, dict) or not event.get("detected"):
        _clear_calendar_event(record)
        return

    start_at = parse_calendar_datetime(event.get("start_at"))
    if not start_at:
        _clear_calendar_event(record)
        return

    end_at = parse_calendar_datetime(event.get("end_at"))
    notify_minutes = int(event.get("notification_minutes_before") or 15)
    notify_minutes = max(0, min(notify_minutes, 1440))
    record.calendar_event_detected = True
    record.detected_intent = str(event.get("event_kind") or "calendar_event").strip() or "calendar_event"
    record.calendar_event_title = str(event.get("title") or record.summarized_subject or "Email event")[:500]
    record.calendar_event_start_at = start_at
    record.calendar_event_end_at = end_at if end_at and end_at >= start_at else None
    record.calendar_event_location = str(event.get("location") or "").strip() or None
    record.calendar_event_source = str(event.get("source") or "").strip()[:50] or None
    record.calendar_event_uid = str(event.get("uid") or "").strip()[:255] or None
    record.calendar_event_organizer = str(event.get("organizer") or "").strip() or None
    record.calendar_event_status = str(event.get("status") or "").strip()[:50] or None
    record.calendar_notification_at = start_at - timedelta(minutes=notify_minutes)
    record.calendar_notification_sent = False


def _analyzer_reminder_deadline(analyzer_result: Dict[str, Any]) -> Optional[str]:
    start_date = str(analyzer_result.get("start_date") or "").strip()
    start_time = str(analyzer_result.get("start_time") or "").strip()
    if start_time.lower() in {"", "none", "null"}:
        start_time = ""
    if start_date and start_time:
        return f"{start_date} {start_time}"
    return start_date or None


def _analyzer_action_items(analyzer_result: Dict[str, Any]) -> List[str]:
    title = str(analyzer_result.get("title") or "").strip()
    description = str(analyzer_result.get("description") or "").strip()
    if title:
        return [title]
    if description:
        return [description]
    return []


def save_analyzed_messages(
    user_email: str,
    messages: List[Dict[str, Any]],
    analysis_decisions: Dict[str, Any],
):
    """Upsert analyzed Gmail messages into PostgreSQL."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        decisions = analysis_decisions.get("emails", [])
        saved = []

        for index, message in enumerate(messages):
            message_id = message.get("id")
            if not message_id:
                continue

            decision = decisions[index] if index < len(decisions) else {}
            message_date, message_time = parse_message_datetime(str(message.get("date", "")))

            record = (
                db.query(EmailMessageReminder)
                .filter(
                    EmailMessageReminder.user_id == user.id,
                    EmailMessageReminder.message_id == message_id,
                )
                .first()
            )

            if not record:
                record = EmailMessageReminder(
                    user_id=user.id,
                    message_id=message_id,
                )
                db.add(record)

            record.summarized_subject = str(
                decision.get("summarized_subject") or message.get("subject", "")
            )
            record.summarized_body = str(decision.get("summarized_body") or "")
            record.message_date = message_date
            record.message_time = message_time
            record.from_address = message.get("from", "")
            record.to_address = message.get("to", "")
            reply_body = str(decision.get("reply_body") or "").strip()
            record.reply_subject = (
                str(decision.get("reply_subject") or f"Re: {message.get('subject', '')}")
                if reply_body
                else None
            )
            record.reply_body = reply_body or None
            saved.append(record)

        db.commit()
        return saved


def _get_or_create_message_record(db: Any, user: GmailUser, message_id: str) -> EmailMessageReminder:
    if not message_id:
        raise ValueError("Cannot save email processing result without message id.")

    record = (
        db.query(EmailMessageReminder)
        .filter(
            EmailMessageReminder.user_id == user.id,
            EmailMessageReminder.message_id == str(message_id),
        )
        .first()
    )
    if record:
        return record

    record = EmailMessageReminder(user_id=user.id, message_id=str(message_id))
    db.add(record)
    return record


def _apply_message_metadata(record: EmailMessageReminder, message: Dict[str, Any]) -> None:
    message_date, message_time = parse_message_datetime(str(message.get("date", "")))
    record.message_date = message_date
    record.message_time = message_time
    record.from_address = message.get("from", "")
    record.to_address = message.get("to", "")
    record.summarized_subject = str(
        message.get("summarized_subject") or message.get("subject", "")
    )


def _save_with_user(
    user_email: str,
    message_id: str,
    message: Dict[str, Any],
    apply_result: Any,
) -> EmailMessageReminder:
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        record = _get_or_create_message_record(db, user, message_id)
        _apply_message_metadata(record, message)
        apply_result(record)
        record.updated_at = datetime.utcnow()
        db.commit()
        return record


def save_email_processing_result(
    user_email: str,
    message: Dict[str, Any],
    processing_status: str,
    skip_reason: Optional[str] = None,
    reply_status: str = "pending",
) -> EmailMessageReminder:
    """Save a deterministic processing decision for one Gmail message."""

    def apply_result(record: EmailMessageReminder) -> None:
        record.processing_status = processing_status
        record.skip_reason = skip_reason
        record.reply_status = reply_status
        if processing_status == "skipped":
            record.reply_needed = False
        elif processing_status == "not_analyzed":
            record.reply_needed = None

    return _save_with_user(user_email, message.get("id"), message, apply_result)


def mark_messages_analysis_queued(user_email: str, message_ids: List[str]) -> List[str]:
    """Create/update records for Gmail messages waiting for AnalyzerAgent.

    Returns only the message IDs that should be queued now. Duplicate calls for
    messages that are already being analyzed are ignored until they are stale.
    """
    clean_ids = []
    seen_ids = set()
    for message_id in message_ids:
        clean_id = str(message_id or "").strip()
        if clean_id and clean_id not in seen_ids:
            clean_ids.append(clean_id)
            seen_ids.add(clean_id)
    if not clean_ids:
        return []

    requeue_after_seconds = _int_env("ANALYSIS_REQUEUE_AFTER_SECONDS", 30 * 60)

    def apply_marks() -> List[str]:
        with SessionLocal() as db:
            user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
            if not user:
                raise ValueError(f"No Gmail user found for {user_email}")

            existing_records = (
                db.query(EmailMessageReminder)
                .filter(
                    EmailMessageReminder.user_id == user.id,
                    EmailMessageReminder.message_id.in_(clean_ids),
                )
                .all()
            )
            records_by_message_id = {
                str(record.message_id): record for record in existing_records
            }

            now = datetime.utcnow()
            queue_ids: List[str] = []
            for message_id in clean_ids:
                record = records_by_message_id.get(message_id)
                if not record:
                    record = EmailMessageReminder(user_id=user.id, message_id=message_id)
                    db.add(record)
                    records_by_message_id[message_id] = record

                status = str(record.processing_status or "").lower()
                if status in {"analyzed", "summarized", "reply_generated", "skipped"}:
                    continue
                if status == "not_analyzed" and record.skip_reason == "no_date_time_expression_detected":
                    continue
                if status == "analyzing" and record.updated_at:
                    elapsed_seconds = (now - record.updated_at).total_seconds()
                    if elapsed_seconds < requeue_after_seconds:
                        continue

                record.processing_status = "analyzing"
                record.skip_reason = None
                record.updated_at = now
                queue_ids.append(message_id)

            db.commit()
            return queue_ids

    try:
        return apply_marks()
    except IntegrityError:
        return apply_marks()


def save_analyzer_result(
    user_email: str,
    message: Dict[str, Any],
    analyzer_result: Dict[str, Any],
) -> EmailMessageReminder:
    """Save AnalyzerAgent event/reminder analysis before user-requested actions."""

    def apply_result(record: EmailMessageReminder) -> None:
        record.processing_status = "analyzed"
        record.skip_reason = None
        record.summarized_body = ""
        record.reply_needed = None
        record.reply_status = "not_required"
        record.detected_intent = str(analyzer_result.get("category") or "") or None
        if record.detected_intent == "reminder":
            record.action_items_json = json.dumps(_analyzer_action_items(analyzer_result))
            record.deadline = _analyzer_reminder_deadline(analyzer_result)
        else:
            record.action_items_json = None
            record.deadline = None
        _apply_calendar_event(record, analyzer_result)

    return _save_with_user(user_email, message.get("id"), message, apply_result)


def save_summary_result(
    user_email: str,
    message: Dict[str, Any],
    summary_result: Dict[str, Any],
    skip_reason: Optional[str] = None,
) -> EmailMessageReminder:
    """Save SummaryAgent output and token observability fields."""

    def apply_result(record: EmailMessageReminder) -> None:
        record.processing_status = "summarized"
        record.skip_reason = skip_reason
        record.summarized_body = str(summary_result.get("summary") or "")
        record.detected_intent = summary_result.get("detected_intent")
        record.action_items_json = json.dumps(summary_result.get("action_items") or [])
        record.deadline = summary_result.get("deadline")
        record.reply_needed = bool(summary_result.get("reply_needed"))
        record.reply_status = "pending" if record.reply_needed else "not_required"
        record.llm_summary_tokens_input = summary_result.get("llm_summary_tokens_input")
        record.llm_summary_tokens_output = summary_result.get("llm_summary_tokens_output")
        record.prompt_cache_hit = summary_result.get("prompt_cache_hit")

    return _save_with_user(user_email, message.get("id"), message, apply_result)


def save_reply_result(
    user_email: str,
    message: Dict[str, Any],
    reply_result: Dict[str, Any],
) -> EmailMessageReminder:
    """Save ReplyAgent output and mark the message reply as generated."""

    def apply_result(record: EmailMessageReminder) -> None:
        suggested_reply = str(reply_result.get("suggested_reply") or "").strip()
        record.processing_status = "reply_generated"
        record.reply_status = "generated"
        record.suggested_reply = suggested_reply or None
        record.reply_body = suggested_reply or None
        record.reply_subject = (
            f"Re: {message.get('subject', '')}"
            if suggested_reply
            else None
        )
        record.llm_reply_tokens_input = reply_result.get("llm_reply_tokens_input")
        record.llm_reply_tokens_output = reply_result.get("llm_reply_tokens_output")

    return _save_with_user(user_email, message.get("id"), message, apply_result)


def get_message_reply_context(user_email: str, message_id: str) -> Dict[str, Any]:
    """Load stored message context needed for a user-requested reply draft."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        record = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.message_id == str(message_id),
            )
            .first()
        )
        if not record:
            raise ValueError(f"No stored message found for {message_id}")

        summary_text = record.summarized_body or ""
        message = {
            "id": record.message_id,
            "from": record.from_address or "",
            "to": record.to_address or user_email,
            "subject": record.summarized_subject or "",
            "date": (
                record.message_date.isoformat()
                if record.message_date
                else ""
            ),
            "body": summary_text,
        }
        summary = {"summary": summary_text} if summary_text else None
        return {
            "message": message,
            "analysis": {},
            "summary": summary,
        }


def list_message_summaries(user_email: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Load summarized messages for the user-facing inbox view."""
    safe_limit = max(1, min(int(limit or 500), 500))

    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        records = (
            db.query(EmailMessageReminder)
            .filter(EmailMessageReminder.user_id == user.id)
            .order_by(
                EmailMessageReminder.message_date.desc().nullslast(),
                EmailMessageReminder.message_time.desc().nullslast(),
                EmailMessageReminder.updated_at.desc(),
            )
            .limit(safe_limit)
            .all()
        )

        messages = []
        for record in records:
            action_items = []
            if record.action_items_json:
                try:
                    action_items = json.loads(record.action_items_json)
                except json.JSONDecodeError:
                    action_items = []

            messages.append(
                {
                    "message_id": record.message_id,
                    "subject": _clean_display_text(record.summarized_subject),
                    "summary": _clean_display_text(record.summarized_body),
                    "from": record.from_address or "",
                    "to": record.to_address or "",
                    "message_date": (
                        record.message_date.isoformat()
                        if record.message_date
                        else None
                    ),
                    "message_time": (
                        record.message_time.isoformat(timespec="minutes")
                        if record.message_time
                        else None
                    ),
                    "processing_status": record.processing_status,
                    "skip_reason": record.skip_reason,
                    "detected_intent": record.detected_intent,
                    "action_items": action_items,
                    "deadline": record.deadline,
                    "reply_needed": record.reply_needed,
                    "reply_status": record.reply_status,
                    "suggested_reply": record.suggested_reply or record.reply_body or "",
                    "calendar_event": _calendar_event_payload(record),
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                }
            )

        return messages


def list_message_analysis_states(user_email: str, message_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Return stored analysis state keyed by Gmail message id."""
    clean_ids = [str(message_id) for message_id in message_ids if message_id]
    if not clean_ids:
        return {}

    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            return {}

        records = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.message_id.in_(clean_ids),
            )
            .all()
        )
        return {
            str(record.message_id): {
                "processing_status": record.processing_status or "pending",
                "skip_reason": record.skip_reason,
                "detected_intent": record.detected_intent,
                "calendar_event": _calendar_event_payload(record),
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            }
            for record in records
        }


def list_calendar_events(user_email: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent and upcoming detected email events for the user calendar view."""
    safe_limit = max(1, min(int(limit or 100), 250))
    now = datetime.utcnow()
    display_start = datetime.combine((now - timedelta(days=60)).date(), TimeType.min)
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        delete_old_calendar_events(db, user.id, now=now)

        records = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.calendar_event_detected.is_(True),
                EmailMessageReminder.calendar_event_start_at >= display_start,
            )
            .order_by(EmailMessageReminder.calendar_event_start_at.asc())
            .limit(safe_limit)
            .all()
        )

        events = []
        for record in records:
            event = _calendar_event_payload(record)
            if not event:
                continue
            events.append(
                {
                    **event,
                    "message_id": record.message_id,
                    "subject": _clean_display_text(record.summarized_subject),
                    "from": record.from_address or "",
                }
            )
        return events


def delete_old_calendar_events(
    db: Any,
    user_id: int,
    now: Optional[datetime] = None,
    retention_days: int = 180,
) -> int:
    """Delete detected event/reminder records older than the retention window."""
    cutoff = (now or datetime.utcnow()) - timedelta(days=max(1, int(retention_days or 180)))
    old_records = (
        db.query(EmailMessageReminder)
        .filter(
            EmailMessageReminder.user_id == user_id,
            EmailMessageReminder.calendar_event_detected.is_(True),
            EmailMessageReminder.calendar_event_start_at < cutoff,
        )
        .all()
    )
    deleted_count = len(old_records)
    for record in old_records:
        db.delete(record)
    if deleted_count:
        db.commit()
    return deleted_count


def list_due_event_notifications(
    user_email: str,
    now: Optional[datetime] = None,
    lookahead_minutes: int = 0,
) -> List[Dict[str, Any]]:
    """Return calendar events whose notification time has arrived."""
    current_time = now or datetime.utcnow()
    window_end = current_time + timedelta(minutes=max(0, int(lookahead_minutes or 0)))

    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        records = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.calendar_event_detected.is_(True),
                EmailMessageReminder.calendar_notification_sent.is_(False),
                EmailMessageReminder.calendar_notification_at.isnot(None),
                EmailMessageReminder.calendar_notification_at <= window_end,
                EmailMessageReminder.calendar_event_start_at >= current_time,
            )
            .order_by(EmailMessageReminder.calendar_event_start_at.asc())
            .all()
        )

        notifications = []
        for record in records:
            event = _calendar_event_payload(record)
            if not event:
                continue
            notifications.append(
                {
                    **event,
                    "message_id": record.message_id,
                    "subject": _clean_display_text(record.summarized_subject),
                    "from": record.from_address or "",
                }
            )
        return notifications


def list_pending_calendar_responses(
    user_email: str,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Return upcoming detected events the user has not yet responded to.

    These drive the "new event found, approve or deny it" prompt, which is
    separate from the time-based reminder in list_due_event_notifications.
    A row drops out of this list as soon as calendar_event_status is set,
    so responding to the prompt is what dismisses it for good.
    """
    current_time = now or datetime.utcnow()

    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        records = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.calendar_event_detected.is_(True),
                EmailMessageReminder.calendar_event_status.is_(None),
                EmailMessageReminder.calendar_event_start_at >= current_time,
            )
            .order_by(EmailMessageReminder.calendar_event_start_at.asc())
            .all()
        )

        pending = []
        for record in records:
            event = _calendar_event_payload(record)
            if not event:
                continue
            pending.append(
                {
                    **event,
                    "message_id": record.message_id,
                    "subject": _clean_display_text(record.summarized_subject),
                    "from": record.from_address or "",
                }
            )
        return pending


def mark_event_notification_sent(user_email: str, message_id: str) -> bool:
    """Mark one detected event notification as shown/sent."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        record = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.message_id == str(message_id),
            )
            .first()
        )
        if not record:
            raise ValueError(f"No stored message found for {message_id}")

        record.calendar_notification_sent = True
        record.updated_at = datetime.utcnow()
        db.commit()
        return True


def calendar_event_response_context(
    user_email: str,
    message_id: str,
) -> Dict[str, Any]:
    """Return organizer details for a stored calendar event."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        record = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.message_id == str(message_id),
                EmailMessageReminder.calendar_event_detected.is_(True),
            )
            .first()
        )
        if not record:
            raise ValueError(f"No stored calendar event found for {message_id}")

        organizer = str(record.calendar_event_organizer or record.from_address or "").strip()
        if organizer.lower().startswith("mailto:"):
            organizer = organizer[7:]
        organizer_email = parseaddr(organizer)[1] or organizer
        if not organizer_email:
            raise ValueError("Calendar event organizer is missing.")

        event = _calendar_event_payload(record) or {}
        return {
            **event,
            "message_id": record.message_id,
            "subject": record.summarized_subject or event.get("title") or "Calendar invite",
            "organizer_email": organizer_email,
        }


def update_calendar_event_response_status(
    user_email: str,
    message_id: str,
    response_status: str,
) -> None:
    """Store the user's latest local response to a calendar invite."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        record = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.message_id == str(message_id),
                EmailMessageReminder.calendar_event_detected.is_(True),
            )
            .first()
        )
        if not record:
            raise ValueError(f"No stored calendar event found for {message_id}")
        record.calendar_event_status = str(response_status or "").strip()[:50] or record.calendar_event_status
        record.updated_at = datetime.utcnow()
        db.commit()


def remove_calendar_event(user_email: str, message_id: str) -> None:
    """Clear a detected calendar event locally. Sends no email to the organizer."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        record = (
            db.query(EmailMessageReminder)
            .filter(
                EmailMessageReminder.user_id == user.id,
                EmailMessageReminder.message_id == str(message_id),
                EmailMessageReminder.calendar_event_detected.is_(True),
            )
            .first()
        )
        if not record:
            raise ValueError(f"No stored calendar event found for {message_id}")

        _clear_calendar_event(record)
        record.updated_at = datetime.utcnow()
        db.commit()


def list_connected_gmail_emails() -> List[str]:
    """Return every Gmail account that has completed OAuth (has stored credentials)."""
    with SessionLocal() as db:
        return [row[0] for row in db.query(GmailUser.email).all()]


def get_gmail_user_status(user_email: str) -> Dict[str, Any]:
    """Return connection/watch state for a Gmail user."""
    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            return {
                "connected": False,
                "email": user_email,
                "watch_active": False,
                "gmail_history_id": None,
                "gmail_watch_expiration": None,
            }

        return {
            "connected": True,
            "email": user.email,
            "watch_active": bool(user.gmail_history_id),
            "gmail_history_id": user.gmail_history_id,
            "gmail_watch_expiration": (
                user.gmail_watch_expiration.isoformat()
                if user.gmail_watch_expiration
                else None
            ),
        }


def _session_ttl_days() -> int:
    try:
        return max(1, int(os.getenv("APP_SESSION_TTL_DAYS", "30")))
    except ValueError:
        return 30


def ensure_session_table() -> None:
    """Create the session table for existing local databases."""
    GmailUserSession.__table__.create(bind=engine, checkfirst=True)


def create_gmail_user_session(user_email: str) -> Dict[str, Any]:
    """Create a unique server-side session for a Gmail user."""
    ensure_session_table()
    expires_at = datetime.utcnow() + timedelta(days=_session_ttl_days())

    with SessionLocal() as db:
        user = db.query(GmailUser).filter(GmailUser.email == user_email).first()
        if not user:
            raise ValueError(f"No Gmail user found for {user_email}")

        while True:
            session_id = secrets.token_urlsafe(32)
            session = GmailUserSession(
                session_id=session_id,
                user_id=user.id,
                expires_at=expires_at,
            )
            db.add(session)
            try:
                db.commit()
                db.refresh(session)
                return {
                    "session_id": session.session_id,
                    "user_id": user.id,
                    "email": user.email,
                    "expires_at": session.expires_at,
                }
            except IntegrityError:
                db.rollback()
                continue


def get_gmail_user_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a browser session id to its Gmail user."""
    clean_session_id = str(session_id or "").strip()
    if not clean_session_id:
        return None

    ensure_session_table()
    now = datetime.utcnow()
    with SessionLocal() as db:
        session = (
            db.query(GmailUserSession)
            .filter(
                GmailUserSession.session_id == clean_session_id,
                GmailUserSession.revoked_at.is_(None),
            )
            .first()
        )
        if not session:
            return None
        if session.expires_at <= now:
            session.revoked_at = now
            db.commit()
            return None

        user = db.query(GmailUser).filter(GmailUser.id == session.user_id).first()
        if not user:
            return None

        return {
            "session_id": session.session_id,
            "user_id": user.id,
            "email": user.email,
            "expires_at": session.expires_at,
        }


def delete_gmail_user_session(session_id: str) -> bool:
    """Revoke one server-side browser session."""
    clean_session_id = str(session_id or "").strip()
    if not clean_session_id:
        return False

    ensure_session_table()
    with SessionLocal() as db:
        session = (
            db.query(GmailUserSession)
            .filter(GmailUserSession.session_id == clean_session_id)
            .first()
        )
        if not session:
            return False
        session.revoked_at = datetime.utcnow()
        db.commit()
        return True


# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/email_reminders")

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


DB_POOL_SIZE = _int_env("DB_POOL_SIZE", 10)
DB_MAX_OVERFLOW = _int_env("DB_MAX_OVERFLOW", 20)
DB_POOL_TIMEOUT = _int_env("DB_POOL_TIMEOUT", 30)
DB_POOL_RECYCLE = _int_env("DB_POOL_RECYCLE", 1800)

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    with SessionLocal() as db:
        yield db
