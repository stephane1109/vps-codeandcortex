FROM rocker/r-ver:4.4.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IRAMUTEQ_APP_DATA_DIR=/data/app \
    IRAMUTEQ_R_LIBS_USER=/opt/iramuteq-r-library \
    IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=1 \
    RGL_USE_NULL=TRUE \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    git \
    curl \
    wget \
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
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app

COPY docker/requirements-python.txt /tmp/requirements-python.txt
RUN pip install --upgrade pip setuptools wheel && pip install -r /tmp/requirements-python.txt

WORKDIR /app

COPY --chown=app:app . /app

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/app /opt/iramuteq-r-library /tmp/iramuteq-lite \
    && chown -R app:app /app /data/app /opt/iramuteq-r-library /tmp/iramuteq-lite

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD wget -qO- "http://127.0.0.1:${PORT:-8000}/api/health" >/dev/null || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
