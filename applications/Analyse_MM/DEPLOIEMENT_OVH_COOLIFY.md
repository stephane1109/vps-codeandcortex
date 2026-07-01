# Deploiement Coolify - Analyse MM

## Branche conseillee

Utiliser la branche dediee :

`deploy-Analyse_MM`

Cette branche doit contenir uniquement les fichiers de l'application a la racine pour eviter les clonages inutiles du depot complet.

## Variables d'environnement

```env
REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0
APP_TICKET_ID=Analyse_MM
APP_TICKET_ENFORCED=1
APP_TICKET_MAX_ACTIVE=1
APP_TICKET_COST=4
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
APP_TICKET_HIDDEN_RELEASE_SECONDS=300
APP_DATA_DIR=/data/app
PORT=8501
```

## Reglages Coolify

- Build Pack : `Dockerfile`
- Base Directory : `/`
- Port expose : `8501`
- Healthcheck : laisser celui du Dockerfile

## Remarques

- `APP_DATA_DIR=/data/app` sert a conserver un espace de travail clair cote conteneur.
- `APP_TICKET_MAX_ACTIVE=1` est adapte a une application multimodale lourde.
- Si une analyse video est longue, augmente `APP_TICKET_TTL_SECONDS`.
