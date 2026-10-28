#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"
NGROK_BIN="${NGROK_BIN:-$HOME/.local/bin/ngrok}"
NGROK_API_URL="${NGROK_API_URL:-http://127.0.0.1:4040/api/tunnels}"

if [ ! -x "$NGROK_BIN" ]; then
  echo "ngrok was not found at $NGROK_BIN."
  echo "Download ngrok or set NGROK_BIN=/path/to/ngrok."
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  EXISTING_TUNNELS="$(curl -fsS "$NGROK_API_URL" 2>/dev/null || true)"
  if printf '%s' "$EXISTING_TUNNELS" | grep -q '"public_url"'; then
    echo "ngrok is already running locally; reusing the existing tunnel."
    printf '%s\n' "$EXISTING_TUNNELS" | sed -n 's/.*"public_url":"\([^"]*\)".*/Public URL: \1/p' | head -n 1
    echo "Leave this process running with the API and worker. Press Ctrl+C to stop local dev."
    while curl -fsS "$NGROK_API_URL" >/dev/null 2>&1; do
      sleep 30
    done
    echo "Existing ngrok tunnel stopped."
    exit 0
  fi
fi

exec "$NGROK_BIN" http "$PORT"
