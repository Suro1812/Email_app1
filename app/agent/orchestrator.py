import asyncio
import json
import importlib
import logging
import os
import re
import urllib.error
import urllib.request
from time import perf_counter
from functools import lru_cache
from datetime import datetime
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *args, **kwargs: None

from app.agent.skills import load_skill as _load_skill_impl

load_dotenv()
logger = logging.getLogger(__name__)
AGENT_IO_LOG_DIR = Path(os.getenv("AGENT_IO_LOG_DIR", "logs/agent_io"))


class Settings:
    VLLM_BASE_URL: str = os.getenv(
        "VLLM_BASE_URL",
        os.getenv(
            "OLLAMA_BASE_URL",
            os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1"),
        ),
    )
    VLLM_API_KEY: str = os.getenv(
        "VLLM_API_KEY",
        os.getenv("OLLAMA_API_KEY", os.getenv("OPENAI_API_KEY", "EMPTY")),
    )
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", os.getenv("VLLM_MODEL", "local-model"))
    ANALYST_MODEL: str = os.getenv(
        "ANALYST_MODEL",
        OLLAMA_MODEL,
    )
    SUMMARY_MODEL: str = os.getenv("SUMMARY_MODEL", ANALYST_MODEL)
    ANALYZER_MODEL: str = os.getenv("ANALYZER_MODEL", ANALYST_MODEL)
    REPLY_MODEL: str = os.getenv("REPLY_MODEL", ANALYST_MODEL)
    ORCHESTRATOR_MODEL: str = os.getenv("ORCHESTRATOR_MODEL", ANALYST_MODEL)
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
    SUMMARY_MAX_TOKENS: int = int(os.getenv("SUMMARY_MAX_TOKENS", "500"))
    REPLY_MAX_TOKENS: int = int(os.getenv("REPLY_MAX_TOKENS", "500"))
    WRITER_MAX_TOKENS: int = int(os.getenv("WRITER_MAX_TOKENS", os.getenv("REPLY_MAX_TOKENS", "500")))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0"))

    @classmethod
    def require_model(cls) -> None:
        if not cls.ANALYST_MODEL:
            raise RuntimeError("Missing ANALYST_MODEL or VLLM_MODEL environment variable.")


Settings.require_model()
_langfuse_callback_handler = None

ANALYZER_SKILL_NAME = "analyzer_agent"
SUMMARIZER_SKILL_NAME = "summarizer_agent"
REPLY_SKILL_NAME = "reply_agent"
WRITER_SKILL_NAME = "writer_agent"


class EmailAnalysisState(TypedDict, total=False):
    email: str
    messages: List[Dict[str, Any]]
    analysis_message_indexes: List[int]
    analysis: Dict[str, Any]
    results: List[Dict[str, Any]]
    result: Dict[str, Any]


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


@lru_cache(maxsize=32)
def load_skill(skill_name: str) -> str:
    """Load skill from cache or disk. LRU cache prevents repeated file reads."""
    return _load_skill_impl(skill_name)


async def _response_text(response: Any) -> str:
    """Extract text from a chat completion or legacy content response."""
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if content:
            return str(content).strip()

    content = getattr(response, "content", None)
    if not content:
        raise RuntimeError("Empty response from LLM API.")
    if isinstance(content, str):
        return content.strip()
    first = content[0]
    text = getattr(first, "text", None)
    if text is None and isinstance(first, dict):
        text = first.get("text", "")
    return str(text or "").strip()


ANALYZER_TOOL_NAME = "analyze_message_context"
ANALYZER_REQUIRED_FIELDS = {
    "category",
    "event_type",
    "title",
    "description",
    "start_date",
    "start_time",
    "end_date",
    "end_time",
    "location",
    "participants",
    "meeting_platform",
    "requires_confirmation",
    "confidence",
    "reason",
}
ANALYZER_OPTIONAL_FIELDS = {
    "calendar_event",
}
ANALYZER_CATEGORIES = {"calendar_event", "reminder", "none"}
ANALYZER_EVENT_TYPES = {
    "meeting",
    "appointment",
    "interview",
    "travel",
    "reservation",
    "webinar",
    "deadline",
    "task_reminder",
    "follow_up",
    "payment",
    "renewal",
    "other",
    "none",
}
ANALYZER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": ANALYZER_TOOL_NAME,
            "description": (
                "Analyze current Gmail messages with thread context and detect "
                "actionable calendar events or reminders."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "description": (
                            "One decision object per input message, in the same order. "
                            "Do not include Gmail metadata; code attaches metadata."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "enum": ["calendar_event", "reminder", "none"],
                                },
                                "event_type": {
                                    "type": "string",
                                    "enum": sorted(ANALYZER_EVENT_TYPES),
                                },
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "start_date": {"type": "string"},
                                "start_time": {"type": ["string", "null"]},
                                "end_date": {"type": ["string", "null"]},
                                "end_time": {"type": ["string", "null"]},
                                "location": {"type": ["string", "null"]},
                                "participants": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "meeting_platform": {"type": ["string", "null"]},
                                "requires_confirmation": {"type": "boolean"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "reason": {"type": "string"},
                            },
                            "required": sorted(ANALYZER_REQUIRED_FIELDS),
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["messages"],
                "additionalProperties": False,
            },
        },
    }
]

SUMMARY_TOOL_NAME = "summarize_email"
SUMMARY_REQUIRED_FIELDS = {"summary"}
SUMMARY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": SUMMARY_TOOL_NAME,
            "description": "Summarize one longer Gmail message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Concise summary of the email body and thread context.",
                    },
                },
                "required": ["summary"],
                "additionalProperties": False,
            },
        },
    }
]

REPLY_TOOL_NAME = "draft_email_reply"
REPLY_REQUIRED_FIELDS = {"suggested_reply", "tone", "confidence"}
REPLY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": REPLY_TOOL_NAME,
            "description": "Draft a suggested reply for one analyzed Gmail message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "suggested_reply": {"type": "string"},
                    "tone": {
                        "type": "string",
                        "enum": ["professional", "friendly", "short", "formal"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["suggested_reply", "tone", "confidence"],
                "additionalProperties": False,
            },
        },
    }
]


async def extract_tool_input(response: Any, tool_name: str) -> Dict[str, Any]:
    langchain_tool_calls = getattr(response, "tool_calls", None) or []
    for tool_call in langchain_tool_calls:
        if isinstance(tool_call, dict):
            name = tool_call.get("name")
            if name != tool_name:
                continue
            args = tool_call.get("args", {})
            if not isinstance(args, dict):
                raise RuntimeError(f"Tool {tool_name} arguments must be a JSON object.")
            return args

    additional_kwargs = getattr(response, "additional_kwargs", {}) or {}
    for tool_call in additional_kwargs.get("tool_calls", []) or []:
        function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        name = function.get("name")
        if name != tool_name:
            continue
        arguments = function.get("arguments", "{}")
        try:
            parsed = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Tool {tool_name} returned invalid JSON arguments.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Tool {tool_name} arguments must be a JSON object.")
        return parsed

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            name = getattr(function, "name", None)
            if name != tool_name:
                continue

            arguments = getattr(function, "arguments", "{}")
            if isinstance(arguments, dict):
                return arguments
            try:
                parsed = json.loads(arguments or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Tool {tool_name} returned invalid JSON arguments.") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError(f"Tool {tool_name} arguments must be a JSON object.")
            return parsed

    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            return block.input

    raise RuntimeError(f"Model did not call tool: {tool_name}")


def _to_openai_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if tools is None:
        return None

    openai_tools = []
    for tool in tools:
        if tool.get("type") == "function":
            openai_tools.append(tool)
            continue

        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object"}),
                },
            }
        )
    return openai_tools


