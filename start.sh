#!/usr/bin/env sh
set -eu

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
