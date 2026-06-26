FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    MPLBACKEND=Agg \
    TF_CPP_MIN_LOG_LEVEL=2 \
    HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    HF_HOME=/home/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/app/.cache/huggingface \
    ULTRALYTICS_HOME=/home/app/.cache/ultralytics \
    APP_TICKET_ID=analyses_multi_modales \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A MODIFIER DANS COOLIFY
# - REDIS_URL
# - APP_TICKET_MAX_ACTIVE=1 pour garder l'exclusivite
# - APP_TICKET_COST selon la charge observee
# - APP_TICKET_TTL_SECONDS si l'analyse dure longtemps
# - CAPACITE_SERVEUR pour piloter la charge globale du VPS

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libsndfile1 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /home/app/.streamlit /home/app/.cache/huggingface /home/app/.cache/ultralytics \
    && chown -R app:app /app /home/app

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
