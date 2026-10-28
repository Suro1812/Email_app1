"""
Post-tool sanitization hooks for Gmail content.

The hooks in this module treat email content as untrusted input before it is
displayed or forwarded into an agent prompt. They remove HTML/XSS surfaces,
decompose hidden prompt carriers, mask PII from message fields, and wrap
sanitized content as external source text.
"""

import html
import logging
import os
import re
from typing import Callable, Tuple

from bs4 import BeautifulSoup

from app.observability import observe_hook_call

logger = logging.getLogger(__name__)

try:
    from presidio_analyzer import AnalyzerEngine
except ImportError:  # pragma: no cover
    AnalyzerEngine = None


HtmlHook = Callable[[object], None]

_DANGEROUS_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "base",
    "link",
    "svg",
    "math",
    "noscript",
}
_HIDDEN_PROMPT_ATTRS = {
    "alt",
    "aria-description",
    "aria-label",
    "aria-labelledby",
    "aria-roledescription",
    "content",
    "placeholder",
    "title",
}
_EXTERNAL_SOURCE_OPEN = "<external_source>"
_EXTERNAL_SOURCE_CLOSE = "</external_source>"
_PII_ENGINE = None
_PII_ENGINE_LOAD_FAILED = False


def _safe_tag_attrs(tag: object) -> dict:
    try:
        attrs = getattr(tag, "attrs", None)
    except Exception:
        return {}
    return attrs if isinstance(attrs, dict) else {}


def _safe_tag_name(tag: object) -> str:
    try:
        return str(getattr(tag, "name", "") or "").lower()
    except Exception:
        return ""


def _decompose_dangerous_tags(soup: object) -> None:
    for node in soup.find_all(_DANGEROUS_TAGS):
        node.decompose()


def _decompose_hidden_prompt_carriers(soup: object) -> None:
    for tag in list(soup.find_all(True)):
        attrs = _safe_tag_attrs(tag)
        if not attrs:
            continue
        attr_names = {str(name).lower() for name in attrs}

        if _safe_tag_name(tag) == "meta":
            tag.decompose()
            continue

        if attr_names.intersection(_HIDDEN_PROMPT_ATTRS):
            tag.decompose()


def _decompose_white_or_hidden_text(soup: object) -> None:
    for tag in list(soup.find_all(True)):
        if not _safe_tag_attrs(tag):
            continue
        get_attr = getattr(tag, "get", None)
        if not callable(get_attr):
            continue
        try:
            style = str(get_attr("style", "")).replace(" ", "").lower()
        except Exception:
            continue
        if not style:
            continue

        if (
            "display:none" in style
            or "visibility:hidden" in style
            or "opacity:0" in style
            or "font-size:0" in style
            or "mso-hide:all" in style
            or "color:white" in style
            or "color:#fff" in style
            or "color:#ffffff" in style
            or "color:rgb(255,255,255)" in style
        ):
            tag.decompose()


_HTML_HOOKS: Tuple[HtmlHook, ...] = (
    _decompose_dangerous_tags,
    _decompose_hidden_prompt_carriers,
    _decompose_white_or_hidden_text,
)


def _sanitize_html(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for hook in _HTML_HOOKS:
        with observe_hook_call(hook.__name__):
            hook(soup)
    return soup.get_text(" ", strip=True)


def _mask_pii_with_presidio(text: str) -> str:
    global _PII_ENGINE, _PII_ENGINE_LOAD_FAILED

    if os.getenv("ENABLE_PRESIDIO_PII", "").strip().lower() not in {"1", "true", "yes"}:
        return text

    if not AnalyzerEngine or _PII_ENGINE_LOAD_FAILED:
        return text

    if not _PII_ENGINE:
        try:
            _PII_ENGINE = AnalyzerEngine()
        except Exception as exc:  # pragma: no cover - depends on local NLP setup
            _PII_ENGINE_LOAD_FAILED = True
            logger.warning("Presidio Analyzer could not be initialized: %s", exc)
            return text

    with observe_hook_call("_mask_pii_with_presidio"):
        results = _PII_ENGINE.analyze(text=text, language="en")
        for result in sorted(results, key=lambda item: item.start, reverse=True):
            label = result.entity_type.replace("_ADDRESS", "").replace("_", " ").upper()
            replacement = f"[{label} REDACTED]"
            text = text[: result.start] + replacement + text[result.end :]
    return text


def _mask_pii(text: str) -> str:
    if not text:
        return text

    return _mask_pii_with_presidio(text)


def _wrap_external_source(text: str) -> str:
    if not text:
        return text
    return f"{_EXTERNAL_SOURCE_OPEN}{text}{_EXTERNAL_SOURCE_CLOSE}"


def sanitize_text_for_tool_use(text: str) -> str:
    """Normalize a Gmail field for safe prompt usage and data display."""
    if not isinstance(text, str) or not text:
        return ""

    with observe_hook_call("sanitize_text_for_tool_use"):
        sanitized = _sanitize_html(text)
        sanitized = html.unescape(sanitized)
        sanitized = html.escape(sanitized)
        sanitized = _mask_pii(sanitized)
        sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()
        sanitized = _wrap_external_source(sanitized)

    if sanitized != text:
        logger.debug(
            "sanitize_text_for_tool_use changed text from %r to %r",
            text,
            sanitized,
        )

    return sanitized


def post_tool_process_gmail_message(message: dict) -> dict:
    """Sanitize Gmail message fields after reading the message from Gmail."""
    if not isinstance(message, dict):
        return message

    with observe_hook_call(
        "post_tool_process_gmail_message",
        {"message_id": message.get("id")},
    ):
        processed = message.copy()

        for key in ("subject", "snippet", "body"):
            processed[key] = sanitize_text_for_tool_use(processed.get(key, ""))

        processed["from"] = _mask_pii(str(processed.get("from", "")))
        processed["to"] = _mask_pii(str(processed.get("to", "")))
        processed["sanitized"] = True
        processed["prompt_injection_detected"] = False

        return processed
