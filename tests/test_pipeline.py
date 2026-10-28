import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.agent.orchestrator as agents
from app.agent import hooks
from app.agent import pipeline


def test_pipeline_security_checks_sanitize_unsanitized_messages(monkeypatch):
    def fake_presidio_mask(text):
        return (
            text.replace("sender@example.com", "[EMAIL REDACTED]")
            .replace("user@example.com", "[EMAIL REDACTED]")
            .replace("+1-234-567-8901", "[PHONE REDACTED]")
        )

    monkeypatch.setattr(hooks, "_mask_pii_with_presidio", fake_presidio_mask)

    checked = pipeline.run_pipeline_security_checks(
        [
            {
                "id": "m1",
                "from": "sender@example.com",
                "to": "user@example.com",
                "subject": "<script>bad()</script>Hello",
                "snippet": "Call +1-234-567-8901",
                "body": "Email user@example.com",
            }
        ]
    )

    assert checked[0]["sanitized"] is True
    assert checked[0]["from"] == "[EMAIL REDACTED]"
    assert checked[0]["to"] == "[EMAIL REDACTED]"
    assert "<script>" not in checked[0]["subject"]
    assert "[PHONE REDACTED]" in checked[0]["snippet"]
    assert "[EMAIL REDACTED]" in checked[0]["body"]


@pytest.mark.asyncio
async def test_pipeline_sanitizes_messages_then_invokes_graph(monkeypatch):
    monkeypatch.setattr(
        hooks,
        "_mask_pii_with_presidio",
        lambda text: text.replace("sender@example.com", "[EMAIL REDACTED]"),
    )

    graph = MagicMock()
    graph.ainvoke = AsyncMock(
        return_value={
            "email": "user@example.com",
            "messages": [{"id": "m1", "sanitized": True}],
            "results": [],
            "processed_message_count": 1,
        }
    )
    monkeypatch.setattr(agents, "build_email_analysis_graph", MagicMock(return_value=graph))

    result = await pipeline.run_pipeline_for_messages(
        "user@example.com",
        [
            {
                "id": "m1",
                "thread_id": "m1",
                "from": "sender@example.com",
                "to": "user@example.com",
                "subject": "Confirm",
                "body": "Please review the notes and confirm.",
            }
        ],
    )

    assert result["processed_message_count"] == 1
    graph.ainvoke.assert_called_once()
    invoked_state = graph.ainvoke.call_args.args[0]
    assert invoked_state["email"] == "user@example.com"
    assert invoked_state["messages"][0]["sanitized"] is True
    assert invoked_state["messages"][0]["from"] == "[EMAIL REDACTED]"


def test_persist_pipeline_results_saves_final_outputs(monkeypatch):
    fake_database = SimpleNamespace(
        save_analyzer_result=MagicMock(),
        save_email_processing_result=MagicMock(),
        save_summary_result=MagicMock(),
        save_reply_result=MagicMock(),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database)

    pipeline.persist_pipeline_results(
        "user@example.com",
        [
            {
                "message": {"id": "m1", "subject": "Review"},
                "analysis": {
                    "category": "reminder",
                    "title": "Review",
                },
                "summary": None,
                "reply": None,
                "processing_status": "analyzed",
                "reply_status": "not_required",
            }
        ],
    )

    fake_database.save_analyzer_result.assert_called_once()
    fake_database.save_summary_result.assert_not_called()
    fake_database.save_reply_result.assert_not_called()
    fake_database.save_email_processing_result.assert_not_called()


def test_persist_pipeline_results_saves_skips(monkeypatch):
    fake_database = SimpleNamespace(
        save_analyzer_result=MagicMock(),
        save_email_processing_result=MagicMock(),
        save_summary_result=MagicMock(),
        save_reply_result=MagicMock(),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database)

    pipeline.persist_pipeline_results(
        "user@example.com",
        [
            {
                "message": {"id": "promo"},
                "processing_status": "skipped",
                "reply_status": "not_required",
                "skip_reason": "present_message_has_html_code",
            }
        ],
    )

    fake_database.save_email_processing_result.assert_called_once_with(
        user_email="user@example.com",
        message={"id": "promo"},
        processing_status="skipped",
        skip_reason="present_message_has_html_code",
        reply_status="not_required",
    )
    fake_database.save_analyzer_result.assert_not_called()
    fake_database.save_summary_result.assert_not_called()
    fake_database.save_reply_result.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_fetches_messages_by_ids_then_processes(monkeypatch):
    messages = [{"id": "m1", "body": "Hello"}]
    fetched_ids = []
    processed = {"processed_message_count": 1}

    async def fake_read_gmail_message(email, message_id):
        fetched_ids.append((email, message_id))
        return messages[0]

    async def fake_run_pipeline_for_messages(user_email, pipeline_messages):
        assert user_email == "user@example.com"
        assert pipeline_messages == messages
        return processed

    monkeypatch.setattr(
        "app.tool.tools.read_gmail_message",
        fake_read_gmail_message,
    )
    monkeypatch.setattr(
        pipeline,
        "run_pipeline_for_messages",
        fake_run_pipeline_for_messages,
    )

    result = await pipeline.run_pipeline_for_message_ids(
        "user@example.com",
        ["m1"],
    )

    assert result == processed
    assert fetched_ids == [("user@example.com", "m1")]


