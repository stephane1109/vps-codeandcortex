# MP3 to Text - version VPS

Application Streamlit pour :

- telecharger l'audio d'une video YouTube
- importer un fichier audio local
- choisir dans l'interface les profils `faster-whisper`, `sm`, `md`
- conserver un mode avance pour choisir directement `tiny`, `base`, `small`, `medium`, `large`
- transcrire l'audio en texte
- telecharger la transcription au format `.txt`

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- interface Streamlit exploitable depuis un navigateur
- conteneur Docker autonome
- compatibilite Coolify via `PORT` et `STREAMLIT_SERVER_BASE_URL_PATH`
- installation systeme de `ffmpeg` dans le conteneur
- backend Whisper CPU compatible avec les contraintes du VPS
- gestion d'un cache Whisper dedie et d'un dossier temporaire `APP_WORKDIR`
- aucun stockage persistant obligatoire, les fichiers restent dans le conteneur temporaire

## Lancer localement avec Docker

```bash
docker build -t mp3-to-text .
docker run --rm -p 8501:8501 mp3-to-text
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin
- `APP_WORKDIR` : dossier temporaire de travail
- `WHISPER_CACHE_DIR` : dossier de cache des modeles Whisper
- `WHISPER_PROFILE_DEFAULT` : profil visible charge par defaut dans l'application
- `WHISPER_COMPUTE_TYPE` : type de calcul Whisper, recommande `int8` sur CPU

## Notes

- Le premier lancement telecharge le modele Whisper choisi, ce qui peut prendre du temps.
- Le profil `sm` charge `small`, le profil `md` charge `medium`.
- Les modeles `medium` et `large` demandent plus de RAM et de CPU.
- L'option YouTube conserve le comportement d'origine et convertit l'audio en MP3 via `ffmpeg`.
