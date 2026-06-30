# Extraction multimedia URL - version VPS

Application Streamlit pour :

- telecharger une video YouTube
- importer une video locale `.mp4`
- normaliser la video en MP4
- extraire un intervalle ou toute la video
- generer des sorties `mp4`, `mp3`, `wav`, images `1 FPS`, images `25 FPS`
- generer un timelapse

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- isolation des fichiers par session utilisateur dans `/tmp/appdata/sessions/...`
- nettoyage automatique des anciennes sessions
- conteneur Docker autonome avec `ffmpeg`
- configuration Streamlit headless
- limite d'upload relevee a `4096 Mo`

## Lancer localement avec Docker

```bash
docker build -t extraction-multimedia .
docker run --rm -p 8501:8501 extraction-multimedia
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin
- `APP_DATA_DIR` : emplacement de stockage temporaire
- `APP_SESSION_TTL_HOURS` : duree de conservation des sessions temporaires

## Notes

- Les cookies YouTube importes sont conserves uniquement dans l'espace temporaire de la session courante.
- Les donnees sont ecrites dans `APP_DATA_DIR`, qui vaut `/tmp/appdata` par defaut.
- Aucun volume persistant n'est obligatoire pour fonctionner, mais il peut etre ajoute si tu veux conserver plus longtemps les sorties temporaires.
- Une aide pas a pas pour exporter un `cookies.txt` depuis Firefox ou Chrome est disponible dans `aide.md`.
