import { useEffect, useState } from "react";
import { fetchMailbox } from "../api";
import type { MailboxMessage } from "../types";

interface UseMessagesResult {
  messages: MailboxMessage[];
  loading: boolean;
  error: string | null;
}

/**
 * Compare this to how frontend/app.js does the same job (its
 * autoRefreshMessages()/loadMessages() functions, around app.js:4184): there,
 * "is this loading" and "did this fail" live in module-level variables
 * (state.messageError, a loading flag) that every render path has to
 * remember to check and clear by hand, and the DOM is mutated directly
 * (`element.textContent = ...`, toggling classes) wherever those variables
 * change.
 *
 * Here, loading/error/messages are ordinary local state. React re-renders
 * whatever reads them automatically when setMessages/setError/setLoading
 * run — there's no separate "now go update the DOM to match" step to
 * forget. That's the actual mechanical difference a rewrite buys you; it
 * isn't about fetch() itself, which is identical either way.
 */
export function useMessages(mailbox: string, category: string): UseMessagesResult {
  const [messages, setMessages] = useState<MailboxMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false; // guards against setting state after unmount/re-trigger

    setLoading(true);
    setError(null);

    fetchMailbox({ mailbox, category })
      .then((data) => {
        if (!cancelled) setMessages(data.messages);
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
  }, [mailbox, category]);

  return { messages, loading, error };
}
