import base64
import html as html_lib
import logging
import os
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import Any, Optional

from app.agent.hooks import post_tool_process_gmail_message
from app.observability import observe_tool_call
from app.service import (
    build_email_display_html,
    check_promotional_basic,
    get_gmail_service,
    extract_body,
    extract_ics_calendar_events,
)
try:
    from googleapiclient.errors import HttpError
except ImportError:
    HttpError = None  # type: ignore[assignment]
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self):
            def decorator(func):
                return func

            return decorator

mcp = FastMCP("my-server")
logger = logging.getLogger(__name__)
_gmail_send_source: ContextVar[str] = ContextVar("gmail_send_source", default="")
_ALLOWED_GMAIL_SEND_SOURCES = {
    "calendar_event_response_endpoint",
    "reply_send_endpoint",
    "writer_send_endpoint",
}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


@contextmanager
def allow_gmail_send_from(source: str):
    token = _gmail_send_source.set(str(source or "").strip())
    try:
        yield
    finally:
        _gmail_send_source.reset(token)


def _require_allowed_gmail_send_source() -> str:
    source = _gmail_send_source.get().strip()
    if source not in _ALLOWED_GMAIL_SEND_SOURCES:
        logger.warning("gmail_send_blocked_unapproved_source", extra={"source": source or "unknown"})
        raise RuntimeError(
            "Gmail send is only allowed from /reply/send, /writer/send, or /calendar/events/respond."
        )
    return source


def _header_map(headers: list[dict]) -> dict:
    return {
        str(header.get("name", "")).lower(): str(header.get("value", ""))
        for header in headers
    }


def _reply_subject(subject: str) -> str:
    clean_subject = str(subject or "").strip()
    if clean_subject.lower().startswith("re:"):
        return clean_subject
    return f"Re: {clean_subject}" if clean_subject else "Re:"


