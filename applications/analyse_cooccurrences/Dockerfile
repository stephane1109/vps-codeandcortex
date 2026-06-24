FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh && chown -R app:app /app

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=3).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
