# CHD Rainette

Reconstruction VPS de `chdrainette` à partir du script source historique.

## Principe

Cette version repart du script d'origine et garde un noyau volontairement simple :

- import d'un corpus texte au format IRaMuTeQ
- découpage en segments
- nettoyage texte
- stopwords `quanteda`
- calcul CHD avec `rainette`
- statistiques par classe
- nuages de mots par classe
- concordancier HTML
- exports texte / CSV / ZIP
- bundle `.rds` pour réouvrir le vrai `rainette_explor()` en local

## Ce qui a été retiré

- toute la couche `spaCy`
- tout le pipeline `reticulate`
- le NER
- les cooccurrences

## Note sur `rainette_explor`

La documentation officielle de `rainette` présente `rainette_explor()` comme un **gadget Shiny** lancé pour ses effets de bord. Cette app VPS n'essaie donc plus de l'imbriquer dans une seconde interface Shiny serveur. À la place :

- l'application affiche la CHD via `rainette_plot()`
- elle exporte un bundle `analysis_bundle.rds`
- elle fournit un script `ouvrir_rainette_explor.R` pour ouvrir le vrai gadget dans une session R locale

## Variables d'environnement Coolify

- `PORT=8000`
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
