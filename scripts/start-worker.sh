#!/usr/bin/env sh
set -eu

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
CELERY_LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"

CELERY_BIN="${CELERY_BIN:-celery}"
if [ -x ".venv/bin/celery" ]; then
  CELERY_BIN=".venv/bin/celery"
fi

exec "$CELERY_BIN" -A app.celery_app.celery_app worker -B \
  --loglevel="$CELERY_LOG_LEVEL" \
  --concurrency="$CELERY_WORKER_CONCURRENCY"
