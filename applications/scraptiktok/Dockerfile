FROM python:3.11-slim-bookworm
ARG INSTALL_VIDEO=0
ENV INSTALL_VIDEO=${INSTALL_VIDEO}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501 \
    CHROME_BINARY=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver \
    CHROME_NO_SANDBOX=1 \
    SCRAPTIKTOK_HEADLESS=0 \
    SE_AVOID_STATS=true \
    DATA_DIR=/app/data

# Navigateur et pilote proviennent du même dépôt Debian : versions compatibles.
# Xvfb fournit l'écran du navigateur sur le VPS, sans bureau ni accès VNC public.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
       xvfb xauth tini fonts-noto-color-emoji fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app

WORKDIR /app
COPY requirements.txt requirements-video.txt ./
RUN pip install -r requirements.txt
# Le profil texte ne télécharge aucun moteur ni modèle audiovisuel.
RUN if [ "$INSTALL_VIDEO" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
      && rm -rf /var/lib/apt/lists/* \
      && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
      && pip install -r requirements-video.txt; fi
COPY . .
RUN mkdir -p /app/data /app/.selenium-cache \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R app:app /app /home/app

USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/healthz',timeout=3).read()"
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
