# LDA

Application Streamlit pour tester une analyse LDA a partir d'un corpus texte.

## Fonctions

- import d'un ou plusieurs fichiers `.txt`
- reconnaissance des séparateurs IRaMuTeQ `****`
- prétraitement spaCy
- choix des POS à conserver
- stopwords, lemmatisation et longueur minimale des mots
- détection de bigrammes
- filtrage du dictionnaire Gensim
- calcul LDA
- export CSV des topics et bigrammes
- visualisation `pyLDAvis`
- nuages de mots par topic
- archive ZIP globale
- contrôle d'accès Redis via `ticket_gate.py`

## Variables d'environnement

```env
REDIS_URL=
APP_TICKET_ID=lda
APP_TICKET_ENFORCED=1
APP_TICKET_MAX_ACTIVE=1
APP_TICKET_COST=3
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_ACTIVE_STALE_SECONDS=900
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_RELEASE_URL=
APP_TICKET_HIDDEN_RELEASE_SECONDS=300
PORT=8501
LDA_SPACY_MODEL=fr_core_news_md
```
