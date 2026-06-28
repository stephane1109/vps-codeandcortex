# Deploiement OVH VPS avec Coolify

Ce projet est pret pour un deploiement sur un VPS OVH via **Coolify** avec le `Dockerfile` present dans ce dossier.

## 1. Configuration Coolify

Dans Coolify :

1. Cree une nouvelle ressource `Application`
2. Selectionne le depot Git
3. Choisis le build `Dockerfile`
4. Definis le `Base Directory` sur :

```text
/applications/symbolic_connectors
```

5. Port applicatif :

```text
8501
```

## 2. Variables d'environnement recommandees

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
APP_DATA_DIR=/tmp/appdata
APP_SESSION_TTL_HOURS=24
```

`APP_DATA_DIR` peut pointer vers un volume persistant si tu veux conserver les caches d'import plus longtemps.

## 3. Healthcheck recommande

- Path : `/_stcore/health`

## 4. Domaine

Exemple de sous-domaine :

- `symbolic-connectors.codeandcortex.fr`

Dans Coolify :

1. Ouvre l'application
2. Ajoute ton domaine
3. Active le certificat SSL automatique

## 5. DNS OVH

Dans la zone DNS de `codeandcortex.fr`, ajoute par exemple :

- Type `A` : `symbolic-connectors` -> `IP publique du VPS`

## 6. Ressources conseillees

Pour cette application :

- CPU : 1 vCPU minimum
- RAM : 2 Go minimum
- Disque : 2 Go minimum

Pour un usage confortable avec spaCy, annotations et plusieurs analyses ouvertes, **2 vCPU / 4 Go RAM** est un bon point de depart.

## 7. Verification locale

```bash
docker build -t symbolic-connectors .
docker run --rm -p 8501:8501 symbolic-connectors
```

Puis ouvrir :

```text
http://localhost:8501
```

## 8. Notes d'exploitation

- Le conteneur ecoute sur `0.0.0.0`.
- Les uploads IRaMuTeQ sont caches par session utilisateur.
- Les stopwords NLTK sont pre-installes a la build pour eviter un telechargement au runtime.
- Le modele spaCy francais est installe via `requirements.txt`.
