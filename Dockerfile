FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    PORT=8501 \
    APP_DATA_DIR=/tmp/appdata \
    APP_FFMPEG_TIMEOUT_SECONDS=3600 \
    APP_TICKET_ID=extraction-multimedia \
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
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=300 pour liberer un onglet laisse en arriere-plan
# - APP_TICKET_MAX_ACTIVE=1 pour reserver cette application a un seul utilisateur a la fois
# - APP_TICKET_COST=4 et CAPACITE_SERVEUR=6 pour rester coherent avec le reste du VPS
# - APP_TICKET_TTL_SECONDS si tu veux allonger ou raccourcir la duree d'un ticket
# - APP_FFMPEG_TIMEOUT_SECONDS=3600 pour fixer le temps maximal d'une commande ffmpeg
# - YTDLP_FORCE_IPV4=1 ou YTDLP_FORCE_IPV6=1 seulement si le réseau Docker/VPS l'exige
# - YTDLP_SOCKET_TIMEOUT_SECONDS=10, YTDLP_RETRIES=1, YTDLP_FRAGMENT_RETRIES=1 ajustent les timeouts réseau yt-dlp
# - YTDLP_PROXY_URL=http://user:pass@host:port ou socks5://user:pass@host:port fait sortir yt-dlp via un proxy
# - YTDLP_GEO_VERIFICATION_PROXY_URL peut utiliser un proxy uniquement pour la vérification géographique yt-dlp
# - YTDLP_SOURCE_ADDRESS permet de fixer l'adresse source si plusieurs IP sont configurées sur le VPS
# - YTDLP_IMPERSONATE=chrome est optionnel. Ne pas le mettre par defaut :
#   certaines versions de l'API Python yt-dlp peuvent echouer avec AssertionError.
# - YTDLP_YOUTUBE_PO_TOKEN_ARGS=web.gvs+XXX si YouTube impose un PO token manuel
# - Ne pas definir YTDLP_YOUTUBE_FORMATS=missing_pot pour cette application :
#   cela peut masquer les formats MP4 classiques et bloquer l'extraction.

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

# Deno est le runtime JavaScript recommande par yt-dlp pour yt-dlp-ejs.
# Cela permet a yt-dlp de traiter les challenges JavaScript YouTube récents.
RUN curl -fsSL -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && rm -f /tmp/deno.zip \
    && deno --version

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt

# YouTube change souvent ses formats/extracteurs. Cette ligne est volontairement
# séparée pour forcer une couche Docker explicite et faciliter les rebuilds Coolify.
ARG YTDLP_REFRESH=2026-07-18-proxy-egress-12
RUN echo "yt-dlp refresh ${YTDLP_REFRESH}" \
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
