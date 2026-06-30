# Deploiement OVH VPS avec Coolify

Ce projet est pret pour un deploiement sur un VPS OVH via **Coolify** avec le `Dockerfile` present dans ce dossier.

## 1. Configuration Coolify

Dans Coolify :

1. Cree une nouvelle ressource `Application`
2. Selectionne le depot Git
3. Choisis le build `Dockerfile`
4. Si tu deployes depuis la branche `main`, definis le `Base Directory` sur :

```text
/applications/extract_comments_youtube
```

Si tu deployes depuis la branche dediee `deploy-extract_comments_youtube`, laisse plutot :

```text
/
```

avec `Dockerfile Location = Dockerfile`.

5. Port applicatif :

```text
8501
```

## 2. Variables d'environnement recommandees

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
YOUTUBE_API_KEY=
REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0
APP_TICKET_ENFORCED=1
APP_TICKET_ID=extract_comments_youtube
APP_TICKET_MAX_ACTIVE=2
APP_TICKET_COST=1
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=900
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=300000
APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
```

`YOUTUBE_API_KEY` est optionnelle mais utile si tu veux que la cle API soit pre-remplie a l'ouverture de l'application.

Les variables `REDIS_URL` et `APP_TICKET_*` activent la file d'attente utilisateur et font apparaitre le bouton `Liberer l'acces` dans la barre laterale.

## 3. Healthcheck recommande

- Path : `/_stcore/health`

## 4. Domaine

Exemple de sous-domaine :

- `extract-comments-youtube.codeandcortex.fr`

Dans Coolify :

1. Ouvre l'application
2. Ajoute ton domaine
3. Active le certificat SSL automatique

## 5. DNS OVH

Dans la zone DNS de `codeandcortex.fr`, ajoute par exemple :

- Type `A` : `extract-comments-youtube` -> `IP publique du VPS`

## 6. Ressources conseillees

Pour cette application :

- CPU : 1 vCPU minimum
- RAM : 512 Mo minimum
- Disque : 2 Go minimum

## 7. Verification locale

```bash
docker build -t extract-comments-youtube .
docker run --rm -p 8501:8501 extract-comments-youtube
```

Puis ouvrir :

```text
http://localhost:8501
```

## 8. Notes d'exploitation

- Le conteneur ecoute sur `0.0.0.0`.
- Aucune donnee persistante n'est requise.
- Les exports texte et Excel sont generes a la demande puis telecharges par l'utilisateur.
