"""Tests for app/agent/orchestrator.py"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import app.agent.orchestrator as orch


class TestSettings:
    def test_default_vllm_base_url(self):
        assert orch.Settings.VLLM_BASE_URL in {
            "http://localhost:8000/v1",
            "http://localhost:11434/v1",
        }

    def test_default_vllm_api_key(self):
        assert orch.Settings.VLLM_API_KEY == "EMPTY"

    def test_default_max_tokens(self):
        assert orch.Settings.MAX_TOKENS in {2048, 4096}

    def test_default_temperature(self):
        assert orch.Settings.TEMPERATURE == 0

    def test_require_model_raises_when_missing(self):
        with patch.object(orch.Settings, "ANALYST_MODEL", ""):
            with pytest.raises(RuntimeError, match="ANALYST_MODEL"):
                orch.Settings.require_model()

    def test_require_model_passes_when_set(self):
        with patch.object(orch.Settings, "ANALYST_MODEL", "local-model"):
            orch.Settings.require_model()  # must not raise


class TestResponseText:
    @pytest.mark.asyncio
    async def test_extracts_text_from_response(self):
        block = SimpleNamespace(text="hello world")
        response = SimpleNamespace(content=[block])
        assert await orch._response_text(response) == "hello world"

    @pytest.mark.asyncio
    async def test_extracts_text_from_openai_response(self):
        message = SimpleNamespace(content="hello from vllm")
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        assert await orch._response_text(response) == "hello from vllm"

    @pytest.mark.asyncio
    async def test_raises_on_empty_content_list(self):
        response = SimpleNamespace(content=[])
        with pytest.raises(RuntimeError, match="Empty response"):
            await orch._response_text(response)

    @pytest.mark.asyncio
    async def test_raises_on_none_content(self):
        response = SimpleNamespace(content=None)
        with pytest.raises(RuntimeError, match="Empty response"):
            await orch._response_text(response)

    @pytest.mark.asyncio
    async def test_handles_dict_block(self):
        block = {"text": "from dict block"}
        response = SimpleNamespace(content=[block])
        result = await orch._response_text(response)
        assert result == "from dict block"

    @pytest.mark.asyncio
    async def test_strips_whitespace(self):
        block = SimpleNamespace(text="  trimmed  ")
        response = SimpleNamespace(content=[block])
        assert await orch._response_text(response) == "trimmed"


class TestExtractToolInput:
    @pytest.mark.asyncio
    async def test_returns_input_for_matching_tool(self):
        block = SimpleNamespace(type="tool_use", name="analyze_emails", input={"emails": []})
        response = SimpleNamespace(content=[block])
        result = await orch.extract_tool_input(response, "analyze_emails")
        assert result == {"emails": []}

    @pytest.mark.asyncio
    async def test_returns_input_for_openai_tool_call(self):
        function = SimpleNamespace(name="analyze_emails", arguments='{"emails": []}')
        tool_call = SimpleNamespace(function=function)
        message = SimpleNamespace(tool_calls=[tool_call])
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

        result = await orch.extract_tool_input(response, "analyze_emails")

        assert result == {"emails": []}

    @pytest.mark.asyncio
    async def test_raises_for_invalid_openai_tool_json(self):
        function = SimpleNamespace(name="analyze_emails", arguments="{bad json")
        tool_call = SimpleNamespace(function=function)
        message = SimpleNamespace(tool_calls=[tool_call])
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

        with pytest.raises(RuntimeError, match="invalid JSON"):
            await orch.extract_tool_input(response, "analyze_emails")

    @pytest.mark.asyncio
    async def test_raises_when_tool_name_does_not_match(self):
        block = SimpleNamespace(type="tool_use", name="other_tool", input={})
        response = SimpleNamespace(content=[block])
        with pytest.raises(RuntimeError, match="analyze_emails"):
            await orch.extract_tool_input(response, "analyze_emails")

    @pytest.mark.asyncio
    async def test_raises_when_no_tool_use_blocks(self):
        block = SimpleNamespace(type="text", text="some text")
        response = SimpleNamespace(content=[block])
        with pytest.raises(RuntimeError, match="Model did not call tool"):
            await orch.extract_tool_input(response, "analyze_emails")

    @pytest.mark.asyncio
    async def test_finds_correct_tool_among_multiple_blocks(self):
        blocks = [
            SimpleNamespace(type="text", text="thinking..."),
            SimpleNamespace(type="tool_use", name="write_reply_emails", input={"emails": [{"reply_body": "s"}]}),
            SimpleNamespace(type="tool_use", name="analyze_emails", input={"emails": [{"category": "reminder"}]}),
        ]
        response = SimpleNamespace(content=blocks)
        result = await orch.extract_tool_input(response, "analyze_emails")
        assert result["emails"][0]["category"] == "reminder"


def valid_context_analysis(category="reminder"):
    event_type = {
        "calendar_event": "meeting",
        "reminder": "task_reminder",
        "none": "none",
    }.get(category, "none")
    return {
        "messages": [
            {
                "category": category,
                "event_type": event_type,
                "title": "Review notes",
                "description": "Review the notes.",
                "start_date": "",
                "start_time": None,
                "end_date": None,
                "end_time": None,
                "location": None,
                "participants": [],
                "meeting_platform": None,
                "requires_confirmation": True,
                "confidence": 0.8,
                "reason": "The message asks the recipient to review notes.",
            }
        ]
    }


class TestEmailAnalysisCall:
    def test_extract_date_time_expressions_detects_body_dates_and_times(self):
        message = {
            "subject": "Project review",
            "body": "Please send feedback before Monday at 4:30 PM. We can follow up next week.",
        }

        assert orch.extract_date_time_expressions(message) == [
            "Monday",
            "4:30 PM",
            "next week",
        ]

    def test_extract_date_time_expressions_ignores_gmail_received_date_header(self):
        message = {
            "date": "Mon, 1 Jan 2024 13:45:00 +0000",
            "body": "Please confirm.",
        }

        assert orch.extract_date_time_expressions(message) == []

    @pytest.mark.asyncio
    async def test_raises_value_error_with_empty_list(self):
        with pytest.raises(ValueError, match="No messages provided"):
            await orch.email_analysis_call([])

    @pytest.mark.asyncio
    async def test_calls_call_agent_with_event_reminder_json_output(self):
        messages = [{"from": "a@b.com", "date": "2024-01-01", "Message_body": "Urgent meeting!"}]
        expected = valid_context_analysis(category="reminder")

        with patch.object(orch, "_call_agent", new_callable=AsyncMock, return_value=valid_context_analysis()):
            result = await orch.email_analysis_call(messages)

        assert result == expected

    @pytest.mark.asyncio
    async def test_prompt_contains_sender_date_body_and_plain_output_instruction(self):
        messages = [{"from": "boss@corp.com", "date": "2024-06-01", "Message_body": "Deadline today"}]
        captured = []

        async def fake_agent(skill_name, prompt, **kwargs):
            captured.append(prompt)
            return valid_context_analysis()

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            await orch.email_analysis_call(messages)

        assert "boss@corp.com" in captured[0]
        assert "2024-06-01" in captured[0]
        assert "Deadline today" in captured[0]
        assert "Event and Reminder Analyzer" in captured[0]
        assert "Extracted_date_time_expressions" in captured[0]
        assert '["today"]' in captured[0]
        assert "Return JSON only" in captured[0]
        assert "calendar_event | reminder | none" in captured[0]
        assert "event_type" in captured[0]
        assert captured[0].rindex("Output instructions:") > captured[0].index("Deadline today")

    @pytest.mark.asyncio
    async def test_uses_plain_analyzer_output_without_tools(self):
        messages = [{"from": "a@b.com", "date": "2024-01-01", "Message_body": "Hi"}]
        calls = []

        async def fake_agent(skill_name, prompt, tools=None, tool_choice=None, **kwargs):
            calls.append((tools, tool_choice, kwargs.get("model")))
            return valid_context_analysis()

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            with patch.object(orch.Settings, "ANALYZER_MODEL", "qwen3.5:9b-q8_0"):
                await orch.email_analysis_call(messages)

        assert calls == [(None, None, "qwen3.5:9b-q8_0")]

    @pytest.mark.asyncio
    async def test_analyzer_writes_raw_and_parsed_agent_io_log(self):
        messages = [{"id": "msg-1", "from": "a@b.com", "date": "2024-01-01", "Message_body": "Hi"}]
        logs = []

        async def fake_agent(skill_name, prompt, **kwargs):
            return valid_context_analysis(category="none")

        with patch.object(orch, "_call_agent", side_effect=fake_agent), \
             patch.object(orch, "_write_agent_io_log", side_effect=lambda *args: logs.append(args)):
            result = await orch.email_analysis_call(messages)

        assert result == valid_context_analysis(category="none")
        assert logs[0][0] == "analyzer"
        assert logs[0][1] == "msg-1"
        assert logs[0][2]["model"] == orch.Settings.ANALYZER_MODEL
        assert '"category": "none"' in logs[0][2]["output"]["raw_text"]
        assert logs[0][2]["output"]["parsed"] == valid_context_analysis(category="none")

    @pytest.mark.asyncio
    async def test_analysis_call_uses_analyzer_skill(self):
        messages = [{"from": "a@b.com", "date": "2024-01-01", "Message_body": "Hi"}]
        skill_names = []

        async def fake_agent(skill_name, prompt, **kwargs):
            skill_names.append(skill_name)
            return valid_context_analysis()

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            await orch.email_analysis_call(messages)

        assert skill_names == [orch.ANALYZER_SKILL_NAME]

    @pytest.mark.asyncio
    async def test_summarize_message_uses_summarizer_skill(self):
        skill_names = []
        models = []

        async def fake_agent(skill_name, prompt, **kwargs):
            skill_names.append(skill_name)
            models.append(kwargs.get("model"))
            return {"summary": "A concise summary."}

        with patch.object(orch.Settings, "SUMMARY_MODEL", "summary-model"), \
             patch.object(orch, "_call_agent", side_effect=fake_agent):
            await orch.summarize_message(
                {"from": "a@b.com", "Message_body": "Please review the attached notes."},
                {},
            )

        assert skill_names == [orch.SUMMARIZER_SKILL_NAME]
        assert models == ["summary-model"]

    def test_structured_thread_context_orders_messages_and_marks_latest(self):
        message = {
            "from": "Nikhil <nikhil@example.com>",
            "date": "Mon, 22 Jun 2026 20:02:24 +0530",
            "body": "I feel better today. Come for dinner today so we can plan it.",
            "thread_messages": [
                {
                    "from": "Surojit <surojit@example.com>",
                    "date": "Sun, 21 Jun 2026 12:12:00 +0530",
                    "body": "Okay lets meet tomorrow. Can you pick me?",
                },
                {
                    "from": "Nikhil <nikhil@example.com>",
                    "date": "Sun, 21 Jun 2026 12:39:00 +0530",
                    "body": "I feel sick. Please cancel tomorrow and plan next week.",
                },
            ],
        }

        result = orch.structured_thread_context(message)

        assert result.startswith("Current message:")
        assert "sender: Nikhil" in result
        assert "Previous message 1:" in result
        assert "Previous message 2:" in result
        assert "content: I feel better today. Come for dinner today so we can plan it." in result
        assert "datetime: 21 Jun 2026 12:12 PM" in result
        assert "content: Okay lets meet tomorrow. Can you pick me?" in result
        assert "content: I feel sick. Please cancel tomorrow and plan next week." in result
        assert result.index("I feel better today") < result.index("Okay lets meet tomorrow")
        assert result.index("I feel better today") < result.index("I feel sick")
        assert result.index("I feel sick") < result.index("Okay lets meet tomorrow")

    def test_thread_content_preserves_hook_sanitized_text(self):
        result = orch._thread_content(
            "<external_source>Hi surojit, I feel better today &amp; can you come?</external_source>"
        )

        assert result == "<external_source>Hi surojit, I feel better today &amp; can you come?</external_source>"

    @pytest.mark.asyncio
    async def test_summarize_message_returns_plain_summary_text(self):
        calls = []
        summary_text = (
            "Current message:\n"
            "- From a@b.com, unknown datetime: Please review the attached notes.\n\n"
            "Previous messages:\n"
            "- None.\n\n"
            "User action:\n"
            "- Review the attached notes.\n\n"
            "Notes:\n"
            "- No major caveats."
        )

        async def fake_agent(skill_name, prompt, **kwargs):
            calls.append((prompt, kwargs))
            return {"text": summary_text}

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            result = await orch.summarize_message(
                {"from": "a@b.com", "Message_body": "Please review the attached notes."},
                {},
            )

        assert result == {
            "summary": (
                "Current message:\n"
                "- From a@b.com, unknown datetime: Please review the attached notes.\n\n"
                "User action:\n"
                "- Review the attached notes."
            )
        }
        assert len(calls) == 1
        assert calls[0][1]["tool_choice"] is None
        assert "EMAIL_THREAD_START" in calls[0][0]
        assert "EMAIL_THREAD_END" in calls[0][0]
        assert "Return the final summary using this exact pointwise structure" not in calls[0][0]

    @pytest.mark.asyncio
    async def test_summarize_message_strips_reasoning_from_plain_output(self):
        calls = []
        summary_text = (
            "<think>I should summarize.</think>\n"
            "Current message:\n"
            "- From a@b.com, unknown datetime: Please review the attached notes.\n\n"
            "Previous messages:\n"
            "- None.\n\n"
            "User action:\n"
            "- Review the attached notes.\n\n"
            "Notes:\n"
            "- No major caveats."
        )

        async def fake_agent(skill_name, prompt, **kwargs):
            calls.append((prompt, kwargs))
            return {"text": summary_text}

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            result = await orch.summarize_message(
                {"from": "a@b.com", "Message_body": "Please review the attached notes."},
                {},
            )

        assert result == {
            "summary": (
                "Current message:\n"
                "- From a@b.com, unknown datetime: Please review the attached notes.\n\n"
                "User action:\n"
                "- Review the attached notes."
            )
        }
        assert len(calls) == 1
        assert calls[0][1]["tool_choice"] is None

    @pytest.mark.asyncio
    async def test_draft_reply_message_uses_reply_skill(self):
        skill_names = []
        models = []

        async def fake_agent(skill_name, prompt, **kwargs):
            skill_names.append(skill_name)
            models.append(kwargs.get("model"))
            return {
                "suggested_reply": "Thanks, I will review this.",
                "tone": "professional",
                "confidence": 0.9,
            }

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            with patch.object(orch.Settings, "REPLY_MODEL", "qwen3.5:9b-q8_0"):
                await orch.draft_reply_message(
                    {"from": "a@b.com", "Message_body": "Please review the attached notes."},
                    {},
                    user_intent="Say I will review it today.",
                )

        assert skill_names == [orch.REPLY_SKILL_NAME]
        assert models == ["qwen3.5:9b-q8_0"]

    @pytest.mark.asyncio
    async def test_draft_reply_logs_reply_model(self):
        logs = []

        async def fake_plain_agent(skill_name, prompt, **kwargs):
            return "Thanks, I will review this."

        with patch.object(orch, "_call_plain_agent", side_effect=fake_plain_agent):
            with patch.object(orch, "_write_agent_io_log", side_effect=lambda *args: logs.append(args)):
                with patch.object(orch.Settings, "REPLY_MODEL", "qwen3.5:9b-q8_0"):
                    await orch.draft_reply_message(
                        {"id": "msg-1", "from": "a@b.com", "Message_body": "Please review this."},
                        {},
                    )

        assert logs[0][2]["model"] == "qwen3.5:9b-q8_0"

    @pytest.mark.asyncio
    async def test_draft_reply_prompt_limits_unauthorized_assurances(self):
        prompts = []

        async def fake_agent(skill_name, prompt, **kwargs):
            prompts.append(prompt)
            return {
                "suggested_reply": "I am checking this and will update you.",
                "tone": "professional",
                "confidence": 0.9,
            }

        with patch.object(orch, "_call_agent", side_effect=fake_agent):
            await orch.draft_reply_message(
                {"from": "a@b.com", "to": "user@example.com", "Message_body": "Please approve or refund this today."},
                {},
                user_intent="I am checking it.",
                user_email="user@example.com",
            )

        assert "User mailbox: user@example.com" in prompts[0]
        assert "The sender: a@b.com" in prompts[0]
        assert "Draft a reply FROM the user mailbox TO the sender" in prompts[0]
        assert "Do not adopt the sender's role" in prompts[0]
        assert "Do not introduce new assurances" in prompts[0]
        assert "If User_reply_intent is brief, keep the reply brief" in prompts[0]
        assert "acknowledge the request but do not grant, deny, schedule, promise" in prompts[0]

    @pytest.mark.asyncio
    async def test_compose_writer_prompt_rewrites_draft_or_generates_from_instruction(self):
        calls = []

        async def fake_writer_agent(prompt, **kwargs):
            calls.append((prompt, kwargs))
            return "Hello,\n\nI will follow up with the details shortly.\n\nBest regards,"

        with patch.object(orch, "_call_writer_plain_agent", side_effect=fake_writer_agent):
            await orch.write_compose_draft(
                to_address="recipient@example.com",
                subject="Follow up",
                user_instruction="correct this mail: i will send details soon",
                writing_format="formal",
            )

        assert calls[0][1]["max_tokens"] == orch.Settings.WRITER_MAX_TOKENS
        prompt = calls[0][0]
        assert "Write or revise a Gmail compose draft" in prompt
        assert "First classify User_writing_input silently" in prompt
        assert "revise that provided text" in prompt
        assert "If User_writing_input is an instruction to write a message" in prompt
        assert "User_writing_input: correct this mail: i will send details soon" in prompt

    def test_analyzer_validator_rejects_missing_required_field(self):
        analysis = valid_context_analysis()
        del analysis["messages"][0]["category"]

        with pytest.raises(ValueError, match="missing keys"):
            orch.validate_analyzer_result(analysis, expected_count=1)

    def test_analyzer_validator_rejects_wrong_email_count(self):
        with pytest.raises(ValueError, match="expected 2"):
            orch.validate_analyzer_result(valid_context_analysis(), expected_count=2)

    def test_analyzer_validator_strips_extra_fields(self):
        analysis = valid_context_analysis()
        analysis["messages"][0]["Message_body"] = "Copied body should not persist."

        assert orch.validate_analyzer_result(analysis, expected_count=1) == valid_context_analysis()

    def test_analyzer_validator_trims_extra_items(self):
        analysis = {
            "messages": [
                {
                    **valid_context_analysis(category="reminder")["messages"][0],
                },
                {
                    **valid_context_analysis(category="none")["messages"][0],
                },
            ]
        }

        assert orch.validate_analyzer_result(analysis, expected_count=1) == {
            "messages": [analysis["messages"][0]]
        }

    def test_analyzer_validator_accepts_none_category(self):
        analysis = valid_context_analysis(category="none")

        assert orch.validate_analyzer_result(analysis, expected_count=1) == analysis

    def test_analyzer_validator_marks_date_only_calendar_event_as_planned_reminder(self):
        analysis = valid_context_analysis(category="calendar_event")
        analysis["messages"][0].update(
            {
                "event_type": "meeting",
                "title": "Plan meeting",
                "description": "Plan a meeting tomorrow.",
                "start_date": "2099-01-01",
                "start_time": None,
                "requires_confirmation": True,
            }
        )

        result = orch.validate_analyzer_result(analysis, expected_count=1)

        assert result["messages"][0]["calendar_event"]["event_kind"] == "meeting"

    def test_analyzer_validator_keeps_today_date_only_planned_event_visible(self):
        analysis = valid_context_analysis(category="calendar_event")
        analysis["messages"][0].update(
            {
                "event_type": "meeting",
                "title": "Plan meeting",
                "description": "Plan a meeting today.",
                "start_date": orch.datetime.utcnow().date().isoformat(),
                "start_time": None,
                "requires_confirmation": True,
            }
        )

        result = orch.validate_analyzer_result(analysis, expected_count=1)

        assert result["messages"][0]["calendar_event"]["event_kind"] == "meeting"

    def test_analyzer_validator_creates_calendar_payload_for_reminder_due_date(self):
        analysis = valid_context_analysis(category="reminder")
        analysis["messages"][0].update(
            {
                "event_type": "deadline",
                "title": "Submit report",
                "description": "Submit the report before the deadline.",
                "start_date": "2099-01-03",
                "start_time": "17:30:00",
                "requires_confirmation": False,
            }
        )

        result = orch.validate_analyzer_result(analysis, expected_count=1)

        event = result["messages"][0]["calendar_event"]
        assert event["title"] == "Submit report"
        assert event["start_at"] == "2099-01-03T17:30:00"
        assert event["event_kind"] == "deadline"

    @pytest.mark.asyncio
    async def test_process_node_does_not_fallback_when_analyzer_misses_calendar_payload(self):
        message = {
            "id": "meeting-plan-1",
            "date": "Fri, 10 Jul 2026 09:00:00 +0530",
            "subject": "Schedule a meeting",
            "body": (
                "Hello surojit,\n\n"
                "Lets plan a meeting for tomorrow and i will send a invite for tomorrow "
                "after checking my calender.\n\n"
                "With regards\n"
                "Nikhil"
            ),
        }
        analyzer_item = valid_context_analysis(category="calendar_event")["messages"][0]
        analyzer_item.update(
            {
                "title": "Plan meeting",
                "description": "Plan meeting tomorrow.",
                "start_date": "",
                "start_time": None,
            }
        )

        result = await orch._process_analyzed_messages_node(
            {
                "email": "user@example.com",
                "messages": [message],
                "analysis": {"messages": [analyzer_item]},
                "analysis_message_indexes": [0],
            }
        )

        analysis = result["results"][0]["analysis"]
        assert analysis["category"] == "calendar_event"
        assert "calendar_event" not in analysis

    def test_analyzer_validator_rejects_invalid_category(self):
        analysis = valid_context_analysis(category="invalid")

        with pytest.raises(ValueError, match="category"):
            orch.validate_analyzer_result(analysis, expected_count=1)

    def test_summary_validator_accepts_only_summary(self):
        assert orch.validate_summary_result({"summary": "A concise summary."}) == {
            "summary": "A concise summary."
        }

    def test_summary_validator_rejects_extra_fields(self):
        with pytest.raises(ValueError, match="unexpected keys"):
            orch.validate_summary_result(
                {
                    "summary": "A concise summary.",
                    "confidence": 0.9,
                }
            )

    @pytest.mark.asyncio
    async def test_process_analyzed_message_never_calls_reply_agent(self):
        message = {
            "id": "mail-1",
            "from": "sender@example.com",
            "to": "user@example.com",
            "subject": "Reminder",
            "body": "Please review this tomorrow.",
        }
        analyzer_result = valid_context_analysis(category="reminder")["messages"][0]

        result = await orch.process_analyzed_message(
            "user@example.com",
            message,
            analyzer_result,
        )

        assert result["reply"] is None
        assert result["reply_status"] == "not_required"
        assert result["processing_status"] == "analyzed"
