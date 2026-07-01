# CHD Rainette

Adaptation VPS de l'application `chdrainette`.

Cette version n'utilise plus Streamlit.
Le VPS sert maintenant :

- un backend **FastAPI**
- une interface **HTML / CSS / JavaScript** inspirée du graphisme de `iramuteq-lite`
- une exécution **R batch** pour la CHD
- une exploration web des résultats dans l'esprit de `rainette_explor(...)`

L'objectif est de conserver l'analyse Rainette, tout en évitant l'ouverture d'un second navigateur
Shiny séparé comme dans le script d'origine.

## Fonctionnalités conservées

- import d'un corpus texte compatible IRaMuTeQ
- découpage par taille fixe ou par ponctuation
- paramètre `k`
- seuil `min_split_segments`
- `min_docfreq`
- lemmatisation UDPipe optionnelle
- sélection des `UPOS`
- nuages de mots chi² et fréquence
- exports des segments par classe
- exports CSV des mots discriminants et segments

## Fonctionnalités ajoutées pour le VPS

- ticket utilisateur Redis dès l'ouverture de la page
- page web unique avec sidebar, navigation et logs
- rendu dynamique du graphe Rainette selon `k`, `measure`, `n_terms`, `same_scales`, `show_negative`, `text_size`
- exploration des segments par cluster avec filtre terme, taille d'extrait et échantillonnage
- génération du code R correspondant au graphe courant
- téléchargement direct des exports générés

## Variables d'environnement Coolify

#### Variables Redis / tickets

- `REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0`
- `APP_TICKET_ID=chdrainette`
- `APP_TICKET_ENFORCED=1`
- `APP_TICKET_MAX_ACTIVE=1`
- `APP_TICKET_COST=4`
- `CAPACITE_SERVEUR=6`
- `APP_TICKET_TTL_SECONDS=3600`
- `APP_TICKET_MAX_WAITING=20`
- `APP_TICKET_WAIT_REFRESH_MS=10000`
- `APP_TICKET_HEARTBEAT_MS=300000`
- `APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release`
- `APP_TICKET_HIDDEN_RELEASE_SECONDS=300`

#### Variables applicatives

- `PORT=8000`
- `APP_DATA_DIR=/data/app`
- `CHDRAINETTE_APP_DATA_DIR=/data/app`
- `CHDRAINETTE_R_LIBS_USER=/data/app/r-library`
- `CHDRAINETTE_CACHE_DIR=/data/app/cache`

## Dépendances système dans l'image

Le Dockerfile s'appuie sur `rocker/r2u:jammy` pour limiter les compilations R longues,
puis installe les paquets R nécessaires à Rainette et à UDPipe ainsi que le runtime Python
léger requis par FastAPI / Uvicorn / Redis.
