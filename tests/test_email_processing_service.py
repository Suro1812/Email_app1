import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.agent.orchestrator as orch


@pytest.fixture(autouse=True)
def reset_agents(monkeypatch):
    class TestEmailAnalysisGraph:
        async def ainvoke(self, state):
            next_state = dict(state)
            next_state.update(await orch._analyze_messages_node(next_state))
            next_state.update(await orch._process_analyzed_messages_node(next_state))
            return next_state

    analyzer_result = {
        "messages": [
            {
                "category": "reminder",
                "title": "Review notes",
                "description": "Review and confirm the notes.",
                "start_date": "",
                "start_time": None,
                "end_date": None,
                "end_time": None,
                "location": None,
                "participants": [],
                "meeting_platform": None,
                "requires_confirmation": True,
                "confidence": 0.8,
                "reason": "The sender asks the recipient to review and confirm.",
            }
        ]
    }
    summary_result = {
        "summary": "The sender asks for review and confirmation.",
    }
    reply_result = {
        "suggested_reply": "Thanks, I will review this.",
        "tone": "professional",
        "confidence": 0.9,
        "llm_reply_tokens_input": 13,
        "llm_reply_tokens_output": 9,
    }
    fake_database = SimpleNamespace(
        save_analyzer_result=MagicMock(return_value=object()),
        save_email_processing_result=MagicMock(return_value=object()),
        save_summary_result=MagicMock(return_value=object()),
        save_reply_result=MagicMock(return_value=object()),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database)
    monkeypatch.setattr(
        orch,
        "build_email_analysis_graph",
        MagicMock(return_value=TestEmailAnalysisGraph()),
    )
    return {
        "analyzer_result": analyzer_result,
        "summary_result": summary_result,
        "reply_result": reply_result,
    }


@pytest.mark.asyncio
async def test_message_goes_to_analyzer_only(monkeypatch, reset_agents):
    email = {"id": "m1", "thread_id": "m1", "body": "Please review the notes by Friday and confirm."}
    analyzer_calls = []

    async def fake_analyzer(messages):
        analyzer_calls.append(messages)
        return reset_agents["analyzer_result"]

    monkeypatch.setattr(orch, "analyze_message_context", fake_analyzer)

    result = await orch.process_fetched_messages("user@example.com", [email])

    assert result["results"][0]["processing_status"] == "analyzed"
    assert result["results"][0]["reply_status"] == "not_required"
    assert result["results"][0]["summary"] is None
    assert result["results"][0]["reply"] is None
    assert len(analyzer_calls) == 1
    database = sys.modules["app.core.database"]
    database.save_analyzer_result.assert_called_once()
    database.save_summary_result.assert_not_called()
    database.save_reply_result.assert_not_called()


@pytest.mark.asyncio
async def test_short_message_without_date_is_not_analyzed(monkeypatch, reset_agents):
    email = {"id": "m2", "thread_id": "m2", "body": "Please confirm."}
    analyzer_calls = []

    async def fake_analyzer(messages):
        analyzer_calls.append(messages)
        return reset_agents["analyzer_result"]

    monkeypatch.setattr(orch, "analyze_message_context", fake_analyzer)

    result = await orch.process_fetched_messages("user@example.com", [email])

    assert result["results"][0]["processing_status"] == "not_analyzed"
    assert result["results"][0]["reply_status"] == "pending"
    assert result["results"][0]["skip_reason"] == "no_date_time_expression_detected"
    assert analyzer_calls == []
    database = sys.modules["app.core.database"]
    database.save_analyzer_result.assert_not_called()
    database.save_email_processing_result.assert_called_once()
    database.save_summary_result.assert_not_called()
    database.save_reply_result.assert_not_called()


@pytest.mark.asyncio
async def test_reply_agent_not_called_during_background_analysis(monkeypatch, reset_agents):
    email = {"id": "m3", "thread_id": "m3", "body": "FYI only for tomorrow."}
    reply_calls = []

    async def fake_analyzer(messages):
        return reset_agents["analyzer_result"]

    async def fake_reply(message, analyzer_result, summary_result=None):
        reply_calls.append((message, analyzer_result, summary_result))
        return dict(reset_agents["reply_result"])

    monkeypatch.setattr(orch, "analyze_message_context", fake_analyzer)
    monkeypatch.setattr(orch, "draft_reply_message", fake_reply)

    result = await orch.process_fetched_messages("user@example.com", [email])

    assert result["results"][0]["processing_status"] == "analyzed"
    assert result["results"][0]["reply_status"] == "not_required"
    assert reply_calls == []
    database = sys.modules["app.core.database"]
    database.save_analyzer_result.assert_called_once()
    database.save_summary_result.assert_not_called()
    database.save_reply_result.assert_not_called()


