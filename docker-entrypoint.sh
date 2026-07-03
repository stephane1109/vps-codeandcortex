#!/bin/sh
set -eu

PORT="${PORT:-8000}"
export PORT

cd /app
exec Rscript /app/start.R
