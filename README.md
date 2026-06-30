# Scraper Wikipedia - version VPS

Application Streamlit pour :

- recuperer le texte brut d'articles Wikipedia via l'API officielle
- traiter un ou plusieurs titres d'articles
- choisir la langue Wikipedia
- filtrer les sections utiles du texte
- telecharger les resultats en `.txt` ou dans une archive `.zip`

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- interface Streamlit exploitable depuis un navigateur
- conteneur Docker autonome
- compatibilite Coolify via `PORT` et `STREAMLIT_SERVER_BASE_URL_PATH`
- telechargement des articles en memoire sans stockage persistant obligatoire
- traitement multiple d'articles et export groupe

## Lancer localement avec Docker

```bash
docker build -t scraper-wikipedia .
docker run --rm -p 8501:8501 scraper-wikipedia
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin

## Notes

- L'application utilise l'API publique Wikipedia, donc aucune cle n'est necessaire.
- Si un article est absent dans la langue choisie, une erreur descriptive est retournee.
- Le filtrage conserve par defaut l'introduction et des sections comme geographie, hydrographie ou climat.
