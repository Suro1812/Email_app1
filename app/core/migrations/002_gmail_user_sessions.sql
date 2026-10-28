CREATE TABLE IF NOT EXISTS gmail_user_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES gmail_users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_gmail_user_sessions_session_id
    ON gmail_user_sessions(session_id);

CREATE INDEX IF NOT EXISTS ix_gmail_user_sessions_user_id
    ON gmail_user_sessions(user_id);
