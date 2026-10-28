import asyncio
import importlib
import logging
import os
from typing import Any, Dict, List

import app.agent.orchestrator as agents
from app.agent.hooks import post_tool_process_gmail_message
from app.observability import observe_hook_call


logger = logging.getLogger(__name__)


def run_tool_security_checks(message: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the same post-tool sanitization used by Gmail read tools."""
    if not isinstance(message, dict):
        return message
    if message.get("sanitized") is True:
        return dict(message)
    with observe_hook_call(
        "run_tool_security_checks",
        {"message_id": message.get("id")},
    ):
        return post_tool_process_gmail_message(message)


def run_pipeline_security_checks(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [run_tool_security_checks(message) for message in messages]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def pipeline_thread_id(user_email: str, messages: List[Dict[str, Any]]) -> str:
    message_ids = [
        str(message.get("id") or "")
        for message in messages
        if isinstance(message, dict) and message.get("id")
    ]
    if message_ids:
        return f"{user_email}:{','.join(message_ids)}"
    return user_email


def persist_pipeline_results(user_email: str, results: List[Dict[str, Any]]) -> None:
    """Persist final graph results after graph execution has completed."""
    if not results:
        return

    database = importlib.import_module("app.core.database")

    for result in results:
        if not isinstance(result, dict):
            continue

        message = result.get("message") or {}
        analysis = result.get("analysis") or {}
        processing_status = str(result.get("processing_status") or "")

        if processing_status == "skipped":
            database.save_email_processing_result(
                user_email=user_email,
                message=message,
                processing_status="skipped",
                skip_reason=result.get("skip_reason"),
                reply_status=str(result.get("reply_status") or "not_required"),
            )
            continue

        if processing_status == "not_analyzed":
            database.save_email_processing_result(
                user_email=user_email,
                message=message,
                processing_status="not_analyzed",
                skip_reason=result.get("skip_reason"),
                reply_status=str(result.get("reply_status") or "pending"),
            )
            continue

        database.save_analyzer_result(user_email, message, analysis)


def enqueue_pipeline_persistence(user_email: str, results: List[Dict[str, Any]]) -> str:
    """Enqueue final graph persistence so the processing task can return sooner."""
    if not results:
        return ""

    try:
        from app.tasks import persist_pipeline_results_task

        task = persist_pipeline_results_task.delay(user_email, results)
        logger.info(
            "pipeline_persistence_task_enqueued",
            extra={
                "email": user_email,
                "result_count": len(results),
                "task_id": task.id,
            },
        )
        return str(task.id)
    except Exception:
        logger.exception(
            "pipeline_persistence_enqueue_failed_using_inline_save",
            extra={"email": user_email, "result_count": len(results)},
        )
        persist_pipeline_results(user_email, results)
        return ""


async def run_pipeline_for_messages(
    user_email: str,
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyzer pipeline: security checks, AnalyzerAgent event/reminder analysis, persistence."""
    if not messages:
        return {
            "email": user_email,
            "messages": [],
            "analysis": {"messages": []},
            "results": [],
            "processed_message_count": 0,
        }

    checked_messages = run_pipeline_security_checks(messages)
    try:
        final_state = await agents.run_email_analysis_graph(
            user_email,
            checked_messages,
            thread_id=pipeline_thread_id(user_email, checked_messages),
        )
    except Exception as exc:
        logger.warning(
            "email_analysis_marked_not_analyzed",
            extra={
                "email": user_email,
                "message_count": len(checked_messages),
                "reason": str(exc),
            },
        )
        not_analyzed_results = []
        for message in checked_messages:
            skip_reason = agents.promotional_basic_skip_reason(message)
            if skip_reason:
                not_analyzed_results.append(
                    {
                        "message": message,
                        "processing_status": "skipped",
                        "reply_status": "not_required",
                        "skip_reason": skip_reason,
                    }
                )
                continue
            if not agents.extract_date_time_expressions(message):
                not_analyzed_results.append(
                    {
                        "message": message,
                        "processing_status": "not_analyzed",
                        "reply_status": "pending",
                        "skip_reason": "no_date_time_expression_detected",
                    }
                )
                continue
            not_analyzed_results.append(
                {
                    "message": message,
                    "processing_status": "not_analyzed",
                    "reply_status": "pending",
                    "skip_reason": "analysis_failed",
                }
            )
        final_state = {
            "email": user_email,
            "messages": checked_messages,
            "analysis": {"messages": []},
            "results": not_analyzed_results,
            "processed_message_count": len(not_analyzed_results),
        }
    results = final_state.get("results", [])
    persist_pipeline_results(user_email, results)
    final_state["persisted_result_count"] = len(results)
    return final_state


async def run_analyzer_pipeline_for_messages(
    user_email: str,
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return await run_pipeline_for_messages(user_email, messages)


async def run_summary_pipeline_for_message(
    user_email: str,
    message_id: str,
) -> Dict[str, Any]:
    """Summary pipeline: fetch, security checks, SummarizerAgent, persistence."""
    database = importlib.import_module("app.core.database")
    from app.tool.tools import read_gmail_message

    message = await read_gmail_message(email=user_email, message_id=message_id)
    checked_message = run_tool_security_checks(message)
    analysis = {}
    try:
        context = database.get_message_reply_context(user_email, message_id)
        analysis = context.get("analysis") or analysis
    except Exception as exc:
        logger.warning(
            "summary_context_lookup_failed_continuing",
            extra={"email": user_email, "message_id": message_id, "reason": str(exc)},
        )

    summary_result = await agents.summarize_message(checked_message, analysis)
    summary_persisted = False
    try:
        database.save_summary_result(user_email, checked_message, summary_result)
        summary_persisted = True
    except Exception as exc:
        logger.warning(
            "summary_persistence_failed_returning_result",
            extra={"email": user_email, "message_id": message_id, "reason": str(exc)},
        )
    return {
        "message": checked_message,
        "analysis": analysis,
        "summary": summary_result,
        "summary_persisted": summary_persisted,
        "processing_status": "summarized",
    }


async def run_reply_pipeline_for_message(
    user_email: str,
    message_id: str,
    user_intent: str = "",
) -> Dict[str, Any]:
    """Reply pipeline: fetch, security checks, ReplyAgent, persistence."""
    database = importlib.import_module("app.core.database")
    from app.tool.tools import read_gmail_message

    message = await read_gmail_message(email=user_email, message_id=message_id)
    checked_message = run_tool_security_checks(message)
    try:
        context = database.get_message_reply_context(user_email, message_id)
    except ValueError:
        context = {"analysis": {}, "summary": None}

    reply_result = await agents.draft_reply_message(
        checked_message,
        context["analysis"],
        context.get("summary"),
        user_intent=user_intent,
        user_email=user_email,
    )
    database.save_reply_result(user_email, checked_message, reply_result)
    return {
        "message": checked_message,
        "analysis": context["analysis"],
        "user_intent": user_intent,
        "reply": reply_result,
        "processing_status": "reply_generated",
        "reply_status": "generated",
    }


async def run_writer_pipeline_for_message(
    user_email: str,
    message_id: str,
    user_instruction: str = "",
    writing_format: str = "formal",
) -> Dict[str, Any]:
    """Writer pipeline: fetch, security checks, WriterAgent draft generation."""
    database = importlib.import_module("app.core.database")
    from app.tool.tools import read_gmail_message

    message = await read_gmail_message(email=user_email, message_id=message_id)
    checked_message = run_tool_security_checks(message)
    try:
        context = database.get_message_reply_context(user_email, message_id)
    except ValueError:
        context = {"analysis": {}, "summary": None}

    writer_result = await agents.write_message_draft(
        checked_message,
        context["analysis"],
        context.get("summary"),
        user_instruction=user_instruction,
        writing_format=writing_format,
    )
    return {
        "message": checked_message,
        "analysis": context["analysis"],
        "summary": context.get("summary"),
        "user_instruction": user_instruction,
        "writer": writer_result,
        "processing_status": "writer_generated",
    }


async def run_writer_pipeline_for_compose(
    to_address: str = "",
    subject: str = "",
    user_instruction: str = "",
    writing_format: str = "formal",
) -> Dict[str, Any]:
    """Writer pipeline for the Compose button."""
    writer_result = await agents.write_compose_draft(
        to_address=to_address,
        subject=subject,
        user_instruction=user_instruction,
        writing_format=writing_format,
    )
    return {
        "to": to_address,
        "subject": subject,
        "user_instruction": user_instruction,
        "writer": writer_result,
        "processing_status": "writer_generated",
    }


async def fetch_messages_by_ids(
    user_email: str,
    message_ids: List[str],
) -> List[Dict[str, Any]]:
    from app.tool.tools import read_gmail_message
    try:
        from googleapiclient.errors import HttpError
    except ImportError:
        HttpError = ()  # type: ignore[assignment]

    if not message_ids:
        return []

    max_concurrency = max(1, _env_int("EMAIL_MESSAGE_FETCH_CONCURRENCY", 5))
    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch_one(message_id: str) -> Dict[str, Any]:
        async with semaphore:
            return await read_gmail_message(email=user_email, message_id=message_id)

    fetched = await asyncio.gather(
        *(fetch_one(message_id) for message_id in message_ids),
        return_exceptions=True,
    )
    messages: List[Dict[str, Any]] = []
    for message_id, result in zip(message_ids, fetched):
        if isinstance(result, Exception):
            status = getattr(getattr(result, "resp", None), "status", None)
            if HttpError and isinstance(result, HttpError) and status == 404:
                logger.warning(
                    "gmail_message_not_found_skipping",
                    extra={"email": user_email, "message_id": message_id},
                )
                continue
            raise result
        messages.append(result)
    return messages


async def run_pipeline_for_message_ids(
    user_email: str,
    message_ids: List[str],
) -> Dict[str, Any]:
    messages = await fetch_messages_by_ids(user_email, message_ids)
    return await run_analyzer_pipeline_for_messages(user_email, messages)
