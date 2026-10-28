"""Tests for app/core/database.py"""

import os
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.database import (
    Base,
    EmailMessageReminder,
    GmailUser,
    get_db,
    list_message_analysis_states,
    list_calendar_events,
    parse_message_datetime,
    save_analyzed_messages,
    save_analyzer_result,
    save_email_processing_result,
    save_summary_result,
)

DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestGmailUserModel:
    def test_create_and_retrieve_user(self, db_session):
        user = GmailUser(
            email="test_create@example.com",
            refresh_token="refresh123",
            access_token="access123",
        )
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(GmailUser).filter_by(email="test_create@example.com").first()
        assert fetched is not None
        assert fetched.refresh_token == "refresh123"
        assert fetched.access_token == "access123"

    def test_email_unique_constraint(self, db_session):
        db_session.add(GmailUser(email="dup_pg@example.com", refresh_token="r1", access_token="a1"))
        db_session.commit()
        db_session.add(GmailUser(email="dup_pg@example.com", refresh_token="r2", access_token="a2"))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_token_expiry_nullable(self, db_session):
        user = GmailUser(email="no_expiry_pg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(GmailUser).filter_by(email="no_expiry_pg@example.com").first()
        assert fetched.token_expiry is None

    def test_token_expiry_stored(self, db_session):
        expiry = datetime(2025, 1, 1, 12, 0, 0)
        user = GmailUser(email="expiry_pg@example.com", refresh_token="r", access_token="a", token_expiry=expiry)
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(GmailUser).filter_by(email="expiry_pg@example.com").first()
        assert fetched.token_expiry == expiry

    def test_created_at_auto_populated(self, db_session):
        user = GmailUser(email="ts_pg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(GmailUser).filter_by(email="ts_pg@example.com").first()
        assert fetched.created_at is not None

    def test_repr_contains_email(self):
        user = GmailUser(email="hello@example.com", refresh_token="r", access_token="a")
        assert "hello@example.com" in repr(user)

    def test_email_cannot_be_null(self, db_session):
        user = GmailUser(refresh_token="r", access_token="a")
        db_session.add(user)
        with pytest.raises(Exception):
            db_session.commit()


class TestEmailMessageReminderModel:
    def test_create_and_retrieve_email_reminder(self, db_session):
        user = GmailUser(
            email="reminder_user@example.com",
            refresh_token="refresh",
            access_token="access",
        )
        db_session.add(user)
        db_session.commit()

        reminder = EmailMessageReminder(
            user_id=user.id,
            message_id="msg-123",
            summarized_subject="Project update",
            summarized_body="The sender shared a project update.",
            reply_subject="Re: Project update",
            reply_body="Thanks for the update.",
            from_address="sender@example.com",
            to_address="reminder_user@example.com",
        )
        db_session.add(reminder)
        db_session.commit()

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-123").first()
        assert fetched is not None
        assert fetched.user_id == user.id
        assert fetched.summarized_subject == "Project update"
        assert fetched.summarized_body == "The sender shared a project update."
        assert fetched.reply_subject == "Re: Project update"
        assert fetched.reply_body == "Thanks for the update."

    def test_user_message_unique_constraint(self, db_session):
        user = GmailUser(email="unique_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        db_session.add(EmailMessageReminder(user_id=user.id, message_id="same-msg"))
        db_session.commit()
        db_session.add(EmailMessageReminder(user_id=user.id, message_id="same-msg"))

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_save_analyzed_messages_inserts_record(self, db_session):
        user = GmailUser(email="save_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        messages = [
            {
                "id": "msg-save-1",
                "subject": "<external_source>Very long project status</external_source>",
                "date": "Mon, 1 Jan 2024 13:45:00 +0000",
                "from": "sender@example.com",
                "to": "save_msg@example.com",
            }
        ]
        analysis = {
            "emails": [
                {
                    "summarized_subject": "Project status",
                    "summarized_body": "The sender shared the project status and expects acknowledgement.",
                    "reply_subject": "Re: Project status",
                    "reply_body": "Thanks for the status update.",
                }
            ]
        }

        saved = save_analyzed_messages("save_msg@example.com", messages, analysis)

        assert len(saved) == 1
        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-save-1").first()
        assert fetched.summarized_subject == "Project status"
        assert fetched.summarized_body == "The sender shared the project status and expects acknowledgement."
        assert fetched.message_date.isoformat() == "2024-01-01"
        assert fetched.message_time.isoformat() == "13:45:00"
        assert fetched.reply_subject == "Re: Project status"
        assert fetched.reply_body == "Thanks for the status update."

    def test_save_analyzed_messages_does_not_suppress_no_reply_sender_reply(self, db_session):
        user = GmailUser(email="no_reply_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        messages = [
            {
                "id": "msg-no-reply-1",
                "subject": "System alert",
                "date": "",
                "from": "Alerts <do-not-reply@example.com>",
                "to": "no_reply_msg@example.com",
            }
        ]
        analysis = {
            "emails": [
                {
                    "summarized_subject": "System alert",
                    "summarized_body": "The message contains an automated system alert.",
                    "reply_subject": "Re: System alert",
                    "reply_body": "Thanks for the alert.",
                }
            ]
        }

        save_analyzed_messages("no_reply_msg@example.com", messages, analysis)

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-no-reply-1").first()
        assert fetched.reply_subject == "Re: System alert"
        assert fetched.reply_body == "Thanks for the alert."

    def test_save_processing_result_persists_skip_reason(self, db_session):
        user = GmailUser(email="skip_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        save_email_processing_result(
            user_email="skip_msg@example.com",
            message={"id": "msg-skip-1", "subject": "Tiny", "date": "", "from": "", "to": ""},
            processing_status="skipped",
            skip_reason="short_non_thread_email_without_action_signal",
            reply_status="not_required",
        )

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-skip-1").first()
        assert fetched.processing_status == "skipped"
        assert fetched.skip_reason == "short_non_thread_email_without_action_signal"
        assert fetched.reply_status == "not_required"
        assert fetched.reply_needed is False

    def test_save_processing_result_marks_not_analyzed_as_pending(self, db_session):
        user = GmailUser(email="not_analyzed_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        save_email_processing_result(
            user_email="not_analyzed_msg@example.com",
            message={"id": "msg-not-analyzed-1", "subject": "Review", "date": "", "from": "", "to": ""},
            processing_status="not_analyzed",
            reply_status="pending",
        )

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-not-analyzed-1").first()
        assert fetched.processing_status == "not_analyzed"
        assert fetched.reply_status == "pending"
        assert fetched.reply_needed is None
        assert list_message_analysis_states(
            "not_analyzed_msg@example.com",
            ["msg-not-analyzed-1"],
        )["msg-not-analyzed-1"]["processing_status"] == "not_analyzed"

    def test_save_summary_result_persists_token_usage(self, db_session):
        user = GmailUser(email="summary_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        save_summary_result(
            user_email="summary_msg@example.com",
            message={"id": "msg-summary-1", "subject": "Request", "date": "", "from": "", "to": ""},
            summary_result={
                "summary": "The sender asks for approval.",
                "detected_intent": "approval",
                "action_items": ["Approve access"],
                "deadline": "Friday",
                "reply_needed": True,
                "reply_reason": "Approval requested.",
                "llm_summary_tokens_input": 101,
                "llm_summary_tokens_output": 33,
                "prompt_cache_hit": True,
            },
            skip_reason="requires_summary_agent",
        )

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-summary-1").first()
        assert fetched.processing_status == "summarized"
        assert fetched.detected_intent == "approval"
        assert fetched.action_items_json == '["Approve access"]'
        assert fetched.deadline == "Friday"
        assert fetched.reply_needed is True
        assert fetched.reply_status == "pending"
        assert fetched.llm_summary_tokens_input == 101
        assert fetched.llm_summary_tokens_output == 33
        assert fetched.prompt_cache_hit is True

    def test_save_analyzer_result_persists_calendar_event(self, db_session):
        user = GmailUser(email="analyzer_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        save_analyzer_result(
            user_email="analyzer_msg@example.com",
            message={"id": "msg-analyzer-1", "subject": "Confirm", "date": "", "from": "", "to": ""},
            analyzer_result={
                "category": "calendar_event",
                "title": "Interview",
                "calendar_event": {
                    "detected": True,
                    "title": "Interview",
                    "start_at": "2099-01-01T10:00:00",
                    "end_at": None,
                    "location": "Zoom",
                    "notification_minutes_before": 15,
                    "source": "ics",
                    "uid": "invite-1",
                    "organizer": "mailto:organizer@example.com",
                    "status": "CONFIRMED",
                },
            },
        )

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-analyzer-1").first()
        assert fetched.processing_status == "analyzed"
        assert fetched.calendar_event_detected is True
        assert fetched.calendar_event_title == "Interview"
        assert fetched.calendar_event_source == "ics"
        assert fetched.calendar_event_uid == "invite-1"
        assert fetched.calendar_event_organizer == "mailto:organizer@example.com"
        assert fetched.calendar_event_status == "CONFIRMED"
        assert fetched.reply_needed is None
        assert fetched.reply_status == "not_required"

    def test_list_calendar_events_deletes_events_older_than_six_months(self, db_session):
        user = GmailUser(email="old_events@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()
        old_start = datetime.utcnow() - timedelta(days=190)
        recent_start = datetime.utcnow() - timedelta(days=30)
        db_session.add(
            EmailMessageReminder(
                user_id=user.id,
                message_id="old-event",
                calendar_event_detected=True,
                calendar_event_title="Old event",
                calendar_event_start_at=old_start,
            )
        )
        db_session.add(
            EmailMessageReminder(
                user_id=user.id,
                message_id="recent-event",
                calendar_event_detected=True,
                calendar_event_title="Recent event",
                calendar_event_start_at=recent_start,
            )
        )
        db_session.commit()

        events = list_calendar_events("old_events@example.com")

        assert [event["message_id"] for event in events] == ["recent-event"]
        assert db_session.query(EmailMessageReminder).filter_by(message_id="old-event").first() is None

    def test_save_analyzer_result_persists_reminder_deadline(self, db_session):
        user = GmailUser(email="analyzer_reminder@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        save_analyzer_result(
            user_email="analyzer_reminder@example.com",
            message={"id": "msg-reminder-1", "subject": "Invoice", "date": "", "from": "", "to": ""},
            analyzer_result={
                "category": "reminder",
                "title": "Pay invoice",
                "description": "Pay the invoice by tomorrow.",
                "start_date": "2099-01-02",
                "start_time": None,
                "calendar_event": {
                    "detected": True,
                    "title": "Pay invoice",
                    "start_at": "2099-01-02T00:00:00",
                    "end_at": None,
                    "location": "",
                    "notification_minutes_before": 15,
                    "event_kind": "payment",
                },
            },
        )

        fetched = db_session.query(EmailMessageReminder).filter_by(message_id="msg-reminder-1").first()
        assert fetched.processing_status == "analyzed"
        assert fetched.detected_intent == "reminder"
        assert fetched.action_items_json == '["Pay invoice"]'
        assert fetched.deadline == "2099-01-02"
        assert fetched.calendar_event_detected is True
        assert fetched.calendar_event_title == "Pay invoice"
        assert fetched.detected_intent == "payment"

    def test_save_analyzed_messages_updates_existing_record(self, db_session):
        user = GmailUser(email="update_msg@example.com", refresh_token="r", access_token="a")
        db_session.add(user)
        db_session.commit()

        messages = [{"id": "msg-update-1", "subject": "Original", "date": "", "from": "", "to": ""}]
        save_analyzed_messages("update_msg@example.com", messages, {"emails": [{}]})

        messages[0]["subject"] = "Updated"
        save_analyzed_messages("update_msg@example.com", messages, {"emails": [{}]})

        records = db_session.query(EmailMessageReminder).filter_by(message_id="msg-update-1").all()
        assert len(records) == 1
        assert records[0].summarized_subject == "Updated"

    def test_save_analyzed_messages_requires_existing_user(self):
        with pytest.raises(ValueError, match="No Gmail user found"):
            save_analyzed_messages("missing@example.com", [], {"emails": []})


class TestEmailMessageReminderHelpers:
    def test_parse_message_datetime_handles_gmail_header(self):
        parsed_date, parsed_time = parse_message_datetime("Mon, 1 Jan 2024 13:45:00 +0000")
        assert parsed_date.isoformat() == "2024-01-01"
        assert parsed_time.isoformat() == "13:45:00"

    def test_parse_message_datetime_handles_invalid_value(self):
        parsed_date, parsed_time = parse_message_datetime("not a date")
        assert parsed_date is None
        assert parsed_time is None


class TestInitDb:
    def test_creates_gmail_users_table(self, engine):
        inspector = inspect(engine)
        assert "gmail_users" in inspector.get_table_names()

    def test_creates_email_message_reminders_table(self, engine):
        inspector = inspect(engine)
        assert "email_message_reminders" in inspector.get_table_names()

    def test_gmail_users_has_expected_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("gmail_users")}
        assert {"id", "email", "refresh_token", "access_token", "token_expiry"}.issubset(cols)

    def test_email_message_reminders_has_expected_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("email_message_reminders")}
        assert {
            "id",
            "message_id",
            "summarized_subject",
            "summarized_body",
            "message_date",
            "message_time",
            "reply_subject",
            "reply_body",
            "user_id",
            "from_address",
            "to_address",
            "processing_status",
            "skip_reason",
            "detected_intent",
            "action_items_json",
            "deadline",
            "reply_needed",
            "reply_status",
            "suggested_reply",
            "llm_summary_tokens_input",
            "llm_summary_tokens_output",
            "llm_reply_tokens_input",
            "llm_reply_tokens_output",
            "prompt_cache_hit",
            "calendar_event_source",
            "calendar_event_uid",
            "calendar_event_organizer",
            "calendar_event_status",
        }.issubset(cols)


class TestGetDb:
    def test_yields_session(self):
        gen = get_db()
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass

    def test_session_closed_after_generator_exhausted(self):
        from unittest.mock import MagicMock, patch
        mock_session = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            try:
                next(gen)
            except StopIteration:
                pass
        mock_session.close.assert_called_once()
