# Rendre audible

Adaptation VPS de l'application source `Rendre_audible`.

Cette version conserve les fonctionnalités d'origine :

- import d'un fichier audio `.wav`
- regroupement du signal par intervalles d'1 seconde
- calcul de la moyenne globale et de l'écart-type
- détection des observations atypiques avec le paramètre `k`
- graphique Plotly du signal condensé
- transcription Whisper optionnelle
- concordancier des observations atypiques
- export CSV du concordancier

## Variables d'environnement Coolify

#### Variables Redis / tickets

- `REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0`
- `APP_TICKET_ID=rendre_audible`
- `APP_TICKET_ENFORCED=1`
- `APP_TICKET_MAX_ACTIVE=1`
- `APP_TICKET_COST=2`
- `CAPACITE_SERVEUR=6`
- `APP_TICKET_TTL_SECONDS=3600`
- `APP_TICKET_MAX_WAITING=20`
- `APP_TICKET_WAIT_REFRESH_MS=10000`
- `APP_TICKET_HEARTBEAT_MS=300000`
- `APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release`
- `APP_TICKET_HIDDEN_RELEASE_SECONDS=300`

#### Variables applicatives

- `APP_DATA_DIR=/data/app`
- `WHISPER_MODEL_NAME=small`
- `WHISPER_LANGUAGE=fr`
- `PORT=8501`

## Dépendances système dans l'image

Le Dockerfile installe :

- `ffmpeg`
- `libsndfile1`

Cela couvre l'analyse audio avec `soundfile` et la transcription Whisper.
