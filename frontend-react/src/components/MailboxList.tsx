import type { MailboxMessage } from "../types";

interface MailboxListProps {
  messages: MailboxMessage[];
  selectedId: string | null;
  onSelect: (message: MailboxMessage) => void;
}

/**
 * A "dumb" / presentational component: it owns no state of its own and no
 * fetch calls — it just renders whatever `messages` it's handed and reports
 * clicks upward via `onSelect`. app.js's equivalent (its message-list
 * rendering code) builds this same list by concatenating HTML strings or
 * calling document.createElement() in a loop, then wiring a click listener
 * onto each row by hand. Here the "template" is just JSX — HTML-shaped
 * syntax that is actually JavaScript, so `{message.subject}` is a real
 * expression, not a string being spliced in.
 */
export function MailboxList({ messages, selectedId, onSelect }: MailboxListProps) {
  if (messages.length === 0) {
    return <p className="empty-state">No messages in this view.</p>;
  }

  return (
    <ul className="mailbox-list">
      {messages.map((message) => (
        // `key` is required on anything produced by .map() — it's how React
        // tells rows apart across re-renders instead of re-rendering the
        // whole list from scratch every time. There is no vanilla-JS
        // equivalent of this requirement; the DOM has no built-in notion of
        // "this element IS the same logical row as last time."
        <li
          key={message.message_id}
          className={message.message_id === selectedId ? "mailbox-row selected" : "mailbox-row"}
          onClick={() => onSelect(message)}
        >
          <div className="mailbox-row-from">{message.from || "(unknown sender)"}</div>
          <div className="mailbox-row-subject">{message.subject || "(No subject)"}</div>
          <div className="mailbox-row-snippet">{message.snippet}</div>
          {message.processing_status && (
            <span className={`status-pill status-${message.processing_status}`}>
              {message.processing_status}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
