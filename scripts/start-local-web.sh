#!/usr/bin/env sh
set -eu

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
UVICORN_RELOAD="${UVICORN_RELOAD:-false}"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing macOS virtualenv at .venv/bin/python."
  echo "Create it with: python3 -m venv .venv"
  exit 1
fi

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Stop the old local web process, then start again."
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  exit 1
fi

if [ "$UVICORN_RELOAD" = "true" ] || [ "$UVICORN_RELOAD" = "1" ]; then
  exec .venv/bin/python -m uvicorn app.webhook:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload
fi

exec .venv/bin/python -m uvicorn app.webhook:app \
  --host "$HOST" \
  --port "$PORT"
