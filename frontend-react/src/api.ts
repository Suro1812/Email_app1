import type { MailboxResponse, MessageDetailResponse } from "./types";

/**
 * app.js makes these same two calls, inline, at each call site — building
 * the query string by hand and reading `response.json()` into an untyped
 * variable (see frontend/app.js's loadMessages()/openMessage()-style
 * functions). The difference here isn't the fetch itself, it's that the
 * return type is declared once and every caller gets it checked, rather
 * than every caller independently trusting the shape is what it expects.
 *
 * `credentials: "include"` is required: this app's auth is a session cookie
 * (app/webhook.py's require_session / gmail_session_id), not a bearer
 * token, same as the vanilla frontend relies on implicitly via same-origin
 * requests.
 */

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(
      `${response.status} ${response.statusText}${detail?.detail ? `: ${detail.detail}` : ""}`
    );
  }
  return response.json() as Promise<T>;
}

export function fetchMailbox(params: {
  mailbox?: string;
  category?: string;
  limit?: number;
}): Promise<MailboxResponse> {
  const query = new URLSearchParams({
    mailbox: params.mailbox ?? "inbox",
    category: params.category ?? "primary",
    limit: String(params.limit ?? 25),
  });
  return requestJson<MailboxResponse>(`/gmail/messages?${query}`);
}

export function fetchMessage(messageId: string, threadId?: string): Promise<MessageDetailResponse> {
  const query = new URLSearchParams({ message_id: messageId });
  if (threadId) query.set("thread_id", threadId);
  return requestJson<MessageDetailResponse>(`/gmail/message?${query}`);
}
