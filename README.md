# Email Reminders

A Gmail assistant that watches an inbox via Google Pub/Sub push notifications,
runs each new message through a multi-agent LangGraph pipeline, and surfaces
actionable items (replies, calendar events, reminders) in a web UI — with a
sanitization layer in front of every agent call to defend against
prompt-injection and hidden-content attacks hiding inside email HTML.

## What's actually in this repo

- **Backend**: FastAPI + Celery (Postgres-backed), a four-agent LangGraph
  pipeline, Gmail API integration via OAuth2 + Pub/Sub push
- **Frontend**: a vanilla JS/HTML/CSS app (the real UI) plus a separate React
  reference implementation of one screen, written to show the same patterns
  side by side (see [`frontend-react/`](frontend-react/))
- **Observability**: Prometheus + Grafana dashboards, an optional
  Pushgateway path for pushing metrics out of environments with no inbound
  network access (e.g. Azure Container Apps), and self-hosted Langfuse for
  LLM tracing — all opt-in, none of it required for the app to run
- **Deployment**: an ARM template for Azure Container Apps
  ([`infra/aca/`](infra/aca/))

## Architecture at a glance

```
Gmail  --push-->  /webhooks/gmail/pubsub  --Celery task-->  pipeline
                                                                │
                              ┌─────────────────────────────────┤
                              ▼                                 ▼
                      sanitize + analyze                  summarize
                   (prompt-injection, PII)                     │
                              │                                 ▼
                              └──────────────▶  writer / reply agent
                                                      │
                                                      ▼
                                              frontend/ (web UI)
```

Postgres and Redis back the API and worker. The worker also renews Gmail
watches on a schedule (Gmail watches expire after 7 days with no way to
extend them in place).

## Quick start

### Prerequisites (either path)

1. **Python 3.8+** (developed and tested against 3.9)
2. **A Gmail OAuth client** — create one in Google Cloud Console, enable the
   Gmail API, download the credentials JSON as `credentials.json` in the repo
   root. Scopes used: `gmail.readonly`, `gmail.send`.
3. **An OpenAI-compatible LLM endpoint** — either a local
   [Ollama](https://ollama.com) server (`OLLAMA_BASE_URL`), or
   `OPENAI_API_KEY` as a fallback. See `.env.example`.
4. Copy `.env.example` to `.env` and fill in the values above.

### With Docker (simplest)

```sh
docker compose up --build api worker redis postgres
```

### Without Docker

The app itself has no Docker dependency — it only needs a reachable Postgres
and Redis, by any means. Install them natively (`brew install postgresql
redis` on macOS, `apt install postgresql redis` on Linux, or point
`DATABASE_URL`/`CELERY_BROKER_URL` in `.env` at any hosted instance), then:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m app.init_db          # create tables
./scripts/start-local-dev.sh   # worker + API + ngrok tunnel
```

Open **http://localhost:8000/app**.

## The agent pipeline

Four LangGraph agents, each a separate prompt under
[`app/agent/skills/`](app/agent/skills/), run in sequence per message:

| Agent | Job |
|---|---|
| **Analyzer** | Decides whether a message contains an actionable item — a calendar event, a reminder, or nothing — and classifies it |
| **Summarizer** | Turns one message plus its thread context into a summary the user (and the reply agent) can act on without reopening the email |
| **Writer** | Drafts a complete new message from a user instruction plus thread context |
| **Reply** | Drafts a reply to the current message, once the user explicitly asks for one, using the analyzer's decision and the summary as context |

## Security: the sanitization pipeline

Every message is run through `app/agent/hooks.py` before any agent sees it:
dangerous tags are stripped, hidden/white-text prompt-injection carriers are
removed, and (optionally, behind `ENABLE_PRESIDIO_PII`) PII is masked via
Microsoft Presidio. A `prompt_injection_detected` flag survives into the API
response and is surfaced in both frontends.

**Known limitation**: Gmail OAuth refresh tokens are currently stored in
Postgres in plaintext (`app/core/database.py`'s `GmailUser.refresh_token`).
Given the token carries `gmail.send` scope, encrypting it at rest is the
natural next hardening step and isn't done yet.

## Observability (optional)

None of this is required to run the app — it's a separate overlay:

```sh
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

Grafana at `localhost:3000` (dashboard auto-provisioned), Prometheus at
`localhost:9090`. See [`infra/monitoring/`](infra/monitoring/) for the
dashboard definitions and [`infra/monitoring/prometheus.yml`](infra/monitoring/prometheus.yml)
for what's scraped.

For environments with no inbound network path to the app (ACA, for
instance), metrics can be **pushed** to a local Pushgateway over an ngrok
tunnel instead of scraped — see the `PUSHGATEWAY_*` variables in `.env.example`
and `app/observability.py`'s `start_metrics_pusher`.

Self-hosted Langfuse (`docker-compose.langfuse.yml`) is **work in progress** —
its object-storage service was originally MinIO, whose server image is no
longer publicly pullable, and the swap to a Garage-based replacement isn't
fully wired up yet.

## Testing

```sh
python -m pytest
```

Most of the suite is self-contained, but the database tests
(`tests/test_database.py`) and a few webhook tests need a live Postgres
reachable via `DATABASE_URL` — expect failures there on a machine with no
database running, not a sign the rest of the suite is broken.

## Deployment

An ARM template for Azure Container Apps lives in
[`infra/aca/azuredeploy.json`](infra/aca/azuredeploy.json), deployed via
[`scripts/deploy-aca.sh`](scripts/deploy-aca.sh). See
[`scripts/deploy-aca.env.example`](scripts/deploy-aca.env.example) for the
required configuration.

## Project structure

```
app/                  FastAPI app, Celery tasks, the agent pipeline, Gmail integration
frontend/             The real web UI (vanilla JS/HTML/CSS)
frontend-react/        A standalone React reference implementation — not wired
                       into the app; see its own README and CODE_WALKTHROUGH.md
infra/
  aca/                Azure Container Apps ARM template
  monitoring/         Prometheus + Grafana config and dashboards
  langfuse/           Self-hosted Langfuse config (work in progress)
scripts/               Launch scripts for local dev, Azure deploy, ngrok
tests/                 pytest suite
```
