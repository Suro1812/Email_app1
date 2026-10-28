import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from app.webhook import APP_SESSION_COOKIE, app, require_session


client = TestClient(app)
TEST_SESSION = {
    "session_id": "test-session",
    "user_id": 1,
    "email": "user@example.com",
}


@pytest.fixture(autouse=True)
def authenticated_session():
    app.dependency_overrides[require_session] = lambda: TEST_SESSION
    client.cookies.set(APP_SESSION_COOKIE, TEST_SESSION["session_id"])
    yield
    app.dependency_overrides.pop(require_session, None)
    client.cookies.clear()


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def test_get_login_endpoint_redirects_to_google():
    with patch(
        "app.core.auth.build_oauth_authorization_url",
        new_callable=AsyncMock,
        return_value=("https://accounts.google.com/o/oauth2/auth?state=test", "test"),
    ) as build_url:
        response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "https://accounts.google.com/o/oauth2/auth?state=test"
    build_url.assert_called_once()


def test_post_login_endpoint_rejects_stale_frontend_calls():
    response = client.post("/auth/login")

    assert response.status_code == 409


def test_start_watch_endpoint():
    with patch(
        "app.webhook.start_gmail_watch",
        new_callable=AsyncMock,
        return_value={"historyId": "456"},
    ) as start_watch:
        response = client.post(
            "/gmail/watch",
            json={
                "email": "user@example.com",
                "topic_name": "projects/proj/topics/gmail",
                "label_ids": ["INBOX"],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "watch_started",
        "email": "user@example.com",
        "watch": {"historyId": "456"},
    }
    start_watch.assert_called_once_with(
        "user@example.com",
        topic_name="projects/proj/topics/gmail",
        label_ids=["INBOX"],
    )


def test_list_messages_endpoint_returns_stored_summaries():
    messages = [
        {
            "message_id": "msg-1",
            "subject": "Project update",
            "summary": "The project update needs a reply.",
        }
    ]

    with patch(
        "app.core.database.list_message_summaries",
        MagicMock(return_value=messages),
    ) as list_messages:
        response = client.get("/messages?email=user@example.com&limit=25")

    assert response.status_code == 200
    assert response.json() == {
        "email": "user@example.com",
        "messages": messages,
    }
    list_messages.assert_called_once_with("user@example.com", limit=25)


def test_gmail_messages_endpoint_fetches_fresh_mailbox_messages():
    result = {
        "email": "user@example.com",
        "mailbox": "social",
        "title": "Social",
        "result_size_estimate": 2,
        "messages": [{"message_id": "msg-1", "subject": "Hello"}],
    }

    with patch(
        "app.service.get_messages.list_gmail_mailbox_messages",
        new_callable=AsyncMock,
        return_value=result,
    ) as list_gmail:
        response = client.get("/gmail/messages?email=user@example.com&mailbox=social&limit=30")

    assert response.status_code == 200
    assert response.json() == result
    list_gmail.assert_called_once_with(
        email="user@example.com",
        mailbox="social",
        category="primary",
        limit=30,
        page_token=None,
        unread_only=False,
        search_query=None,
    )


def test_gmail_messages_endpoint_fetches_unread_mailbox_messages():
    result = {
        "email": "user@example.com",
        "mailbox": "inbox",
        "title": "Inbox",
        "unread_only": True,
        "result_size_estimate": 1,
        "messages": [{"message_id": "msg-1", "subject": "Hello"}],
    }

    with patch(
        "app.service.get_messages.list_gmail_mailbox_messages",
        new_callable=AsyncMock,
        return_value=result,
    ) as list_gmail:
        response = client.get("/gmail/messages?mailbox=inbox&limit=1&unread_only=true")

    assert response.status_code == 200
    assert response.json() == result
    list_gmail.assert_called_once_with(
        email="user@example.com",
        mailbox="inbox",
        category="primary",
        limit=1,
        page_token=None,
        unread_only=True,
        search_query=None,
    )


def test_gmail_messages_endpoint_forwards_search_query():
    result = {
        "email": "user@example.com",
        "mailbox": "search",
        "title": "Search",
        "result_size_estimate": 1,
        "messages": [{"message_id": "msg-1", "subject": "Invoice"}],
    }

    with patch(
        "app.service.get_messages.list_gmail_mailbox_messages",
        new_callable=AsyncMock,
        return_value=result,
    ) as list_gmail:
        response = client.get(
            "/gmail/messages?email=user@example.com&mailbox=search&limit=25&q=invoice"
        )

    assert response.status_code == 200
    assert response.json() == result
    list_gmail.assert_called_once_with(
        email="user@example.com",
        mailbox="search",
        category="primary",
        limit=25,
        page_token=None,
        unread_only=False,
        search_query="invoice",
    )


def test_gmail_messages_endpoint_requires_session():
    app.dependency_overrides.pop(require_session, None)
    client.cookies.clear()

    response = client.get("/gmail/messages?email=attacker@example.com&mailbox=inbox&limit=1")

    assert response.status_code == 401


def test_reply_send_endpoint_requires_session_when_logged_out():
    app.dependency_overrides.pop(require_session, None)
    client.cookies.clear()

    response = client.post(
        "/reply/send",
        json={
            "email": "user@example.com",
            "message_id": "msg-1",
            "reply_body": "Thanks, I will review this today.",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gmail_inbox_uses_inbox_query():
    list_call = MagicMock(
        execute=MagicMock(return_value={"threads": [], "resultSizeEstimate": 0})
    )
    list_method = MagicMock(return_value=list_call)
    threads_resource = MagicMock()
    threads_resource.list = list_method
    users_resource = MagicMock()
    users_resource.threads.return_value = threads_resource
    gmail_service = MagicMock()
    gmail_service.users.return_value = users_resource

    with patch(
        "app.service.get_messages.get_gmail_service",
        new_callable=AsyncMock,
        return_value=gmail_service,
    ):
        from app.service.get_messages import list_gmail_mailbox_messages

        result = await list_gmail_mailbox_messages(
            email="user@example.com",
            mailbox="inbox",
            limit=25,
        )

    assert result["mailbox"] == "inbox"
    list_method.assert_called_once_with(
        userId="me",
        maxResults=25,
        labelIds=["INBOX"],
    )


@pytest.mark.asyncio
async def test_gmail_mailbox_forwards_page_token():
    list_call = MagicMock(
        execute=MagicMock(return_value={"threads": [], "resultSizeEstimate": 0})
    )
    list_method = MagicMock(return_value=list_call)
    threads_resource = MagicMock()
    threads_resource.list = list_method
    users_resource = MagicMock()
    users_resource.threads.return_value = threads_resource
    gmail_service = MagicMock()
    gmail_service.users.return_value = users_resource

    with patch(
        "app.service.get_messages.get_gmail_service",
        new_callable=AsyncMock,
        return_value=gmail_service,
    ):
        from app.service.get_messages import list_gmail_mailbox_messages

        await list_gmail_mailbox_messages(
            email="user@example.com",
        mailbox="updates",
        limit=25,
        page_token="next-token",
    )

    list_method.assert_called_once_with(
        userId="me",
        maxResults=25,
        pageToken="next-token",
        q="category:updates",
    )


@pytest.mark.asyncio
async def test_gmail_mailbox_groups_conversation_threads():
    thread = {
        "id": "thread-1",
        "messages": [
            {
                "id": "old-msg",
                "threadId": "thread-1",
                "internalDate": "1000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Old Sender <old@example.com>"},
                        {"name": "Subject", "value": "Old subject"},
                        {"name": "Date", "value": "Sat, 27 Jun 2026 10:00:00 +0530"},
                    ]
                },
                "snippet": "Old snippet",
                "labelIds": ["INBOX"],
            },
            {
                "id": "new-msg",
                "threadId": "thread-1",
                "internalDate": "2000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "New Sender <new@example.com>"},
                        {"name": "Subject", "value": "New subject"},
                        {"name": "Date", "value": "Sat, 27 Jun 2026 11:00:00 +0530"},
                    ]
                },
                "snippet": "New snippet",
                "labelIds": ["INBOX", "CATEGORY_PERSONAL"],
            },
        ],
    }
    list_call = MagicMock(
        execute=MagicMock(return_value={"threads": [{"id": "thread-1"}], "resultSizeEstimate": 1})
    )
    get_call = MagicMock(execute=MagicMock(return_value=thread))
    threads_resource = MagicMock()
    threads_resource.list.return_value = list_call
    threads_resource.get.return_value = get_call
    users_resource = MagicMock()
    users_resource.threads.return_value = threads_resource
    gmail_service = MagicMock()
    gmail_service.users.return_value = users_resource
    gmail_service.new_batch_http_request.side_effect = RuntimeError("batch unavailable")

    with patch(
        "app.service.get_messages.get_gmail_service",
        new_callable=AsyncMock,
        return_value=gmail_service,
    ), patch(
        "app.core.database.list_message_analysis_states",
        return_value={},
    ):
        from app.service.get_messages import list_gmail_mailbox_messages

        result = await list_gmail_mailbox_messages(
            email="user@example.com",
            mailbox="inbox",
            limit=25,
        )

    assert result["result_size_estimate"] == 1
    assert len(result["messages"]) == 1
    assert result["messages"][0]["message_id"] == "new-msg"
    assert result["messages"][0]["thread_id"] == "thread-1"
    assert result["messages"][0]["thread_message_count"] == 2
    assert result["messages"][0]["subject"] == "New subject"
    threads_resource.get.assert_called_once_with(
        userId="me",
        id="thread-1",
        format="metadata",
        metadataHeaders=["From", "To", "Subject", "Date"],
    )


