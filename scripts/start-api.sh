#!/usr/bin/env sh
set -eu

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
UVICORN_BIN="${UVICORN_BIN:-uvicorn}"

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

if [ -x ".venv/bin/uvicorn" ]; then
  UVICORN_BIN=".venv/bin/uvicorn"
fi

exec "$UVICORN_BIN" app.webhook:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WEB_CONCURRENCY"
