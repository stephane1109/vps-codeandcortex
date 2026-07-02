FROM rocker/r2u:jammy

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    APP_DATA_DIR=/data/app \
    CHDRAINETTE_APP_DATA_DIR=/data/app \
    CHDRAINETTE_R_LIBS_USER=/data/app/r-library \
    CHDRAINETTE_CACHE_DIR=/data/app/cache \
    R_LIBS_USER=/data/app/r-library \
    APP_TICKET_ID=chdrainette \
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
# - APP_TICKET_MAX_ACTIVE=1 pour garder cette CHD Rainette sur un seul utilisateur a la fois
# - APP_TICKET_COST=4 pour compter cette application comme application lourde
# - CAPACITE_SERVEUR=6 pour coller a la capacite globale du VPS
# - APP_TICKET_TTL_SECONDS=3600 si l'analyse peut durer longtemps
# - APP_DATA_DIR=/data/app pour conserver les jobs et les sorties cote serveur
# - CHDRAINETTE_APP_DATA_DIR=/data/app pour que le backend web et le R utilisent le meme volume
# - CHDRAINETTE_R_LIBS_USER=/data/app/r-library pour les packages R persistants
# - CHDRAINETTE_CACHE_DIR=/data/app/cache pour les caches NLP / spaCy
# - PORT=8000 pour FastAPI / Uvicorn

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        gfortran \
        pkg-config \
        git \
        curl \
        wget \
        ffmpeg \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        libfontconfig1-dev \
        libcairo2-dev \
        libfreetype6-dev \
        libfribidi-dev \
        libharfbuzz-dev \
        libpng-dev \
        libjpeg-dev \
        libtiff-dev \
        libicu-dev \
        libgit2-dev \
        libgsl-dev \
        libudunits2-dev \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && binary_r_packages="\
      r-cran-dplyr \
      r-cran-factominer \
      r-cran-htmltools \
      r-cran-igraph \
      r-cran-jsonlite \
      r-cran-quanteda \
      r-cran-quanteda.textstats \
      r-cran-rcolorbrewer \
      r-cran-remotes \
      r-cran-stopwords \
      r-cran-stringi \
      r-cran-wordcloud \
      r-cran-xml2 \
    " \
    && available_r_packages="" \
    && for pkg in $binary_r_packages; do \
         if apt-cache show "$pkg" >/dev/null 2>&1; then \
           available_r_packages="$available_r_packages $pkg"; \
         else \
           echo "APT package unavailable on this base image, skipped: $pkg"; \
         fi; \
       done \
    && if [ -n "$available_r_packages" ]; then \
         apt-get install -y --no-install-recommends $available_r_packages; \
       fi \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir --prefer-binary --no-compile -r /app/requirements.txt

COPY backend/install-r-packages.R /tmp/install-r-packages.R
RUN Rscript /tmp/install-r-packages.R

COPY . /app

RUN useradd --create-home --shell /bin/bash app \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/app /data/app/r-library /data/app/cache \
    && chown -R app:app /app /home/app /data/app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
  CMD python3 -c "import os, urllib.request; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
