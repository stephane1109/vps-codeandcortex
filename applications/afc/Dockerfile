# Image Python avec R et FactoMineR fournis par Debian Bookworm.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    AFC_TIMEOUT_SECONDS=180

RUN apt-get update && apt-get install -y --no-install-recommends \
    r-base-core \
    r-cran-factominer \
    curl \
    fonts-dejavu-core \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && Rscript -e "stopifnot(requireNamespace('FactoMineR', quietly = TRUE))"

RUN useradd --create-home --uid 10001 analyste
COPY --chown=analyste:analyste . /app
USER analyste

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl --fail http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "application.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
