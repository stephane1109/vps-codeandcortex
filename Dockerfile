FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    MPLBACKEND=Agg \
    PORT=8501 \
    APP_DATA_DIR=/data/app \
    XDG_CACHE_HOME=/home/app/.cache \
    HF_HOME=/home/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/app/.cache/huggingface \
    APP_TICKET_ID=Analyse_MM \
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
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=300 pour liberer aussi un onglet cache trop longtemps
# - APP_DATA_DIR=/data/app pour stocker les fichiers temporaires et les sorties de travail
# - APP_TICKET_MAX_ACTIVE=1 pour garder une seule session active
# - APP_TICKET_COST=4 pour compter cette application comme application lourde
# - APP_TICKET_TTL_SECONDS si une analyse peut durer plus longtemps que prevu
# - CAPACITE_SERVEUR=6 pour coller a la capacite globale du VPS
# - STREAMLIT_SERVER_BASE_URL_PATH uniquement si Coolify t'impose un sous-chemin

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libsndfile1 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /home/app/.streamlit /home/app/.cache/huggingface "${APP_DATA_DIR}" \
    && chown -R app:app /app /home/app "${APP_DATA_DIR}"

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
