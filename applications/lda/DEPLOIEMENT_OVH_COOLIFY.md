# Déploiement OVH VPS avec Coolify

## 1. Position dans le dépôt

- dossier applicatif sur GitHub : `/applications/lda`

## 2. Configuration Coolify

Si tu déploies depuis `main` :

- `Base Directory` : `/applications/lda`
- `Dockerfile Location` : `Dockerfile`

Si tu déploies depuis la branche dédiée `deploy-lda` :

- `Base Directory` : `/`
- `Dockerfile Location` : `Dockerfile`

## 3. Port interne

```env
PORT=8501
```

Le `Ports Exposes` de Coolify doit aussi être `8501`.

## 4. Variables d'environnement recommandées

```env
REDIS_URL=redis://:2rdFbUtaTM25strnSVDecw3dHeTjMByzy12NAfhcKuPpJa270iPbr9zPzf5iECzH@pcsnxc6jxim5d2gqa6mbhijn:6379/0
APP_TICKET_ID=lda
APP_TICKET_ENFORCED=1
APP_TICKET_MAX_ACTIVE=1
APP_TICKET_COST=3
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
APP_TICKET_HIDDEN_RELEASE_SECONDS=300
PORT=8501
LDA_SPACY_MODEL=fr_core_news_md
```

## 5. Healthcheck

- path : `/_stcore/health`

## 6. Notes

- le modèle spaCy `fr_core_news_md` est installé dans l'image Docker
- le script source `LDA/lda.py` a été transformé en application Streamlit VPS
- l'archive ZIP contient les CSV, la visualisation HTML, l'histogramme et les wordclouds
