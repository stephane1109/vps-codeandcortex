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

## Import des corpus texte sur le VPS

Le VPS n'a pas besoin d'un parametrage special pour "autoriser" les fichiers texte :

- le navigateur lit le fichier `.txt` choisi par l'utilisateur
- le frontend envoie ensuite le contenu texte au backend HTTP
- le backend ecrit le corpus et les sorties du job dans `IRAMUTEQ_APP_DATA_DIR`
- en production Coolify, cela correspond normalement a `/data/app/jobs`

En clair :

- si le corpus s'importe mais qu'aucun resultat ne sort, le blocage vient en general du conteneur ou des dependances R/Python
- ce n'est pas un probleme de capacite native du VPS a stocker un `.txt`

## Variables d'environnement utiles

```env
PORT=8000
IRAMUTEQ_APP_DATA_DIR=/data/app
IRAMUTEQ_PYTHON_SITE_DIR=/data/app/python-site-packages
IRAMUTEQ_R_LIBS_USER=/data/app/r-library
RGL_USE_NULL=TRUE
IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=1
REDIS_URL=redis://redis:6379/0
APP_TICKET_ENFORCED=1
APP_TICKET_ID=iramuteq-lite
APP_TICKET_MAX_ACTIVE=1
APP_TICKET_COST=4
CAPACITE_SERVEUR=6
APP_TICKET_TTL_SECONDS=3600
APP_TICKET_MAX_WAITING=20
APP_TICKET_WAIT_REFRESH_MS=10000
APP_TICKET_HEARTBEAT_MS=30000
```

Optionnel si vous voulez explicitement desactiver le bootstrap build-time :

```text
Build arg: IRAMUTEQ_BUILD_BOOTSTRAP=0
```

La configuration recommandee est maintenant :

- bootstrap build-time actif par defaut
- `IRAMUTEQ_R_LIBS_USER=/data/app/r-library` pour conserver les packages dans le volume persistant
- `IRAMUTEQ_PYTHON_SITE_DIR=/data/app/python-site-packages` pour conserver les packages Python eventuellement reinstalles au runtime

Dans ce mode, l'image arrive normalement prete et l'application ne doit plus rester bloquee au premier clic sur le controle des dependances.
Si vous repassez a `IRAMUTEQ_BUILD_BOOTSTRAP=0`, l'application retombera sur une installation complementaire au premier lancement. Le build Docker relance aussi un test de fumee CHD sur `docker/smoke-corpus.txt` : si `stats_par_classe.csv`, `segments_par_classe.txt`, `dendrogramme_chd.png` ou `segments_par_classe.html` ne sont pas produits, le build echoue.

## Pourquoi ce choix

- sur un petit VPS, le deploiement doit d'abord aboutir avant d'exiger un build R complet
- les packages R et Python peuvent etre installes une seule fois puis reutilises s'ils vivent dans `/data/app`
- si l'interface affiche `Packages incomplets`, cela signifie en pratique que le bootstrap runtime n'a pas encore termine ou a echoue

## Que faire si `Packages incomplets` apparait

1. Verifier que Coolify rebuild bien l'application a partir du dernier code.
2. Forcer un nouveau build de l'image Docker, si possible sans cache.
3. Confirmer que le `Base Directory` est bien `/applications/iramuteq-lite`.
4. Verifier que `IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL` vaut bien `1` en production Coolify.
5. Verifier que `IRAMUTEQ_R_LIBS_USER` pointe vers `/data/app/r-library`.
6. Verifier que `IRAMUTEQ_PYTHON_SITE_DIR` pointe vers `/data/app/python-site-packages`.
7. Regarder les logs de build : si le build meurt pendant `Matrix` ou `quanteda` sans message R final, il s'agit souvent d'un timeout ou d'un manque d'espace sur Coolify et non d'un bug applicatif.
8. Si le smoke-test CHD casse au build, le probleme est alors confirme dans l'image Docker elle-meme, avant meme l'ouverture de l'application dans le navigateur.

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
