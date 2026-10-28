ALTER TABLE email_message_reminders
    ADD COLUMN IF NOT EXISTS calendar_event_source VARCHAR(50),
    ADD COLUMN IF NOT EXISTS calendar_event_uid VARCHAR(255),
    ADD COLUMN IF NOT EXISTS calendar_event_organizer TEXT,
    ADD COLUMN IF NOT EXISTS calendar_event_status VARCHAR(50);
