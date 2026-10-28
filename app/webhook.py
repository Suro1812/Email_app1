import logging
import asyncio
import os
from pathlib import Path
from urllib.parse import quote
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from google.auth.exceptions import RefreshError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field
try:
    from googleapiclient.errors import HttpError
except ImportError:
    HttpError = ()  # type: ignore[assignment]

from app.logging_config import configure_logging
from app.observability import (
    CONTENT_TYPE_LATEST,
    install_http_metrics,
    prometheus_metrics,
    start_metrics_pusher,
)
from app.service.gmail_push import (
    decode_pubsub_push,
    start_gmail_watch,
    verify_pubsub_push_token,
)


configure_logging()
logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
APP_SESSION_COOKIE = "gmail_session_id"
LEGACY_AUTH_COOKIE = "gmail_authenticated"
WRITER_REQUEST_TIMEOUT_SECONDS = int(os.getenv("WRITER_REQUEST_TIMEOUT_SECONDS", "45"))
app = FastAPI(title="Email Reminders API")
install_http_metrics(app)
start_metrics_pusher("api")


class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


if FRONTEND_DIR.exists():
    app.mount("/static", NoCacheStaticFiles(directory=str(FRONTEND_DIR)), name="static")


def current_session(request: Request) -> Optional[Dict[str, Any]]:
    from app.core.database import get_gmail_user_session

    return get_gmail_user_session(request.cookies.get(APP_SESSION_COOKIE, ""))


def require_session(request: Request) -> Dict[str, Any]:
    session = current_session(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with Google first.",
        )
    return session


def session_email(session: Dict[str, Any]) -> str:
    return str(session["email"])


def send_audit_context(
    http_request: Request,
    session: Dict[str, Any],
    *,
    request_email: str = "",
) -> Dict[str, Any]:
    client_host = http_request.client.host if http_request.client else ""
    return {
        "email": session_email(session),
        "request_email": request_email,
        "client_host": client_host,
        "user_agent": str(http_request.headers.get("user-agent", ""))[:300],
        "origin": str(http_request.headers.get("origin", ""))[:300],
        "referer": str(http_request.headers.get("referer", ""))[:300],
        "session_id_prefix": str(session.get("session_id", ""))[:8],
    }


def gmail_result_context(sent: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "gmail_message_id": sent.get("id", ""),
        "gmail_thread_id": sent.get("threadId", ""),
    }


class LoginStartResponse(BaseModel):
    status: str
    authorization_url: str


class StartWatchRequest(BaseModel):
    email: str
    topic_name: Optional[str] = None
    label_ids: Optional[List[str]] = None


class PipelineMessageIdsRequest(BaseModel):
    email: str
    message_ids: List[str] = Field(default_factory=list)
    mailbox: str = "inbox"
    category: str = "primary"


class ReplyMessageRequest(BaseModel):
    email: str
    message_id: str
    intent: str = Field(default="", description="User guidance for the reply draft.")


class WriterMessageRequest(BaseModel):
    email: str
    message_id: str = ""
    to: str = ""
    cc: str = ""
    bcc: str = ""
    subject: str = ""
    instruction: str = Field(default="", description="User guidance for the writer draft.")
    format: str = Field(default="formal", description="Writing format: formal or informal.")


class SummaryMessageRequest(BaseModel):
    email: str
    message_id: str


class GmailMessageRequest(BaseModel):
    email: str
    message_id: str


class NotificationAckRequest(BaseModel):
    email: str
    message_id: str


class CalendarEventResponseRequest(BaseModel):
    message_id: str
    response: str = Field(description="accepted, declined, tentative, or proposed.")
    proposed_date: str = ""
    proposed_time: str = ""


class CalendarEventRemoveRequest(BaseModel):
    message_id: str


class EmailAttachmentRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    data: str


class SendReplyRequest(BaseModel):
    email: str
    message_id: str
    to: str = ""
    cc: str = ""
    bcc: str = ""
    reply_body: str
    reply_html: str = ""
    attachments: List[EmailAttachmentRequest] = Field(default_factory=list)


class SendWriterMessageRequest(BaseModel):
    email: str
    to: str
    cc: str = ""
    bcc: str = ""
    subject: str = ""
    body: str
    body_html: str = ""
    attachments: List[EmailAttachmentRequest] = Field(default_factory=list)


