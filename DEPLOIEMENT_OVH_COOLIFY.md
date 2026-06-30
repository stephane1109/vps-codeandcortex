# Deploiement OVH VPS avec Coolify

Ce projet est pret pour un deploiement sur un VPS OVH via **Coolify** avec le `Dockerfile` present dans ce dossier.

## 1. Configuration Coolify

Dans Coolify :

1. Cree une nouvelle ressource `Application`
2. Selectionne le depot Git
3. Choisis le build `Dockerfile`
4. Definis le `Base Directory` sur :

```text
/applications/divergence-jensen-shannon
```

5. Port applicatif :

```text
8501
```

## 2. Variables d'environnement recommandees

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
REDIS_URL=redis://:motdepasse@nom-exact-du-service-redis:6379/0
APP_TICKET_ID=divergence-jensen-shannon
APP_TICKET_MAX_ACTIVE=1
APP_TICKET_COST=4
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_WAIT_STALE_SECONDS=120
APP_TICKET_ENFORCED=1
APP_TICKET_RELEASE_URL=https://ton-dashboard.codeandcortex.fr/api/tickets/release
```

### Commentaires utiles

- `REDIS_URL` doit contenir le nom exact du service Redis visible dans Coolify.
- Si Redis exige un utilisateur ACL, utilise `redis://default:motdepasse@nom-exact-du-service-redis:6379/0`
- `APP_TICKET_RELEASE_URL` doit pointer vers le dashboard racine du depot, celui qui expose `/api/tickets/release`.
- `APP_TICKET_WAIT_STALE_SECONDS=120` est recommande pour que les tickets d'attente abandonnes disparaissent vite.
- Si l'application affiche `Controle d'acces temporairement indisponible`, la cause Redis exacte doit maintenant s'afficher juste en dessous dans l'interface.

## 3. Healthcheck recommande

- Path : `/_stcore/health`

## 4. Domaine

Exemple de sous-domaine :

- `divergence-jensen-shannon.codeandcortex.fr`

Dans Coolify :

1. Ouvre l'application
2. Ajoute ton domaine
3. Active le certificat SSL automatique

## 5. DNS OVH

Dans la zone DNS de `codeandcortex.fr`, ajoute par exemple :

- Type `A` : `divergence-jensen-shannon` -> `IP publique du VPS`

## 6. Ressources conseillees

Pour cette application :

- CPU : 1 vCPU minimum
- RAM : 1 Go minimum
- Disque : 2 Go minimum

## 7. Verification locale

```bash
docker build -t divergence-jensen-shannon .
docker run --rm -p 8501:8501 divergence-jensen-shannon
```

Puis ouvrir :

```text
http://localhost:8501
```

## 8. Notes d'exploitation

- Le conteneur ecoute sur `0.0.0.0`.
- Aucune base de donnees n'est necessaire.
- Les exports sont generes a la demande puis telecharges par l'utilisateur.