@pytest.mark.asyncio
async def test_gmail_mailbox_preserves_gmail_thread_order():
    old_thread = {
        "id": "thread-old",
        "messages": [
            {
                "id": "old-msg",
                "threadId": "thread-old",
                "internalDate": "1000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Old Sender <old@example.com>"},
                        {"name": "Subject", "value": "Old subject"},
                        {"name": "Date", "value": "Wed, 1 Jul 2026 18:53:00 +0530"},
                    ]
                },
                "snippet": "Old snippet",
                "labelIds": ["INBOX"],
            }
        ],
    }
    new_thread = {
        "id": "thread-new",
        "messages": [
            {
                "id": "new-msg",
                "threadId": "thread-new",
                "internalDate": "2000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "New Sender <new@example.com>"},
                        {"name": "Subject", "value": "New subject"},
                        {"name": "Date", "value": "Thu, 2 Jul 2026 14:54:00 +0530"},
                    ]
                },
                "snippet": "New snippet",
                "labelIds": ["INBOX"],
            }
        ],
    }
    threads_by_id = {
        "thread-old": old_thread,
        "thread-new": new_thread,
    }

    list_call = MagicMock(
        execute=MagicMock(
            return_value={
                "threads": [{"id": "thread-old"}, {"id": "thread-new"}],
                "resultSizeEstimate": 2,
            }
        )
    )

    def get_thread(**kwargs):
        return MagicMock(execute=MagicMock(return_value=threads_by_id[kwargs["id"]]))

    threads_resource = MagicMock()
    threads_resource.list.return_value = list_call
    threads_resource.get.side_effect = get_thread
    users_resource = MagicMock()
    users_resource.threads.return_value = threads_resource
    gmail_service = MagicMock()
    gmail_service.users.return_value = users_resource
    gmail_service.new_batch_http_request.side_effect = RuntimeError("batch unavailable")

    with patch(
        "app.service.get_messages.get_gmail_service",
        new_callable=AsyncMock,
        return_value=gmail_service,
    ), patch(
        "app.core.database.list_message_analysis_states",
        return_value={},
    ):
        from app.service.get_messages import list_gmail_mailbox_messages

        result = await list_gmail_mailbox_messages(
            email="user@example.com",
            mailbox="inbox",
            limit=25,
        )

    assert [message["message_id"] for message in result["messages"]] == ["old-msg", "new-msg"]
    assert [message["thread_id"] for message in result["messages"]] == ["thread-old", "thread-new"]
    assert [message["thread_message_count"] for message in result["messages"]] == [1, 1]


