FROM rocker/r-ver:4.4.1

ARG IRAMUTEQ_BUILD_BOOTSTRAP=1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IRAMUTEQ_APP_DATA_DIR=/data/app \
    IRAMUTEQ_PYTHON_SITE_DIR=/data/app/python-site-packages \
    IRAMUTEQ_R_LIBS_USER=/data/app/r-library \
    IRAMUTEQ_R_SYSTEM_LIBS=/usr/lib/R/site-library:/usr/lib/R/library:/usr/local/lib/R/site-library:/usr/local/lib/R/library \
    R_LIBS_SITE=/usr/lib/R/site-library:/usr/lib/R/library:/usr/local/lib/R/site-library:/usr/local/lib/R/library \
    IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=1 \
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
# - IRAMUTEQ_R_LIBS_USER=/data/app/r-library pour conserver
#   les packages R installes au runtime dans le volume persistant Coolify
# - IRAMUTEQ_PYTHON_SITE_DIR=/data/app/python-site-packages pour conserver
#   les packages Python installes au runtime dans le volume persistant
# #### MODE VPS / COOLIFY
# Par defaut, on preinstalle maintenant le bootstrap R/CHD dans l'image
# (`IRAMUTEQ_BUILD_BOOTSTRAP=1`) pour eviter un premier lancement bloque
# plusieurs minutes sur le controle des dependances.
# #### MODE BUILD COMPLET
# Si besoin, vous pouvez desactiver ce bootstrap build-time via
# `IRAMUTEQ_BUILD_BOOTSTRAP=0` et retomber sur l'installation au runtime.
# #### NOTE BUILD R
# USE_BUNDLED_LIBUV=1 reste active pour securiser l'installation du package R `fs`
# si Coolify ou le miroir CRAN ne voit pas correctement `libuv.pc`.
# #### BIBLIOTHEQUES R SYSTEME
# Les paquets `r-cran-*` installes via `apt` tombent dans `/usr/lib/R/...` alors que
# `rocker/r-ver` utilise aussi `/usr/local/lib/R/...`. On force ici la visibilite des
# deux emplacements pour eviter que le bootstrap recompilie inutilement depuis CRAN.
# #### COMPILATION Rcpp / quanteda
# `quanteda` retombe en compilation source sur cette image Ubuntu/R. Certains couples
# GCC + Rcpp declenchent un `-Werror=format-security` dans les headers Rcpp, ce qui
# casse le build alors qu'il ne s'agit pas d'une erreur fonctionnelle du package.
# On neutralise uniquement cette promotion warning -> error dans Makevars.

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
    && binary_r_packages="\
      r-cran-ape \
      r-cran-broom \
      r-cran-bslib \
      r-cran-car \
      r-cran-cardata \
      r-cran-colorspace \
      r-cran-corrplot \
      r-cran-cowplot \
      r-cran-dplyr \
      r-cran-dt \
      r-cran-ellipse \
      r-cran-emmeans \
      r-cran-factoextra \
      r-cran-factominer \
      r-cran-flashclust \
      r-cran-fontawesome \
      r-cran-fs \
      r-cran-ggplot2 \
      r-cran-ggpubr \
      r-cran-ggrepel \
      r-cran-ggsignif \
      r-cran-gridextra \
      r-cran-htmltools \
      r-cran-htmlwidgets \
      r-cran-igraph \
      r-cran-irlba \
      r-cran-isoband \
      r-cran-jquerylib \
      r-cran-jsonlite \
      r-cran-knitr \
      r-cran-later \
      r-cran-lazyeval \
      r-cran-lme4 \
      r-cran-markdown \
      r-cran-modeltools \
      r-cran-nloptr \
      r-cran-pbkrtest \
      r-cran-plotly \
      r-cran-promises \
      r-cran-proxy \
      r-cran-purrr \
      r-cran-quanteda \
      r-cran-quantreg \
      r-cran-rcppeigen \
      r-cran-rcolorbrewer \
      r-cran-reticulate \
      r-cran-rgexf \
      r-cran-rgl \
      r-cran-rmarkdown \
      r-cran-rstatix \
      r-cran-scales \
      r-cran-scatterplot3d \
      r-cran-shiny \
      r-cran-shinyfiles \
      r-cran-slam \
      r-cran-sna \
      r-cran-snowballc \
      r-cran-stopwords \
      r-cran-stringi \
      r-cran-stringr \
      r-cran-tibble \
      r-cran-tidyr \
      r-cran-tm \
      r-cran-topicmodels \
      r-cran-vctrs \
      r-cran-viridis \
      r-cran-viridislite \
      r-cran-visnetwork \
      r-cran-wordcloud \
      r-cran-xml2 \
      r-cran-yaml \
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
         echo "Installing available binary R packages:$available_r_packages"; \
         apt-get install -y --no-install-recommends $available_r_packages; \
       fi \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/R /root/.R \
    && printf '%s\n' \
      'CFLAGS += -Wno-error=format-security' \
      'CXXFLAGS += -Wno-error=format-security' \
      'CXX11FLAGS += -Wno-error=format-security' \
      'CXX14FLAGS += -Wno-error=format-security' \
      'CXX17FLAGS += -Wno-error=format-security' \
      'CXX20FLAGS += -Wno-error=format-security' \
      > /etc/R/Makevars.site \
    && cp /etc/R/Makevars.site /root/.R/Makevars

RUN useradd --create-home --shell /bin/bash app
RUN mkdir -p /home/app/.R \
    && cp /etc/R/Makevars.site /home/app/.R/Makevars \
    && chown -R app:app /home/app/.R

COPY docker/requirements-python.txt /tmp/requirements-python.txt
RUN pip install --upgrade pip setuptools wheel && pip install -r /tmp/requirements-python.txt

WORKDIR /app

COPY --chown=app:app . /app

# #### VPS / COOLIFY
# Le bootstrap build-time est prefere pour livrer une image deja exploitable
# des le premier lancement utilisateur. Si vous manquez encore de temps de build
# sur Coolify, vous pouvez explicitement revenir a `IRAMUTEQ_BUILD_BOOTSTRAP=0`.
# #### BUILD COMPLET OPTIONNEL
# Definir `IRAMUTEQ_BUILD_BOOTSTRAP=1` si vous souhaitez a nouveau:
# - preinstaller les packages R au build
# - executer le smoke-test CHD pendant le build
RUN python3 -c "import numpy, sklearn, matplotlib, pyLDAvis, wordcloud, altair, vl_convert" \
    && if [ "${IRAMUTEQ_BUILD_BOOTSTRAP}" = "1" ]; then \
         Rscript /app/backend/r/bootstrap_iramuteq_env.R --mode install \
         && sh /app/docker/smoke-test-chd.sh; \
       else \
         echo "Build R/CHD saute pour Coolify (IRAMUTEQ_BUILD_BOOTSTRAP=${IRAMUTEQ_BUILD_BOOTSTRAP})."; \
       fi

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data/app /data/app/r-library /data/app/python-site-packages /tmp/iramuteq-lite \
    && chown -R app:app /app /data/app /tmp/iramuteq-lite

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD wget -qO- "http://127.0.0.1:${PORT:-8000}/api/health" >/dev/null || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
