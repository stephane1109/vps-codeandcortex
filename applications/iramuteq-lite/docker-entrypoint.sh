#!/bin/sh
set -eu

APP_DATA_DIR="${IRAMUTEQ_APP_DATA_DIR:-/data/app}"
MPLCONFIG_PATH="${MPLCONFIGDIR:-$APP_DATA_DIR/mplconfig}"
PORT="${PORT:-8000}"

mkdir -p "$APP_DATA_DIR"
mkdir -p "$APP_DATA_DIR/jobs"
mkdir -p "$APP_DATA_DIR/downloads"
mkdir -p "$APP_DATA_DIR/dictionnaires"
mkdir -p "$MPLCONFIG_PATH"
mkdir -p "${IRAMUTEQ_R_LIBS_USER:-/opt/iramuteq-r-library}"
mkdir -p /tmp/iramuteq-lite

export TMPDIR="${TMPDIR:-/tmp/iramuteq-lite}"
export MPLCONFIGDIR="$MPLCONFIG_PATH"
export R_LIBS_SITE="${R_LIBS_SITE:-${IRAMUTEQ_R_SYSTEM_LIBS:-/usr/lib/R/site-library:/usr/lib/R/library:/usr/local/lib/R/site-library:/usr/local/lib/R/library}}"

exec python3 -m uvicorn webapp.main:app --host 0.0.0.0 --port "$PORT"
