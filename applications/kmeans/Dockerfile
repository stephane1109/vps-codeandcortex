FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    MPLBACKEND=Agg \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    KMEANS_OUTPUT_DIR=/tmp/kmeans \
    HF_HOME=/home/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/home/app/.cache/sentence-transformers \
    NLTK_DATA=/home/app/nltk_data \
    APP_TICKET_ID=kmeans \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_ACTIVE_STALE_SECONDS=900 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_HIDDEN_RELEASE_SECONDS=300 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A AJUSTER DANS COOLIFY
# - REDIS_URL
# - APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=300 pour liberer si l'onglet reste cache
# - APP_TICKET_MAX_ACTIVE
# - APP_TICKET_COST
# - CAPACITE_SERVEUR
# - APP_TICKET_TTL_SECONDS
# - APP_TICKET_ACTIVE_STALE_SECONDS=900 pour nettoyer un ancien ticket actif sans heartbeat
# - PORT=8501
# - KMEANS_OUTPUT_DIR=/tmp/kmeans
# - KMEANS_SENTENCE_MODEL=all-MiniLM-L6-v2

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && mkdir -p /home/app/.cache/huggingface /home/app/.cache/sentence-transformers /home/app/nltk_data "${KMEANS_OUTPUT_DIR}"

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt \
    && python -m nltk.downloader -d /home/app/nltk_data stopwords

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /home/app/.streamlit "${KMEANS_OUTPUT_DIR}" \
    && chown -R app:app /app /home/app "${KMEANS_OUTPUT_DIR}"

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
