# Deploiement OVH VPS avec Coolify

Cette application est prete pour un deploiement sur Coolify via le `Dockerfile` du dossier.

## 1. Position dans le depot

- dossier applicatif : `/applications/cooccurrencesmotpivot`

## 2. Configuration Coolify

Si tu deployes depuis `main` :

- `Base Directory` : `/applications/cooccurrencesmotpivot`
- `Dockerfile Location` : `Dockerfile`

Si tu deployes depuis une branche dediee `deploy-cooccurrencesmotpivot` :

- `Base Directory` : `/`
- `Dockerfile Location` : `Dockerfile`

## 3. Port interne

```env
PORT=8501
```

Le `Ports Exposes` de Coolify doit aussi etre `8501`.

## 4. Variables d'environnement recommandees

```env
REDIS_URL=redis://:2rdFbUtaTM25strnSVDecw3dHeTjMByzy12NAfhcKuPpJa270iPbr9zPzf5iECzH@pcsnxc6jxim5d2gqa6mbhijn:6379/0
APP_TICKET_ID=cooccurrencesmotpivot
APP_TICKET_ENFORCED=1
APP_TICKET_MAX_ACTIVE=2
APP_TICKET_COST=2
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
APP_TICKET_HIDDEN_RELEASE_SECONDS=300
PORT=8501
```

## 5. Healthcheck recommande

- path : `/_stcore/health`

## 6. Notes techniques

- le modele spaCy `fr_core_news_md` est installe a la build
- aucun telechargement supplementaire ne doit etre fait au runtime
- l'application conserve toutes les options du script source
- le bouton `Liberer l'acces` apparait dans la sidebar si Redis est configure
