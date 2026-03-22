#!/usr/bin/env sh
set -eu

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec .venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
