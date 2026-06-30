# Extraction infos YouTube - version VPS

Application Streamlit pour :

- rechercher des videos YouTube par mot-cle
- filtrer par region, langue et plage de dates
- affiner l'affichage avec des cases a cocher par date de publication
- recuperer les metadonnees principales des videos
- trier les resultats par vues, likes ou commentaires
- afficher des graphiques d'evolution par date (videos, vues, likes, commentaires)
- exporter les resultats au format Excel

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- conteneur Docker autonome pour Streamlit
- configuration headless compatible Coolify
- gestion robuste des resultats vides et des erreurs API
- export Excel genere en memoire, sans stockage persistant requis
- script d'entree compatible avec `PORT` et `STREAMLIT_SERVER_BASE_URL_PATH`

## Lancer localement avec Docker

```bash
docker build -t extraction-infos-youtube .
docker run --rm -p 8501:8501 extraction-infos-youtube
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin

## Notes

- Une cle API YouTube Data v3 est necessaire pour lancer les recherches.
- Les donnees ne sont pas stockees sur le serveur par defaut.
- Les exports sont construits a la demande et renvoyes directement au navigateur.
