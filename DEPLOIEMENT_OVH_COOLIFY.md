# Deploiement OVH VPS avec Coolify

Ce projet est pret pour un deploiement sur un VPS OVH via **Coolify** avec le `Dockerfile` present dans ce dossier.

## 1. Configuration Coolify

Dans Coolify :

1. Cree une nouvelle ressource `Application`
2. Selectionne le depot Git
3. Choisis le build `Dockerfile`
4. Definis le `Base Directory` sur :

```text
/applications/stopmotion_opticalflow
```

5. Port applicatif :

```text
8501
```

## 2. Variables d'environnement recommandees

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
STREAMLIT_SERVER_MAX_UPLOAD_SIZE=4096
APP_DATA_DIR=/tmp/appdata
APP_SESSION_TTL_HOURS=24
APP_MAX_PREVIEW_MB=200
```

`STREAMLIT_SERVER_BASE_URL_PATH` peut rester vide si l'application est exposee directement sur son sous-domaine.

## 3. Healthcheck recommande

- Path : `/_stcore/health`

## 4. Domaine

Exemple de sous-domaine :

- `stopmotion-opticalflow.codeandcortex.fr`

Dans Coolify :

1. Ouvre l'application
2. Ajoute ton domaine
3. Active le certificat SSL automatique

## 5. DNS OVH

Dans la zone DNS de `codeandcortex.fr`, ajoute par exemple :

- Type `A` : `stopmotion-opticalflow` -> `IP publique du VPS`

## 6. Ressources conseillees

Pour cette application video :

- CPU : 1 vCPU minimum
- RAM : 2 Go minimum
- Disque : 10 Go minimum si les utilisateurs manipulent de grosses videos

Pour un usage confortable avec upload, extraction d'images et reencodage `ffmpeg`, **2 vCPU / 4 Go RAM** est un bon point de depart.

## 7. Verification locale

```bash
docker build -t stopmotion-opticalflow .
docker run --rm -p 8501:8501 stopmotion-opticalflow
```

Puis ouvrir :

```text
http://localhost:8501
```

## 8. Notes d'exploitation

- Le conteneur ecoute sur `0.0.0.0`.
- Les fichiers temporaires sont isoles par session utilisateur.
- Les anciennes sessions sont supprimees automatiquement apres la duree definie par `APP_SESSION_TTL_HOURS`.
- `ffmpeg` est installe dans l'image Docker.