def test_gmail_message_endpoint_fetches_full_sanitized_message():
    message = {
        "id": "msg-1",
        "thread_id": "thread-1",
        "body": "<external_source>Hello</external_source>",
        "thread_messages": [{"id": "msg-0", "body": "<external_source>Earlier</external_source>"}],
    }

    with patch(
        "app.tool.tools.read_gmail_message",
        new_callable=AsyncMock,
        return_value=message,
    ) as read_message:
        response = client.get("/gmail/message?email=user@example.com&message_id=msg-1")

    assert response.status_code == 200
    assert response.json() == {
        "email": "user@example.com",
        "message_id": "msg-1",
        "message": message,
    }
    read_message.assert_called_once_with(
        email="user@example.com",
        message_id="msg-1",
        thread_id=None,
        mark_read=False,
    )


def test_gmail_message_endpoint_can_mark_message_read():
    message = {
        "id": "msg-1",
        "thread_id": "thread-1",
        "body": "<external_source>Hello</external_source>",
    }

    with patch(
        "app.tool.tools.read_gmail_message",
        new_callable=AsyncMock,
        return_value=message,
    ) as read_message:
        response = client.get("/gmail/message?email=user@example.com&message_id=msg-1&mark_read=true")

    assert response.status_code == 200
    read_message.assert_called_once_with(
        email="user@example.com",
        message_id="msg-1",
        thread_id=None,
        mark_read=True,
    )


