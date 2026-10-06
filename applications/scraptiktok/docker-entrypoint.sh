#!/bin/sh
set -eu

# Un processus Uvicorn : le registre de sessions et la limite de navigateurs
# sont partagés en mémoire. Ne pas ajouter --workers > 1 ni --reload en production.
exec xvfb-run -a -s "-screen 0 1440x1000x24 -nolisten tcp" \
    python -m uvicorn webapp:app --host 0.0.0.0 --port "${PORT:-8501}" \
    --workers 1 --timeout-graceful-shutdown 30
