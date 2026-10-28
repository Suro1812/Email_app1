import base64
import asyncio
import html as html_lib
import logging
import time
from html.parser import HTMLParser
from datetime import date as DateType, datetime, time as TimeType
from typing import Any, Optional

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

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDENTIALS_PATH = "credentials.json"

mcp = FastMCP("gmail-mcp-server")
logger = logging.getLogger(__name__)

GMAIL_MAILBOXES: dict[str, dict[str, Any]] = {
    "inbox": {"label_ids": ["INBOX"], "title": "Inbox"},
    "starred": {"label_ids": ["STARRED"], "title": "Starred"},
    "snoozed": {"query": "in:snoozed", "title": "Snoozed"},
    "important": {"label_ids": ["IMPORTANT"], "title": "Important"},
    "sent": {"label_ids": ["SENT"], "title": "Sent"},
    "drafts": {"label_ids": ["DRAFT"], "title": "Drafts"},
    "purchases": {"query": "category:purchases", "title": "Purchases"},
    "social": {"query": "category:social", "title": "Social"},
    "updates": {"query": "category:updates", "title": "Updates"},
    "forums": {"query": "category:forums", "title": "Forums"},
    "promotions": {"query": "category:promotions", "title": "Promotions"},
    "more": {"title": "More"},
    "search": {"title": "Search"},
}

MAX_SEARCH_QUERY_LENGTH = 500

GMAIL_INBOX_CATEGORIES: dict[str, dict[str, str]] = {
    "primary": {"query": "category:primary", "title": "Primary"},
    "promotions": {"query": "category:promotions", "title": "Promotions"},
    "social": {"query": "category:social", "title": "Social"},
    "updates": {"query": "category:updates", "title": "Updates"},
}


async def get_credentials_from_db(email: str):
    from app.core.auth import get_credentials_from_db as _get_credentials_from_db

    return await _get_credentials_from_db(email)


def build(*args, **kwargs):
    from googleapiclient.discovery import build as _build

    return _build(*args, **kwargs)


async def get_gmail_service(email: str):
    """
    Get Gmail service for a user.
    If email not provided, start OAuth flow for new user.
    """
    # Get existing user credentials from database
    creds = await get_credentials_from_db(email)
    return await asyncio.to_thread(
        build,
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False,
    )


def _header_map(headers: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(header.get("name", "")).lower(): str(header.get("value", ""))
        for header in headers
    }