def test_gmail_message_endpoint_forwards_thread_id():
    message = {
        "id": "msg-1",
        "thread_id": "thread-1",
        "body": "<external_source>Hello</external_source>",
    }

    with patch(
        "app.tool.tools.read_gmail_message",
        new_callable=AsyncMock,
        return_value=message,
    ) as read_message:
        response = client.get(
            "/gmail/message?email=user@example.com&message_id=msg-1&thread_id=thread-1"
        )

    assert response.status_code == 200
    read_message.assert_called_once_with(
        email="user@example.com",
        message_id="msg-1",
        thread_id="thread-1",
        mark_read=False,
    )


def test_pipeline_message_ids_endpoint_queues_pipeline():
    task = SimpleNamespace(id="pipeline-task-123")

    with patch(
        "app.tasks.run_pipeline_for_message_ids_task.delay",
        MagicMock(return_value=task),
    ) as delay, patch(
        "app.core.database.mark_messages_analysis_queued",
        MagicMock(return_value=["msg-1"]),
    ) as mark_queued:
        response = client.post(
            "/pipeline/messages",
            json={"email": "user@example.com", "message_ids": ["msg-1"]},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "email": "user@example.com",
        "message_ids": ["msg-1"],
        "queued_message_ids": ["msg-1"],
        "task_id": "pipeline-task-123",
    }
    delay.assert_called_once_with("user@example.com", ["msg-1"])
    mark_queued.assert_called_once_with("user@example.com", ["msg-1"])


def test_pipeline_message_ids_endpoint_skips_duplicate_analysis():
    with patch(
        "app.tasks.run_pipeline_for_message_ids_task.delay",
        MagicMock(),
    ) as delay, patch(
        "app.core.database.mark_messages_analysis_queued",
        MagicMock(return_value=[]),
    ) as mark_queued:
        response = client.post(
            "/pipeline/messages",
            json={"email": "user@example.com", "message_ids": ["msg-1"]},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "skipped",
        "email": "user@example.com",
        "message_ids": ["msg-1"],
        "queued_message_ids": [],
        "task_id": None,
    }
    delay.assert_not_called()
    mark_queued.assert_called_once_with("user@example.com", ["msg-1"])


