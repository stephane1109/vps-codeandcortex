# Deploiement OVH VPS avec Coolify

Ce projet est pret pour un deploiement sur un VPS OVH via **Coolify** avec le `Dockerfile` present dans ce dossier.

## 1. Configuration Coolify

Dans Coolify :

1. Cree une nouvelle ressource `Application`
2. Selectionne le depot Git
3. Choisis le build `Dockerfile`
4. Definis le `Base Directory` sur :

```text
/applications/mp3_to_text
```

5. Port applicatif :

```text
8501
```

## 2. Variables d'environnement recommandees

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
APP_WORKDIR=/tmp/mp3-to-text
WHISPER_CACHE_DIR=/home/app/.cache/whisper
REDIS_URL=redis://:motdepasse@nom-exact-du-service-redis:6379/0
APP_TICKET_ID=mp3_to_text
APP_TICKET_MAX_ACTIVE=1
APP_TICKET_COST=4
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_ENFORCED=1
```

### Commentaires utiles

- `REDIS_URL` doit contenir le nom exact du service Redis visible dans Coolify.
- Si Redis exige un utilisateur ACL, utilise `redis://default:motdepasse@nom-exact-du-service-redis:6379/0`
- Si l'application affiche `Controle d'acces temporairement indisponible`, la cause Redis exacte doit maintenant s'afficher juste en dessous dans l'interface.

## 3. Healthcheck recommande

- Path : `/_stcore/health`

## 4. Domaine

Exemple de sous-domaine :

- `mp3totext.codeandcortex.fr`

Dans Coolify :

1. Ouvre l'application
2. Ajoute ton domaine
3. Active le certificat SSL automatique

## 5. DNS OVH

Dans la zone DNS de `codeandcortex.fr`, ajoute par exemple :

- Type `A` : `mp3totext` -> `IP publique du VPS`

## 6. Ressources conseillees

Pour cette application :

- CPU : 2 vCPU minimum
- RAM : 4 Go minimum pour `base` ou `small`
- RAM : 8 Go ou plus si tu veux proposer `medium` ou `large`
- Disque : 5 Go minimum pour les modeles et fichiers temporaires

## 7. Verification locale

```bash
docker build -t mp3-to-text .
docker run --rm -p 8501:8501 mp3-to-text
```

Puis ouvrir :

```text
http://localhost:8501
```

## 8. Notes d'exploitation

- Le conteneur ecoute sur `0.0.0.0`.
- Le premier lancement d'un modele Whisper est plus lent a cause du telechargement.
- Le cache Whisper peut rester ephemere ou etre monte sur un volume si tu veux accelerer les redeploiements.
- Aucune base de donnees n'est necessaire.
