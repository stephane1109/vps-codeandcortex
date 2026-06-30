# Deploiement OVH / Coolify

## Repertoire

- Depot : `stephane1109/vps-codeandcortex`
- Base directory : `/applications/scraping_reddit`

## Build

- Type : `Dockerfile`
- Port interne : `8501`

## Variables d'environnement possibles

- `PORT=8501`
- `STREAMLIT_SERVER_BASE_URL_PATH=` laisser vide sauf besoin de sous-chemin
- `REDDIT_CLIENT_ID=...`
- `REDDIT_CLIENT_SECRET=...`
- `REDDIT_USER_AGENT=...`
- `REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0`
- `APP_TICKET_ID=scraping_reddit`
- `APP_TICKET_ENFORCED=1`
- `APP_TICKET_MAX_ACTIVE=2`
- `APP_TICKET_COST=1`
- `CAPACITE_SERVEUR=6`
- `APP_TICKET_TTL_SECONDS=3600`
- `APP_TICKET_MAX_WAITING=20`
- `APP_TICKET_WAIT_REFRESH_MS=10000`
- `APP_TICKET_HEARTBEAT_MS=300000`
- `APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release`
- `APP_TICKET_HIDDEN_RELEASE_SECONDS=300`

## Notes

- L'application conserve aussi la saisie manuelle des identifiants Reddit dans l'interface.
- Le bouton `Liberer l'acces` apparait dans la sidebar si `REDIS_URL` et `APP_TICKET_*` sont configures.
- La date de debut est interpretee en UTC.
- L'export texte reste disponible depuis Streamlit.
