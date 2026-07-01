#!/bin/sh
set -eu

PORT="${PORT:-8000}"

exec python3 -m uvicorn webapp.main:app --host 0.0.0.0 --port "${PORT}"
