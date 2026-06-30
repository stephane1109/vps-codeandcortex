# scraping_reddit

Application Streamlit pour rechercher des posts Reddit recents a partir d'un mot-cle, filtrer les contenus francophones et exporter les posts avec leurs commentaires.

## Fonctionnalites conservees

- saisie manuelle des identifiants Reddit API
- recherche sur Reddit avec mot-cle
- filtre "titre seulement"
- borne temporelle a partir d'une date de debut
- filtrage francophone sur les posts et les commentaires
- apercu des premiers resultats
- export `.txt` complet
- controle d'acces Redis avec bouton `Liberer l'acces` dans la sidebar

## Variables d'environnement optionnelles

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`
- `REDIS_URL`
- `APP_TICKET_ID=scraping_reddit`
- `APP_TICKET_MAX_ACTIVE`
- `APP_TICKET_RELEASE_URL`

Ces variables sont optionnelles et n'enlevent pas la saisie manuelle dans l'interface.

## Execution locale

```bash
streamlit run main.py
```

## Deploiement VPS / Coolify

Le dossier GitHub cible est `applications/scraping_reddit`.

## Aide

Une aide dediee a la creation du `client_id`, du `client_secret` et du
`user_agent` Reddit est disponible dans `aide.md`.
