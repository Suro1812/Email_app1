"""Tests for Gmail Pub/Sub push helpers."""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.service import gmail_push


def _push_payload(data):
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    return {"message": {"data": encoded}}


class TestDecodePubSubPush:
    def test_decodes_gmail_notification(self):
        result = gmail_push.decode_pubsub_push(
            _push_payload({"emailAddress": "user@example.com", "historyId": "123"})
        )

        assert result == {"emailAddress": "user@example.com", "historyId": "123"}

    def test_rejects_missing_message(self):
        with pytest.raises(ValueError, match="message object"):
            gmail_push.decode_pubsub_push({})

    def test_rejects_missing_required_gmail_fields(self):
        with pytest.raises(ValueError, match="emailAddress and historyId"):
            gmail_push.decode_pubsub_push(_push_payload({"emailAddress": "user@example.com"}))


class TestVerifyPubSubPushToken:
    def test_allows_disabled_verification(self, monkeypatch):
        monkeypatch.setenv("GMAIL_PUBSUB_VERIFY_TOKEN", "false")

        assert gmail_push.verify_pubsub_push_token(None) == {}

    def test_rejects_missing_authorization_header(self, monkeypatch):
        monkeypatch.delenv("GMAIL_PUBSUB_VERIFY_TOKEN", raising=False)

        with pytest.raises(ValueError, match="Authorization"):
            gmail_push.verify_pubsub_push_token(None)

    def test_rejects_non_bearer_authorization_header(self, monkeypatch):
        monkeypatch.delenv("GMAIL_PUBSUB_VERIFY_TOKEN", raising=False)

        with pytest.raises(ValueError, match="Bearer"):
            gmail_push.verify_pubsub_push_token("Basic abc")

    def test_verifies_google_token_with_expected_audience(self, monkeypatch):
        monkeypatch.setenv("GMAIL_PUBSUB_AUDIENCE", "https://example.com/webhooks/gmail/pubsub")
        monkeypatch.setenv(
            "GMAIL_PUBSUB_SERVICE_ACCOUNT",
            "pubsub-push@example.iam.gserviceaccount.com",
        )
        claims = {
            "iss": "https://accounts.google.com",
            "aud": "https://example.com/webhooks/gmail/pubsub",
            "email": "pubsub-push@example.iam.gserviceaccount.com",
            "email_verified": True,
        }

        with patch.object(gmail_push, "_verify_google_id_token", return_value=claims) as verify:
            result = gmail_push.verify_pubsub_push_token("Bearer token-123")

        assert result == claims
        verify.assert_called_once_with("token-123", "https://example.com/webhooks/gmail/pubsub")

    def test_rejects_wrong_service_account(self, monkeypatch):
        monkeypatch.setenv("GMAIL_PUBSUB_AUDIENCE", "https://example.com/webhooks/gmail/pubsub")
        monkeypatch.setenv(
            "GMAIL_PUBSUB_SERVICE_ACCOUNT",
            "allowed@example.iam.gserviceaccount.com",
        )
        claims = {
            "iss": "accounts.google.com",
            "email": "other@example.iam.gserviceaccount.com",
            "email_verified": True,
        }

        with patch.object(gmail_push, "_verify_google_id_token", return_value=claims):
            with pytest.raises(ValueError, match="service account"):
                gmail_push.verify_pubsub_push_token("Bearer token-123")

    def test_rejects_missing_audience_config(self, monkeypatch):
        monkeypatch.delenv("GMAIL_PUBSUB_AUDIENCE", raising=False)
        monkeypatch.delenv("PUBSUB_AUDIENCE", raising=False)

        with pytest.raises(RuntimeError, match="GMAIL_PUBSUB_AUDIENCE"):
            gmail_push.verify_pubsub_push_token("Bearer token-123")


class TestStartGmailWatch:
    @pytest.mark.asyncio
    async def test_starts_watch_for_inbox_topic(self):
        service = MagicMock()
        request = MagicMock()
        request.execute.return_value = {
            "historyId": "456",
            "expiration": "1710000000000",
        }
        service.users().watch.return_value = request

        with patch.object(gmail_push, "get_gmail_service", new_callable=AsyncMock, return_value=service), \
             patch.object(gmail_push, "save_gmail_watch_state") as save_state:
            result = await gmail_push.start_gmail_watch(
                "user@example.com",
                topic_name="projects/proj/topics/gmail",
            )

        assert result["historyId"] == "456"
        service.users().watch.assert_called_once_with(
            userId="me",
            body={
                "topicName": "projects/proj/topics/gmail",
                "labelIds": ["INBOX"],
            },
        )
        save_state.assert_called_once_with(
            email="user@example.com",
            history_id="456",
            expiration="1710000000000",
        )


class TestListChangedMessageIds:
    @pytest.mark.asyncio
    async def test_lists_unique_added_inbox_message_ids(self):
        service = MagicMock()
        request = MagicMock()
        request.execute.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "msg-1"}},
                        {"message": {"id": "msg-1"}},
                        {"message": {"id": "msg-2"}},
                    ]
                }
            ]
        }
        service.users().history().list.return_value = request

        with patch.object(gmail_push, "get_gmail_service", new_callable=AsyncMock, return_value=service):
            result = await gmail_push.list_changed_message_ids("user@example.com", "123")

        assert sorted(result) == ["msg-1", "msg-2"]
        service.users().history().list.assert_called_once_with(
            userId="me",
            startHistoryId="123",
            historyTypes=["messageAdded"],
            labelId="INBOX",
            pageToken=None,
        )


class TestProcessGmailNotification:
    @pytest.mark.asyncio
    async def test_fetches_changed_messages_processes_them_and_updates_history_id(self):
        notification = {"emailAddress": "user@example.com", "historyId": "789"}
        analysis = {"saved_message_count": 2}

        with patch.object(gmail_push, "get_last_gmail_history_id", return_value="456"), \
             patch.object(gmail_push, "list_changed_message_ids", new_callable=AsyncMock, return_value=["msg-1"]), \
             patch("app.agent.pipeline.run_pipeline_for_message_ids", new_callable=AsyncMock, return_value=analysis) as run_pipeline, \
             patch.object(gmail_push, "save_gmail_watch_state") as save_state:
            result = await gmail_push.process_gmail_notification(notification)

        assert result["email"] == "user@example.com"
        assert result["history_id"] == "789"
        assert result["previous_history_id"] == "456"
        assert result["changed_message_ids"] == ["msg-1"]
        assert result["analysis"] == analysis
        run_pipeline.assert_called_once_with("user@example.com", ["msg-1"])
        save_state.assert_called_once_with(email="user@example.com", history_id="789")

    @pytest.mark.asyncio
    async def test_establishes_baseline_when_user_has_no_active_watch(self):
        notification = {"emailAddress": "user@example.com", "historyId": "789"}

        with patch.object(gmail_push, "get_last_gmail_history_id", side_effect=ValueError("No active Gmail watch")), \
             patch("app.agent.pipeline.run_pipeline_for_message_ids", new_callable=AsyncMock) as run_pipeline, \
             patch.object(gmail_push, "save_gmail_watch_state") as save_state:
            result = await gmail_push.process_gmail_notification(notification)

        run_pipeline.assert_not_called()
        save_state.assert_called_once_with(email="user@example.com", history_id="789")
        assert result == {
            "email": "user@example.com",
            "history_id": "789",
            "previous_history_id": None,
            "changed_message_ids": [],
            "analysis": {
                "status": "baseline_established",
                "processed_message_count": 0,
                "reason": "No active Gmail watch",
            },
        }
