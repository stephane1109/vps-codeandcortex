#!/bin/sh
set -eu
# Un seul moteur FastAPI ; Streamlit est relayé derrière le même port public.
exec xvfb-run -a -s "-screen 0 1440x1000x24 -nolisten tcp" \
    python /app/lancer_interface.py --host 0.0.0.0 --port "${PORT:-8501}"
