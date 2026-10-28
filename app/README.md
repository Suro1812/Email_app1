# Email Reminders API and MCP Server

A FastAPI and Model Context Protocol (MCP) Gmail integration with multi-user OAuth,
Pub/Sub-triggered email analysis, Celery/Redis background workers,
user-requested reply drafts, and observability.

## Setup

### 1. Install Dependencies
```bash
cd app/
pip install -e .
```

### 2. Set Up PostgreSQL Database
Create a PostgreSQL database and set the environment variable:
```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/email_reminders"
```

You can copy the root example env file for local development:

```bash
cp .env.example .env
```

### 3. Initialize Database
```bash
python init_db.py
```
This creates both:
- `gmail_users` for OAuth credentials
- `email_message_reminders` for analyzed Gmail messages with message id, processing status, skip reason, summary, detected intent, action items, deadline, reply status, suggested reply, token usage, user id, from, to, and calendar event fields

Database models use SQLModel on top of SQLAlchemy. The app engine uses a
QueuePool; tune it with:

```bash
export DB_POOL_SIZE=10
export DB_MAX_OVERFLOW=20
export DB_POOL_TIMEOUT=30
export DB_POOL_RECYCLE=1800
```

For an existing database, apply:
```bash
psql "$DATABASE_URL" -f app/core/migrations/001_email_processing_fields.sql
```

### 4. Get Google OAuth Credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project
3. Enable Gmail API
4. Create OAuth 2.0 Desktop Application credentials
5. Download the JSON file as `credentials.json` in the `app/` directory

### 5. Authenticate Users
For each user who wants to use the app:
```bash
python authenticate_user.py
```
This will open a browser for Gmail login and save credentials to the database.

You can also start OAuth through the API:

```bash
curl -X POST "http://localhost:8000/auth/login?start_watch=true"
```

### 6. Configure Gmail Pub/Sub Push
Gmail push notifications are delivered through Google Cloud Pub/Sub.

1. Create a Pub/Sub topic, for example `projects/YOUR_PROJECT/topics/gmail-inbox`.
2. Grant Gmail permission to publish to the topic:
   `gmail-api-push@system.gserviceaccount.com`
   with the `Pub/Sub Publisher` role.
3. Expose the webhook endpoint publicly over HTTPS:
   `/webhooks/gmail/pubsub`
4. Create a Pub/Sub push subscription that points to that URL, and enable authenticated push with a service account.
5. Set the topic, token audience, and optional service account pin:
```bash
export GMAIL_PUBSUB_TOPIC="projects/YOUR_PROJECT/topics/gmail-inbox"
export GMAIL_PUBSUB_AUDIENCE="https://YOUR_DOMAIN/webhooks/gmail/pubsub"
export GMAIL_PUBSUB_SERVICE_ACCOUNT="pubsub-push@YOUR_PROJECT.iam.gserviceaccount.com"
```
For local development only, token verification can be disabled:
```bash
export GMAIL_PUBSUB_VERIFY_TOKEN=false
```
6. Start a Gmail watch for each authenticated user:
```python
import asyncio
from app.service.gmail_push import start_gmail_watch

asyncio.run(start_gmail_watch("user@gmail.com"))
```

Gmail watches expire, so schedule `start_gmail_watch` to run again before expiration.
Webhook notifications are accepted immediately and the pipeline runs in a
Celery worker. The worker still needs stored OAuth
credentials and an active `gmail_history_id` for the notification email.

### 7. Run Webhook Server
```bash
uvicorn app.webhook:app --host 0.0.0.0 --port 8000
```

Open the local frontend console:

```text
http://localhost:8000/
```

Local macOS startup script:

```bash
./scripts/start-local-web.sh
```

Start an ngrok tunnel to the same port:

```bash
./scripts/start-ngrok.sh
```

Or start both together:

```bash
./scripts/start-local-dev.sh
```

Container startup script:

