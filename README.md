# Extract Comments YouTube - version VPS

Application Streamlit pour :

- extraire les commentaires d'une video YouTube ou YouTube Shorts
- gerer les URLs `watch`, `shorts`, `youtu.be`, `embed` et `live`
- inclure ou non les reponses aux commentaires
- nettoyer les emojis et homogeniser la casse si besoin
- telecharger les resultats au format texte et Excel

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- interface Streamlit exploitable depuis un navigateur
- conteneur Docker autonome
- compatibilite Coolify via `PORT` et `STREAMLIT_SERVER_BASE_URL_PATH`
- prise en charge optionnelle de `YOUTUBE_API_KEY` comme variable d'environnement
- aucun stockage persistant requis, les exports sont generes en memoire

## Lancer localement avec Docker

```bash
docker build -t extract-comments-youtube .
docker run --rm -p 8501:8501 extract-comments-youtube
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin
- `YOUTUBE_API_KEY` : cle API YouTube Data v3 optionnelle pour pre-remplir le champ

## Notes

- Une cle API YouTube Data v3 valide est necessaire.
- Seuls les commentaires publics exposes par l'API YouTube peuvent etre recuperes.
- Si les commentaires sont desactives pour une video, l'application retourne quand meme les metadonnees de la video.
- Une aide dediee a la creation de la cle API YouTube et a la comprehension des quotas est disponible dans `aide.md`.
