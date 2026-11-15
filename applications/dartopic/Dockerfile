FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none HF_HOME=/data/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PORT=8501
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* && useradd -m -u 10001 app \
    && mkdir -p /data/huggingface /home/app/nltk_data && chown -R app:app /data /home/app
COPY requirements.txt /app/requirements.txt
# Installation des roues CPU : éviter les dépendances CUDA inutiles sur le VPS.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader -d /usr/local/nltk_data stopwords
ENV NLTK_DATA=/usr/local/nltk_data
COPY . /app
RUN chown -R app:app /app
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=3)"
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.maxUploadSize=100"]