```bash
./scripts/start-api.sh
```

### 8. Configure Celery Queue

The webhook enqueues Gmail notification work into Celery. The same code works
locally and in Azure by changing Redis URLs.

Local:

```bash
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/1"
export CELERY_WORKER_CONCURRENCY=4
export EMAIL_MESSAGE_FETCH_CONCURRENCY=5
```

Azure Cache for Redis:

```bash
export CELERY_BROKER_URL="rediss://:<password>@<azure-redis-host>:6380/0"
export CELERY_RESULT_BACKEND="rediss://:<password>@<azure-redis-host>:6380/1"
export CELERY_WORKER_CONCURRENCY=4
export EMAIL_MESSAGE_FETCH_CONCURRENCY=5
```

Local Redis with AOF and RDB persistence is provided by the root
`docker-compose.yml`:

```bash
docker compose up redis
```

The Redis service uses:

```text
appendonly yes
appendfsync everysec
save 60 1000
```

Start a local Celery worker:

```bash
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency="${CELERY_WORKER_CONCURRENCY:-4}"
```

Container startup script:

```bash
./scripts/start-worker.sh
```

### 9. Run API and Worker as Separate Containers

The project uses one Docker image and two runtime commands:

- `api`: runs FastAPI and accepts Gmail Pub/Sub webhooks.
- `worker`: runs Celery and processes queued Gmail notifications.
- `redis`: shared queue broker/result backend.

For local container testing:

```bash
docker compose up --build api worker redis
```

Inside Compose, both app containers use:

```bash
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

For a cloud deployment, build and publish the same image once, then configure
two services with different startup commands:

```bash
# API/webhook container
./scripts/start-api.sh

# Celery worker container
./scripts/start-worker.sh
```

In Azure Container Apps, use the same Docker image for API and worker, with
different startup commands:

```text
api:    uvicorn app.webhook:app --host 0.0.0.0 --port 8000
worker: celery -A app.celery_app.celery_app worker --loglevel=info --concurrency="${CELERY_WORKER_CONCURRENCY:-4}"
```

`CELERY_WORKER_CONCURRENCY` controls how many notification tasks a worker
processes at once. `EMAIL_MESSAGE_FETCH_CONCURRENCY` controls how many changed
Gmail messages are fetched concurrently inside one notification task.

### 9. Configure Email Processing
```bash
export ENABLE_PROMPT_CACHING=true
export ENABLE_LANGFUSE_CALLBACKS=true
export ENABLE_LANGFUSE_EVENTS=true
```

Optional LangGraph Postgres checkpointing:

```bash
export LANGGRAPH_POSTGRES_CHECKPOINTS=true
export LANGGRAPH_CHECKPOINT_DB_URL="$DATABASE_URL"
export LANGGRAPH_CHECKPOINT_SETUP=true
```

`LANGGRAPH_POSTGRES_CHECKPOINTS=true` stores graph state checkpoints in
Postgres using the LangGraph async Postgres saver. If
`LANGGRAPH_CHECKPOINT_DB_URL` is omitted, the app falls back to `DATABASE_URL`.

### 10. Observability

Prometheus metrics are available at:

```text
GET /metrics
```

The app exports counters and latency histograms for Gmail tool calls and
sanitization hooks:

```text
email_reminders_tool_calls_total
email_reminders_tool_call_duration_seconds
email_reminders_hook_calls_total
email_reminders_hook_call_duration_seconds
```

Langfuse is used in two ways:

- LangChain callback tracing for LLM calls when `ENABLE_LANGFUSE_CALLBACKS=true`
- Direct event export for tool and hook calls using `langfuse.get_client()` when `ENABLE_LANGFUSE_EVENTS=true`

## Usage

### API Endpoints

```text
GET  /health
GET  /metrics
POST /auth/login?start_watch=true
POST /gmail/watch
POST /pipeline/messages
POST /reply/message
POST /reply/send
POST /webhooks/gmail/pubsub
```

### Manually Run Pipeline for Message IDs

```bash
curl -X POST "http://localhost:8000/pipeline/messages" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@gmail.com","message_ids":["MESSAGE_ID"]}'
```

This endpoint enqueues `email_reminders.run_pipeline_for_message_ids` and
returns `accepted` with a Celery `task_id`. Pipeline execution runs in the
Celery worker, analyzes and optionally summarizes messages, and persists final
graph results to the database only after graph execution completes.

### Generate a User-Requested Reply

```bash
curl -X POST "http://localhost:8000/reply/message" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@gmail.com","message_id":"MESSAGE_ID","intent":"Politely say I will review this today."}'
```

This endpoint is only called when a user explicitly requests a draft. It loads
stored analysis metadata, fetches the Gmail message by ID, passes the user's
reply intent to the reply agent, and saves the generated reply.

After the frontend user reviews or edits the generated text, send it through
Gmail:

```bash
curl -X POST "http://localhost:8000/reply/send" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@gmail.com","message_id":"MESSAGE_ID","reply_body":"Thanks, I will review this today."}'
```

Sending requires the OAuth scope `https://www.googleapis.com/auth/gmail.send`.
Users who authenticated before this scope was added must authenticate again.