@pytest.mark.asyncio
async def test_summary_pipeline_returns_summary_when_persistence_fails(monkeypatch):
    fake_database = SimpleNamespace(
        get_message_reply_context=MagicMock(side_effect=RuntimeError("context unavailable")),
        save_summary_result=MagicMock(side_effect=RuntimeError("save unavailable")),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database)

    async def fake_read_gmail_message(email, message_id):
        return {
            "id": message_id,
            "from": "sender@example.com",
            "to": email,
            "subject": "Project review",
            "body": "Please review the project notes.",
            "sanitized": True,
        }

    monkeypatch.setattr("app.tool.tools.read_gmail_message", fake_read_gmail_message)
    monkeypatch.setattr(
        agents,
        "summarize_message",
        AsyncMock(return_value={"summary": "The sender asks for a project review."}),
    )

    result = await pipeline.run_summary_pipeline_for_message("user@example.com", "m1")

    assert result["processing_status"] == "summarized"
    assert result["summary"] == {"summary": "The sender asks for a project review."}
    assert result["summary_persisted"] is False
    fake_database.get_message_reply_context.assert_called_once_with("user@example.com", "m1")
    fake_database.save_summary_result.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_marks_not_analyzed_when_graph_unavailable(monkeypatch):
    fake_database = SimpleNamespace(
        save_analyzer_result=MagicMock(),
        save_email_processing_result=MagicMock(),
        save_summary_result=MagicMock(),
        save_reply_result=MagicMock(),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database)
    monkeypatch.setattr(
        agents,
        "run_email_analysis_graph",
        AsyncMock(side_effect=RuntimeError("LLM unavailable")),
    )

    result = await pipeline.run_pipeline_for_messages(
        "user@example.com",
        [
            {
                "id": "m1",
                "thread_id": "m1",
                "from": "sender@example.com",
                "to": "user@example.com",
                "subject": "Review",
                "body": "Please review the proposal and send feedback before Monday.",
            }
        ],
    )

    assert result["processed_message_count"] == 1
    assert "analysis_error" not in result
    assert result["results"][0]["message"]["id"] == "m1"
    assert result["results"][0]["message"]["sanitized"] is True
    assert result["results"][0]["processing_status"] == "not_analyzed"
    assert result["results"][0]["reply_status"] == "pending"
    fake_database.save_analyzer_result.assert_not_called()
    fake_database.save_summary_result.assert_not_called()
    fake_database.save_reply_result.assert_not_called()
    fake_database.save_email_processing_result.assert_called_once_with(
        user_email="user@example.com",
        message=result["results"][0]["message"],
        processing_status="not_analyzed",
        skip_reason="analysis_failed",
        reply_status="pending",
    )


@pytest.mark.asyncio
async def test_pipeline_preserves_parser_gate_when_analyzer_fails(monkeypatch):
    fake_database = SimpleNamespace(
        save_analyzer_result=MagicMock(),
        save_email_processing_result=MagicMock(),
        save_summary_result=MagicMock(),
        save_reply_result=MagicMock(),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database)
    monkeypatch.setattr(
        agents,
        "run_email_analysis_graph",
        AsyncMock(side_effect=RuntimeError("LLM unavailable")),
    )

    result = await pipeline.run_pipeline_for_messages(
        "user@example.com",
        [
            {"id": "date-msg", "body": "Please send feedback before Monday."},
            {"id": "plain-msg", "body": "Please send feedback when you can."},
        ],
    )

    assert [item["skip_reason"] for item in result["results"]] == [
        "analysis_failed",
        "no_date_time_expression_detected",
    ]
    fake_database.save_analyzer_result.assert_not_called()
    assert fake_database.save_email_processing_result.call_count == 2
