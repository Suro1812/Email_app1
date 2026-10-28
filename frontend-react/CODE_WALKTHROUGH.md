# Code walkthrough

Line-by-line explanation of every file in this folder, in the order a new
reader should go through them: config first (how the project starts), then
the entry point, then the data layer (types → fetch → hook), then the
components, then the root that ties them together.

For the "why React does it this way" framing, each section also says what
the equivalent looks like in `frontend/app.js` (the real app's vanilla JS),
since that's the comparison this whole folder exists to make.

---

## `package.json`

```json
{
  "name": "email-reminders-frontend-react",
  "private": true,
```
`private: true` stops `npm publish` from ever accidentally publishing this to the public npm registry — standard for any app that isn't itself a library.

```json
  "type": "module",
```
Tells Node (not the browser — this only affects tooling like Vite's own config loading) to treat `.js`/`.ts` files here as ES modules (`import`/`export`) rather than CommonJS (`require`). Vite 5 expects this.

```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
```
Three commands, each `npm run <name>`:
- `dev` — starts Vite's dev server (what you use while actively working on the code; includes hot-reload)
- `build` — type-checks everything (`tsc -b`) **then** bundles for production (`vite build`); if `tsc` finds a type error, `&&` means `vite build` never runs
- `preview` — serves the already-built `dist/` folder locally, to sanity-check a production build before deploying it anywhere

```json
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
```
The only two packages the *built app* actually ships to the browser. `react` is the library itself (components, hooks, the reconciliation algorithm); `react-dom` is the adapter that knows how to turn React's output into actual DOM nodes — React itself is renderer-agnostic (there's a separate `react-native` for mobile that swaps this package out).

```json
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.11"
  }
}
```
Tools needed only while *building*, never shipped to the browser:
- `@types/react` / `@types/react-dom` — TypeScript type definitions for React itself (React is written in plain JS; these are community-maintained `.d.ts` files describing its shape)
- `@vitejs/plugin-react` — teaches Vite how to transform JSX syntax into real JavaScript function calls
- `typescript` — the compiler/type-checker
- `vite` — the dev server + bundler

---

## `tsconfig.json`

The TypeScript compiler's settings. Read as a flat list of switches, not sequential logic — order doesn't matter here.

```json
"target": "ES2020",
```
Compile down to JavaScript syntax that works in any ES2020-capable runtime. Doesn't matter much in practice since Vite re-transforms everything anyway, but it's what `tsc`'s own type-checking rules against.

```json
"lib": ["ES2020", "DOM", "DOM.Iterable"],
```
Which built-in type definitions to load — `DOM` is why `document.getElementById(...)` in `main.tsx` type-checks at all; without it TypeScript wouldn't know `document` exists.

```json
"module": "ESNext",
"moduleResolution": "bundler",
```
Use modern `import`/`export` syntax, and resolve imports the way a bundler (Vite) actually does, not the way Node.js would. This is what allows `import "./App.css"` in `App.tsx` — Node has no idea what to do with a `.css` import, but a bundler does.

```json
"noEmit": true,
```
`tsc` here only type-checks; it never writes `.js` files to disk. Vite does the actual compiling (via esbuild, much faster). This is why `npm run build` is `tsc -b && vite build` — two separate jobs, type-checking and bundling, not one tool doing both.

```json
"jsx": "react-jsx",
```
Lets you write `<div>` directly in `.tsx` files without manually importing `React` in every file just to use JSX (an older requirement from React 16 and earlier).

```json
"strict": true,
"noUnusedLocals": true,
"noUnusedParameters": true,
```
The settings actually doing work for you: `strict` turns on every meaningful type-safety check at once (no implicit `any`, null-checking, etc.); the other two flag a variable or parameter you declared but never used — real mistakes, not style nitpicks.

```json
"include": ["src"]
```
Only type-check files under `src/`. `vite.config.ts` at the project root is intentionally outside this — Vite loads its own config independently, before TypeScript project-checking even starts.

---

## `vite.config.ts`

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
```
`defineConfig` is just a helper that gives you editor autocomplete on the config object — purely a DX convenience, has no runtime effect.

```ts
export default defineConfig({
  plugins: [react()],
```
Registers the JSX-transforming plugin from `package.json`'s devDependencies. Without this line, `<div>` in a `.tsx` file would be a syntax error as far as the bundler is concerned.

```ts
  server: {
    port: 5173,
```
Fixes the dev server's port rather than letting Vite pick the next free one — so "go to localhost:5173" in the README stays true every time.

```ts
    proxy: {
      "/gmail": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/notifications": "http://127.0.0.1:8000",
    },
  },
});
```
This is the one line of config doing real architectural work. When the browser (talking to `localhost:5173`) requests `/gmail/messages`, Vite's dev server itself — not the browser — forwards that request to the real FastAPI backend at `127.0.0.1:8000`, and relays the response back. The browser never knows a second server was involved; from its point of view, every request went to `localhost:5173`, so there's no cross-origin request happening and no CORS headers need adding to `app/webhook.py`. This is the entire reason `app/webhook.py` needed zero changes for this folder to exist.

---

## `index.html`

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```
This is the *only* HTML in the whole app. Compare to `frontend/index.html`'s 32KB — that file contains the actual markup for every screen (mailbox, composer, calendar...) because the vanilla app's JS mutates pre-existing DOM nodes. Here, this one empty `<div>` is the entire static page; React builds everything inside it at runtime, starting from `main.tsx`.

---

## `src/vite-env.d.ts`

```ts
/// <reference types="vite/client" />
```
One line, and it's not code — it's a directive telling TypeScript "also load Vite's own ambient type definitions." Without it, TypeScript wouldn't know about Vite-specific globals (like `import.meta.env`, not currently used here, but this is the standard file Vite scaffolds for when you need it).

---

## `src/main.tsx` — the entry point

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
```
Three imports: the React library itself, the DOM-specific renderer, and the one component this file actually uses.

```tsx
ReactDOM.createRoot(document.getElementById("root")!).render(
```
`document.getElementById("root")` — this is the single place in the entire `src/` tree that touches the real DOM directly. `document.getElementById(...)` returns `HTMLElement | null` in TypeScript's eyes (it can't prove the element exists); the trailing `!` is the "trust me" operator, asserting it's not null — safe here because `index.html` guarantees that `<div id="root">` exists. `createRoot(...)` hands React ownership of everything inside that div from this point forward; no other code should ever manually touch its contents.

```tsx
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```
`<App />` is the actual UI. `<React.StrictMode>` wrapping it adds zero visible UI — in development only, it intentionally double-invokes components and effects once, to surface bugs where code wrongly assumes "this only runs once" (a very common source of subtle bugs). It's stripped out entirely in production builds.

---

## `src/types.ts` — the data contract

No logic in this file at all — every line is a type declaration, read as documentation of exactly what the backend sends back.

```ts
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
```
One field per key in the dict that `app/service/get_messages.py`'s `format_thread()` actually builds (traced directly from that function, not guessed). `string | null` fields are the ones that function can genuinely set to `None` — `skip_reason`, `detected_intent`, `calendar_event`, `analysis_updated_at` all come from a lookup (`analysis_states.get(...)`) that may have nothing for a given message, so TypeScript is told up front that reading `.skip_reason` might hand you `null` — every place that reads it has to handle that case or the compiler rejects it.

```ts
export interface MailboxResponse {
  email: string;
  mailbox: string;
  ...
  messages: MailboxMessage[];
  next_page_token: string | null;
}
```
The envelope `GET /gmail/messages` returns — one `MailboxMessage` per entry in `messages`. `next_page_token` is only used by `fetchMailbox` partially (see below) — this project doesn't implement pagination, but the field is still typed accurately because the real endpoint sends it.

```ts
export interface GmailMessageDetail {
  id: string;
  ...
  sanitized: boolean;
  prompt_injection_detected: boolean;
  ...
}
```
The single-message shape from `read_gmail_message` in `app/tool/tools.py`. `sanitized` and `prompt_injection_detected` exist *because* of the hook pipeline discussed elsewhere in this project — they're not generic email fields, Gmail's API doesn't return them; `post_tool_process_gmail_message` adds them.

```ts
export interface MessageDetailResponse {
  email: string;
  message_id: string;
  message: GmailMessageDetail;
}
```
The envelope `GET /gmail/message` returns — the actual message is nested one level under `.message`, which is why `api.ts`'s `fetchMessage` and every caller of it reaches in as `data.message`, not `data` directly.

---

## `src/api.ts` — the fetch layer

```ts
async function requestJson<T>(path: string): Promise<T> {
```
A generic function — `<T>` is a placeholder type filled in by each caller (`requestJson<MailboxResponse>(...)`, `requestJson<MessageDetailResponse>(...)`). One implementation, two different guaranteed return types depending on how it's called.

```ts
  const response = await fetch(path, { credentials: "include" });
```
`fetch` is the same browser API `app.js` uses — nothing React-specific here. `credentials: "include"` is the one option that matters: by default, `fetch` does **not** send cookies on every request; this app's login is a session cookie (`app/webhook.py`'s `require_session`), so without this flag every request would arrive at the backend looking logged-out.

```ts
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(
      `${response.status} ${response.statusText}${detail?.detail ? `: ${detail.detail}` : ""}`
    );
  }
```
`response.ok` is `false` for any status outside 200–299 — `fetch` does **not** throw on a 404 or 500 by itself, which is a common beginner mistake to miss. This block converts that into a thrown `Error`, with two layers of defense: `.catch(() => null)` in case the error response isn't even valid JSON (e.g. a raw 500 HTML page from a proxy, which is exactly what happens in the "backend not running" case tested in the README), and `detail?.detail` using FastAPI's actual error shape (`{"detail": "..."}` — the same field `HTTPException(detail=...)` produces throughout `app/webhook.py`) only if it's present.

```ts
  return response.json() as Promise<T>;
}
```
On success, parse the body as JSON and tell TypeScript to trust it matches `T`. This `as` is an assertion, not a runtime check — nothing here actually verifies the backend sent the shape `types.ts` describes; if the backend changed its response shape tomorrow, this line wouldn't catch it. (A schema-validation library like `zod` is the usual next step beyond this reference's scope.)

```ts
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
```
`?` after each param name means all three are optional when calling this function. `??` (nullish coalescing) supplies the default only when the value is genuinely `null`/`undefined` — different from `||`, which would also override a legitimate falsy value. `URLSearchParams` builds the query string and handles escaping for you (no manual `encodeURIComponent` needed, unlike string-concatenation approaches). `limit` has to go through `String(...)` because `URLSearchParams` only accepts strings, and `params.limit` is typed as `number`.

```ts
export function fetchMessage(messageId: string, threadId?: string): Promise<MessageDetailResponse> {
  const query = new URLSearchParams({ message_id: messageId });
  if (threadId) query.set("thread_id", threadId);
  return requestJson<MessageDetailResponse>(`/gmail/message?${query}`);
}
```
`message_id` is required (no `?`), `threadId` is optional. Unlike `fetchMailbox`, this one only *conditionally* adds `thread_id` to the query at all — mirroring the real endpoint's own `Optional[str] = Query(default=None)` on `thread_id` in `app/webhook.py`; sending an empty string there would behave differently from omitting the parameter entirely.

---

## `src/hooks/useMessages.ts` — the core pattern

```ts
interface UseMessagesResult {
  messages: MailboxMessage[];
  loading: boolean;
  error: string | null;
}
```
The shape this hook hands back to whatever calls it — three independent pieces of state, each tracked separately rather than, say, one combined "status" enum (a legitimate alternative design, not used here for simplicity).

```ts
export function useMessages(mailbox: string, category: string): UseMessagesResult {
  const [messages, setMessages] = useState<MailboxMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
```
Three separate `useState` calls. Each returns a `[currentValue, setterFunction]` pair. `loading` starts `true` deliberately — the very first render, before any fetch has even started, should still show a loading state, not a flash of "no messages."

```ts
  useEffect(() => {
```
Everything inside `useEffect` runs *after* React has rendered, as a separate step — not during rendering itself. This matters because fetching data is a **side effect** (it reaches outside this component, to the network); React's rendering phase is supposed to be a pure calculation of "what should the UI look like," with anything that touches the outside world pushed into effects like this one.

```ts
    let cancelled = false;
```
A plain local variable, reset fresh on every run of this effect. This is the fix for a very real bug class: without it, if `mailbox` or `category` changes while a fetch is still in flight, the *old* fetch's `.then(...)` could still resolve later and overwrite state with stale data — a React warning ("state update on an unmounted component") and a genuine correctness bug combined.

```ts
    setLoading(true);
    setError(null);
```
Reset both before starting a new fetch — otherwise, switching mailboxes while a previous error was showing would leave that stale error message on screen during the new load.

```ts
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
```
The actual fetch, from `api.ts`. Every single state update here is guarded by `if (!cancelled)` — this is `cancelled`'s entire purpose: if the cleanup function below ran before this promise settled, skip updating state entirely, because a newer effect run has already taken over.

```ts
    return () => {
      cancelled = true;
    };
  }, [mailbox, category]);
```
The function `useEffect` returns is its **cleanup** — React calls it right before running the effect again, and once more when the component is removed from the screen entirely. Here, cleanup just flips `cancelled` to `true`, which is what makes the guards above work. The dependency array `[mailbox, category]` is what tells React *when* to re-run this whole effect: only when `mailbox` or `category` actually changes between renders — not on every render, and not never.

```ts
  return { messages, loading, error };
}
```
Hand back the three pieces of state as one object, for `App.tsx` to destructure.

**The comparison that matters:** `frontend/app.js` does the equivalent fetch with the same `fetch(...).then(...)` shape — that part isn't different. What's different is everything above it: `cancelled`, the three separate `useState` calls, the dependency array — that's the bookkeeping React makes you do explicitly, in one place, instead of it being implicit in "well, there's only one mailbox view on screen at a time, so it probably doesn't race" (true until it isn't).

---

## `src/components/MailboxList.tsx`

```tsx
interface MailboxListProps {
  messages: MailboxMessage[];
  selectedId: string | null;
  onSelect: (message: MailboxMessage) => void;
}
```
A component's props are just a typed function parameter — nothing magic. `onSelect` is typed as a function that takes a `MailboxMessage` and returns nothing (`void`); this is what lets `App.tsx` pass `setSelected` directly as `onSelect` below, since `setSelected`'s signature already matches.

```tsx
export function MailboxList({ messages, selectedId, onSelect }: MailboxListProps) {
  if (messages.length === 0) {
    return <p className="empty-state">No messages in this view.</p>;
  }
```
Destructuring the props object directly in the function signature. An early return for the empty case — once this returns, nothing below it runs for this render.

```tsx
  return (
    <ul className="mailbox-list">
      {messages.map((message) => (
```
`{...}` inside JSX is how you drop a real JavaScript expression into markup — `messages.map(...)` is plain `Array.prototype.map`, nothing React-specific; it returns an array of `<li>` elements, and JSX knows how to render an array of elements in place.

```tsx
        <li
          key={message.message_id}
```
`key` is not a prop your component can read — React intercepts it. It's how React matches "this `<li>` in the new render" to "this `<li>` in the previous render" when the list changes, so it can update only what actually changed instead of discarding and rebuilding the whole list. Must be unique and stable across renders — `message_id` fits both.

```tsx
          className={message.message_id === selectedId ? "mailbox-row selected" : "mailbox-row"}
          onClick={() => onSelect(message)}
        >
```
`className`, not `class` — `class` is a reserved word in JavaScript, so JSX (which compiles to real JS function calls) uses the DOM property name instead. The ternary picks one of two class strings based on whether this row is the selected one. `onClick` takes a function; `() => onSelect(message)` is an inline arrow function so that `message` (this specific row's data, from the closure) gets passed — `onClick={onSelect}` directly wouldn't work, since that would pass the raw click *event* instead.

```tsx
          <div className="mailbox-row-from">{message.from || "(unknown sender)"}</div>
          <div className="mailbox-row-subject">{message.subject || "(No subject)"}</div>
          <div className="mailbox-row-snippet">{message.snippet}</div>
```
`||` here (not `??`) is deliberate: an empty string `""` from the backend should also fall back to the placeholder text, not just `null`/`undefined` — this is a case where the looser `||` behavior is exactly what's wanted, unlike the `??` used in `api.ts` for numeric defaults.

```tsx
          {message.processing_status && (
            <span className={`status-pill status-${message.processing_status}`}>
              {message.processing_status}
            </span>
          )}
```
`condition && <jsx>` is the standard React idiom for "render this only if the condition is truthy." If `message.processing_status` is an empty string (falsy), React renders nothing for this expression; if it holds a real string, it renders the span. The backtick string builds a dynamic class name like `status-pending` or `status-done` so each status can be styled differently in CSS without a lookup table in the component itself.

---

## `src/components/MessageReader.tsx`

```tsx
interface MessageReaderProps {
  messageId: string | null;
  threadId: string | null;
}
```
Both nullable — `null` specifically means "nothing is selected," which is the state before the user has clicked any row.

```tsx
export function MessageReader({ messageId, threadId }: MessageReaderProps) {
  const [detail, setDetail] = useState<GmailMessageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
```
Same three-state pattern as `useMessages`, but kept local to this component rather than factored into its own hook — a deliberate inconsistency left in on purpose: `useMessages` is reused conceptually in the sense that this same shape could become its own `useMessageDetail` hook, but doing that here would just be repeating the exact same hook-extraction lesson a second time rather than showing something new.

```tsx
  useEffect(() => {
    if (!messageId) {
      setDetail(null);
      return;
    }
```
If nothing is selected, clear any previously-shown message and skip the fetch entirely — this is what makes switching from "message A shown" back to "nothing selected" clear the screen instead of leaving message A's content behind.

```tsx
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchMessage(messageId, threadId ?? undefined)
```
`threadId ?? undefined` converts `MessageReaderProps`'s `string | null` into what `fetchMessage`'s signature actually wants (`string | undefined` — see `api.ts`'s `threadId?: string`). `null` and `undefined` are different types to TypeScript even though both are "nothing" at runtime; this is the explicit conversion between the two conventions.

```tsx
      .then((data) => {
        if (!cancelled) setDetail(data.message);
      })
```
`data.message` — reaching into the nested field, per `MessageDetailResponse`'s shape in `types.ts` (the actual message isn't at the top level of the response).

```tsx
  }, [messageId, threadId]);
```
Re-run this whole effect whenever the user selects a different message (or, less commonly, the same message arrives via a different thread). This dependency array is why clicking a new row in `MailboxList` causes this component to fetch again — `App.tsx` passes the newly-selected message's id down as the `messageId` prop, which changes, which this array is watching.

```tsx
  if (!messageId) {
    return <p className="empty-state">Select a message to read it.</p>;
  }
  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="error-state">Couldn't load this message: {error}</p>;
  if (!detail) return null;
```
Four early-return guards in order of precedence: nothing selected, still loading, failed, and a defensive final check (`!detail`) for the case where loading finished without error but `detail` somehow never got set — shouldn't happen given the logic above, but costs nothing to guard against, and TypeScript's `strict` mode effectively requires it anyway (every line below assumes `detail` is non-null, and the compiler wouldn't allow that without this check first).

```tsx
  return (
    <article className="message-reader">
      <h2>{detail.subject || "(No subject)"}</h2>
```
Past all four guards, TypeScript now knows `detail` is a real `GmailMessageDetail`, not possibly `null` — that narrowing is exactly what the `if (!detail) return null` line above bought.

```tsx
      <dl className="message-headers">
        <dt>From</dt>
        <dd>{detail.from}</dd>
        ...
```
`<dl>`/`<dt>`/`<dd>` — a "description list," the semantically correct HTML elements for label/value pairs like email headers, rather than generic `<div>`s.

```tsx
      {detail.has_display_html && detail.display_html ? (
        <div
          className="message-body"
          dangerouslySetInnerHTML={{ __html: detail.display_html }}
        />
      ) : (
        <p className="message-body message-body-plain">{detail.body}</p>
      )}
```
Two checks, not one: `has_display_html` is the backend's own flag (set in `app/tool/tools.py`), and `detail.display_html` is checked again directly because TypeScript can't otherwise prove the optional field (`display_html?: string` in `types.ts`) is actually present just from the boolean being true — the type system has no way to know those two fields are logically linked, so both are checked explicitly.

`dangerouslySetInnerHTML` takes an object with an `__html` key (not a raw string) — that unusual shape is itself a deliberate speed bump, making it a little harder to do by accident. Everywhere else in this codebase, `{someVariable}` in JSX is automatically HTML-escaped (so a message literally containing `<script>` text would render as visible text, not execute) — this is the **one** opt-out from that default, and it's safe here specifically because `detail.display_html` has already been through `app/agent/hooks.py`'s sanitization before this component ever sees it. The fallback branch, `{detail.body}`, uses ordinary JSX interpolation and gets that automatic escaping.

```tsx
      {detail.prompt_injection_detected && (
        <p className="warning-banner">
          ⚠ This message contained a prompt-injection pattern that was stripped before display.
        </p>
      )}
    </article>
  );
}
```
Same `&&` pattern as `MailboxList`'s status pill — renders only when the backend's own detection flag is true.

---

## `src/App.tsx` — the root

```tsx
export default function App() {
  const [mailbox] = useState("inbox");
  const [category] = useState("primary");
```
Array destructuring where only the first element (the value) is pulled out — the setter function (normally `setMailbox`) is discarded, because this reference app never actually changes mailbox/category after the initial load. They're still `useState` rather than plain constants so the door is left open for an actual mailbox switcher to be added later without restructuring anything.

```tsx
  const [selected, setSelected] = useState<MailboxMessage | null>(null);

  const { messages, loading, error } = useMessages(mailbox, category);
```
This is the "lifting state up" the file's own top comment describes: `App` is the one place that holds `selected` — neither `MailboxList` nor `MessageReader` tracks it themselves. Calling the custom hook here is exactly like calling `useState` — from this component's point of view, `useMessages` is indistinguishable from a built-in hook; it's just a function that happens to internally use three `useState` calls and an effect of its own.

```tsx
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
```
Three `&&` expressions in sequence, mutually exclusive in practice (only one of `loading`/`error`/neither is ever true at once given how `useMessages` sets them) — React renders whichever one currently evaluates truthy and nothing for the other two.

`selected?.message_id ?? null` — `?.` (optional chaining) short-circuits to `undefined` if `selected` itself is `null`, without throwing; `?? null` then converts that `undefined` into an explicit `null`, matching `MailboxListProps`'s `selectedId: string | null` exactly (`undefined` and `null` are different types here, same distinction as in `MessageReader`).

`onSelect={setSelected}` — passing the raw state setter straight down as the callback prop. `MailboxList` calls `onSelect(message)`; React has `setSelected(message)` run that same call under a different name. No wrapper function needed because `setSelected`'s own signature already matches what `MailboxListProps` expects.

```tsx
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
```
Same `?.`/`??` pattern again, twice — passing down the two pieces of the selected message that `MessageReader` actually needs, rather than the whole `MailboxMessage` object. This is itself a small design choice: `MessageReader` doesn't need to know anything about `MailboxMessage`'s shape at all, only two plain strings — keeping its own prop type minimal and decoupled from the list's.

---

## `src/App.css`

Plain CSS, no CSS-in-JS, no preprocessor — nothing React-specific to explain here. `className="mailbox-row"` in a component and `.mailbox-row { ... }` in this file are connected by nothing more than that matching string; React doesn't scope styles to components by default (CSS Modules or styled-components are the common ways to add that, neither used here, to keep this reference minimal).
