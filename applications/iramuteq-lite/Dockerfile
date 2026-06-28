FROM rocker/r-ver:4.4.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IRAMUTEQ_APP_DATA_DIR=/data/app \
    IRAMUTEQ_R_LIBS_USER=/opt/iramuteq-r-library \
    IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=0 \
    USE_BUNDLED_LIBUV=1 \
    RGL_USE_NULL=TRUE \
    PORT=8000 \
    APP_TICKET_ID=iramuteq-lite \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=30000 \
    APP_TICKET_ENFORCED=1

# #### VARIABLES D'ENVIRONNEMENT A MODIFIER DANS COOLIFY
# - REDIS_URL
# - APP_TICKET_MAX_ACTIVE=1 pour conserver l'exclusivite
# - APP_TICKET_COST selon la charge reelle du VPS
# - APP_TICKET_TTL_SECONDS si une analyse peut durer longtemps
# #### NOTE BUILD R
# USE_BUNDLED_LIBUV=1 reste active pour securiser l'installation du package R `fs`
# si Coolify ou le miroir CRAN ne voit pas correctement `libuv.pc`.

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    gfortran \
    git \
    curl \
    wget \
    pkg-config \
    python3 \
    python3-pip \
    ffmpeg \
    python3-venv \
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
    libgl1 \
    libglpk-dev \
    libglu1-mesa-dev \
    libglib2.0-0 \
    libgsl-dev \
    libuv1-dev \
    libudunits2-dev \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app

COPY docker/requirements-python.txt /tmp/requirements-python.txt
RUN pip install --upgrade pip setuptools wheel && pip install -r /tmp/requirements-python.txt

WORKDIR /app

COPY --chown=app:app . /app

# #### PREINSTALLATION DES DEPENDANCES R
# On installe les packages R necessaires pendant le build Docker pour eviter
# que le premier utilisateur bloque sur un bootstrap long ou incomplet.
# #### TEST DE FUMEE CHD
# Une vraie analyse CHD est lancee pendant le build afin d'eviter
# de deployer une image qui demarre mais ne produit aucun resultat exploitable.
RUN Rscript /app/backend/r/bootstrap_iramuteq_env.R --mode install \
    && python3 -c "import numpy, sklearn, matplotlib, pyLDAvis, wordcloud, altair, vl_convert" \
    && sh /app/docker/smoke-test-chd.sh

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/app /opt/iramuteq-r-library /tmp/iramuteq-lite \
    && chown -R app:app /app /data/app /opt/iramuteq-r-library /tmp/iramuteq-lite

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD wget -qO- "http://127.0.0.1:${PORT:-8000}/api/health" >/dev/null || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
