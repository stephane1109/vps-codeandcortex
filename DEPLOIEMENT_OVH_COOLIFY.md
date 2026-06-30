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

## Notes

- L'application conserve aussi la saisie manuelle des identifiants Reddit dans l'interface.
- La date de debut est interpretee en UTC.
- L'export texte reste disponible depuis Streamlit.
