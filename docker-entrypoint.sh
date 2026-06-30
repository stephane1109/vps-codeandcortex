#!/bin/sh
set -eu

PORT="${PORT:-8501}"
BASE_URL_PATH="${STREAMLIT_SERVER_BASE_URL_PATH:-}"
MAX_UPLOAD_MB="${STREAMLIT_SERVER_MAX_UPLOAD_SIZE:-4096}"

set -- streamlit run main.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT}" \
  --server.maxUploadSize="${MAX_UPLOAD_MB}" \
  --server.maxMessageSize="${MAX_UPLOAD_MB}"

if [ -n "${BASE_URL_PATH}" ]; then
  set -- "$@" --server.baseUrlPath="${BASE_URL_PATH}"
fi

exec "$@"