def _to_openai_tool_choice(tool_choice: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if tool_choice is None:
        return None
    if tool_choice.get("type") == "function":
        return tool_choice
    return {"type": "function", "function": {"name": tool_choice["name"]}}


def _tool_choice_name(tool_choice: Dict[str, Any]) -> str:
    if tool_choice.get("type") == "function":
        return tool_choice["function"]["name"]
    return tool_choice["name"]


def _get_langfuse_callbacks() -> List[Any]:
    global _langfuse_callback_handler

    if not _env_flag("ENABLE_LANGFUSE_CALLBACKS", default=False):
        return []

    if _langfuse_callback_handler is not None:
        return [_langfuse_callback_handler]

    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        try:
            from langfuse.callback import CallbackHandler
        except ImportError:
            logger.warning(
                "Langfuse callback handler is not installed; token usage will not be traced."
            )
            return []

    try:
        _langfuse_callback_handler = CallbackHandler()
    except Exception as exc:
        logger.warning("Langfuse callback handler could not be initialized: %s", exc)
        return []
    return [_langfuse_callback_handler]


def _to_langchain_messages(
    system_prompt: str,
    request_messages: List[Dict[str, Any]],
) -> List[Any]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    langchain_messages: List[Any] = [SystemMessage(content=system_prompt)]
    for message in request_messages:
        role = str(message.get("role", "user")).lower()
        content = message.get("content", "")
        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        else:
            langchain_messages.append(HumanMessage(content=content))
    return langchain_messages


async def _call_agent(
    skill_name: str,
    prompt: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    include_skill: bool = True,
) -> Dict[str, Any]:
    skill = load_skill(skill_name) if include_skill else ""
    resolved_model = model or Settings.ANALYST_MODEL
    resolved_max_tokens = max_tokens or Settings.MAX_TOKENS
    request_messages = messages or [{"role": "user", "content": prompt}]
    langchain_messages = (
        _to_langchain_messages(skill, request_messages)
        if skill
        else _to_langchain_messages("Follow the user instruction exactly.", request_messages)
    )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Missing langchain-openai dependency. Install project dependencies before "
            "running agent calls."
        ) from exc

    openai_tools = _to_openai_tools(tools)

    async def invoke_once(model_name: str, api_key: str, base_url: str) -> Dict[str, Any]:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=Settings.TEMPERATURE,
            max_tokens=resolved_max_tokens,
            extra_body={
                "reasoning_effort": "none",
                "think": False,
                "thinking": False,
                "do_sample": False,
            },
        )

        if openai_tools:
            llm = llm.bind_tools(
                openai_tools,
                tool_choice=_to_openai_tool_choice(tool_choice),
            )

        callbacks = _get_langfuse_callbacks()
        config = {"callbacks": callbacks} if callbacks else None
        started_at = perf_counter()
        try:
            response = await llm.ainvoke(langchain_messages, config=config)

            if tool_choice is None:
                result = {"text": await _response_text(response)}
            else:
                result = await extract_tool_input(response, _tool_choice_name(tool_choice))

            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            logger.info(
                "model_call_completed %s",
                json.dumps(
                    {
                        "skill_name": skill_name,
                        "model": model_name,
                        "base_url": base_url,
                        "latency_ms": latency_ms,
                        "output": result,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            return result
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "model_call_failed %s",
                json.dumps(
                    {
                        "skill_name": skill_name,
                        "model": model_name,
                        "base_url": base_url,
                        "latency_ms": latency_ms,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            raise

    return await invoke_once(
        resolved_model,
        api_key or Settings.VLLM_API_KEY,
        base_url or Settings.VLLM_BASE_URL,
    )


async def _call_agent_validated(
    skill_name: str,
    prompt: str,
    validator: Any,
    messages: Optional[List[Dict[str, Any]]] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tool_name = _tool_choice_name(tool_choice)
    try:
        primary_result = await _call_agent(
            skill_name,
            prompt,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
        return validator(primary_result)
    except Exception as exc:
        last_error = exc
        for retry_index in range(_local_llm_schema_retries()):
            retry_prompt = _schema_retry_prompt(prompt, last_error, tool_name)
            try:
                logger.warning(
                    "primary_llm_schema_failed_retrying_local_model",
                    extra={
                        "skill_name": skill_name,
                        "primary_model": model or Settings.ANALYST_MODEL,
                        "retry_index": retry_index + 1,
                        "error": str(last_error),
                    },
                )
                retry_result = await _call_agent(
                    skill_name,
                    retry_prompt,
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                )
                return validator(retry_result)
            except Exception as retry_exc:
                last_error = retry_exc

        raise last_error


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _local_llm_schema_retries() -> int:
    try:
        return max(0, int(os.getenv("LOCAL_LLM_SCHEMA_RETRIES", "1")))
    except ValueError:
        return 1


def _schema_retry_prompt(prompt: str, error: Exception, tool_name: Optional[str]) -> str:
    tool_instruction = (
        f"You must call the `{tool_name}` tool exactly once. "
        if tool_name
        else "You must return only the requested structured output. "
    )
    return (
        f"{prompt}\n\n"
        "Previous model attempt failed schema validation.\n"
        f"Validation error: {error}\n\n"
        f"{tool_instruction}"
        "Do not answer in prose. Do not include markdown. Do not include copied "
        "email metadata unless that exact field is part of the tool schema. "
        "Use only the allowed fields."
    )


def _strip_reasoning_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"^\s*(summary|final summary)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _clean_summary_placeholders(text: str) -> str:
    cleaned = str(text or "").strip()
    placeholder_sections = [
        r"Previous messages:\s*(?:[-*]\s*)?None\.?",
        r"User action:\s*(?:[-*]\s*)?No clear user action requested(?:\s*\([^)]*\))?\.?",
        r"Notes:\s*(?:[-*]\s*)?No major caveats\.?",
    ]
    for pattern in placeholder_sections:
        cleaned = re.sub(
            rf"(?:^|\n\n){pattern}(?=\n\n|$)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


async def _call_plain_agent(
    skill_name: str,
    prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    result = await _call_agent(
        skill_name,
        prompt,
        model=model,
        max_tokens=max_tokens,
        tools=None,
        tool_choice=None,
        include_skill=True,
    )
    text = result.get("text") or result.get("summary") or result.get("suggested_reply")
    if text is None and isinstance(result.get("messages"), list):
        text = json.dumps({"messages": result["messages"]}, ensure_ascii=False)
    return _strip_reasoning_text(str(text or ""))


def _ollama_native_chat_url(base_url: str) -> Optional[str]:
    clean_base = str(base_url or "").strip().rstrip("/")
    if not clean_base:
        return None
    if clean_base.endswith("/v1"):
        clean_base = clean_base[:-3]
    if "localhost:11434" not in clean_base and "127.0.0.1:11434" not in clean_base:
        return None
    return f"{clean_base}/api/chat"


def _post_ollama_native_chat(
    url: str,
    payload: Dict[str, Any],
    timeout: float = 120,
) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama native chat request failed: {exc}") from exc
    return json.loads(body)


async def _call_writer_plain_agent(
    prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    resolved_model = model or Settings.OLLAMA_MODEL
    resolved_max_tokens = max_tokens or Settings.WRITER_MAX_TOKENS
    native_url = _ollama_native_chat_url(Settings.VLLM_BASE_URL)
    if not native_url:
        return await _call_plain_agent(
            WRITER_SKILL_NAME,
            prompt,
            model=resolved_model,
            max_tokens=resolved_max_tokens,
        )

    skill = load_skill(WRITER_SKILL_NAME)
    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": skill or "Follow the user instruction exactly."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "num_predict": resolved_max_tokens,
            "temperature": Settings.TEMPERATURE,
        },
    }
    started_at = perf_counter()
    response = await asyncio.to_thread(_post_ollama_native_chat, native_url, payload)
    text = str((response.get("message") or {}).get("content") or "")
    latency_ms = round((perf_counter() - started_at) * 1000, 2)
    logger.info(
        "writer_native_ollama_call_completed %s",
        json.dumps(
            {
                "skill_name": WRITER_SKILL_NAME,
                "model": resolved_model,
                "url": native_url,
                "latency_ms": latency_ms,
                "done_reason": response.get("done_reason"),
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    return _strip_reasoning_text(text)


async def _call_summary_text(prompt: str) -> Dict[str, Any]:
    summary = _clean_summary_placeholders(
        await _call_plain_agent(
            SUMMARIZER_SKILL_NAME,
            prompt,
            model=Settings.SUMMARY_MODEL,
            max_tokens=Settings.SUMMARY_MAX_TOKENS,
        )
    )
    if not summary:
        raise ValueError("Summary agent returned an empty summary.")
    return {"summary": summary}


def _token_budget_instruction(max_tokens: int) -> str:
    return (
        f"Keep the final answer within {max_tokens} tokens. "
        "Prefer concise wording over extra detail when space is tight."
    )


def _safe_log_id(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "unknown")).strip("-")
    return text[:80] or "unknown"


def _write_agent_io_log(
    agent_name: str,
    message_id: Any,
    payload: Dict[str, Any],
) -> None:
    if os.getenv("ENABLE_AGENT_IO_LOGS", "true").strip().lower() in {"0", "false", "no", "off"}:
        return

    try:
        AGENT_IO_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        path = AGENT_IO_LOG_DIR / f"{timestamp}-{_safe_log_id(agent_name)}-{_safe_log_id(message_id)}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("agent_io_log_write_failed: %s", exc)


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = _strip_reasoning_text(text)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Analyzer returned no JSON object.")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Analyzer JSON must be an object.")
    return parsed


def _parse_analyzer_json(text: str, expected_count: int) -> Dict[str, Any]:
    parsed = _extract_json_object(text)
    if isinstance(parsed.get("messages"), list):
        return parsed
    if expected_count == 1:
        return {"messages": [parsed]}
    raise ValueError("Analyzer JSON must include a messages list for multiple inputs.")


def _line_field(line: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}\s*=\s*([^;|]+)"
    match = re.search(pattern, line, flags=re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).strip()
    return "" if value.lower() in {"none", "null", "n/a", "na", "-"} else value


def _parse_event_datetime(value: str) -> Optional[datetime]:
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


def _combine_analyzer_date_time(date_value: Any, time_value: Any = None) -> Optional[datetime]:
    date_text = str(date_value or "").strip()
    if not date_text:
        return None
    time_text = str(time_value or "").strip()
    if not time_text or time_text.lower() in {"none", "null"}:
        time_text = "00:00:00"
    elif re.fullmatch(r"\d{1,2}:\d{2}", time_text):
        time_text = f"{time_text}:00"
    return _parse_event_datetime(f"{date_text}T{time_text}")


def _parse_calendar_event_from_line(line: str) -> Optional[Dict[str, Any]]:
    title = _line_field(line, "event_title")
    start_text = _line_field(line, "event_start")
    if not title or not start_text:
        return None

    start_at = _parse_event_datetime(start_text)
    if not start_at or start_at < datetime.utcnow():
        return None

    end_text = _line_field(line, "event_end")
    end_at = _parse_event_datetime(end_text)
    location = _line_field(line, "event_location")
    return {
        "detected": True,
        "title": title,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat() if end_at and end_at >= start_at else None,
        "location": location,
        "notification_minutes_before": 15,
    }


def _message_body(email: Dict[str, Any]) -> str:
    return str(
        email.get("Message_body")
        or email.get("body")
        or email.get("snippet")
        or ""
    )


def _message_body_for_word_count(email: Dict[str, Any]) -> str:
    return str(email.get("Message_body") or email.get("body") or "")


def count_body_words(email: Dict[str, Any]) -> int:
    body_parts = [_message_body_for_word_count(email)]
    thread_messages = email.get("thread_messages") or email.get("thread_history") or []
    if isinstance(thread_messages, list):
        body_parts.extend(
            _message_body_for_word_count(message)
            for message in thread_messages
            if isinstance(message, dict)
        )
    elif thread_messages:
        body_parts.append(str(thread_messages))

    return len(re.findall(r"\b[\w'-]+\b", "\n".join(body_parts)))


DATE_TIME_EXPRESSION_PATTERN = re.compile(
    r"""
    \b\d{4}-\d{1,2}-\d{1,2}\b
    |\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b
    |\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{2,4})?\b
    |\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?(?:\s+\d{2,4})?\b
    |\b(?:today|tomorrow|tonight|yesterday|day\s+after\s+tomorrow)\b
    |\b(?:next|this|coming)\s+(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?|week|month|year|quarter)\b
    |\b(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b
    |\b\d{1,2}:\d{2}\s*(?:am|pm)?\b
    |\b\d{1,2}\s*(?:am|pm)\b
    |\b(?:in|within)\s+\d+\s+(?:minutes?|hours?|days?|weeks?|months?)\b
    |\b\d+\s+(?:minutes?|hours?|days?|weeks?|months?)\s+(?:left|remaining|from\s+now)\b
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def _date_expression_text_parts(message: Dict[str, Any]) -> List[str]:
    parts = [
        str(message.get("subject") or ""),
        _message_body(message),
        str(message.get("snippet") or ""),
    ]
    thread_messages = message.get("thread_messages") or message.get("thread_history") or []
    if isinstance(thread_messages, list):
        for thread_message in thread_messages:
            if isinstance(thread_message, dict):
                parts.extend(
                    [
                        str(thread_message.get("subject") or ""),
                        _message_body(thread_message),
                        str(thread_message.get("snippet") or ""),
                    ]
                )
    elif thread_messages:
        parts.append(str(thread_messages))
    return parts


def extract_date_time_expressions(message: Dict[str, Any]) -> List[str]:
    """Detect message-content date/time expressions before spending analyzer tokens."""
    seen = set()
    expressions = []
    for part in _date_expression_text_parts(message):
        for match in DATE_TIME_EXPRESSION_PATTERN.finditer(part):
            expression = " ".join(match.group(0).split())
            key = expression.lower()
            if key not in seen:
                seen.add(key)
                expressions.append(expression)
    return expressions


def message_has_date_time_expression(message: Dict[str, Any]) -> bool:
    return bool(extract_date_time_expressions(message))


def has_thread_context(email: Dict[str, Any]) -> bool:
    if email.get("thread_messages") or email.get("thread_history"):
        return True
    thread_count = email.get("thread_message_count")
    if isinstance(thread_count, int) and thread_count > 1:
        return True

    message_id = str(email.get("id") or "")
    thread_id = str(email.get("thread_id") or email.get("threadId") or "")
    if message_id and thread_id and message_id != thread_id:
        return True

    references = str(email.get("references") or email.get("in_reply_to") or "")
    return bool(references.strip())


def promotional_basic_skip_reason(message: Dict[str, Any]) -> Optional[str]:
    promotional_check = message.get("promotional_check")
    if not isinstance(promotional_check, dict) or not promotional_check.get("skip_llm"):
        return None

    if promotional_check.get("has_list_unsubscribe_header"):
        return "present_message_has_list_unsubscribe_header"
    if promotional_check.get("has_html_code"):
        return "present_message_has_html_code"
    if promotional_check.get("plain_text_word_count", 0) < 5:
        return "present_message_plain_text_under_5_words"
    return "present_message_promotional_basic_check"


def _thread_context(message: Dict[str, Any]) -> str:
    thread = message.get("thread_messages") or message.get("thread_history") or ""
    if isinstance(thread, list):
        return "\n\n".join(str(item) for item in thread)
    return str(thread)


def _display_sender(value: Any) -> str:
    name, address = parseaddr(str(value or ""))
    return name or address or str(value or "").strip() or "Unknown sender"


def _parsed_message_datetime(value: Any) -> Optional[Any]:
    try:
        return parsedate_to_datetime(str(value or ""))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _format_thread_date(value: Any) -> str:
    parsed = _parsed_message_datetime(value)
    if parsed:
        return parsed.strftime("%d %b %Y %I:%M %p").lstrip("0")
    return str(value or "unknown date").strip() or "unknown date"


def _thread_content(value: Any) -> str:
    """Use hook-sanitized content as-is; do not do prompt-side cleanup."""
    return str(value or "").strip()


def structured_thread_messages(current_message: Dict[str, Any]) -> List[Dict[str, Any]]:
    thread = current_message.get("thread_messages") or current_message.get("thread_history") or []
    messages: List[Dict[str, Any]] = []
    if isinstance(thread, list):
        messages.extend(message for message in thread if isinstance(message, dict))
    elif thread:
        messages.append({"body": str(thread)})

    messages.append(current_message)

    indexed_messages = list(enumerate(messages))
    indexed_messages.sort(
        key=lambda item: (
            _parsed_message_datetime(item[1].get("date")) is None,
            _parsed_message_datetime(item[1].get("date")) or item[0],
            item[0],
        )
    )
    return [message for _, message in indexed_messages]


def structured_thread_context(current_message: Dict[str, Any]) -> str:
    messages = structured_thread_messages(current_message)
    current = messages[-1] if messages else current_message
    previous = list(reversed(messages[:-1]))
    blocks = [
        "\n".join(
            [
                "Current message:",
                f"datetime: {_format_thread_date(current.get('date'))}",
                f"sender: {_display_sender(current.get('from'))}",
                f"content: {_thread_content(_message_body(current))}",
            ]
        )
    ]
    blocks.extend(
        "\n".join(
            [
                f"Previous message {index}:",
                f"datetime: {_format_thread_date(message.get('date'))}",
                f"sender: {_display_sender(message.get('from'))}",
                f"content: {_thread_content(_message_body(message))}",
            ]
        )
        for index, message in enumerate(previous, start=1)
    )
    return "\n\n".join(
        blocks
    )


def raw_thread_debug_context(current_message: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "datetime": message.get("date", ""),
            "sender": message.get("from", ""),
            "body": _message_body(message),
        }
        for message in structured_thread_messages(current_message)
    ]


def _format_message_for_context_analysis(message: Dict[str, Any], index: int) -> str:
    extracted_expressions = message.get("extracted_date_time_expressions")
    if not isinstance(extracted_expressions, list):
        extracted_expressions = extract_date_time_expressions(message)
    return (
        f"Message {index}\n"
        f"Date: {message.get('date', '')}\n"
        f"To: {message.get('to', '')}\n"
        f"From: {message.get('from', '')}\n"
        f"Subject: {message.get('subject', '')}\n"
        f"Extracted_date_time_expressions: {json.dumps(extracted_expressions, ensure_ascii=False)}\n"
        f"Message_body: {_message_body(message)}\n"
        f"Structured_thread: {structured_thread_context(message)}"
    )


def validate_analyzer_result(result: Dict[str, Any], expected_count: int) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("Analyzer result must be an object.")

    messages = result.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Analyzer result must include a messages list.")
    if len(messages) < expected_count:
        raise ValueError(f"Analyzer returned {len(messages)} messages, expected {expected_count}.")
    if len(messages) > expected_count:
        logger.warning(
            "analyzer_returned_extra_items_trimming",
            extra={"returned_count": len(messages), "expected_count": expected_count},
        )
        messages = messages[:expected_count]

    normalized_messages = []
    for index, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            raise ValueError(f"Analyzer item {index} must be an object.")
        missing = ANALYZER_REQUIRED_FIELDS - set(message)
        extra = set(message) - ANALYZER_REQUIRED_FIELDS - ANALYZER_OPTIONAL_FIELDS
        if missing:
            raise ValueError(f"Analyzer item {index} is missing keys: {sorted(missing)}")
        if extra:
            logger.warning(
                "analyzer_returned_extra_keys_stripping",
                extra={"item_index": index, "extra_keys": sorted(extra)},
            )
        category = str(message["category"] or "").strip().lower()
        if category not in ANALYZER_CATEGORIES:
            raise ValueError(f"Analyzer item {index}.category is invalid.")
        event_type = str(message["event_type"] or "").strip().lower()
        if event_type not in ANALYZER_EVENT_TYPES:
            raise ValueError(f"Analyzer item {index}.event_type is invalid.")
        if category == "none":
            event_type = "none"
        elif event_type == "none":
            event_type = "task_reminder" if category == "reminder" else "other"
        confidence = message["confidence"]
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError(f"Analyzer item {index}.confidence must be between 0 and 1.")
        participants = message["participants"]
        if not isinstance(participants, list):
            raise ValueError(f"Analyzer item {index}.participants must be a list.")
        normalized_message: Dict[str, Any] = {
            "category": category,
            "event_type": event_type,
            "title": str(message["title"] or ""),
            "description": str(message["description"] or ""),
            "start_date": str(message["start_date"] or ""),
            "start_time": str(message["start_time"]) if message["start_time"] is not None else None,
            "end_date": str(message["end_date"]) if message["end_date"] is not None else None,
            "end_time": str(message["end_time"]) if message["end_time"] is not None else None,
            "location": str(message["location"]) if message["location"] is not None else None,
            "participants": [str(participant) for participant in participants],
            "meeting_platform": (
                str(message["meeting_platform"]) if message["meeting_platform"] is not None else None
            ),
            "requires_confirmation": bool(message["requires_confirmation"]),
            "confidence": float(confidence),
            "reason": str(message["reason"] or ""),
        }
        if category in {"calendar_event", "reminder"}:
            has_start_time = bool(
                normalized_message["start_time"]
                and str(normalized_message["start_time"]).strip().lower()
                not in {"none", "null"}
            )
            start_at = _combine_analyzer_date_time(
                normalized_message["start_date"],
                normalized_message["start_time"],
            )
            is_visible_event = bool(
                start_at
                and (
                    not has_start_time
                    or start_at >= datetime.utcnow()
                )
            )
            if is_visible_event:
                end_date = normalized_message["end_date"] or normalized_message["start_date"]
                end_at = _combine_analyzer_date_time(end_date, normalized_message["end_time"])
                normalized_message["calendar_event"] = {
                    "detected": True,
                    "title": (normalized_message["title"] or "Email event")[:500],
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat() if end_at and end_at >= start_at else None,
                    "location": str(normalized_message["location"] or "").strip(),
                    "notification_minutes_before": 15,
                    "event_kind": normalized_message["event_type"],
                }
        normalized_messages.append(normalized_message)
    return {"messages": normalized_messages}


def tag_message_metadata(
    message: Dict[str, Any],
    analyzer_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach code-owned Gmail metadata to an analyzer decision."""
    return {
        "date": str(message.get("date", "")),
        "to": str(message.get("to", "")),
        "from": str(message.get("from", "")),
        "subject": str(message.get("subject", "")),
        "Message_body": _message_body(message),
        **analyzer_result,
    }


def validate_summary_result(result: Dict[str, Any]) -> Dict[str, Any]:
    missing = SUMMARY_REQUIRED_FIELDS - set(result)
    if missing:
        raise ValueError(f"Summary result is missing keys: {sorted(missing)}")
    extra = set(result) - SUMMARY_REQUIRED_FIELDS
    if extra:
        raise ValueError(f"Summary result has unexpected keys: {sorted(extra)}")
    if not isinstance(result["summary"], str):
        raise ValueError("Summary result summary must be a string.")
    return result


def validate_reply_result(result: Dict[str, Any]) -> Dict[str, Any]:
    missing = REPLY_REQUIRED_FIELDS - set(result)
    if missing:
        raise ValueError(f"Reply result is missing keys: {sorted(missing)}")
    if result["tone"] not in {"professional", "friendly", "short", "formal"}:
        raise ValueError("Reply tone is invalid.")
    confidence = result["confidence"]
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("Reply confidence must be between 0 and 1.")
    return result


async def analyze_message_context(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not messages:
        raise ValueError("No messages provided for context analysis.")

    now_text = datetime.utcnow().replace(microsecond=0).isoformat()
    prompt = f"Analyze the following Gmail message context. Current datetime: {now_text}\n\n"
    prompt += "\n\n".join(
        _format_message_for_context_analysis(message, index)
        for index, message in enumerate(messages, start=1)
    )
    prompt += (
        "\n\nOutput instructions:\n"
        "Return JSON only. Do not include markdown, reasoning, labels, or tool calls.\n"
        "Return one object with a messages array, in the same order as the input messages.\n"
        "Each item in messages must follow this schema exactly:\n"
        "{\n"
        '  "category": "calendar_event | reminder | none",\n'
        '  "event_type": "meeting | appointment | interview | travel | reservation | webinar | deadline | task_reminder | follow_up | payment | renewal | other | none",\n'
        '  "title": "",\n'
        '  "description": "",\n'
        '  "start_date": "",\n'
        '  "start_time": null,\n'
        '  "end_date": null,\n'
        '  "end_time": null,\n'
        '  "location": null,\n'
        '  "participants": [],\n'
        '  "meeting_platform": null,\n'
        '  "requires_confirmation": false,\n'
        '  "confidence": 0.0,\n'
        '  "reason": ""\n'
        "}\n\n"
        "You are an Event and Reminder Analyzer.\n\n"
        "Your job is to determine whether an email contains an actionable item for the email recipient.\n\n"
        "The input email has already passed a rule-based filter and contains one or more detected date/time expressions.\n\n"
        "The detected expressions are provided in Extracted_date_time_expressions for each message.\n\n"
        "Your responsibilities are:\n\n"
        "1. Identify which extracted date(s) and time(s) actually belong to an actionable item.\n\n"
        "Ignore dates that refer to:\n"
        "- historical events\n"
        "- payment history\n"
        "- publication dates\n"
        "- previous meetings\n"
        "- examples\n"
        "- unrelated future dates\n"
        "- expiry dates unless they require user action\n\n"
        "2. Classify the actionable item.\n\n"
        "Choose exactly one category.\n\n"
        "Also choose exactly one event_type from: meeting, appointment, interview, travel, "
        "reservation, webinar, deadline, task_reminder, follow_up, payment, renewal, other, none.\n\n"
        "Use event_type none only when category is none. For reminders, use the most specific "
        "reminder type, such as deadline, payment, renewal, follow_up, or task_reminder. "
        "For calendar events, use the most specific attendance type, such as meeting, interview, "
        "appointment, travel, reservation, or webinar.\n\n"
        "A. CALENDAR_EVENT\n\n"
        "Choose this if the user is expected to attend something at a specific date/time.\n\n"
        "If the email asks to plan, schedule, attend, join, or arrange a meeting/event on a date "
        "but the time is missing, still choose calendar_event and set requires_confirmation to true.\n\n"
        "Use date-only meeting or planning asks as planned event reminders. They should appear on "
        "the calendar date but must not be treated as confirmed timed calendar blocks.\n\n"
        "Only messages with a concrete invite, .ics/calendar details, or explicit date and time "
        "should become confirmed timed calendar events.\n\n"
        "Examples:\n"
        "- Meeting\n"
        "- Interview\n"
        "- Doctor appointment\n"
        "- Conference\n"
        "- Webinar\n"
        "- Flight\n"
        "- Hotel check-in\n"
        "- Restaurant reservation\n"
        "- Official calendar invitation\n"
        "- Zoom/Google Meet/Teams meeting\n"
        "- Physical meeting\n\n"
        "B. REMINDER\n\n"
        "Choose this if the user must remember to perform an action but there is no scheduled event requiring attendance.\n\n"
        "Because the message already contains a detected date/time expression, choose reminder for "
        "date/time-related items that may require user attention and are not calendar events.\n\n"
        "Examples:\n"
        "- Pay invoice\n"
        "- Submit report\n"
        "- Renew insurance\n"
        "- Complete assignment\n"
        "- Send documents\n"
        "- Follow up\n"
        "- Call customer\n"
        "- Buy groceries\n\n"
        "C. NONE\n\n"
        "Choose NONE if no actionable reminder or event exists.\n\n"
        "Keep NONE for historical dates, payment history, FYI/news/general announcements, and dates "
        "that do not require future user attention.\n\n"
        "Examples:\n"
        "- News\n"
        "- Advertisements\n"
        "- FYI emails\n"
        "- Historical references\n"
        "- General announcements\n\n"
        "3. If multiple dates exist:\n\n"
        "Determine which date belongs to the actionable item.\n\n"
        "Ignore dates that merely describe:\n"
        "- unavailable dates\n"
        "- previous events\n"
        "- alternative examples\n"
        "- historical references\n\n"
        "4. Determine whether user confirmation is required.\n\n"
        "Confirmation should be true when:\n"
        "- date missing\n"
        "- time missing\n"
        "- multiple possible dates\n"
        "- ambiguous wording\n"
        "- confidence is low\n\n"
        "5. Never invent missing information.\n\n"
        "If time is missing, set start_time to null.\n"
        "If end time is unknown, set end_time to null.\n"
        "If location is unknown, set location to null.\n"
        "Use lowercase category values only: calendar_event, reminder, none.\n"
        "Use ISO date format YYYY-MM-DD and 24-hour time format HH:MM:SS when known.\n"
        "For reminders, extract the exact due date and due time when present so code can "
        "create a reminder event on the calendar; if only a date is present, set start_time to null.\n"
        "Use the email received Date only to resolve relative phrases in the content, "
        "such as today, tomorrow, or 3 hours left.\n"
        "Do not draft a reply."
    )
    text = await _call_plain_agent(ANALYZER_SKILL_NAME, prompt, model=Settings.ANALYZER_MODEL)
    parsed_result = _parse_analyzer_json(text, expected_count=len(messages))
    validated_result = validate_analyzer_result(parsed_result, expected_count=len(messages))
    _write_agent_io_log(
        "analyzer",
        ",".join(
            _safe_log_id(message.get("id") or message.get("message_id") or index)
            for index, message in enumerate(messages, start=1)
        ),
        {
            "agent": "analyzer",
            "message_ids": [
                message.get("id") or message.get("message_id")
                for message in messages
            ],
            "model": Settings.ANALYZER_MODEL,
            "input": {
                "prompt": prompt,
                "messages": messages,
            },
            "output": {
                "raw_text": text,
                "parsed": parsed_result,
                "validated": validated_result,
            },
        },
    )
    return validated_result


async def summarize_message(
    email: Dict[str, Any],
    analyzer_result: Dict[str, Any],
) -> Dict[str, Any]:
    clean_thread = structured_thread_context(email)
    prompt = (
        f"{_token_budget_instruction(Settings.SUMMARY_MAX_TOKENS)}\n"
        f"From: {email.get('from', '')}\n"
        f"To: {email.get('to', '')}\n"
        f"Date: {email.get('date', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        "EMAIL_THREAD_START\n"
        f"{clean_thread}\n"
        "EMAIL_THREAD_END"
    )
    result = await _call_summary_text(prompt)
    _write_agent_io_log(
        "summary",
        email.get("id") or email.get("message_id"),
        {
            "agent": "summary",
            "message_id": email.get("id") or email.get("message_id"),
            "model": Settings.SUMMARY_MODEL,
            "input": {
                "prompt": prompt,
                "thread_messages": clean_thread,
                "raw_thread_messages": raw_thread_debug_context(email),
            },
            "output": result,
        },
    )
    return result


async def draft_reply_message(
    email: Dict[str, Any],
    analyzer_result: Dict[str, Any],
    summary_result: Optional[Dict[str, Any]] = None,
    user_intent: str = "",
    user_email: str = "",
) -> Dict[str, Any]:
    intent_text = user_intent.strip()
    mailbox_email = str(user_email or email.get("to") or "").strip()
    sender_email = str(email.get("from") or "").strip()
    clean_thread = structured_thread_context(email)
    prompt = (
        "Draft a complete reply for the following Gmail conversation in plain text only. "
        f"User mailbox: {mailbox_email}\n"
        f"The sender: {sender_email}\n"
        "The sender sent the following email/thread to the user mailbox. "
        "Draft a reply FROM the user mailbox TO the sender. "
        "Do not adopt the sender's role, organization, duties, apologies, or responsibilities. "
        "Use User_reply_intent to express the mailbox owner's position, complaint, preference, question, or response. "
        "If User_reply_intent criticizes the sender's service, write the reply as criticism from the user to the sender, "
        "not as an apology from the sender/provider side. "
        "Use only the thread messages below to understand the conversation history. "
        "The thread messages are chronological; the newest thread message is the current/latest email. "
        "Mentally convert them into: Current message with sender/content, then Previous messages "
        "as numbered datetime | sender | action lines. "
        "Greet first if appropriate with hi/hello/dear, then respond to the latest message. "
        "Close naturally with regards, best wishes, or another suitable closing when appropriate. "
        "Do not add facts that are not present in the message, thread, summary, or user intent. "
        "Use Summary_JSON as helpful context only, but prefer the actual message/thread if they differ. "
        "Write a useful reply body, but keep it bounded by the user's intent and known facts. "
        "Acknowledge every question, request, date, requirement, constraint, or next step that needs a response, "
        "but do not answer unavailable details or create a solution that the user did not authorize. "
        "Follow User_reply_intent closely; if the intent is empty, draft a neutral helpful reply "
        "that fits the latest/current message and covers the relevant details. "
        "Treat User_reply_intent as the strongest signal for what the user is willing to say. "
        "Do not introduce new assurances that are not explicitly present in User_reply_intent or the thread, "
        "including promises of action, compensation, timelines, confirmations, communication channels, "
        "responsibility or blame, and conditional outcomes. "
        "If User_reply_intent is brief, keep the reply brief and only express the stated intent. "
        "When the sender asks for a result that the user has not authorized, acknowledge the request "
        "but do not grant, deny, schedule, promise, or conditionally commit to that result. "
        "If User_reply_intent says the user is checking, reviewing, investigating, confirming, "
        "or looking into something, only say that the matter is being checked/reviewed/investigated/confirmed "
        "and that the sender will be updated when confirmed information is available. "
        "Do not add speculative causes, internal records, team actions, policy conditions, dates, "
        "follow-up windows, refund conditions, delivery estimates, or outcomes. "
        "Respond to the latest sender and latest ask, while respecting dates, cancellations, "
        "scheduling context, and earlier thread details. "
        "Do not invent availability, promises, attachments, payments, project details, logistics explanations, "
        "investigation findings, operational outcomes, or facts. "
        "If information is missing, ask a clear clarification instead of making it up. "
        f"{_token_budget_instruction(Settings.REPLY_MAX_TOKENS)} "
        "Return only the reply body. Do not return JSON, labels, reasoning, markdown, or tool calls.\n\n"
        f"From: {email.get('from', '')}\n"
        f"To: {email.get('to', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        "EMAIL_THREAD_START\n"
        f"{clean_thread}\n"
        "EMAIL_THREAD_END\n"
        "USER_REPLY_INTENT_START\n"
        f"{intent_text}\n"
        "USER_REPLY_INTENT_END"
    )
    suggested_reply = await _call_plain_agent(
        REPLY_SKILL_NAME,
        prompt,
        model=Settings.REPLY_MODEL,
        max_tokens=Settings.REPLY_MAX_TOKENS,
    )
    if not suggested_reply:
        raise ValueError("Reply agent returned an empty draft.")
    result = {
        "suggested_reply": suggested_reply,
        "tone": "professional",
        "confidence": 0.7,
    }
    _write_agent_io_log(
        "reply",
        email.get("id") or email.get("message_id"),
        {
            "agent": "reply",
            "message_id": email.get("id") or email.get("message_id"),
            "model": Settings.REPLY_MODEL,
            "input": {
                "prompt": prompt,
                "thread_messages": clean_thread,
                "raw_thread_messages": raw_thread_debug_context(email),
                "user_reply_intent": intent_text,
            },
            "output": result,
        },
    )
    return result


def _normalize_writer_format(format_name: str) -> str:
    normalized = str(format_name or "").strip().lower()
    if normalized not in {"formal", "informal"}:
        raise ValueError("Writer format must be either 'formal' or 'informal'.")
    return normalized


async def write_message_draft(
    email: Dict[str, Any],
    analyzer_result: Dict[str, Any],
    summary_result: Optional[Dict[str, Any]] = None,
    user_instruction: str = "",
    writing_format: str = "formal",
) -> Dict[str, Any]:
    format_name = _normalize_writer_format(writing_format)
    instruction_text = user_instruction.strip()
    clean_thread = structured_thread_context(email)
    prompt = (
        "Write a Gmail message draft in plain text only. "
        "First understand the selected email and thread context, then write the draft "
        f"in a {format_name} format. "
        "Use the thread messages below as the source of truth. "
        "Use Summary_JSON as helpful context only, but prefer the actual message/thread if they differ. "
        "Follow User_writing_instruction closely. If the instruction is empty, write a useful draft "
        "that responds to the latest/current message. "
        "Do not invent availability, promises, attachments, payments, project details, or facts. "
        "If information is missing, ask a concise clarification instead of making it up. "
        "Return only the draft body. Do not return JSON, labels, reasoning, markdown, or tool calls.\n\n"
        f"Writing_format: {format_name}\n"
        f"From: {email.get('from', '')}\n"
        f"To: {email.get('to', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Analyzer_JSON: {json.dumps(analyzer_result or {}, ensure_ascii=False)}\n"
        f"Summary_JSON: {json.dumps(summary_result or {}, ensure_ascii=False)}\n"
        "EMAIL_THREAD_START\n"
        f"{clean_thread}\n"
        "EMAIL_THREAD_END\n"
        f"User_writing_instruction: {instruction_text}"
    )
    draft = await _call_writer_plain_agent(
        prompt,
        model=Settings.OLLAMA_MODEL,
        max_tokens=Settings.WRITER_MAX_TOKENS,
    )
    if not draft:
        raise ValueError("Writer agent returned an empty draft.")
    result = {
        "draft": draft,
        "format": format_name,
    }
    _write_agent_io_log(
        "writer",
        email.get("id") or email.get("message_id"),
        {
            "agent": "writer",
            "message_id": email.get("id") or email.get("message_id"),
            "model": Settings.OLLAMA_MODEL,
            "input": {
                "prompt": prompt,
                "thread_messages": clean_thread,
                "raw_thread_messages": raw_thread_debug_context(email),
                "user_writing_instruction": instruction_text,
                "writing_format": format_name,
            },
            "output": result,
        },
    )
    return result


async def write_compose_draft(
    to_address: str = "",
    subject: str = "",
    user_instruction: str = "",
    writing_format: str = "formal",
) -> Dict[str, Any]:
    format_name = _normalize_writer_format(writing_format)
    instruction_text = user_instruction.strip()
    prompt = (
        "Write or revise a Gmail compose draft in plain text only. "
        f"Use a {format_name} format. "
        "Follow User_writing_input closely. Use To and Subject only as context. "
        "First classify User_writing_input silently: "
        "if it is an existing email body, draft text, or a request to correct, rephrase, polish, improve, "
        "rewrite, make formal, make informal, shorten, or expand provided text, revise that provided text "
        "while preserving its meaning, facts, recipients, and intent. "
        "If User_writing_input is an instruction to write a message, generate the requested email body. "
        "If User_writing_input contains both an instruction and draft text, apply the instruction to the draft text. "
        "Do not invent facts, attachments, payments, project details, calendar availability, "
        "or commitments that are not provided by the user. "
        "If the input is too vague to safely write a complete message, write a concise "
        "draft that asks for the missing details. "
        "Return only the email body. Do not return JSON, labels, subject, reasoning, markdown, or tool calls.\n\n"
        f"Writing_format: {format_name}\n"
        f"To: {to_address}\n"
        f"Subject: {subject}\n"
        f"User_writing_input: {instruction_text}"
    )
    draft = await _call_writer_plain_agent(
        prompt,
        model=Settings.OLLAMA_MODEL,
        max_tokens=Settings.WRITER_MAX_TOKENS,
    )
    if not draft:
        raise ValueError("Writer agent returned an empty draft.")
    result = {
        "draft": draft,
        "format": format_name,
    }
    _write_agent_io_log(
        "writer-compose",
        subject or to_address or "compose",
        {
            "agent": "writer",
            "model": Settings.OLLAMA_MODEL,
            "input": {
                "prompt": prompt,
                "to": to_address,
                "subject": subject,
                "user_writing_instruction": instruction_text,
                "writing_format": format_name,
            },
            "output": result,
        },
    )
    return result


async def process_analyzed_message(
    user_email: str,
    message: Dict[str, Any],
    analyzer_result: Dict[str, Any],
) -> Dict[str, Any]:
    email_id = str(message.get("id") or "")
    base_log = {
        "email_id": email_id,
        "user_id": user_email,
        "word_count": count_body_words(message),
        "has_thread_context": has_thread_context(message),
    }

    reply_called = False
    reply_result = None
    processing_status = "analyzed"
    reply_status = "not_required"

    logger.info(
        "email_processing_decision",
        extra={
            **base_log,
            "analyzer_agent_called": True,
            "summary_agent_called": False,
            "reply_agent_called": reply_called,
            "processing_status": processing_status,
        },
    )
    return {
        "message": message,
        "analysis": analyzer_result,
        "summary": None,
        "reply": reply_result,
        "processing_status": processing_status,
        "reply_status": reply_status,
    }


async def _analyze_messages_node(state: EmailAnalysisState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    date_expression_by_index = {
        index: extract_date_time_expressions(message)
        for index, message in enumerate(messages)
    }
    analysis_message_indexes = [
        index
        for index, message in enumerate(messages)
        if promotional_basic_skip_reason(message) is None
        and date_expression_by_index.get(index)
    ]
    messages_to_analyze = [
        {
            **messages[index],
            "extracted_date_time_expressions": date_expression_by_index[index],
        }
        for index in analysis_message_indexes
    ]

    if not messages_to_analyze:
        return {"analysis": {"messages": []}, "analysis_message_indexes": []}

    return {
        "analysis": await email_analysis_call(messages_to_analyze),
        "analysis_message_indexes": analysis_message_indexes,
    }


async def _process_analyzed_messages_node(state: EmailAnalysisState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    analyzed_messages = state.get("analysis", {}).get("messages", [])
    analysis_message_indexes = state.get("analysis_message_indexes", [])
    analyzed_by_index = {
        message_index: analyzed_messages[analysis_index]
        for analysis_index, message_index in enumerate(analysis_message_indexes)
        if analysis_index < len(analyzed_messages)
    }
    results = []
    for index, message in enumerate(messages):
        if isinstance(message.get("calendar_event"), dict) and message["calendar_event"].get("detected"):
            event = message["calendar_event"]
            ics_analysis = {
                "category": "calendar_event",
                "event_type": str(event.get("event_kind") or "ics_invite"),
                "title": str(event.get("title") or message.get("subject") or "Email event"),
                "description": str(message.get("snippet") or ""),
                "start_date": str(event.get("start_at") or "")[:10] or None,
                "start_time": str(event.get("start_at") or "")[11:16] or None,
                "end_date": str(event.get("end_at") or "")[:10] or None,
                "end_time": str(event.get("end_at") or "")[11:16] or None,
                "location": event.get("location"),
                "participants": [],
                "meeting_platform": None,
                "requires_confirmation": False,
                "confidence": 1.0,
                "reason": "Parsed from .ics calendar invite.",
                "calendar_event": event,
            }
            results.append(
                await process_analyzed_message(
                    state["email"],
                    {**message, **ics_analysis},
                    ics_analysis,
                )
            )
            continue

        skip_reason = promotional_basic_skip_reason(message)
        if skip_reason:
            results.append(
                {
                    "message": message,
                    "processing_status": "skipped",
                    "reply_status": "not_required",
                    "skip_reason": skip_reason,
                }
            )
            continue
        extracted_expressions = extract_date_time_expressions(message)
        if not extracted_expressions:
            results.append(
                {
                    "message": message,
                    "processing_status": "not_analyzed",
                    "reply_status": "pending",
                    "skip_reason": "no_date_time_expression_detected",
                }
            )
            continue

        analyzed = analyzed_by_index.get(index)
        if not analyzed:
            results.append(
                {
                    "message": message,
                    "processing_status": "not_analyzed",
                    "reply_status": "pending",
                    "skip_reason": "analysis_failed",
                }
            )
            continue
        enriched_analysis = tag_message_metadata(message, analyzed)
        enriched_message = {**message, **enriched_analysis}
        results.append(
            await process_analyzed_message(
                state["email"],
                enriched_message,
                enriched_analysis,
            )
        )
    return {"results": results, "processed_message_count": len(results)}


@lru_cache(maxsize=1)
def build_email_analysis_graph() -> Any:
    return _compile_email_analysis_graph()


def _compile_email_analysis_graph(checkpointer: Any = None) -> Any:
    from langgraph.graph import END, StateGraph

    graph = StateGraph(EmailAnalysisState)
    graph.add_node("analyze_messages", _analyze_messages_node)
    graph.add_node("process_analyzed_messages", _process_analyzed_messages_node)

    graph.set_entry_point("analyze_messages")
    graph.add_edge("analyze_messages", "process_analyzed_messages")
    graph.add_edge("process_analyzed_messages", END)

    return graph.compile(checkpointer=checkpointer)


def _checkpoint_conn_string() -> str:
    return _env_str("LANGGRAPH_CHECKPOINT_DB_URL") or _env_str("DATABASE_URL")


def _checkpoint_config(thread_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "configurable": {
            "thread_id": thread_id or "email-analysis",
            "checkpoint_ns": "email-analysis",
        }
    }


async def _run_checkpointed_email_analysis_graph(
    state: EmailAnalysisState,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    conn_string = _checkpoint_conn_string()
    if not conn_string:
        raise RuntimeError(
            "LANGGRAPH_CHECKPOINT_DB_URL or DATABASE_URL is required for LangGraph checkpointing."
        )

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:
        raise RuntimeError(
            "Install langgraph-checkpoint-postgres and psycopg to use Postgres checkpointing."
        ) from exc

    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        if _env_flag("LANGGRAPH_CHECKPOINT_SETUP", default=True):
            await checkpointer.setup()
        graph = _compile_email_analysis_graph(checkpointer=checkpointer)
        final_state = await graph.ainvoke(
            state,
            config=_checkpoint_config(thread_id),
        )
        return dict(final_state)


async def run_email_analysis_graph(
    email: str,
    messages: List[Dict[str, Any]],
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    state = {"email": email, "messages": messages}

    if _env_flag("LANGGRAPH_POSTGRES_CHECKPOINTS", default=False):
        return await _run_checkpointed_email_analysis_graph(state, thread_id=thread_id)

    final_state = await build_email_analysis_graph().ainvoke(state)
    return dict(final_state)


async def process_fetched_messages(
    email: str,
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run agent processing for messages fetched outside the orchestrator."""
    from app.agent.pipeline import run_pipeline_for_messages

    return await run_pipeline_for_messages(email, messages)


async def email_analysis_call(msg: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not msg:
        raise ValueError("No messages provided for email analysis.")

    return await analyze_message_context(msg)


async def draft_reply_for_stored_message(
    user_email: str,
    message_id: str,
    user_intent: str = "",
) -> Dict[str, Any]:
    """Compatibility wrapper for the user-triggered reply pipeline."""
    from app.agent.pipeline import run_reply_pipeline_for_message

    return await run_reply_pipeline_for_message(
        user_email,
        message_id,
        user_intent=user_intent,
    )


async def summarize_gmail_message_on_demand(
    user_email: str,
    message_id: str,
) -> Dict[str, Any]:
    """Compatibility wrapper for the user-triggered summary pipeline."""
    from app.agent.pipeline import run_summary_pipeline_for_message

    return await run_summary_pipeline_for_message(user_email, message_id)
