# Extraction PDF to TEXT to IRAMUTEQ

Adaptation VPS de l'application `pdf-to-text-to-iramuteq`.

Cette version conserve les options de l'application d'origine :

- extraction multi-PDF
- lecture auto / 1 colonne / 2 colonnes
- portée gauche / droite / totale
- intervalle de pages
- réparation des ligatures / espaces intra-mot
- variables étoilées
- injection optionnelle des métadonnées
- nettoyages avancés
- export individuel `.txt`
- export global `.zip`

## Variables d'environnement Coolify

#### Variables Redis / tickets

- `REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0`
- `APP_TICKET_ID=pdf-to-text-to-iramuteq`
- `APP_TICKET_ENFORCED=1`
- `APP_TICKET_MAX_ACTIVE=1`
- `APP_TICKET_COST=1`
- `CAPACITE_SERVEUR=6`
- `APP_TICKET_TTL_SECONDS=3600`
- `APP_TICKET_MAX_WAITING=20`
- `APP_TICKET_WAIT_REFRESH_MS=10000`
- `APP_TICKET_HEARTBEAT_MS=300000`
- `APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release`
- `APP_TICKET_HIDDEN_RELEASE_SECONDS=300`

#### Variable Streamlit

- `PORT=8501`

## Dépendances système dans l'image

Le Dockerfile installe :

- `tesseract-ocr`
- `poppler-utils`

Cela couvre les dépendances système attendues par `pytesseract` et `pdf2image`, même si l'application actuelle repose d'abord sur PyMuPDF pour l'extraction texte.