@pytest.mark.asyncio
async def test_promotional_basic_present_message_skips_llm_for_only_that_message(
    monkeypatch,
    reset_agents,
):
    skipped_email = {
        "id": "promo",
        "thread_id": "promo",
        "body": "Trailing thread text might look actionable but should not matter.",
        "promotional_check": {
            "has_list_unsubscribe_header": True,
            "has_html_code": False,
            "plain_text_word_count": 3,
            "skip_llm": True,
        },
    }
    normal_email = {
        "id": "normal",
        "thread_id": "normal",
        "body": "Please confirm by Friday.",
        "promotional_check": {
            "has_list_unsubscribe_header": False,
            "has_html_code": False,
            "plain_text_word_count": 2,
            "skip_llm": False,
        },
    }
    analyzer_calls = []

    async def fake_analyzer(messages):
        analyzer_calls.append(messages)
        return reset_agents["analyzer_result"]

    monkeypatch.setattr(orch, "analyze_message_context", fake_analyzer)

    result = await orch.process_fetched_messages(
        "user@example.com",
        [skipped_email, normal_email],
    )

    assert len(result["results"]) == 2
    assert result["results"][0]["message"]["id"] == "promo"
    assert result["results"][0]["processing_status"] == "skipped"
    assert result["results"][0]["skip_reason"] == "present_message_has_list_unsubscribe_header"
    assert result["results"][1]["message"]["id"] == "normal"
    assert result["results"][1]["processing_status"] == "analyzed"
    assert result["results"][1]["reply_status"] == "not_required"
    assert len(analyzer_calls) == 1
    assert [message["id"] for message in analyzer_calls[0]] == ["normal"]
    assert analyzer_calls[0][0]["promotional_check"]["skip_llm"] is False
    database = sys.modules["app.core.database"]
    database.save_email_processing_result.assert_called_once()
    database.save_analyzer_result.assert_called_once()
    database.save_reply_result.assert_not_called()


@pytest.mark.asyncio
async def test_human_requested_reply_uses_stored_context_and_saves(monkeypatch, reset_agents):
    database = sys.modules["app.core.database"]
    database.get_message_reply_context = MagicMock(
        return_value={
            "message": {
                "id": "m4",
                "from": "sender@example.com",
                "to": "user@example.com",
                "subject": "Review",
                "body": "The sender asks for review and confirmation.",
            },
            "analysis": {},
            "summary": {"summary": "The sender asks for review and confirmation."},
        }
    )
    gmail_message = {
        "id": "m4",
        "from": "sender@example.com",
        "to": "user@example.com",
        "subject": "Review",
        "body": "Please review and confirm.",
    }
    reply_calls = []

    async def fake_read_gmail_message(email, message_id):
        return gmail_message

    async def fake_reply(message, analyzer_result, summary_result=None, user_intent="", user_email=""):
        reply_calls.append((message, analyzer_result, summary_result, user_intent, user_email))
        return dict(reset_agents["reply_result"])

    monkeypatch.setattr("app.tool.tools.read_gmail_message", fake_read_gmail_message)
    monkeypatch.setattr(orch, "draft_reply_message", fake_reply)

    result = await orch.draft_reply_for_stored_message(
        "user@example.com",
        "m4",
        user_intent="Say I will review it today.",
    )

    assert result["processing_status"] == "reply_generated"
    assert result["reply_status"] == "generated"
    assert result["reply"]["suggested_reply"] == "Thanks, I will review this."
    database.get_message_reply_context.assert_called_once_with("user@example.com", "m4")
    database.save_reply_result.assert_called_once()
    assert len(reply_calls) == 1
    checked_message = reply_calls[0][0]
    assert checked_message["sanitized"] is True
    assert checked_message["subject"] == "<external_source>Review</external_source>"
    assert checked_message["body"] == "<external_source>Please review and confirm.</external_source>"
    assert reply_calls[0] == (
        checked_message,
        {},
        {"summary": "The sender asks for review and confirmation."},
        "Say I will review it today.",
        "user@example.com",
    )