async def list_gmail_mailbox_messages(
    email: str,
    mailbox: str = "inbox",
    category: str = "primary",
    limit: int = 50,
    page_token: Optional[str] = None,
    unread_only: bool = False,
    search_query: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch current Gmail messages for a UI mailbox/category, or a free-text search."""
    total_started_at = time.perf_counter()
    timings: dict[str, float] = {}
    batch_request_count = 0
    used_batch_fallback = False

    def mark_timing(name: str, started_at: float) -> None:
        timings[name] = round((time.perf_counter() - started_at) * 1000, 2)

    mailbox_key = str(mailbox or "inbox").lower()
    mailbox_config = GMAIL_MAILBOXES.get(mailbox_key)
    if not mailbox_config:
        raise ValueError(f"Unsupported Gmail mailbox: {mailbox}")
    category_key = str(category or "primary").lower()
    inbox_category = GMAIL_INBOX_CATEGORIES.get(category_key) if mailbox_key == "inbox" else None
    if mailbox_key == "inbox" and not inbox_category:
        raise ValueError(f"Unsupported Gmail inbox category: {category}")

    clean_search_query = " ".join(str(search_query or "").split())[:MAX_SEARCH_QUERY_LENGTH]
    if mailbox_key == "search" and not clean_search_query:
        raise ValueError("Search needs a query.")

    safe_limit = max(1, min(int(limit or 50), 100))
    service = await get_gmail_service(email=email)

    list_kwargs: dict[str, Any] = {
        "userId": "me",
        "maxResults": safe_limit,
        "fields": "threads(id),nextPageToken,resultSizeEstimate",
    }
    clean_page_token = str(page_token or "").strip()
    if clean_page_token:
        list_kwargs["pageToken"] = clean_page_token
    if mailbox_config.get("label_ids"):
        label_ids = list(mailbox_config["label_ids"])
        if unread_only and "UNREAD" not in label_ids:
            label_ids.append("UNREAD")
        list_kwargs["labelIds"] = label_ids
    query_parts = [
        str(mailbox_config.get("query") or "").strip(),
        str((inbox_category or {}).get("query") or "").strip(),
        clean_search_query,
    ]
    query = " ".join(part for part in query_parts if part)
    if unread_only and "is:unread" not in query.lower():
        query = f"{query} is:unread".strip()
    if query:
        list_kwargs["q"] = query

    threads_list_started_at = time.perf_counter()
    response = await asyncio.to_thread(
        service.users().threads().list(**list_kwargs).execute
    )
    mark_timing("threads_list_ms", threads_list_started_at)
    thread_refs = response.get("threads", [])

    def fetch_thread_metadata(thread_id: str) -> dict[str, Any]:
        return service.users().threads().get(
            userId="me",
            id=thread_id,
            format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
            fields=(
                "id,snippet,messages("
                "id,threadId,labelIds,snippet,internalDate,"
                "payload/headers(name,value)"
                ")"
            ),
        ).execute()

    def latest_thread_message(gmail_thread: dict[str, Any]) -> dict[str, Any]:
        thread_messages = [
            message
            for message in gmail_thread.get("messages", [])
            if isinstance(message, dict)
        ]
        if not thread_messages:
            return {}
        return max(
            thread_messages,
            key=lambda message: int(str(message.get("internalDate") or "0")),
        )

    def format_thread(gmail_thread: dict[str, Any], fallback_id: str) -> dict[str, Any]:
        gmail_message = latest_thread_message(gmail_thread)
        headers = _header_map(gmail_message.get("payload", {}).get("headers", []))
        thread_id = gmail_thread.get("id") or gmail_message.get("threadId") or fallback_id
        thread_messages = [
            message
            for message in gmail_thread.get("messages", [])
            if isinstance(message, dict)
        ]
        return {
            "message_id": gmail_message.get("id", fallback_id),
            "thread_id": thread_id,
            "thread_message_count": len(thread_messages),
            "subject": headers.get("subject", "(No subject)"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "date": headers.get("date", ""),
            "internal_date": str(gmail_message.get("internalDate", "")),
            "snippet": gmail_message.get("snippet", ""),
            "summary": gmail_message.get("snippet", ""),
            "label_ids": gmail_message.get("labelIds", []),
        }

    def fetch_thread_metadata_batch() -> list[dict[str, Any]]:
        nonlocal batch_request_count
        results: dict[str, dict[str, Any]] = {}
        exceptions: dict[str, str] = {}

        def callback(request_id: str, response: Any, exception: Exception) -> None:
            if exception:
                exceptions[str(request_id)] = str(exception)
                return
            if not response:
                return
            results[str(request_id)] = response

        batch_build_started_at = time.perf_counter()
        batch = service.new_batch_http_request(callback=callback)
        for thread_ref in thread_refs:
            thread_id = thread_ref.get("id")
            if not thread_id:
                continue
            batch_request_count += 1
            batch.add(
                service.users().threads().get(
                    userId="me",
                    id=str(thread_id),
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                    fields=(
                        "id,snippet,messages("
                        "id,threadId,labelIds,snippet,internalDate,"
                        "payload/headers(name,value)"
                        ")"
                    ),
                ),
                request_id=str(thread_id),
            )
        mark_timing("metadata_batch_build_ms", batch_build_started_at)
        batch_execute_started_at = time.perf_counter()
        batch.execute()
        mark_timing("metadata_batch_execute_ms", batch_execute_started_at)
        if exceptions:
            logger.warning(
                "gmail_mailbox_metadata_batch_partial_failures",
                extra={
                    "email": email,
                    "mailbox": mailbox_key,
                    "category": category_key if inbox_category else "",
                    "failure_count": len(exceptions),
                    "request_count": batch_request_count,
                },
            )
        parse_started_at = time.perf_counter()
        formatted = [
            format_thread(results[str(thread_ref["id"])], str(thread_ref["id"]))
            for thread_ref in thread_refs
            if thread_ref.get("id") and str(thread_ref["id"]) in results
        ]
        mark_timing("response_parsing_ms", parse_started_at)
        return formatted

    try:
        messages = await asyncio.to_thread(fetch_thread_metadata_batch)
    except Exception as exc:
        used_batch_fallback = True
        logger.warning(
            "gmail_mailbox_metadata_batch_failed_falling_back",
            extra={
                "email": email,
                "mailbox": mailbox_key,
                "category": category_key if inbox_category else "",
                "thread_count": len(thread_refs),
                "error": str(exc),
            },
        )
        fallback_started_at = time.perf_counter()
        messages = []
        for thread_ref in thread_refs:
            thread_id = thread_ref.get("id")
            if not thread_id:
                continue
            gmail_thread = await asyncio.to_thread(fetch_thread_metadata, str(thread_id))
            messages.append(format_thread(gmail_thread, str(thread_id)))
        mark_timing("metadata_fallback_total_ms", fallback_started_at)

    db_started_at = time.perf_counter()
    try:
        from app.core.database import list_message_analysis_states

        analysis_states = list_message_analysis_states(
            email,
            [message["message_id"] for message in messages if message.get("message_id")],
        )
    except Exception:
        analysis_states = {}
    mark_timing("analysis_state_lookup_ms", db_started_at)

    response_build_started_at = time.perf_counter()
    for message in messages:
        analysis_state = analysis_states.get(str(message.get("message_id")), {})
        message["processing_status"] = analysis_state.get("processing_status", "pending")
        message["skip_reason"] = analysis_state.get("skip_reason")
        message["detected_intent"] = analysis_state.get("detected_intent")
        message["calendar_event"] = analysis_state.get("calendar_event")
        message["analysis_updated_at"] = analysis_state.get("updated_at")

    payload = {
        "email": email,
        "mailbox": mailbox_key,
        "title": mailbox_config["title"],
        "category": category_key if inbox_category else "",
        "category_title": inbox_category["title"] if inbox_category else "",
        "unread_only": unread_only,
        "result_size_estimate": response.get("resultSizeEstimate", len(messages)),
        "messages": messages,
        "next_page_token": response.get("nextPageToken"),
    }
    mark_timing("fastapi_response_construction_ms", response_build_started_at)
    timings["total_ms"] = round((time.perf_counter() - total_started_at) * 1000, 2)
    logger.info(
        "gmail_mailbox_messages_timing email=%s mailbox=%s category=%s limit=%s "
        "thread_ref_count=%s message_count=%s metadata_request_count=%s "
        "used_batch_fallback=%s timings=%s",
        email,
        mailbox_key,
        category_key if inbox_category else "",
        safe_limit,
        len(thread_refs),
        len(messages),
        batch_request_count or len(thread_refs),
        used_batch_fallback,
        timings,
    )
    return payload


async def filter_primary_inbox_message_ids(email: str, message_ids: list[str]) -> list[str]:
    """Keep only Gmail messages that belong to Inbox Primary."""
    clean_ids = [str(message_id).strip() for message_id in message_ids if str(message_id).strip()]
    if not clean_ids:
        return []

    service = await get_gmail_service(email=email)

    def fetch_label_map() -> dict[str, set[str]]:
        results: dict[str, set[str]] = {}

        def callback(request_id: str, response: Any, exception: Exception) -> None:
            if exception or not response:
                return
            results[str(request_id)] = set(response.get("labelIds") or [])

        batch = service.new_batch_http_request(callback=callback)
        for message_id in clean_ids:
            batch.add(
                service.users().messages().get(
                    userId="me",
                    id=message_id,
                    format="minimal",
                    fields="id,labelIds",
                ),
                request_id=message_id,
            )
        batch.execute()
        return results

    label_map = await asyncio.to_thread(fetch_label_map)
    return [
        message_id
        for message_id in clean_ids
        if {"INBOX", "CATEGORY_PERSONAL"}.issubset(label_map.get(message_id, set()))
    ]


def decode_gmail_data(data: str) -> str:
    if not data:
        return ""

    data = data.replace("-", "+").replace("_", "/")
    data += "=" * (-len(data) % 4)

    return base64.b64decode(data).decode("utf-8", errors="ignore")


def _decoded_gmail_bytes(data: str) -> bytes:
    if not data:
        return b""
    clean_data = data.replace("-", "+").replace("_", "/")
    clean_data += "=" * (-len(clean_data) % 4)
    return base64.b64decode(clean_data)


def _calendar_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, DateType):
        return datetime.combine(value, TimeType.min)
    return None


def _calendar_value(component: Any, name: str, default: str = "") -> str:
    value = component.get(name)
    return str(value) if value is not None else default


def _parse_ics_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if ":" in text:
        text = text.split(":", 1)[1]
    text = text.replace("Z", "")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%Y%m%d":
                return datetime.combine(parsed.date(), TimeType.min)
            return parsed
        except ValueError:
            continue
    return None


def _unfold_ics_lines(raw_text: str) -> list[str]:
    lines = []
    for raw_line in str(raw_text or "").splitlines():
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line.strip())
    return lines


def _fallback_parse_ics_calendar_events(raw_ics: bytes) -> list[dict[str, Any]]:
    text = raw_ics.decode("utf-8", errors="ignore")
    events = []
    current: Optional[dict[str, str]] = None
    for line in _unfold_ics_lines(text):
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT" and current is not None:
            start_at = _parse_ics_datetime(current.get("DTSTART", ""))
            if start_at:
                end_at = _parse_ics_datetime(current.get("DTEND", ""))
                events.append(
                    {
                        "detected": True,
                        "uid": current.get("UID", ""),
                        "title": current.get("SUMMARY", "Email event"),
                        "start_at": start_at.isoformat(),
                        "end_at": end_at.isoformat() if end_at and end_at >= start_at else None,
                        "location": current.get("LOCATION", ""),
                        "status": current.get("STATUS", ""),
                        "organizer": current.get("ORGANIZER", ""),
                        "notification_minutes_before": 15,
                        "event_kind": "ics_invite",
                        "source": "ics",
                    }
                )
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean_key = key.split(";", 1)[0].upper()
        if clean_key in {"UID", "SUMMARY", "DTSTART", "DTEND", "LOCATION", "STATUS", "ORGANIZER"}:
            current[clean_key] = value.strip()
    return events


def parse_ics_calendar_events(raw_ics: bytes) -> list[dict[str, Any]]:
    if not raw_ics:
        return []
    try:
        from icalendar import Calendar
    except ImportError:
        return _fallback_parse_ics_calendar_events(raw_ics)

    calendar = Calendar.from_ical(raw_ics)
    events = []
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue
        start_at = _calendar_datetime(component.decoded("dtstart", None))
        if not start_at:
            continue
        end_at = _calendar_datetime(component.decoded("dtend", None))
        events.append(
            {
                "detected": True,
                "uid": _calendar_value(component, "uid"),
                "title": _calendar_value(component, "summary", "Email event"),
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat() if end_at and end_at >= start_at else None,
                "location": _calendar_value(component, "location"),
                "status": _calendar_value(component, "status"),
                "organizer": _calendar_value(component, "organizer"),
                "notification_minutes_before": 15,
                "event_kind": "ics_invite",
                "source": "ics",
            }
        )
    return events


def extract_ics_calendar_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    def walk(part: dict[str, Any]) -> None:
        mime_type = str(part.get("mimeType") or "").lower()
        filename = str(part.get("filename") or "").lower()
        body_data = part.get("body", {}).get("data")
        is_calendar_part = mime_type in {"text/calendar", "application/ics"} or filename.endswith(".ics")
        if is_calendar_part and body_data:
            try:
                events.extend(parse_ics_calendar_events(_decoded_gmail_bytes(body_data)))
            except (ValueError, TypeError):
                pass

        for sub_part in part.get("parts", []):
            walk(sub_part)

    walk(payload)
    return events


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._ignored_depth = 0

    def _append_break(self) -> None:
        if self._parts and self._parts[-1] != "\n":
            self._parts.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag_name in self._BLOCK_TAGS:
            self._append_break()

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag_name in self._BLOCK_TAGS:
            self._append_break()

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        clean = str(data or "").strip()
        if clean:
            self._parts.append(clean)

    def text(self) -> str:
        text = " ".join(self._parts)
        return "\n".join(
            line.strip()
            for line in text.splitlines()
            if line.strip()
        )


def html_to_text(html_code: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(str(html_code or ""))
    return parser.text()


def extract_email_parts(payload: dict[str, Any]) -> dict[str, Any]:
    headers = {
        h.get("name", "").lower(): h.get("value", "")
        for h in payload.get("headers", [])
    }

    plain_text = ""
    html_code = ""

    def walk(part: dict[str, Any]) -> None:
        nonlocal plain_text, html_code

        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")

        if body_data:
            decoded = decode_gmail_data(body_data)

            if mime_type == "text/plain":
                plain_text += "\n" + decoded
            elif mime_type == "text/html":
                html_code += "\n" + decoded

        for sub_part in part.get("parts", []):
            walk(sub_part)

    walk(payload)

    return {
        "headers": headers,
        "plain_text": plain_text.strip(),
        "html_code": html_code.strip(),
    }


_DISPLAY_BLOCKED_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "base",
    "link",
    "meta",
}
_DISPLAY_URL_ATTRS = {"href", "src", "xlink:href", "formaction", "poster", "background"}
_DISPLAY_SAFE_LINK_PREFIXES = ("http://", "https://", "mailto:", "tel:")
_DISPLAY_BLOCKED_URL_PREFIXES = (
    "javascript:",
    "vbscript:",
    "data:text/html",
    "data:application/xhtml",
)


def sanitize_email_display_html(html_code: str) -> str:
    """Keep email HTML visual markup, but remove active browser surfaces."""
    raw_html = str(html_code or "").strip()
    if not raw_html:
        return ""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html_lib.escape(raw_html)

    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(_DISPLAY_BLOCKED_TAGS):
        tag.decompose()

    for tag in soup.find_all(True):
        for attr, value in list(tag.attrs.items()):
            attr_name = str(attr).lower()
            values = value if isinstance(value, list) else [value]
            attr_value = " ".join(str(item) for item in values).strip().lower()
            if attr_name.startswith("on") or attr_name == "srcdoc":
                del tag.attrs[attr]
            elif attr_name in _DISPLAY_URL_ATTRS and attr_value.startswith(
                _DISPLAY_BLOCKED_URL_PREFIXES
            ):
                del tag.attrs[attr]

        if str(tag.name).lower() == "a" and tag.has_attr("href"):
            href_value = str(tag.get("href") or "").strip()
            if href_value.lower().startswith(_DISPLAY_SAFE_LINK_PREFIXES):
                tag["target"] = "_blank"
                tag["rel"] = "noopener noreferrer nofollow"
            else:
                del tag.attrs["href"]

    return str(soup).strip()


def build_email_display_html(payload: dict[str, Any]) -> dict[str, str]:
    """Return UI-only email HTML plus plain text fallback from a Gmail payload."""
    parts = extract_email_parts(payload)
    return {
        "display_html": sanitize_email_display_html(parts.get("html_code", "")),
        "display_text": str(parts.get("plain_text") or "").strip(),
    }


def check_promotional_basic(gmail_message: dict[str, Any]) -> dict[str, Any]:
    payload = gmail_message.get("payload", {})
    extracted = extract_email_parts(payload)

    headers = extracted["headers"]
    plain_text = extracted["plain_text"]
    html_code = extracted["html_code"]

    has_list_unsubscribe_header = "list-unsubscribe" in headers
    has_html_code = bool(html_code)
    readable_text = plain_text or html_to_text(html_code)
    plain_text_word_count = len(readable_text.split())

    skip_llm = (
        has_list_unsubscribe_header
        or plain_text_word_count < 5
    )

    return {
        "has_list_unsubscribe_header": has_list_unsubscribe_header,
        "has_html_code": has_html_code,
        "plain_text_word_count": plain_text_word_count,
        "skip_llm": skip_llm,
    }

async def extract_body(payload: dict[str, Any]) -> str:
    """
    Extract plain text body from Gmail message payload.
    """
    if "parts" in payload:
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data")

            if mime_type == "text/plain" and body_data:
                return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

        for part in payload["parts"]:
            nested = await extract_body(part)
            if nested:
                return nested

    body_data = payload.get("body", {}).get("data")
    if body_data:
        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
        if payload.get("mimeType") == "text/html":
            return html_to_text(decoded)
        return decoded

    return ""
