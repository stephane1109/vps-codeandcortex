#!/bin/sh
set -eu

PORT="${PORT:-8501}"
BASE_URL_PATH="${STREAMLIT_SERVER_BASE_URL_PATH:-}"
APP_DATA_DIR="${APP_DATA_DIR:-/tmp/appdata}"

mkdir -p "$APP_DATA_DIR"

set -- streamlit run main.py --server.address=0.0.0.0 --server.port="${PORT}"

if [ -n "${BASE_URL_PATH}" ]; then
  set -- "$@" --server.baseUrlPath="${BASE_URL_PATH}"
fi

exec "$@"
