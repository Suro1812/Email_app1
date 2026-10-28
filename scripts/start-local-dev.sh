#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"

if command -v docker >/dev/null 2>&1; then
  docker compose up -d postgres redis
else
  echo "Docker is not installed or not on PATH; Postgres/Redis must already be running."
fi

cleanup() {
  if [ -n "${WORKER_PID:-}" ]; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
  if [ -n "${WEB_PID:-}" ]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

./scripts/start-worker.sh &
WORKER_PID="$!"

PORT="$PORT" ./scripts/start-local-web.sh &
WEB_PID="$!"

sleep 2

PORT="$PORT" ./scripts/start-ngrok.sh
