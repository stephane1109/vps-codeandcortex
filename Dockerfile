FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    MPLBACKEND=Agg \
    APP_DATA_DIR=/tmp/appdata \
    APP_TICKET_ID=vecteur-emotionnel \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A REGLER DANS COOLIFY
# - REDIS_URL=redis://:motdepasse@redis:6379/0
# - APP_TICKET_RELEASE_URL=https://ton-dashboard.codeandcortex.fr/api/tickets/release
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=0 pour desactiver la liberation auto sur onglet cache
# - CAPACITE_SERVEUR=6 pour coller a la capacite globale du VPS

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        unzip \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

# Deno permet à yt-dlp de résoudre les challenges JavaScript YouTube récents.
RUN curl -fsSL -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && rm -f /tmp/deno.zip \
    && deno --version

COPY requirements.txt /app/requirements.txt

ARG YTDLP_REFRESH=2026-07-19-vecteur-emotionnel-alternate-googlevideo-cdn-01
RUN pip install --no-cache-dir --upgrade pip "setuptools<81" wheel \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir --no-deps fer==22.4.0 \
    && echo "yt-dlp refresh ${YTDLP_REFRESH}" \
    && python -m pip install --upgrade --no-cache-dir "yt-dlp[default,curl-cffi]" \
    && python -m yt_dlp --version \
    && python -c "import pkg_resources; from fer import FER" \
    && rm -rf /root/.cache/pip /tmp/*

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /tmp/appdata /home/app/.streamlit \
    && chown -R app:app /app /tmp/appdata /home/app

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
