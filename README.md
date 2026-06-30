# Cooccurrences mot pivot

Application Streamlit d'analyse de cooccurrences centree sur un mot pivot.

## Fonctions conservees

- analyse par frequences
- analyse par log-likelihood
- fenetres `Mots (±k)`, `Phrase`, `Paragraphe` et `Document`
- import d'un ou plusieurs fichiers `.txt`
- saisie libre de texte
- concordanciers HTML
- nuages de mots PNG
- graphes interactifs PyVis
- export CSV et HTML
- etiquetage POS via spaCy

## Compatibilite VPS / Coolify

L'application est adaptee pour :

- execution sur `0.0.0.0`
- port dynamique via `PORT`
- image Docker autonome
- installation du modele spaCy `fr_core_news_md` a la build
- controle d'acces Redis via `ticket_gate.py`

## Variables d'environnement utiles

```env
REDIS_URL=redis://:motdepasse@nom-exact-du-service-redis:6379/0
APP_TICKET_ID=cooccurrencesmotpivot
APP_TICKET_ENFORCED=1
APP_TICKET_MAX_ACTIVE=2
APP_TICKET_COST=2
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
APP_TICKET_HIDDEN_RELEASE_SECONDS=300
PORT=8501
```

## Lancement local

```bash
docker build -t cooccurrencesmotpivot .
docker run --rm -p 8501:8501 cooccurrencesmotpivot
```
