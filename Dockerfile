FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    PORT=8501 \
    APP_WORKDIR=/tmp/mp3-to-text \
    XDG_CACHE_HOME=/home/app/.cache \
    WHISPER_CACHE_DIR=/home/app/.cache/whisper \
    WHISPER_PROFILE_DEFAULT=faster-whisper \
    WHISPER_LANGUAGE_DEFAULT=fr \
    WHISPER_COMPUTE_TYPE=int8 \
    APP_TICKET_ID=mp3_to_text \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A REGLER DANS COOLIFY
# - REDIS_URL=redis://:motdepasse@redis:6379/0
# - ne pas definir APP_TICKET_DEFAULT_REDIS_URL dans cette application
# - APP_TICKET_RELEASE_URL=https://ton-dashboard.codeandcortex.fr/api/tickets/release
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=0 pour desactiver, sinon liberation auto si onglet cache
# - WHISPER_PROFILE_DEFAULT=faster-whisper pour choisir le profil par defaut visible dans l'application
# - WHISPER_LANGUAGE_DEFAULT=fr pour preselectionner la langue, utiliser en pour l'anglais
# - WHISPER_COMPUTE_TYPE=int8 pour le CPU, a augmenter seulement si le serveur suit
# - APP_TICKET_MAX_ACTIVE pour autoriser plus d'un utilisateur
# - APP_TICKET_COST pour ajuster la charge serveur
# - APP_TICKET_TTL_SECONDS si une transcription peut durer longtemps

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        unzip \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app

# Deno est le runtime JavaScript recommande par yt-dlp pour les challenges YouTube recents.
RUN curl -fsSL -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && rm -f /tmp/deno.zip \
    && deno --version

COPY requirements.txt /app/requirements.txt

# #### BACKEND WHISPER INSTALLE DANS L'IMAGE
# L'interface permet ensuite de choisir explicitement les profils
# `faster-whisper`, `sm` et `md`, sans figer l'utilisateur dans un seul
# modele visible.
ARG YTDLP_REFRESH=2026-07-13
RUN pip install -r /app/requirements.txt \
    && echo "yt-dlp refresh ${YTDLP_REFRESH}" \
    && python -m pip install --upgrade --no-cache-dir "yt-dlp[default,curl-cffi]" \
    && python -m yt_dlp --version

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /home/app/.streamlit /home/app/.cache/whisper "${APP_WORKDIR}" \
    && chown -R app:app /app /home/app "${APP_WORKDIR}"

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