@app.get("/health")
async def health() -> Dict[str, str]:
    try:
        from app.core.database import SessionLocal

        with SessionLocal() as db:
            db.exec(text("SELECT 1")).first()
    except SQLAlchemyError:
        return {"status": "degraded", "database": "unavailable"}

    return {"status": "ok", "database": "ok"}


@app.get("/", include_in_schema=False)
async def login_page(request: Request) -> Response:
    if current_session(request):
        return RedirectResponse("/app", status_code=status.HTTP_303_SEE_OTHER)

    login_path = FRONTEND_DIR / "login.html"
    if not login_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Login assets are not available.",
        )
    response = FileResponse(login_path)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/app", include_in_schema=False)
async def index(request: Request) -> Response:
    if not current_session(request):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend assets are not available.",
        )
    response = FileResponse(index_path)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/metrics")
async def metrics() -> Response:
    return Response(
        content=prometheus_metrics(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/auth/status", status_code=status.HTTP_200_OK)
async def auth_status(
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Return whether the Gmail account is connected locally."""
    from app.core.database import get_gmail_user_status
    email = session_email(session)

    try:
        user_status = get_gmail_user_status(email)
    except SQLAlchemyError as exc:
        logger.exception("auth_status_database_unavailable", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Restart the app with local service access.",
        ) from exc

    if not user_status.get("connected"):
        return user_status

    try:
        from app.service.get_messages import get_gmail_service

        service = await get_gmail_service(email)
        await asyncio.to_thread(service.users().getProfile(userId="me").execute)
    except (RefreshError, ValueError):
        user_status["connected"] = False
        user_status["detail"] = "Gmail connection expired. Connect Gmail again."
    except HttpError as exc:
        if getattr(exc, "status_code", None) in {401, 403} or getattr(getattr(exc, "resp", None), "status", None) in {401, 403}:
            user_status["connected"] = False
            user_status["detail"] = "Gmail connection expired. Connect Gmail again."
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gmail status check failed. Try again.",
            ) from exc
    except SQLAlchemyError as exc:
        logger.exception("auth_status_database_unavailable", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Restart the app with local service access.",
        ) from exc

    return user_status


@app.get("/messages", status_code=status.HTTP_200_OK)
async def list_messages(
    limit: int = Query(default=500, ge=1, le=500),
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Return stored Gmail message summaries for the frontend inbox."""
    email = session_email(session)
    try:
        from app.core.database import list_message_summaries

        messages = list_message_summaries(email, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception("list_messages_database_unavailable", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Restart the app with local service access.",
        ) from exc

    return {
        "email": email,
        "messages": messages,
    }


@app.get("/calendar/events", status_code=status.HTTP_200_OK)
async def list_calendar_events_endpoint(
    limit: int = Query(default=100, ge=1, le=250),
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Return upcoming calendar events detected from analyzed emails."""
    email = session_email(session)
    try:
        from app.core.database import list_calendar_events

        events = list_calendar_events(email, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception("calendar_events_database_unavailable", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Calendar events could not be loaded.",
        ) from exc

    return {
        "email": email,
        "events": events,
    }


@app.get("/notifications/events/due", status_code=status.HTTP_200_OK)
async def due_event_notifications_endpoint(
    lookahead_minutes: int = Query(default=0, ge=0, le=1440),
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Return detected email events whose notification time has arrived."""
    email = session_email(session)
    try:
        from app.core.database import (
            list_due_event_notifications,
            list_pending_calendar_responses,
        )

        notifications = list_due_event_notifications(
            email,
            lookahead_minutes=lookahead_minutes,
        )
        pending_responses = list_pending_calendar_responses(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception("event_notifications_database_unavailable", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Event notifications could not be loaded.",
        ) from exc

    return {
        "email": email,
        "notifications": notifications,
        "pending_responses": pending_responses,
    }


@app.post("/notifications/events/ack", status_code=status.HTTP_200_OK)
async def acknowledge_event_notification_endpoint(
    request: NotificationAckRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Mark one event notification as shown to the user."""
    email = session_email(session)
    try:
        from app.core.database import mark_event_notification_sent

        mark_event_notification_sent(email, request.message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception(
            "event_notification_ack_database_unavailable",
            extra={"email": email, "message_id": request.message_id},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Event notification was not acknowledged.",
        ) from exc

    return {
        "status": "acknowledged",
        "email": email,
        "message_id": request.message_id,
    }


@app.post("/calendar/events/respond", status_code=status.HTTP_200_OK)
async def respond_to_calendar_event_endpoint(
    request: CalendarEventResponseRequest,
    http_request: Request,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Send an email response to a stored calendar event organizer/sender."""
    email = session_email(session)
    clean_response = str(request.response or "").strip().lower()
    allowed_responses = {"accepted", "declined", "tentative", "proposed"}
    if clean_response not in allowed_responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Response must be accepted, declined, tentative, or proposed.",
        )
    if clean_response == "proposed" and not (request.proposed_date.strip() and request.proposed_time.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New proposal needs a date and time.",
        )

    try:
        from app.core.database import (
            calendar_event_response_context,
            update_calendar_event_response_status,
        )
        from app.tool.tools import allow_gmail_send_from, send_gmail_message

        # Recipient and title come only from the stored event. Never from the
        # request: a client-supplied organizer can belong to a different message
        # than message_id, which addresses the response to the wrong person.
        event: Dict[str, Any] = calendar_event_response_context(email, request.message_id)

        title = str(event.get("title") or event.get("subject") or "Calendar invite")
        organizer = str(event.get("organizer_email") or "").strip()
        if not organizer:
            raise ValueError("Calendar event organizer is missing.")
        if clean_response == "proposed":
            body = (
                f"New proposal for {title}\n\n"
                f"Time: {request.proposed_time.strip()}\n"
                f"Date: {request.proposed_date.strip()}"
            )
            subject = f"New proposal: {title}"
        else:
            label = {
                "accepted": "Accepted",
                "declined": "Declined",
                "tentative": "Tentative",
            }[clean_response]
            body = f"{label}: {title}"
            subject = f"{label}: {title}"

        logger.warning(
            "gmail_send_attempt",
            extra={
                **send_audit_context(http_request, session),
                "email": email,
                "action": "calendar_event_response",
                "endpoint": "/calendar/events/respond",
                "message_id": request.message_id,
                "to": organizer,
                "subject": subject,
                "body_length": len(body.strip()),
                "html_length": 0,
                "attachment_count": 0,
                "has_cc": False,
                "has_bcc": False,
            },
        )
        with allow_gmail_send_from("calendar_event_response_endpoint"):
            sent = await send_gmail_message(email, organizer, subject, body)
        logger.warning(
            "gmail_send_success",
            extra={
                **send_audit_context(http_request, session),
                "email": email,
                "action": "calendar_event_response",
                "endpoint": "/calendar/events/respond",
                "message_id": request.message_id,
                **gmail_result_context(sent),
            },
        )
        update_calendar_event_response_status(email, request.message_id, clean_response)
    except ValueError as exc:
        logger.exception(
            "gmail_send_failed",
            extra={
                **send_audit_context(http_request, session),
                "email": email,
                "action": "calendar_event_response",
                "endpoint": "/calendar/events/respond",
                "message_id": request.message_id,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception(
            "gmail_send_failed",
            extra={
                **send_audit_context(http_request, session),
                "email": email,
                "action": "calendar_event_response",
                "endpoint": "/calendar/events/respond",
                "message_id": request.message_id,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception(
            "calendar_event_response_database_unavailable",
            extra={"email": email, "message_id": request.message_id},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Calendar response was not sent.",
        ) from exc

    return {
        "status": "calendar_response_sent",
        "email": email,
        "message_id": request.message_id,
        "response": clean_response,
        "gmail_result": sent,
    }


@app.post("/calendar/events/remove", status_code=status.HTTP_200_OK)
async def remove_calendar_event_endpoint(
    request: CalendarEventRemoveRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Clear a detected calendar event from the user's local calendar. Sends no email."""
    email = session_email(session)
    try:
        from app.core.database import remove_calendar_event

        remove_calendar_event(email, request.message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception(
            "calendar_event_remove_database_unavailable",
            extra={"email": email, "message_id": request.message_id},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable. Event was not removed.",
        ) from exc

    return {
        "status": "calendar_event_removed",
        "email": email,
        "message_id": request.message_id,
    }


@app.get("/gmail/messages", status_code=status.HTTP_200_OK)
async def list_gmail_messages(
    mailbox: str = Query(default="inbox", min_length=2),
    category: str = Query(default="primary", min_length=3),
    limit: int = Query(default=50, ge=1, le=100),
    page_token: Optional[str] = Query(default=None),
    unread_only: bool = Query(default=False),
    q: Optional[str] = Query(default=None, max_length=500),
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Fetch fresh messages from Gmail for a mailbox/category click, or a free-text search."""
    email = session_email(session)
    try:
        from app.service.get_messages import list_gmail_mailbox_messages

        return await list_gmail_mailbox_messages(
            email=email,
            mailbox=mailbox,
            category=category,
            limit=limit,
            page_token=page_token,
            unread_only=unread_only,
            search_query=q,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RefreshError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail connection expired. Connect Gmail again.",
        ) from exc
    except HttpError as exc:
        logger.exception(
            "list_gmail_messages_gmail_api_failed",
            extra={"email": email, "mailbox": mailbox},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail could not load {mailbox}. Try another mailbox or refresh.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("list_gmail_messages_database_unavailable", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable, so Gmail credentials cannot be loaded. Start Postgres and connect Gmail again.",
        ) from exc


@app.get("/gmail/message", status_code=status.HTTP_200_OK)
async def get_gmail_message(
    message_id: str = Query(..., min_length=1),
    thread_id: Optional[str] = Query(default=None),
    mark_read: bool = Query(default=False),
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Fetch one full sanitized Gmail message with thread context for preview."""
    email = session_email(session)
    try:
        from app.tool.tools import read_gmail_message

        message = await read_gmail_message(
            email=email,
            message_id=message_id,
            thread_id=thread_id,
            mark_read=mark_read,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RefreshError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail connection expired. Connect Gmail again.",
        ) from exc
    except HttpError as exc:
        logger.exception(
            "get_gmail_message_gmail_api_failed",
            extra={"email": email, "message_id": message_id},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail could not load the full message. Try again.",
        ) from exc

    return {
        "email": email,
        "message_id": message_id,
        "message": message,
    }


@app.get("/auth/login", include_in_schema=False)
async def redirect_to_google_login() -> RedirectResponse:
    """Redirect the browser to Google's OAuth login page."""
    try:
        from app.core.auth import build_oauth_authorization_url, oauth_redirect_uri

        authorization_url, _state = await build_oauth_authorization_url(oauth_redirect_uri())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(authorization_url, status_code=status.HTTP_303_SEE_OTHER)


@app.post("/auth/login", response_model=LoginStartResponse)
async def login_user() -> Dict[str, Any]:
    """Reject stale frontend login calls that cannot navigate to Google."""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="The frontend was updated. Refresh the page once, then click Connect again.",
    )


@app.get("/auth/logout", include_in_schema=False)
async def logout_user(request: Request) -> RedirectResponse:
    """Clear the browser session and return to the login page."""
    from app.core.database import delete_gmail_user_session

    delete_gmail_user_session(request.cookies.get(APP_SESSION_COOKIE, ""))
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(APP_SESSION_COOKIE, path="/")
    response.delete_cookie(LEGACY_AUTH_COOKIE, path="/")
    return response


@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(request: Request) -> RedirectResponse:
    """Handle Google's OAuth callback, save tokens, and return to the frontend."""
    try:
        from app.core.auth import complete_oauth_callback, oauth_redirect_uri

        email, _creds = await complete_oauth_callback(
            authorization_response=str(request.url),
            redirect_uri=oauth_redirect_uri(),
            state=request.query_params.get("state"),
        )
    except Exception as exc:
        logger.exception("gmail_oauth_callback_failed")
        return RedirectResponse(
            f"/?auth_error={quote(str(exc))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    response = RedirectResponse(
        f"/app?email={quote(email)}&connected=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    from app.core.database import create_gmail_user_session

    session = create_gmail_user_session(email)
    response.set_cookie(
        APP_SESSION_COOKIE,
        session["session_id"],
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    response.delete_cookie(LEGACY_AUTH_COOKIE, path="/")
    return response


@app.post("/gmail/watch", status_code=status.HTTP_200_OK)
async def start_watch(
    request: StartWatchRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Start or refresh a Gmail watch for an already-authenticated user."""
    email = session_email(session)
    try:
        watch = await start_gmail_watch(
            email,
            topic_name=request.topic_name,
            label_ids=request.label_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "watch_started",
        "email": email,
        "watch": watch,
    }


@app.post("/pipeline/messages", status_code=status.HTTP_200_OK)
async def run_pipeline_for_message_ids_endpoint(
    request: PipelineMessageIdsRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Queue pipeline processing for exact Gmail message IDs."""
    email = session_email(session)
    try:
        from app.core.database import mark_messages_analysis_queued
        from app.service.get_messages import filter_primary_inbox_message_ids
        from app.tasks import run_pipeline_for_message_ids_task

        if request.mailbox.strip().lower() != "inbox" or request.category.strip().lower() != "primary":
            return {
                "status": "skipped",
                "email": email,
                "message_ids": request.message_ids,
                "queued_message_ids": [],
                "task_id": None,
                "reason": "analysis_limited_to_primary_inbox",
            }

        primary_message_ids = await filter_primary_inbox_message_ids(email, request.message_ids)
        queue_ids = mark_messages_analysis_queued(email, primary_message_ids)
        if not queue_ids:
            return {
                "status": "skipped",
                "email": email,
                "message_ids": request.message_ids,
                "queued_message_ids": [],
                "task_id": None,
                "reason": "no_primary_inbox_messages_to_analyze",
            }

        task = run_pipeline_for_message_ids_task.delay(
            email,
            queue_ids,
        )
    except Exception as exc:
        logger.exception(
            "pipeline_message_ids_enqueue_failed",
            extra={
                "email": email,
                "message_ids": request.message_ids,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not enqueue message IDs for processing.",
        ) from exc

    return {
        "status": "accepted",
        "email": email,
        "message_ids": request.message_ids,
        "queued_message_ids": queue_ids,
        "task_id": task.id,
    }


@app.post("/reply/message", status_code=status.HTTP_200_OK)
async def draft_reply_for_message_endpoint(
    request: ReplyMessageRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Generate a reply from Gmail message context when the user requests it."""
    email = session_email(session)
    try:
        from app.agent.pipeline import run_reply_pipeline_for_message

        result = await run_reply_pipeline_for_message(
            email,
            request.message_id,
            user_intent=request.intent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "reply_generated",
        "email": email,
        "message_id": request.message_id,
        "result": result,
    }


@app.post("/writer/message", status_code=status.HTTP_200_OK)
async def write_message_endpoint(
    request: WriterMessageRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Generate a formal or informal draft from Gmail message context."""
    email = session_email(session)
    try:
        from app.agent.pipeline import (
            run_writer_pipeline_for_compose,
            run_writer_pipeline_for_message,
        )

        if request.message_id:
            result = await asyncio.wait_for(
                run_writer_pipeline_for_message(
                    email,
                    request.message_id,
                    user_instruction=request.instruction,
                    writing_format=request.format,
                ),
                timeout=WRITER_REQUEST_TIMEOUT_SECONDS,
            )
        else:
            compose_instruction = "\n".join(
                part
                for part in [
                    f"Cc: {request.cc.strip()}" if request.cc.strip() else "",
                    f"Bcc: {request.bcc.strip()}" if request.bcc.strip() else "",
                    request.instruction,
                ]
                if part
            )
            result = await asyncio.wait_for(
                run_writer_pipeline_for_compose(
                    to_address=request.to,
                    subject=request.subject,
                    user_instruction=compose_instruction,
                    writing_format=request.format,
                ),
                timeout=WRITER_REQUEST_TIMEOUT_SECONDS,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI writer timed out waiting for the model server. Check that the local model is running and responsive.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "writer_generated",
        "email": email,
        "message_id": request.message_id,
        "result": result,
    }


@app.post("/summary/message", status_code=status.HTTP_200_OK)
async def summarize_message_endpoint(
    request: SummaryMessageRequest,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Summarize Gmail message context when the user explicitly requests it."""
    email = session_email(session)
    try:
        from app.agent.pipeline import run_summary_pipeline_for_message

        result = await run_summary_pipeline_for_message(
            email,
            request.message_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "summarized",
        "email": email,
        "message_id": request.message_id,
        "result": result,
    }


@app.post("/reply/send", status_code=status.HTTP_200_OK)
async def send_reply_endpoint(
    request: SendReplyRequest,
    http_request: Request,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Send a user-approved reply in Gmail."""
    email = session_email(session)
    try:
        from app.tool.tools import allow_gmail_send_from, send_gmail_reply

        logger.warning(
            "gmail_send_attempt",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "reply_send",
                "endpoint": "/reply/send",
                "message_id": request.message_id,
                "to": request.to,
                "has_cc": bool(request.cc.strip()),
                "has_bcc": bool(request.bcc.strip()),
                "body_length": len(str(request.reply_body or "").strip()),
                "html_length": len(str(request.reply_html or "").strip()),
                "attachment_count": len(request.attachments),
            },
        )
        reply_kwargs: Dict[str, str] = {}
        if request.to:
            reply_kwargs["to"] = request.to
        if request.cc:
            reply_kwargs["cc"] = request.cc
        if request.bcc:
            reply_kwargs["bcc"] = request.bcc
        with allow_gmail_send_from("reply_send_endpoint"):
            sent = await send_gmail_reply(
                email,
                request.message_id,
                request.reply_body,
                request.reply_html,
                [attachment.model_dump() for attachment in request.attachments],
                **reply_kwargs,
            )
        logger.warning(
            "gmail_send_success",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "reply_send",
                "endpoint": "/reply/send",
                "message_id": request.message_id,
                **gmail_result_context(sent),
            },
        )
    except ValueError as exc:
        logger.exception(
            "gmail_send_failed",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "reply_send",
                "endpoint": "/reply/send",
                "message_id": request.message_id,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception(
            "gmail_send_failed",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "reply_send",
                "endpoint": "/reply/send",
                "message_id": request.message_id,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "reply_sent",
        "email": email,
        "message_id": request.message_id,
        "gmail_result": sent,
    }


@app.post("/writer/send", status_code=status.HTTP_200_OK)
async def send_writer_message_endpoint(
    request: SendWriterMessageRequest,
    http_request: Request,
    session: Dict[str, Any] = Depends(require_session),
) -> Dict[str, Any]:
    """Send a user-approved compose draft in Gmail."""
    email = session_email(session)
    try:
        from app.tool.tools import allow_gmail_send_from, send_gmail_message

        logger.warning(
            "gmail_send_attempt",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "writer_send",
                "endpoint": "/writer/send",
                "to": request.to,
                "has_cc": bool(request.cc.strip()),
                "has_bcc": bool(request.bcc.strip()),
                "subject": request.subject,
                "body_length": len(str(request.body or "").strip()),
                "html_length": len(str(request.body_html or "").strip()),
                "attachment_count": len(request.attachments),
            },
        )
        with allow_gmail_send_from("writer_send_endpoint"):
            sent = await send_gmail_message(
                email,
                request.to,
                request.subject,
                request.body,
                request.body_html,
                [attachment.model_dump() for attachment in request.attachments],
                cc=request.cc,
                bcc=request.bcc,
            )
        logger.warning(
            "gmail_send_success",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "writer_send",
                "endpoint": "/writer/send",
                **gmail_result_context(sent),
            },
        )
    except ValueError as exc:
        logger.exception(
            "gmail_send_failed",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "writer_send",
                "endpoint": "/writer/send",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception(
            "gmail_send_failed",
            extra={
                **send_audit_context(http_request, session, request_email=request.email),
                "email": email,
                "action": "writer_send",
                "endpoint": "/writer/send",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "writer_sent",
        "email": email,
        "gmail_result": sent,
    }


@app.post("/webhooks/gmail/pubsub", status_code=status.HTTP_200_OK)
async def gmail_pubsub_webhook(
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    try:
        verify_pubsub_push_token(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    try:
        notification = decode_pubsub_push(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        from app.tasks import process_gmail_notification_task

        task = process_gmail_notification_task.delay(notification)
    except Exception as exc:
        logger.exception(
            "gmail_notification_enqueue_failed",
            extra={
                "email": notification.get("emailAddress"),
                "history_id": notification.get("historyId"),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not enqueue Gmail notification for analysis.",
        ) from exc

    return {
        "status": "accepted",
        "email": notification["emailAddress"],
        "history_id": notification["historyId"],
        "task_id": task.id,
    }
