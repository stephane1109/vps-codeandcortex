# Déploiement du dashboard Coolify

Ce service est le tableau de bord racine du dépôt. Il ne faut pas déployer
seulement `index.html` : il faut déployer la racine complète du dépôt avec
le `Dockerfile` situé à la racine.

## 1. Service à déployer

- Repository : `stephane1109/vps-codeandcortex`
- Branche : `main`
- Base directory : laisser vide
- Dockerfile : `./Dockerfile`
- Port interne : `8000`

## 2. Variables d'environnement obligatoires

- `REDIS_URL=redis://:MOTDEPASSE@NOM_DU_SERVICE_REDIS:6379/0`
- `CAPACITE_SERVEUR=6`

Ne pas utiliser `APP_TICKET_DEFAULT_REDIS_URL` sur ce service dashboard.

## 3. Vérifications après déploiement

### Healthcheck

Ouvrir :

- `/api/health`

Réponse attendue :

```json
{"status":"ok"}
```

ou éventuellement :

```json
{"status":"degraded"}
```

si Redis répond mal.

### Endpoint dashboard

Ouvrir :

- `/api/tickets/dashboard`

Réponse attendue : un JSON avec deux blocs :

- `global`
- `apps`

Si toutes les applications remontent `offline`, vérifier `REDIS_URL`.

## 4. Applications branchées au système de tickets

Les applications suivantes doivent écrire dans Redis avec leur identifiant exact :

- `iramuteq-lite`
- `symbolic_connectors`
- `mp3_to_text`
- `Analyses_multi_modales`
- `divergence-jensen-shannon`

## 5. Variables attendues sur les applications à tickets

Chaque application à tickets doit avoir au minimum :

- `REDIS_URL=redis://:MOTDEPASSE@NOM_DU_SERVICE_REDIS:6379/0`
- `APP_TICKET_ENFORCED=1`
- `APP_TICKET_ID=<nom exact>`

Valeurs exactes :

- `iramuteq-lite` -> `APP_TICKET_ID=iramuteq-lite`
- `symbolic_connectors` -> `APP_TICKET_ID=symbolic_connectors`
- `mp3_to_text` -> `APP_TICKET_ID=mp3_to_text`
- `Analyses_multi_modales` -> `APP_TICKET_ID=Analyses_multi_modales`
- `divergence-jensen-shannon` -> `APP_TICKET_ID=divergence-jensen-shannon`
