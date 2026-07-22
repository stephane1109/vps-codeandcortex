# KMeans

Application Streamlit pour analyser un corpus texte avec K-Means++.

## Fonctionnalites

- import d'un fichier texte Europresse/IRaMuTeQ separe par `****`
- import depuis une URL
- choix du repertoire de sauvegarde
- parametrage `Min DF`, `Max DF` et nombre de clusters
- methode du coude
- visualisation des centroides
- visualisation des clusters en bulles
- visualisation 2D des clusters
- matrice de similarite cosinus
- concordancier KMeans
- nuages de mots par topic

## Deploiement Coolify

Variables principales :

- `REDIS_URL`
- `APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release`
- `APP_TICKET_ID=kmeans`
- `APP_TICKET_MAX_ACTIVE=1`
- `APP_TICKET_COST=4`
- `KMEANS_OUTPUT_DIR=/tmp/kmeans`
- `PORT=8501`
