#!/bin/sh
set -eu

APP_DATA_DIR="${IRAMUTEQ_APP_DATA_DIR:-/data/app}"
MPLCONFIG_PATH="${MPLCONFIGDIR:-$APP_DATA_DIR/mplconfig}"
PORT="${PORT:-8000}"
PYTHON_SITE_DIR="${IRAMUTEQ_PYTHON_SITE_DIR:-$APP_DATA_DIR/python-site-packages}"
R_LIBRARY_DIR="${IRAMUTEQ_R_LIBS_USER:-$APP_DATA_DIR/r-library}"

mkdir -p "$APP_DATA_DIR"
mkdir -p "$APP_DATA_DIR/jobs"
mkdir -p "$APP_DATA_DIR/downloads"
mkdir -p "$APP_DATA_DIR/dictionnaires"
mkdir -p "$MPLCONFIG_PATH"
mkdir -p "$PYTHON_SITE_DIR"
mkdir -p "$R_LIBRARY_DIR"
mkdir -p /tmp/iramuteq-lite

export TMPDIR="${TMPDIR:-/tmp/iramuteq-lite}"
export MPLCONFIGDIR="$MPLCONFIG_PATH"
export IRAMUTEQ_PYTHON_SITE_DIR="$PYTHON_SITE_DIR"
export IRAMUTEQ_R_LIBS_USER="$R_LIBRARY_DIR"
export PYTHONPATH="${PYTHON_SITE_DIR}${PYTHONPATH:+:$PYTHONPATH}"
export R_LIBS_SITE="${R_LIBS_SITE:-${IRAMUTEQ_R_SYSTEM_LIBS:-/usr/lib/R/site-library:/usr/lib/R/library:/usr/local/lib/R/site-library:/usr/local/lib/R/library}}"

exec python3 -m uvicorn webapp.main:app --host 0.0.0.0 --port "$PORT"
