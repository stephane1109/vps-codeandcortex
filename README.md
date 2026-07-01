# Analyse MM - version VPS

Application Streamlit multimodale pour :

- preparer une video source depuis YouTube ou un fichier local
- extraire video, audio et images
- analyser l'audio
- analyser les mouvements et les anomalies visuelles
- produire des timelapses
- transcrire et chercher des cooccurrences horodatees

## Adaptation VPS

Cette version est preparee pour un deploiement sur VPS/Coolify avec :

- Dockerfile autonome
- compatibilite `PORT` et `STREAMLIT_SERVER_BASE_URL_PATH`
- controle d'acces Redis via `ticket_gate.py`
- stockage de travail configurable via `APP_DATA_DIR`
- dependances multimedia et Whisper installees dans l'image

## Variables d'environnement utiles

- `REDIS_URL`
- `APP_TICKET_ID=Analyse_MM`
- `APP_TICKET_MAX_ACTIVE=1`
- `APP_TICKET_COST=4`
- `CAPACITE_SERVEUR=6`
- `APP_TICKET_TTL_SECONDS=3600`
- `APP_TICKET_MAX_WAITING=20`
- `APP_TICKET_WAIT_REFRESH_MS=10000`
- `APP_TICKET_HEARTBEAT_MS=300000`
- `APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release`
- `APP_TICKET_HIDDEN_RELEASE_SECONDS=300`
- `APP_DATA_DIR=/data/app`
- `PORT=8501`

## Notes

- L'application conserve toutes les fonctionnalites de l'interface d'origine.
- Les traitements longs relancent un heartbeat ticket pour eviter une liberation trop rapide.
- Si un calcul est tres long, augmente `APP_TICKET_TTL_SECONDS`.
