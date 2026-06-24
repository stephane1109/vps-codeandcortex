# Déploiement OVH VPS avec Coolify

Ce projet est prêt pour un déploiement sur un VPS OVH via **Coolify** en s'appuyant sur le `Dockerfile` présent à la racine du dossier applicatif.

## 1. Position du projet dans le repo

Dans le repo `VPS`, cette application doit se trouver ici :

- `/applications/analyse_coccurrences`

## 2. Vérifier localement le conteneur

```bash
docker build -t analyse-coccurrences .
docker run --rm -p 8501:8501 analyse-coccurrences
```

Application accessible ensuite sur `http://localhost:8501`.

## 3. Configurer l'application dans Coolify

Dans Coolify :

1. `New Resource` -> `Application`
2. Sélectionnez votre dépôt Git `VPS`
3. Branche recommandée : `main`
4. Type de build : `Dockerfile`
5. `Base Directory` : `/applications/analyse_coccurrences`
6. `Dockerfile Location` : `./Dockerfile`
7. `Port` : `8501`

## 4. Variables d'environnement recommandées

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

`STREAMLIT_SERVER_BASE_URL_PATH` peut rester vide si l'application est exposée directement sur son propre sous-domaine.

## 5. Healthcheck recommandé

- Path : `/_stcore/health`

## 6. Associer le sous-domaine

Exemple cible :

- `analyse-coccurrences.codeandcortex.fr`

Dans Coolify :

1. Ouvrez l'application
2. Ajoutez le domaine `analyse-coccurrences.codeandcortex.fr`
3. Activez le certificat SSL automatique

## 7. Configurer le DNS chez OVH

Dans la zone DNS de `codeandcortex.fr`, créez l'une de ces entrées :

- Type `A` : `analyse-coccurrences` -> `IP publique du VPS OVH`
- ou type `CNAME` : `analyse-coccurrences` -> `nom d'hôte déjà utilisé par le VPS/reverse proxy`

## 8. Ressources VPS recommandées

Pour cette application Streamlit :

- CPU : `1 vCPU` minimum
- RAM : `2 Go` minimum
- Disque : faible besoin hors logs et images exportées temporairement

Si tu prévois plusieurs utilisateurs ou plusieurs analyses volumineuses, vise plutôt `2 vCPU / 4 Go RAM`.

## 9. Notes d'exploitation

- le conteneur écoute sur `0.0.0.0`
- le port exposé est piloté par la variable `PORT`
- aucun volume persistant n'est nécessaire pour le fonctionnement standard
- le modèle spaCy est déjà installé dans l'image, donc pas de téléchargement au démarrage