def test_reply_message_endpoint_generates_reply_from_stored_context():
    result = {
        "processing_status": "reply_generated",
        "reply_status": "generated",
        "reply": {"suggested_reply": "Thanks, I will review this."},
    }

    with patch(
        "app.agent.pipeline.run_reply_pipeline_for_message",
        new_callable=AsyncMock,
        return_value=result,
    ) as draft_reply:
        response = client.post(
            "/reply/message",
            json={
                "email": "user@example.com",
                "message_id": "msg-1",
                "intent": "Say I will review it today.",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "reply_generated",
        "email": "user@example.com",
        "message_id": "msg-1",
        "result": result,
    }
    draft_reply.assert_called_once_with(
        "user@example.com",
        "msg-1",
        user_intent="Say I will review it today.",
    )


def test_summary_message_endpoint_summarizes_on_demand():
    result = {
        "processing_status": "summarized",
        "summary": {"summary": "The sender asks for a project review."},
    }

    with patch(
        "app.agent.pipeline.run_summary_pipeline_for_message",
        new_callable=AsyncMock,
        return_value=result,
    ) as summarize:
        response = client.post(
            "/summary/message",
            json={"email": "user@example.com", "message_id": "msg-1"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "summarized",
        "email": "user@example.com",
        "message_id": "msg-1",
        "result": result,
    }
    summarize.assert_called_once_with("user@example.com", "msg-1")


def test_send_reply_endpoint_sends_user_approved_reply():
    sent = {"id": "sent-123", "threadId": "thread-123"}

    with patch(
        "app.tool.tools.send_gmail_reply",
        new_callable=AsyncMock,
        return_value=sent,
    ) as send_reply:
        response = client.post(
            "/reply/send",
            json={
                "email": "user@example.com",
                "message_id": "msg-1",
                "reply_body": "Thanks, I will review this today.",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "reply_sent",
        "email": "user@example.com",
        "message_id": "msg-1",
        "gmail_result": sent,
    }
    send_reply.assert_called_once_with(
        "user@example.com",
        "msg-1",
        "Thanks, I will review this today.",
        "",
        [],
    )

def test_send_writer_endpoint_sends_user_approved_compose_draft():
    sent = {"id": "sent-456"}

    with patch(
        "app.tool.tools.send_gmail_message",
        new_callable=AsyncMock,
        return_value=sent,
    ) as send_message:
        response = client.post(
            "/writer/send",
            json={
                "email": "user@example.com",
                "to": "recipient@example.com",
                "subject": "Medicine delivery",
                "body": "Please send an update on my medicines.",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "writer_sent",
        "email": "user@example.com",
        "gmail_result": sent,
    }
    send_message.assert_called_once_with(
        "user@example.com",
        "recipient@example.com",
        "Medicine delivery",
        "Please send an update on my medicines.",
        "",
        [],
        cc="",
        bcc="",
    )


def test_send_writer_endpoint_passes_cc_and_bcc():
    sent = {"id": "sent-789"}

    with patch(
        "app.tool.tools.send_gmail_message",
        new_callable=AsyncMock,
        return_value=sent,
    ) as send_message:
        response = client.post(
            "/writer/send",
            json={
                "email": "user@example.com",
                "to": "recipient@example.com",
                "cc": "copy@example.com",
                "bcc": "hidden@example.com",
                "subject": "Medicine delivery",
                "body": "Please send an update on my medicines.",
            },
        )

    assert response.status_code == 200
    send_message.assert_called_once_with(
        "user@example.com",
        "recipient@example.com",
        "Medicine delivery",
        "Please send an update on my medicines.",
        "",
        [],
        cc="copy@example.com",
        bcc="hidden@example.com",
    )


def test_gmail_pubsub_webhook_queues_notification_for_analysis():
    payload = {
        "message": {
            "data": base64.b64encode(
                json.dumps(
                    {"emailAddress": "user@example.com", "historyId": "789"}
                ).encode()
            ).decode()
        }
    }

    task = SimpleNamespace(id="task-123")

    with patch("app.webhook.verify_pubsub_push_token", return_value={}) as verify, patch(
        "app.tasks.process_gmail_notification_task.delay",
        MagicMock(return_value=task),
    ) as delay:
        response = client.post(
            "/webhooks/gmail/pubsub",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "email": "user@example.com",
        "history_id": "789",
        "task_id": "task-123",
    }
    verify.assert_called_once_with("Bearer token")
    delay.assert_called_once_with(
        {"emailAddress": "user@example.com", "historyId": "789"}
    )


def test_calendar_event_response_uses_stored_organizer_only():
    sent = {"id": "sent-cal-1"}

    with patch(
        "app.core.database.calendar_event_response_context",
        MagicMock(
            return_value={
                "title": "Team sync",
                "organizer_email": "organizer@example.com",
            }
        ),
    ), patch(
        "app.core.database.update_calendar_event_response_status", MagicMock()
    ) as update_status, patch(
        "app.tool.tools.send_gmail_message",
        new_callable=AsyncMock,
        return_value=sent,
    ) as send_message:
        response = client.post(
            "/calendar/events/respond",
            json={
                "message_id": "msg-1",
                "response": "accepted",
                "organizer": "attacker@example.com",
                "title": "Unrelated message",
            },
        )

    assert response.status_code == 200
    assert response.json()["gmail_result"] == sent
    send_message.assert_called_once_with(
        "user@example.com",
        "organizer@example.com",
        "Accepted: Team sync",
        "Accepted: Team sync",
    )
    update_status.assert_called_once_with("user@example.com", "msg-1", "accepted")


def test_calendar_event_response_rejects_message_without_stored_event():
    with patch(
        "app.core.database.calendar_event_response_context",
        MagicMock(side_effect=ValueError("No stored calendar event found for msg-9")),
    ), patch(
        "app.tool.tools.send_gmail_message", new_callable=AsyncMock
    ) as send_message:
        response = client.post(
            "/calendar/events/respond",
            json={
                "message_id": "msg-9",
                "response": "accepted",
                "organizer": "attacker@example.com",
            },
        )

    assert response.status_code == 400
    assert "No stored calendar event" in response.json()["detail"]
    send_message.assert_not_called()


def test_calendar_event_remove_clears_stored_event():
    with patch(
        "app.core.database.remove_calendar_event", MagicMock(return_value=None)
    ) as remove_event:
        response = client.post(
            "/calendar/events/remove",
            json={"message_id": "msg-1"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "calendar_event_removed",
        "email": "user@example.com",
        "message_id": "msg-1",
    }
    remove_event.assert_called_once_with("user@example.com", "msg-1")


def test_calendar_event_remove_rejects_message_without_stored_event():
    with patch(
        "app.core.database.remove_calendar_event",
        MagicMock(side_effect=ValueError("No stored calendar event found for msg-9")),
    ):
        response = client.post(
            "/calendar/events/remove",
            json={"message_id": "msg-9"},
        )

    assert response.status_code == 400
    assert "No stored calendar event" in response.json()["detail"]
