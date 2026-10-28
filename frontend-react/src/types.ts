/**
 * Mirrors what the backend actually returns — traced from
 * app/service/get_messages.py (list_gmail_mailbox_messages) and
 * app/tool/tools.py (read_gmail_message), not guessed. Compare this file to
 * how the vanilla frontend (frontend/app.js) consumes the same endpoints:
 * there, a response is just an untyped object read with optional-chaining
 * and hope; here, the shape is written down once and the compiler checks
 * every place that uses it.
 */

/** One row in a mailbox list — GET /gmail/messages, each entry of `messages`. */
export interface MailboxMessage {
  message_id: string;
  thread_id: string;
  thread_message_count: number;
  subject: string;
  from: string;
  to: string;
  date: string;
  internal_date: string;
  snippet: string;
  summary: string;
  label_ids: string[];
  processing_status: string;
  skip_reason: string | null;
  detected_intent: string | null;
  calendar_event: Record<string, unknown> | null;
  analysis_updated_at: string | null;
}

/** GET /gmail/messages full response. */
export interface MailboxResponse {
  email: string;
  mailbox: string;
  title: string;
  category: string;
  category_title: string;
  unread_only: boolean;
  result_size_estimate: number;
  messages: MailboxMessage[];
  next_page_token: string | null;
}

/**
 * The fully sanitized message body — the part app/agent/hooks.py's
 * post_tool_process_gmail_message() produces. `sanitized` and
 * `prompt_injection_detected` only exist because of that pipeline; showing
 * them here is the point of this reference screen, not decoration.
 */
export interface GmailMessageDetail {
  id: string;
  thread_id: string;
  from: string;
  to: string;
  cc: string;
  bcc: string;
  subject: string;
  date: string;
  snippet: string;
  body: string;
  display_html?: string;
  has_display_html: boolean;
  sanitized: boolean;
  prompt_injection_detected: boolean;
  calendar_event?: Record<string, unknown>;
}

/** GET /gmail/message full response. */
export interface MessageDetailResponse {
  email: string;
  message_id: string;
  message: GmailMessageDetail;
}
