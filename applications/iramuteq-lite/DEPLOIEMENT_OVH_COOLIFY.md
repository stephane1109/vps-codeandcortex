# Déploiement OVH VPS avec Coolify

Cette application `iramuteq-lite` est la version **web uniquement** de `iramuteq-lite`, pensée pour un VPS OVH avec :

- `FastAPI` pour le backend HTTP
- le frontend statique conservé et servi comme application web
- `R` + `Python` embarqués dans le conteneur Docker

Il n'est donc pas nécessaire d'installer manuellement `Python`, `R`, `Streamlit` ou Tauri sur le VPS hôte.

## Architecture déployée

- `webapp/main.py` : serveur FastAPI
- `webapp/runtime.py` : pont entre le frontend web et les scripts Python/R
- `frontend/` : interface web servie telle quelle
- `backend/` + `backend/r/` : pipeline d'analyse existant

Le code desktop/Tauri natif n'est pas embarqué ici.

## Build local

```bash
docker build -t iramuteq-lite .
docker run --rm -p 8000:8000 iramuteq-lite
```

Application accessible ensuite sur :

- `http://localhost:8000`

## Configuration Coolify

1. Créer une nouvelle `Application`
2. Connecter le dépôt Git `VPS`
3. Choisir `Dockerfile`
4. Définir le `Base Directory` sur `/applications/iramuteq-lite`
5. Définir le port exposé sur `8000`
6. Ajouter un volume persistant monté sur `/data/app`

## Variables d'environnement utiles

```env
PORT=8000
IRAMUTEQ_APP_DATA_DIR=/data/app
IRAMUTEQ_R_LIBS_USER=/opt/iramuteq-r-library
RGL_USE_NULL=TRUE
```

Optionnel en environnement non conteneurisé :

```env
IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=1
```

Par défaut, le bootstrap vérifie les dépendances sans faire d'installation dynamique au démarrage.

## Domaine et sous-domaine

Exemple :

- `iramuteqlite.codeandcortex.fr`

Dans Coolify :

1. Ajouter le domaine voulu à l'application
2. Activer le SSL automatique

## DNS OVH

Dans la zone DNS de `codeandcortex.fr`, créer par exemple :

- type `A`
- sous-domaine `iramuteqlite`
- cible `IP publique du VPS OVH`

## Notes importantes

- Le conteneur installe l'environnement applicatif complet en interne.
- Le frontend reprend l'esthétique de la version Tauri, mais fonctionne dans le navigateur.
- Les sorties utilisateurs, dictionnaires d'annotation et jobs sont stockés dans `IRAMUTEQ_APP_DATA_DIR`.
- Certaines dépendances multimodales très spécifiques peuvent rester optionnelles selon l'image finale ; le coeur texte CHD/LDA/similitudes reste prioritaire.
