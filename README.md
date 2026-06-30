# StopMotion Optical Flow - version VPS

Application Streamlit pour :

- telecharger une video YouTube
- importer une video locale
- echantillonner la video pour produire un rendu stop motion
- ajouter un rendu optical flow entre les images successives
- generer une video finale MP4 H.264
- telecharger aussi les images JPG en archive ZIP

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
docker build -t stopmotion-opticalflow .
docker run --rm -p 8501:8501 stopmotion-opticalflow
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin
- `STREAMLIT_SERVER_MAX_UPLOAD_SIZE` : taille max d'upload en Mo
- `APP_DATA_DIR` : emplacement de stockage temporaire
- `APP_SESSION_TTL_HOURS` : duree de conservation des sessions temporaires
- `APP_MAX_PREVIEW_MB` : taille max de preview video chargee en memoire

## Notes

- Les videos YouTube sont telechargees cote serveur via `yt-dlp`.
- Les donnees temporaires sont ecrites dans `APP_DATA_DIR`, qui vaut `/tmp/appdata` par defaut.
- La video finale est reencodee en H.264 pour une meilleure compatibilite navigateur.
