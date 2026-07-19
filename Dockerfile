FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    APP_DATA_DIR=/tmp/appdata \
    APP_SESSION_TTL_HOURS=24 \
    APP_TICKET_ID=stopmotion_opticalflow \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_ACTIVE_STALE_SECONDS=900 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A AJUSTER DANS COOLIFY
# - REDIS_URL=redis://:motdepasse@redis:6379/0
# - APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=300 pour liberer si onglet cache trop longtemps
# - APP_TICKET_ACTIVE_STALE_SECONDS=900 pour nettoyer un ticket actif abandonne
# - APP_TICKET_WAIT_STALE_SECONDS=120 pour nettoyer rapidement une attente abandonnee
# - CAPACITE_SERVEUR=6 pour piloter la charge globale du VPS
# - PORT=8501
# - STREAMLIT_SERVER_MAX_UPLOAD_SIZE=4096 pour les grosses videos

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        unzip \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

# Deno est le runtime JavaScript recommandé par yt-dlp pour résoudre les
# challenges YouTube récents avant l'exposition des formats vidéo.
RUN curl -fsSL -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && rm -f /tmp/deno.zip \
    && deno --version

COPY requirements.txt /app/requirements.txt

ARG YTDLP_REFRESH=2026-07-19-stopmotion-alternate-googlevideo-cdn-01
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt \
    && echo "yt-dlp refresh ${YTDLP_REFRESH}" \
    && python -m pip install --upgrade --no-cache-dir "yt-dlp[default,curl-cffi]" \
    && python -m yt_dlp --version

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /tmp/appdata /home/app/.streamlit \
    && chown -R app:app /app /tmp/appdata /home/app

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