def _base64url_message(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


_OUTGOING_ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "div",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "s",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
_OUTGOING_DANGEROUS_TAGS = {
    "base",
    "embed",
    "form",
    "iframe",
    "input",
    "link",
    "meta",
    "object",
    "script",
    "style",
}
_OUTGOING_SAFE_LINK_PREFIXES = ("http://", "https://", "mailto:", "tel:")
_OUTGOING_ALLOWED_STYLE_PROPERTIES = {"color", "background-color", "text-align"}
_OUTGOING_ALLOWED_CLASS_PREFIXES = (
    "ql-align-",
    "ql-direction-",
    "ql-font-",
    "ql-indent-",
    "ql-size-",
)
_OUTGOING_SAFE_CSS_VALUE_RE = re.compile(r"^[#(),.%\w\s-]+$")
MAX_ATTACHMENT_COUNT = 10
MAX_ATTACHMENT_TOTAL_BYTES = 20 * 1024 * 1024


def _sanitize_outgoing_style(value: str) -> str:
    safe_rules = []
    for rule in str(value or "").split(";"):
        if ":" not in rule:
            continue
        property_name, property_value = rule.split(":", 1)
        property_name = property_name.strip().lower()
        property_value = property_value.strip()
        if property_name not in _OUTGOING_ALLOWED_STYLE_PROPERTIES:
            continue
        if "url(" in property_value.lower() or not _OUTGOING_SAFE_CSS_VALUE_RE.match(property_value):
            continue
        safe_rules.append(f"{property_name}: {property_value}")
    return "; ".join(safe_rules)


def _sanitize_outgoing_classes(value: object) -> list[str]:
    classes = value if isinstance(value, list) else str(value or "").split()
    safe_classes = []
    for class_name in classes:
        clean_name = str(class_name or "").strip()
        if clean_name.startswith(_OUTGOING_ALLOWED_CLASS_PREFIXES):
            safe_classes.append(clean_name)
    return safe_classes


def sanitize_outgoing_email_html(html_body: str) -> str:
    """Keep useful compose formatting while removing active HTML surfaces."""
    raw_html = str(html_body or "").strip()
    if not raw_html:
        return ""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html_lib.escape(raw_html)

    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(_OUTGOING_DANGEROUS_TAGS):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        tag_name = str(tag.name or "").lower()
        if tag_name not in _OUTGOING_ALLOWED_TAGS:
            tag.unwrap()
            continue

        for attr, value in list(tag.attrs.items()):
            attr_name = str(attr).lower()
            attr_value = " ".join(str(item) for item in (value if isinstance(value, list) else [value])).strip()
            if attr_name.startswith("on") or attr_name in {"src", "srcdoc"}:
                del tag.attrs[attr]
                continue
            if attr_name == "style":
                clean_style = _sanitize_outgoing_style(attr_value)
                if clean_style:
                    tag.attrs[attr] = clean_style
                else:
                    del tag.attrs[attr]
                continue
            if attr_name == "class":
                clean_classes = _sanitize_outgoing_classes(value)
                if clean_classes:
                    tag.attrs[attr] = clean_classes
                else:
                    del tag.attrs[attr]
                continue
            if tag_name == "a" and attr_name == "href":
                if not attr_value.lower().startswith(_OUTGOING_SAFE_LINK_PREFIXES):
                    del tag.attrs[attr]
                continue
            if tag_name in {"td", "th"} and attr_name in {"colspan", "rowspan"}:
                continue
            del tag.attrs[attr]

        if tag_name == "a" and tag.has_attr("href"):
            tag["target"] = "_blank"
            tag["rel"] = "noopener noreferrer nofollow"

    return str(soup).strip()


def html_to_plain_text(html_body: str) -> str:
    raw_html = str(html_body or "")
    if not raw_html.strip():
        return ""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return raw_html

    text = BeautifulSoup(raw_html, "html.parser").get_text("\n", strip=True)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def set_email_content(outbound: EmailMessage, plain_text: str, html_body: Optional[str] = None) -> None:
    clean_body = str(plain_text or "").strip()
    clean_html = sanitize_outgoing_email_html(html_body or "")
    if not clean_body and clean_html:
        clean_body = html_to_plain_text(clean_html)
    if not clean_body:
        raise ValueError("Message body cannot be empty.")

    outbound.set_content(clean_body)
    if clean_html:
        outbound.add_alternative(clean_html, subtype="html")


def attach_email_files(outbound: EmailMessage, attachments: Optional[list[dict[str, Any]]] = None) -> None:
    clean_attachments = attachments or []
    if not clean_attachments:
        return
    if len(clean_attachments) > MAX_ATTACHMENT_COUNT:
        raise ValueError(f"Cannot attach more than {MAX_ATTACHMENT_COUNT} files.")

    total_size = 0
    for attachment in clean_attachments:
        filename = os.path.basename(str(attachment.get("filename") or "attachment")).strip() or "attachment"
        content_type = str(attachment.get("content_type") or "application/octet-stream").strip()
        if "/" not in content_type:
            content_type = "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        encoded_data = str(attachment.get("data") or "")
        if "," in encoded_data:
            encoded_data = encoded_data.split(",", 1)[1]
        try:
            payload = base64.b64decode(encoded_data, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Attachment {filename} is not valid base64.") from exc

        total_size += len(payload)
        if total_size > MAX_ATTACHMENT_TOTAL_BYTES:
            raise ValueError("Attachments exceed the 20 MB limit.")

        outbound.add_attachment(
            payload,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=filename,
        )


async def _thread_message_context(gmail_message: dict[str, Any]) -> dict[str, Any]:
    payload = gmail_message.get("payload", {})
    headers = _header_map(payload.get("headers", []))
    body = await extract_body(payload)
    display_parts = build_email_display_html(payload)
    processed = post_tool_process_gmail_message(
        {
            "id": gmail_message.get("id", ""),
            "thread_id": gmail_message.get("threadId"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "bcc": headers.get("bcc", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "snippet": gmail_message.get("snippet", ""),
            "body": body,
        }
    )
    processed.update(display_parts)
    ics_events = extract_ics_calendar_events(payload)
    if ics_events:
        processed["calendar_event"] = ics_events[0]
    processed["has_display_html"] = bool(display_parts.get("display_html"))
    return processed


async def _fetch_thread_messages(
    service: Any,
    email: str,
    current_message_id: str,
    thread_id: Optional[str],
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    if not thread_id:
        return []

    with observe_tool_call(
        "gmail.threads.get",
        {"email": email, "thread_id": thread_id, "message_id": current_message_id},
    ):
        thread = service.users().threads().get(
            userId="me",
            id=thread_id,
            format="full",
        ).execute()

    if limit is None:
        limit = max(0, _env_int("GMAIL_THREAD_CONTEXT_LIMIT", 10))
    else:
        limit = max(0, int(limit))
    thread_messages = []
    for thread_message in thread.get("messages", []):
        if thread_message.get("id") == current_message_id:
            continue
        thread_messages.append(await _thread_message_context(thread_message))

    if limit and len(thread_messages) > limit:
        thread_messages = thread_messages[-limit:]

    return thread_messages


async def _thread_context_from_messages(
    gmail_messages: list[dict[str, Any]],
    current_message_id: str,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    if limit is None:
        limit = max(0, _env_int("GMAIL_THREAD_CONTEXT_LIMIT", 10))
    else:
        limit = max(0, int(limit))

    thread_messages = []
    for thread_message in gmail_messages:
        if thread_message.get("id") == current_message_id:
            continue
        thread_messages.append(await _thread_message_context(thread_message))

    if limit and len(thread_messages) > limit:
        thread_messages = thread_messages[-limit:]

    return thread_messages


@mcp.tool()
async def read_gmail_message(
    email: str,
    message_id: str,
    thread_id: Optional[str] = None,
    thread_context_limit: Optional[int] = None,
    mark_read: bool = False,
) -> dict:
    """
    Read full Gmail message by message_id.
    """
    total_started_at = time.perf_counter()
    timings: dict[str, float] = {}

    def mark_timing(name: str, started_at: float) -> None:
        timings[name] = round((time.perf_counter() - started_at) * 1000, 2)

    with observe_tool_call(
        "read_gmail_message",
        {"email": email, "message_id": message_id},
    ):
        mark_read_enabled = _env_enabled("GMAIL_MARK_READ_ENABLED")
        service_started_at = time.perf_counter()
        service = await get_gmail_service(email=email)
        mark_timing("gmail_service_ms", service_started_at)

        thread_messages: list[dict[str, Any]] = []
        thread_id = str(thread_id or "").strip() or None
        msg: dict[str, Any]

        if thread_id:
            with observe_tool_call(
                "gmail.threads.get",
                {"email": email, "thread_id": thread_id, "message_id": message_id},
            ):
                thread_get_started_at = time.perf_counter()
                thread = service.users().threads().get(
                    userId="me",
                    id=thread_id,
                    format="full",
                ).execute()
                mark_timing("gmail_threads_get_ms", thread_get_started_at)

            thread_gmail_messages = [
                message
                for message in thread.get("messages", [])
                if isinstance(message, dict)
            ]
            msg = next(
                (
                    thread_message
                    for thread_message in thread_gmail_messages
                    if str(thread_message.get("id") or "") == str(message_id)
                ),
                {},
            )
            if not msg:
                logger.warning(
                    "gmail_thread_missing_selected_message email=%s message_id=%s thread_id=%s",
                    email,
                    message_id,
                    thread_id,
                )
        else:
            thread_gmail_messages = []
            msg = {}

        if not msg:
            with observe_tool_call(
                "gmail.messages.get",
                {"email": email, "message_id": message_id},
            ):
                message_get_started_at = time.perf_counter()
                msg = service.users().messages().get(
                    userId="me",
                    id=message_id,
                    format="full",
                ).execute()
                mark_timing("gmail_messages_get_ms", message_get_started_at)
            thread_id = msg.get("threadId")

        if mark_read and "UNREAD" in set(msg.get("labelIds") or []):
            if mark_read_enabled:
                with observe_tool_call(
                    "gmail.messages.modify",
                    {"email": email, "message_id": message_id, "remove_label": "UNREAD"},
                ):
                    modify_started_at = time.perf_counter()
                    try:
                        service.users().messages().modify(
                            userId="me",
                            id=message_id,
                            body={"removeLabelIds": ["UNREAD"]},
                        ).execute()
                        mark_timing("gmail_mark_read_ms", modify_started_at)
                    except Exception as exc:
                        mark_timing("gmail_mark_read_ms", modify_started_at)
                        status = getattr(getattr(exc, "resp", None), "status", None)
                        if HttpError and isinstance(exc, HttpError) and status == 403:
                            logger.warning(
                                "gmail_mark_read_insufficient_scope_ignored email=%s message_id=%s",
                                email,
                                message_id,
                            )
                        else:
                            raise
            else:
                timings["gmail_mark_read_skipped_ms"] = 0.0

        headers = msg.get("payload", {}).get("headers", [])

        header_map = _header_map(headers)
        thread_id = msg.get("threadId") or thread_id

        with observe_tool_call(
            "extract_body",
            {"email": email, "message_id": message_id},
        ):
            extract_body_started_at = time.perf_counter()
            body = await extract_body(msg.get("payload", {}))
            mark_timing("extract_body_ms", extract_body_started_at)
        with observe_tool_call(
            "check_promotional_basic",
            {"email": email, "message_id": message_id},
        ):
            promotional_check_started_at = time.perf_counter()
            promotional_check = check_promotional_basic(msg)
            mark_timing("check_promotional_basic_ms", promotional_check_started_at)
        with observe_tool_call(
            "build_email_display_html",
            {"email": email, "message_id": message_id},
        ):
            display_html_started_at = time.perf_counter()
            display_parts = build_email_display_html(msg.get("payload", {}))
            mark_timing("build_email_display_html_ms", display_html_started_at)

        if thread_gmail_messages:
            thread_started_at = time.perf_counter()
            thread_messages = await _thread_context_from_messages(
                thread_gmail_messages,
                msg["id"],
                limit=thread_context_limit,
            )
            mark_timing("gmail_thread_context_ms", thread_started_at)
        else:
            try:
                thread_started_at = time.perf_counter()
                thread_messages = await _fetch_thread_messages(
                    service,
                    email,
                    msg["id"],
                    thread_id,
                    limit=thread_context_limit,
                )
                mark_timing("gmail_thread_context_ms", thread_started_at)
            except Exception as exc:
                mark_timing("gmail_thread_context_ms", thread_started_at)
                logger.warning(
                    "gmail_thread_context_fetch_failed: %s",
                    exc,
                    extra={"email": email, "message_id": message_id, "thread_id": thread_id},
                )
                thread_messages = []

        with observe_tool_call(
            "post_tool_process_gmail_message",
            {"email": email, "message_id": message_id},
        ):
            process_started_at = time.perf_counter()
            processed = post_tool_process_gmail_message({
                "id": msg["id"],
                "thread_id": thread_id,
                "from": header_map.get("from", ""),
                "to": header_map.get("to", ""),
                "cc": header_map.get("cc", ""),
                "bcc": header_map.get("bcc", ""),
                "subject": header_map.get("subject", ""),
                "date": header_map.get("date", ""),
                "snippet": msg.get("snippet", ""),
                "body": body,
                "thread_messages": thread_messages,
                "promotional_check": promotional_check,
            })
            processed.update(display_parts)
            ics_events = extract_ics_calendar_events(msg.get("payload", {}))
            if ics_events:
                processed["calendar_event"] = ics_events[0]
            processed["has_display_html"] = bool(display_parts.get("display_html"))
            mark_timing("post_process_and_response_ms", process_started_at)
            timings["total_ms"] = round((time.perf_counter() - total_started_at) * 1000, 2)
            logger.info(
                "gmail_full_message_timing email=%s message_id=%s thread_id=%s "
                "thread_message_count=%s has_display_html=%s timings=%s",
                email,
                message_id,
                thread_id,
                len(thread_messages),
                processed["has_display_html"],
                timings,
            )
            return processed


async def send_gmail_reply(
    email: str,
    message_id: str,
    reply_body: str,
    reply_html: Optional[str] = None,
    attachments: Optional[list[dict[str, Any]]] = None,
    to: str = "",
    cc: str = "",
    bcc: str = "",
) -> dict:
    """Send a Gmail reply in the original thread with optional sanitized HTML."""
    _require_allowed_gmail_send_source()
    clean_body = str(reply_body or "").strip()
    clean_html = sanitize_outgoing_email_html(reply_html or "")
    if not clean_body and clean_html:
        clean_body = html_to_plain_text(clean_html)
    if not clean_body:
        raise ValueError("Reply body cannot be empty.")

    with observe_tool_call(
        "send_gmail_reply",
        {"email": email, "message_id": message_id},
    ):
        service = await get_gmail_service(email=email)

        original = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Reply-To", "Subject", "Message-ID", "References"],
        ).execute()

        headers = _header_map(original.get("payload", {}).get("headers", []))
        recipient = str(to or "").strip()
        if not recipient:
            raise ValueError("Reply recipient is required.")
        clean_cc = str(cc or "").strip()
        clean_bcc = str(bcc or "").strip()

        outbound = EmailMessage()
        outbound["To"] = recipient
        outbound["From"] = email
        if clean_cc:
            outbound["Cc"] = clean_cc
        if clean_bcc:
            outbound["Bcc"] = clean_bcc
        outbound["Subject"] = _reply_subject(headers.get("subject", ""))
        outbound["Date"] = formatdate(localtime=True)
        outbound["Message-ID"] = make_msgid()

        original_message_id = headers.get("message-id", "").strip()
        if original_message_id:
            outbound["In-Reply-To"] = original_message_id
            references = headers.get("references", "").strip()
            outbound["References"] = (
                f"{references} {original_message_id}".strip()
                if references
                else original_message_id
            )

        set_email_content(outbound, clean_body, clean_html)
        attach_email_files(outbound, attachments)

        body = {
            "raw": _base64url_message(outbound),
            "threadId": original.get("threadId"),
        }
        return service.users().messages().send(userId="me", body=body).execute()


async def send_gmail_message(
    email: str,
    to_address: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachments: Optional[list[dict[str, Any]]] = None,
    cc: str = "",
    bcc: str = "",
) -> dict:
    """Send a new Gmail message with optional sanitized HTML."""
    _require_allowed_gmail_send_source()
    clean_to = parseaddr(str(to_address or "").strip())[1]
    clean_cc = str(cc or "").strip()
    clean_bcc = str(bcc or "").strip()
    clean_subject = str(subject or "").strip()
    clean_body = str(body_text or "").strip()
    clean_html = sanitize_outgoing_email_html(body_html or "")
    if not clean_body and clean_html:
        clean_body = html_to_plain_text(clean_html)
    if not clean_to:
        raise ValueError("Recipient cannot be empty.")
    if not clean_body:
        raise ValueError("Message body cannot be empty.")

    with observe_tool_call(
        "send_gmail_message",
        {"email": email, "to": clean_to},
    ):
        service = await get_gmail_service(email=email)

        outbound = EmailMessage()
        outbound["To"] = clean_to
        if clean_cc:
            outbound["Cc"] = clean_cc
        if clean_bcc:
            outbound["Bcc"] = clean_bcc
        outbound["From"] = email
        outbound["Subject"] = clean_subject
        outbound["Date"] = formatdate(localtime=True)
        outbound["Message-ID"] = make_msgid()
        set_email_content(outbound, clean_body, clean_html)
        attach_email_files(outbound, attachments)

        return service.users().messages().send(
            userId="me",
            body={"raw": _base64url_message(outbound)},
        ).execute()
