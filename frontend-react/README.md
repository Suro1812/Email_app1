# React reference frontend

A standalone, minimal React + TypeScript + Vite implementation of **one
screen** from this app — the mailbox list and message reader — written to
show the same patterns the real frontend (`frontend/app.js`, vanilla JS) uses,
side by side, for comparison.

**Not wired into anything.** `app/webhook.py`, `docker-compose*.yml`, and
`scripts/*.sh` are all untouched. This directory has its own `package.json`
and runs entirely on its own.

## What it covers

- Mailbox list (`GET /gmail/messages`)
- Reading one full message, including the sanitized body and the
  `prompt_injection_detected` flag from `app/agent/hooks.py`'s pipeline
  (`GET /gmail/message`)

What it deliberately **doesn't** cover: the Quill-based reply composer,
calendar view, notifications, signatures, or the local caching layer
(`frontend/mail-cache.js`). Porting those wasn't the ask — this is a reference
for the pattern, not a feature-complete replacement.

## Run it

```sh
cd frontend-react
npm install
npm run dev
```

Opens on **http://localhost:5173**. For it to show real mail instead of an
error state, the real backend needs to be running first:

```sh
# in the repo root, in another terminal
source .venv/bin/activate
./scripts/start-local-web.sh
```

`vite.config.ts` proxies `/gmail`, `/auth`, and `/notifications` to
`127.0.0.1:8000`, so from the browser's point of view every request looks
same-origin — no CORS headers were added to the FastAPI app, and none are
needed. Auth is the same session cookie the real app uses
(`app/webhook.py`'s `require_session`); log in through the real app first in
the same browser and this page will pick up that session.

If the backend isn't running, the page still loads — `useMessages`/
`MessageReader` just show "Couldn't load messages: ..." instead of crashing.
That's deliberate, not a bug: see `src/hooks/useMessages.ts`.

## Where to look, and why

For a full line-by-line walkthrough of every file — config included — see
[`CODE_WALKTHROUGH.md`](CODE_WALKTHROUGH.md). The table below is the
short version.

| File | What it demonstrates |
|---|---|
| [`src/types.ts`](src/types.ts) | API response shapes written down once, traced from the real backend code (not guessed) |
| [`src/api.ts`](src/api.ts) | A typed fetch wrapper — compare to how `app.js` calls `fetch()` inline at each call site |
| [`src/hooks/useMessages.ts`](src/hooks/useMessages.ts) | The core difference from vanilla: loading/error state as `useState`, not module-level variables you remember to check everywhere |
| [`src/components/MailboxList.tsx`](src/components/MailboxList.tsx) | A "dumb" component — JSX instead of string concatenation / `createElement` loops, plus why `key` is required |
| [`src/components/MessageReader.tsx`](src/components/MessageReader.tsx) | A second independent fetch, `dangerouslySetInnerHTML` and why it's safe *here specifically* (the content already passed through `hooks.py`'s sanitization) |
| [`src/App.tsx`](src/App.tsx) | "Lifting state up" — one parent owns `selected`, hands it to both children |

## Known gap

`npm audit` flags a moderate advisory in `esbuild` (via Vite 5's dev server —
any site can send requests to it while `npm run dev` is running). It doesn't
affect `npm run build`'s output. Left as-is rather than force an unrelated
major-version Vite 8 upgrade into a reference example; a real migration
would want to track that separately.

## Build

```sh
npm run build   # tsc -b && vite build  → dist/
```

Verified clean: no TypeScript errors, 146KB JS bundle. `dist/` is exactly
what would get mounted by `app.mount("/static", StaticFiles(directory=...))`
in `app/webhook.py` *if* this were ever actually integrated — which, again,
it isn't.
