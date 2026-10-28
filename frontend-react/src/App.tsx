import { useState } from "react";
import { useMessages } from "./hooks/useMessages";
import { MailboxList } from "./components/MailboxList";
import { MessageReader } from "./components/MessageReader";
import type { MailboxMessage } from "./types";
import "./App.css";

/**
 * The root component: owns "which message is selected" and hands it down
 * to both children. This is "lifting state up" — a core React pattern with
 * no real vanilla-JS counterpart, because app.js doesn't need one: it just
 * has one giant shared mutable scope (module-level `state` object /
 * variables), and any function anywhere can read or write it directly.
 * That's simpler right up until two different pieces of UI need to agree on
 * what changed and re-render in response, at which point "just a shared
 * variable" stops being enough and you're back to writing the update-the-
 * DOM-by-hand code this file doesn't have to.
 */
export default function App() {
  const [mailbox] = useState("inbox");
  const [category] = useState("primary");
  const [selected, setSelected] = useState<MailboxMessage | null>(null);

  const { messages, loading, error } = useMessages(mailbox, category);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Email Reminders — React reference</h1>
        <p className="app-header-note">
          Standalone demo. Talks to the same FastAPI backend as frontend/app.js via Vite's
          dev proxy (see vite.config.ts) — not mounted or deployed anywhere.
        </p>
      </header>

      <main className="app-main">
        <section className="mailbox-pane">
          {loading && <p className="empty-state">Loading mailbox…</p>}
          {error && <p className="error-state">Couldn't load messages: {error}</p>}
          {!loading && !error && (
            <MailboxList
              messages={messages}
              selectedId={selected?.message_id ?? null}
              onSelect={setSelected}
            />
          )}
        </section>

        <section className="reader-pane">
          <MessageReader
            messageId={selected?.message_id ?? null}
            threadId={selected?.thread_id ?? null}
          />
        </section>
      </main>
    </div>
  );
}
