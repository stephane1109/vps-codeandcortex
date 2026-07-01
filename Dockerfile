FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    PORT=8501 \
    APP_DATA_DIR=/data/app \
    XDG_CACHE_HOME=/home/app/.cache \
    WHISPER_CACHE_DIR=/home/app/.cache/whisper \
    WHISPER_MODEL_NAME=small \
    APP_TICKET_ID=analyse_debit_parole \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A REGLER DANS COOLIFY
# - REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0
# - APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=300
# - APP_TICKET_MAX_ACTIVE=1 pour reserver l'application a un seul utilisateur
# - APP_TICKET_COST=4 pour une application relativement lourde
# - CAPACITE_SERVEUR=6 pour coller a la capacite globale du VPS
# - APP_TICKET_TTL_SECONDS=3600 si une analyse longue doit garder son ticket
# - APP_DATA_DIR=/data/app pour conserver les exports sur le serveur
# - WHISPER_MODEL_NAME=small pour conserver le comportement d'origine

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app

COPY requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /home/app/.streamlit /home/app/.cache/whisper "${APP_DATA_DIR}" \
    && chown -R app:app /app /home/app "${APP_DATA_DIR}"

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