### Read Message by Gmail Message ID
```python
from app.tool.tools import read_gmail_message
message = read_gmail_message(email="user@gmail.com", message_id="123456789")
```

## Architecture

- **Multi-user support**: Each user's Gmail credentials stored securely in PostgreSQL.
- **OAuth2 authentication**: Automatic token refresh
- **SQLModel persistence**: SQLModel table models backed by SQLAlchemy sessions and QueuePool connections.
- **MCP integration**: Compatible with MCP clients
- **Async support**: Built with FastMCP for async operations
- **Durable background processing**: Gmail notifications are accepted by the webhook, queued in Celery, and processed by worker containers.
- **Split Gmail AI flow**: Gmail History API identifies changed Inbox message IDs, and those exact messages are passed into the agent processing service.
- **Orchestrator agent calls**: `orchestrator.py` contains event/reminder analysis, user-requested summarization, user-requested reply generation, and DB handoff functions.
- **Analyzer call**: The present message and any thread context are analyzed into structured event/reminder JSON.
- **Summarizer call**: A message is summarized only when a user explicitly requests it from the frontend.
- **Reply generation**: Suggested replies are generated only from the reply endpoint when a user explicitly requests a draft and provides reply intent from the frontend.
- **LangGraph checkpoints**: Optional async Postgres checkpoint saver stores graph state by thread id.
- **Observability**: Prometheus exposes system metrics and Langfuse receives LLM traces plus tool/hook events.

## Processing Flow

1. Gmail Pub/Sub webhook receives a notification.
2. The webhook verifies and decodes the notification.
3. The webhook enqueues `email_reminders.process_gmail_notification` in Celery and returns `accepted` with a `task_id`.
4. Manual `/pipeline/messages` requests also enqueue `email_reminders.run_pipeline_for_message_ids` and return immediately with a `task_id`.
5. A Celery worker uses the previous Gmail `history_id` to list changed Inbox message IDs.
6. The worker fetches each changed message directly by ID using the authenticated Gmail client.
7. The present-message promotional/basic check can skip messages before LLM analysis.
8. The analyzer function reads each non-skipped present message with available thread context and returns structured event/reminder JSON.
9. Final graph results are saved to the database after graph execution.
10. When a user requests a summary, the summary endpoint fetches the Gmail message and thread context, calls the summarizer agent, and saves the generated summary.
11. When a user requests a draft, the reply endpoint fetches the Gmail message, combines it with the user's reply intent, calls the reply agent, and saves the generated reply.

This keeps background processing lightweight while summaries and replies remain explicit user-triggered actions.
