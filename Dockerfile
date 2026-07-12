FROM rocker/r2u:jammy

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=8000 \
    APP_DATA_DIR=/data/app \
    CHDRAINETTE_APP_DATA_DIR=/data/app \
    CHDRAINETTE_R_LIBS_USER=/data/app/r-library \
    CHDRAINETTE_CACHE_DIR=/data/app/cache \
    R_LIBS_USER=/data/app/r-library \
    APP_TICKET_ID=chdrainette \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=300 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=30000 \
    APP_TICKET_WAIT_STALE_SECONDS=120 \
    APP_TICKET_FAIL_OPEN=1 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A REGLER DANS COOLIFY
# - REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0
# - APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
# - APP_TICKET_HIDDEN_RELEASE_SECONDS=300
# - APP_TICKET_MAX_ACTIVE=1
# - APP_TICKET_COST=4
# - CAPACITE_SERVEUR=6
# - APP_TICKET_TTL_SECONDS=300
# - APP_TICKET_WAIT_STALE_SECONDS=120
# - APP_TICKET_FAIL_OPEN=1 pour ne pas bloquer l'application si Redis est temporairement indisponible
# - PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
        pkg-config \
        curl \
        python3 \
        python3-redis \
        redis-tools \
        zip \
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
    && binary_r_packages="\
      r-cran-bslib \
      r-cran-dplyr \
      r-cran-factominer \
      r-cran-htmltools \
      r-cran-markdown \
      r-cran-quanteda \
      r-cran-quanteda.textstats \
      r-cran-rcolorbrewer \
      r-cran-remotes \
      r-cran-shiny \
      r-cran-stopwords \
      r-cran-stringi \
      r-cran-wordcloud \
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
  CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-8000}/" >/dev/null'

ENTRYPOINT ["/app/docker-entrypoint.sh"]
