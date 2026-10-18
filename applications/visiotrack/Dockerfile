FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_SERVER_MAX_UPLOAD_SIZE=1024 \
    APP_TICKET_ENFORCED=1 \
    APP_TICKET_ID=visiotrack \
    APP_TICKET_MAX_ACTIVE=1 \
    APP_TICKET_COST=4 \
    CAPACITE_SERVEUR=10 \
    APP_TICKET_TTL_SECONDS=3600 \
    APP_TICKET_MAX_WAITING=20 \
    APP_TICKET_WAIT_REFRESH_MS=10000 \
    APP_TICKET_HEARTBEAT_MS=300000 \
    APP_TICKET_HIDDEN_RELEASE_SECONDS=0 \
    APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release \
    YOLO_AUTOINSTALL=false \
    YOLO_CONFIG_DIR=/home/app/.config/ultralytics \
    VISIOTRACK_MODEL=/app/models/yolo11s.pt \
    VISIOTRACK_CPU_THREADS=2 \
    OMP_NUM_THREADS=2 \
    PORT=8501

WORKDIR /app

# ffprobe fournit la durée de la piste vidéo ; ffmpeg sert aussi à yt-dlp.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

COPY requirements.txt .

# Installer les roues CPU de PyTorch pour éviter plusieurs Go de bibliothèques CUDA.
# Ultralytics déclare OpenCV avec interface graphique : le remplacer ensuite par
# la version headless, qui expose exactement le même module Python cv2.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 torchvision==0.21.0 \
    && pip install -r requirements.txt \
    && pip uninstall -y opencv-python opencv-python-headless \
    && pip install 'opencv-python-headless==4.11.0.86'

# Vérifier la conversion des tableaux dès la construction, avant le déploiement.
RUN python -c "import pandas as pd; import pyarrow as pa; tableau = pd.DataFrame({'categorie': ['smartphone'], 'duree_visibilite_s': [1.0]}); assert pa.Table.from_pandas(tableau).to_pandas().equals(tableau)"

# Deno est le moteur JavaScript recommandé par yt-dlp pour les pages YouTube.
COPY --from=denoland/deno:bin-2.5.6 /deno /usr/local/bin/deno

COPY --chown=app:app . .
RUN mkdir -p /app/models /home/app/.config/ultralytics \
    && chown -R app:app /app /home/app
USER app

# Télécharger les poids pendant la construction : aucune attente au premier lot.
RUN python -c "from detection import charger_modele; charger_modele()"

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health',timeout=3)"
CMD ["sh", "-c", "exec streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
