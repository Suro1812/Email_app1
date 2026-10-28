import { useEffect, useState } from "react";
import { fetchMessage } from "../api";
import type { GmailMessageDetail } from "../types";

interface MessageReaderProps {
  messageId: string | null;
  threadId: string | null;
}

/**
 * Fetches and renders ONE message's full body — a second, independent data
 * fetch from MailboxList's, triggered whenever `messageId` changes (i.e.
 * whenever the user clicks a different row). This mirrors how app.js's
 * openMessage()-equivalent function re-fetches on each click; the
 * difference again is bookkeeping, not capability — this effect's cleanup
 * function (the `cancelled` flag) is what stops a slow, stale request from
 * clobbering the screen if the user clicks a second message before the
 * first one's fetch finishes. Getting that right by hand in app.js would
 * need the same kind of request-id tracking spelled out manually.
 */
export function MessageReader({ messageId, threadId }: MessageReaderProps) {
  const [detail, setDetail] = useState<GmailMessageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!messageId) {
      setDetail(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchMessage(messageId, threadId ?? undefined)
      .then((data) => {
        if (!cancelled) setDetail(data.message);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [messageId, threadId]);

  if (!messageId) {
    return <p className="empty-state">Select a message to read it.</p>;
  }
  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="error-state">Couldn't load this message: {error}</p>;
  if (!detail) return null;

  return (
    <article className="message-reader">
      <h2>{detail.subject || "(No subject)"}</h2>
      <dl className="message-headers">
        <dt>From</dt>
        <dd>{detail.from}</dd>
        <dt>To</dt>
        <dd>{detail.to}</dd>
        <dt>Date</dt>
        <dd>{detail.date}</dd>
      </dl>

      {/*
        app/agent/hooks.py's post_tool_process_gmail_message() has already
        run _decompose_dangerous_tags / _decompose_hidden_prompt_carriers on
        this body before it ever reached this component — that's WHY
        rendering it as raw HTML here is safe. dangerouslySetInnerHTML is
        the one place React steps out of its default behavior (everywhere
        else, {someVariable} is auto-escaped as plain text, which is why the
        name is a deliberate warning sign: it's telling you "you are now
        responsible for this being safe," not "this specific usage is
        unsafe." Swap in content that skipped that sanitization pipeline and
        this becomes exactly the prompt-injection/XSS vector that pipeline
        exists to prevent — same risk discussed earlier for the vanilla
        frontend's own innerHTML usage, just opt-in here instead of
        implicit.
      */}
      {detail.has_display_html && detail.display_html ? (
        <div
          className="message-body"
          dangerouslySetInnerHTML={{ __html: detail.display_html }}
        />
      ) : (
        <p className="message-body message-body-plain">{detail.body}</p>
      )}

      {detail.prompt_injection_detected && (
        <p className="warning-banner">
          ⚠ This message contained a prompt-injection pattern that was stripped before display.
        </p>
      )}
    </article>
  );
}
