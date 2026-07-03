# CHD Rainette

Refonte VPS de l'application `chdrainette`.

Cette version démarre désormais comme une vraie application **Shiny** et utilise
le package **{bslib}** pour l'interface.

Le pipeline Python reste conservé, mais il n'est plus lancé en shell externe :
les traitements **spaCy / NER / stopwords** sont appelés depuis R via
**{reticulate}**.

## Architecture actuelle

- application Shiny native (`app.R`, `ui.R`, `start.R`)
- interface `bslib` avec sidebar, onglets, métriques, logs et exports
- pipeline CHD / AFC / concordancier en R
- pont Python via `reticulate` pour spaCy et le NER
- Docker basé sur `rocker/r2u:jammy`

## Options conservées

- import d'un corpus texte compatible IRaMuTeQ
- découpage par taille fixe ou par ponctuation
- `k` (nombre de classes)
- `min_segment_size`
- `min_split_members`
- `min_docfreq`
- `max_p`
- classification simple `rainette` ou double `rainette2`
- nettoyage du corpus
- stopwords spaCy
- filtrage morphosyntaxique spaCy avec mode `keep` / `remove`
- sélection des POS
- lemmatisation spaCy
- NER spaCy
- AFC classes / termes / variables étoilées
- nuages de mots et cooccurrences
- exports globaux, segments, stats, HTML et AFC
- exploration Rainette après calcul

## Variables d'environnement Coolify

### Variables applicatives

- `PORT=8000`
- `APP_DATA_DIR=/data/app`
- `CHDRAINETTE_APP_DATA_DIR=/data/app`
- `CHDRAINETTE_R_LIBS_USER=/data/app/r-library`
- `CHDRAINETTE_CACHE_DIR=/data/app/cache`
- `RETICULATE_PYTHON=/usr/bin/python3`

### Variables VPS / tickets

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

## Dépendances de l'image

Le Dockerfile installe :

- `shiny`
- `bslib`
- `rainette`
- `quanteda`
- `FactoMineR`
- `reticulate`
- `wordcloud`
- les dépendances Python spaCy nécessaires au prétraitement et au NER
