# Analyse du debit de parole

Application Streamlit adaptee pour le VPS.

Fonctions conservees :

- telechargement d'une video YouTube
- decoupage d'un segment temporel
- analyse du debit de parole
- mode de segmentation `whisper`
- mode de segmentation `ponctuation`
- analyse des pauses
- exports TXT, CSV, HTML et PNG

Adaptations VPS ajoutees :

- stockage serveur sous `APP_DATA_DIR`
- telechargement direct des exports depuis l'interface
- integration du ticket Redis dans la colonne laterale
- Dockerfile et entrypoint compatibles Coolify

## Variables d'environnement principales

#### Ticket / file d'attente

- `REDIS_URL`
- `APP_TICKET_ID`
- `APP_TICKET_ENFORCED`
- `APP_TICKET_MAX_ACTIVE`
- `APP_TICKET_COST`
- `CAPACITE_SERVEUR`
- `APP_TICKET_TTL_SECONDS`
- `APP_TICKET_MAX_WAITING`
- `APP_TICKET_WAIT_REFRESH_MS`
- `APP_TICKET_HEARTBEAT_MS`
- `APP_TICKET_RELEASE_URL`
- `APP_TICKET_HIDDEN_RELEASE_SECONDS`

#### Stockage / application

- `PORT`
- `APP_DATA_DIR`
- `WHISPER_MODEL_NAME`
