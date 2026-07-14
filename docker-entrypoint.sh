#!/usr/bin/env sh
set -eu

PORT="${PORT:-8501}"

exec streamlit run main.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT}"
