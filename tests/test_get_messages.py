"""Tests for app/service/get_messages.py"""

import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.service.get_messages import (
    check_promotional_basic,
    extract_body,
    extract_ics_calendar_events,
    get_gmail_service,
    html_to_text,
    parse_ics_calendar_events,
)


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


class TestExtractBody:
    @pytest.mark.asyncio
    async def test_simple_body_data(self):
        payload = {"body": {"data": _b64("Hello, world!")}}
        assert await extract_body(payload) == "Hello, world!"

    @pytest.mark.asyncio
    async def test_empty_payload_returns_empty_string(self):
        assert await extract_body({}) == ""

    @pytest.mark.asyncio
    async def test_multipart_picks_text_plain(self):
        payload = {
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<b>HTML</b>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("Plain text")}},
            ]
        }
        assert await extract_body(payload) == "Plain text"


class TestIcsCalendarEvents:
    def test_parses_ics_vevent(self):
        raw_ics = b"""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:invite-1
SUMMARY:Design review
DTSTART:20990102T103000Z
DTEND:20990102T110000Z
LOCATION:Zoom
STATUS:CONFIRMED
ORGANIZER:mailto:organizer@example.com
END:VEVENT
END:VCALENDAR
"""

        event = parse_ics_calendar_events(raw_ics)[0]

        assert event["uid"] == "invite-1"
        assert event["title"] == "Design review"
        assert event["start_at"] == "2099-01-02T10:30:00"
        assert event["organizer"] == "mailto:organizer@example.com"
        assert event["status"] == "CONFIRMED"

    def test_extracts_ics_from_gmail_payload(self):
        raw_ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:payload-1
SUMMARY:Planning
DTSTART:20990103T090000Z
ORGANIZER:mailto:lead@example.com
END:VEVENT
END:VCALENDAR
"""
        payload = {
            "parts": [
                {
                    "mimeType": "text/calendar",
                    "filename": "invite.ics",
                    "body": {"data": _b64(raw_ics)},
                }
            ]
        }

        event = extract_ics_calendar_events(payload)[0]

        assert event["uid"] == "payload-1"
        assert event["title"] == "Planning"

    @pytest.mark.asyncio
    async def test_multipart_html_only_falls_through_to_nested(self):
        # html part is skipped; function recurses into sub-parts
        inner = {"mimeType": "text/plain", "body": {"data": _b64("inner plain")}}
        payload = {
            "parts": [
                {"mimeType": "multipart/alternative", "body": {}, "parts": [inner]}
            ]
        }
        assert await extract_body(payload) == "inner plain"

    @pytest.mark.asyncio
    async def test_part_without_body_data_returns_empty(self):
        payload = {"parts": [{"mimeType": "text/plain", "body": {}}]}
        assert await extract_body(payload) == ""

    @pytest.mark.asyncio
    async def test_decodes_utf8(self):
        text = "Héllo wörld"
        payload = {"body": {"data": _b64(text)}}
        assert await extract_body(payload) == text

    @pytest.mark.asyncio
    async def test_text_plain_is_preferred_over_later_parts(self):
        # First text/plain found should be returned
        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("first")}},
                {"mimeType": "text/plain", "body": {"data": _b64("second")}},
            ]
        }
        assert await extract_body(payload) == "first"

    @pytest.mark.asyncio
    async def test_html_body_preserves_block_spacing(self):
        payload = {
            "mimeType": "text/html",
            "body": {
                "data": _b64(
                    "<p>Hey Suro1812!</p>"
                    "<p>A sign in attempt requires verification.</p>"
                    "<div>Device: Chrome on macOS<br>Verification code: 851155</div>"
                    "<p>Thanks,<br>The GitHub Team</p>"
                )
            },
        }

        assert await extract_body(payload) == (
            "Hey Suro1812!\n"
            "A sign in attempt requires verification.\n"
            "Device: Chrome on macOS\n"
            "Verification code: 851155\n"
            "Thanks,\n"
            "The GitHub Team"
        )


class TestHtmlToText:
    def test_preserves_paragraph_and_break_tags(self):
        assert html_to_text("<p>First line</p><p>Second<br>Third</p>") == (
            "First line\nSecond\nThird"
        )


class TestCheckPromotionalBasic:
    def test_detects_present_message_list_unsubscribe_header(self):
        message = {
            "payload": {
                "headers": [{"name": "List-Unsubscribe", "value": "<mailto:unsubscribe@example.com>"}],
                "body": {"data": _b64("Please review this message today")},
            }
        }

        result = check_promotional_basic(message)

        assert result["has_list_unsubscribe_header"] is True
        assert result["skip_llm"] is True

    def test_html_part_does_not_skip_when_plain_text_has_enough_words(self):
        message = {
            "payload": {
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("Please review this message today")}},
                    {"mimeType": "text/html", "body": {"data": _b64("<p>Sale</p>")}},
                ]
            }
        }

        result = check_promotional_basic(message)

        assert result["has_html_code"] is True
        assert result["plain_text_word_count"] == 5
        assert result["skip_llm"] is False

    def test_allows_plain_present_message_with_enough_words(self):
        message = {
            "payload": {
                "body": {"data": _b64("Please review this message today")},
                "mimeType": "text/plain",
            }
        }

        result = check_promotional_basic(message)

        assert result["plain_text_word_count"] == 5
        assert result["skip_llm"] is False


class TestGetGmailService:
    @pytest.mark.asyncio
    async def test_fetches_credentials_and_builds_service(self):
        mock_creds = MagicMock()
        mock_service = MagicMock()

        with patch("app.service.get_messages.get_credentials_from_db", new_callable=AsyncMock, return_value=mock_creds), \
             patch("app.service.get_messages.build", return_value=mock_service):
            result = await get_gmail_service("user@example.com")

        assert result == mock_service

    @pytest.mark.asyncio
    async def test_passes_email_to_get_credentials(self):
        captured = []

        async def fake_get_creds(email):
            captured.append(email)
            return MagicMock()

        with patch("app.service.get_messages.get_credentials_from_db", side_effect=fake_get_creds), \
             patch("app.service.get_messages.build", return_value=MagicMock()):
            await get_gmail_service("target@example.com")

        assert captured[0] == "target@example.com"

    @pytest.mark.asyncio
    async def test_builds_gmail_v1_service(self):
        build_calls = []

        def fake_build(service_name, version, **kwargs):
            build_calls.append((service_name, version))
            return MagicMock()

        with patch("app.service.get_messages.get_credentials_from_db", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.service.get_messages.build", side_effect=fake_build):
            await get_gmail_service("user@example.com")

        assert build_calls[0] == ("gmail", "v1")


class TestSearchMailbox:
    @pytest.mark.asyncio
    async def test_search_mailbox_forwards_free_text_query(self):
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
                mailbox="search",
                limit=25,
                search_query="  invoice   from:billing@example.com  ",
            )

        assert result["mailbox"] == "search"
        assert result["title"] == "Search"
        list_method.assert_called_once_with(
            userId="me",
            maxResults=25,
            fields="threads(id),nextPageToken,resultSizeEstimate",
            q="invoice from:billing@example.com",
        )

    @pytest.mark.asyncio
    async def test_search_mailbox_requires_non_empty_query(self):
        from app.service.get_messages import list_gmail_mailbox_messages

        with pytest.raises(ValueError, match="Search needs a query"):
            await list_gmail_mailbox_messages(
                email="user@example.com",
                mailbox="search",
                search_query="   ",
            )
