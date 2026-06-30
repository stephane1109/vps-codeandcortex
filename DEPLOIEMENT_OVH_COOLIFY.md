# Déploiement OVH VPS avec Coolify

Ce projet est prêt pour un déploiement sur un VPS OVH via **Coolify** en s'appuyant sur le `Dockerfile` présent à la racine.

## 1. Préparer le dépôt

Coolify déploie plus facilement l'application depuis un dépôt Git distant.

1. Placez ce dossier dans un dépôt GitHub, GitLab ou Gitea.
2. Vérifiez que les fichiers suivants sont bien versionnés :
   - `Dockerfile`
   - `docker-entrypoint.sh`
   - `.streamlit/config.toml`
   - `requirements.txt`

## 2. Vérifier localement le conteneur

```bash
docker build -t europress-to-iramuteq .
docker run --rm -p 8501:8501 europress-to-iramuteq
```

Application accessible ensuite sur `http://localhost:8501`.

## 3. Configurer l'application dans Coolify

Dans Coolify :

1. `New Resource` -> `Application`
2. Sélectionnez votre dépôt Git
3. Branche recommandée : `main`
4. Type de build : `Dockerfile`
5. `Dockerfile Location` : `./Dockerfile`
6. `Port` : `8501`

### Variables d'environnement recommandées

Vous pouvez laisser Coolify gérer `PORT`, mais ces variables sont utiles :

```env
PORT=8501
STREAMLIT_SERVER_BASE_URL_PATH=
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

`STREAMLIT_SERVER_BASE_URL_PATH` peut rester vide si l'application est exposée directement sur son sous-domaine.

### Healthcheck recommandé

- Path : `/_stcore/health`

## 4. Associer le sous-domaine

Exemple cible :

- `europressetoiramuteq.codeandcortex.fr`

Dans Coolify :

1. Ouvrez l'application
2. Ajoutez le domaine `europressetoiramuteq.codeandcortex.fr`
3. Activez le certificat SSL automatique

## 5. Configurer le DNS chez OVH

Dans la zone DNS de `codeandcortex.fr`, créez l'une de ces entrées :

- Type `A` : `europressetoiramuteq` -> `IP publique du VPS OVH`
- ou type `CNAME` : `europressetoiramuteq` -> `nom d'hôte déjà utilisé par le VPS/reverse proxy`

Si Coolify est installé directement sur le VPS et reçoit le trafic web, l'entrée `A` vers l'IP publique est généralement le plus simple.

## 6. Ressources VPS recommandées

Pour cette application Streamlit :

- CPU : 0.5 à 1 vCPU minimum
- RAM : 1 Go minimum
- Disque : faible besoin, hors logs et sauvegardes

Si vous chargez de gros exports Europresse, démarrez plutôt à **1 vCPU / 2 Go RAM**.

## 7. Notes d'exploitation

- Le conteneur écoute sur `0.0.0.0` et sur le port fourni par Coolify.
- Le healthcheck HTTP permet à Coolify de savoir rapidement si l'application est saine.
- La limite d'upload Streamlit est fixée à `512 Mo` dans `.streamlit/config.toml`.
- Aucun volume persistant n'est nécessaire pour le fonctionnement courant de l'application.
