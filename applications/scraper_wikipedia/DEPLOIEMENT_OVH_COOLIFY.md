# Deploiement OVH VPS avec Coolify

Ce projet est pret pour un deploiement sur un VPS OVH via **Coolify** avec le `Dockerfile` present dans ce dossier.

## 1. Configuration Coolify

Dans Coolify :

1. Cree une nouvelle ressource `Application`
2. Selectionne le depot Git
3. Choisis le build `Dockerfile`
4. Definis le `Base Directory` sur :

```text
/applications/scraper_wikipedia
```

5. Port applicatif :

```text
8501
```

## 2. Variables d'environnement recommandees

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
```

## 3. Healthcheck recommande

- Path : `/_stcore/health`

## 4. Domaine

Exemple de sous-domaine :

- `scraperwikipedia.codeandcortex.fr`

Dans Coolify :

1. Ouvre l'application
2. Ajoute ton domaine
3. Active le certificat SSL automatique

## 5. DNS OVH

Dans la zone DNS de `codeandcortex.fr`, ajoute par exemple :

- Type `A` : `scraperwikipedia` -> `IP publique du VPS`

## 6. Ressources conseillees

Pour cette application :

- CPU : 1 vCPU minimum
- RAM : 512 Mo minimum
- Disque : 1 Go minimum

## 7. Verification locale

```bash
docker build -t scraper-wikipedia .
docker run --rm -p 8501:8501 scraper-wikipedia
```

Puis ouvrir :

```text
http://localhost:8501
```

## 8. Notes d'exploitation

- Le conteneur ecoute sur `0.0.0.0`.
- Aucune base de donnees n'est necessaire.
- Les exports texte et zip sont generes a la demande puis telecharges par l'utilisateur.
