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
IRAMUTEQ_R_LIBS_USER=/opt/iramuteq-r-library
RGL_USE_NULL=TRUE
IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=0
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

Optionnel en environnement non conteneurisé ou pour du debug local :

```env
IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=1
IRAMUTEQ_BOOTSTRAP_INSTALL_OPTIONAL=1
```

Dans l'image Docker VPS a deployer sur Coolify, les dependances R/Python du coeur applicatif doivent etre preinstallees pendant le build.
Le conteneur en production doit donc rester en `IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL=0` pour eviter qu'un utilisateur declenche une installation longue au premier lancement.
Les dependances Python multimodales lourdes restent optionnelles sauf si `IRAMUTEQ_BOOTSTRAP_INSTALL_OPTIONAL=1` est defini pour un contexte local specifique.
Le build Docker lance aussi un test de fumee CHD sur `sante/santementale.txt` : si `stats_par_classe.csv`, `segments_par_classe.txt`, `dendrogramme_chd.png` ou `segments_par_classe.html` ne sont pas produits, le build echoue.

## Pourquoi ce choix

- le premier utilisateur ne doit plus rester bloque sur `Installation des dependances manquantes si necessaire`
- si l'interface affiche `Packages incomplets`, cela signifie en pratique que l'image construite ne contient pas toutes les dependances attendues
- dans ce cas il faut verifier les logs de build Coolify et relancer un redeploiement complet de l'application, idealement sans cache de build

## Que faire si `Packages incomplets` apparait

1. Verifier que Coolify rebuild bien l'application a partir du dernier code.
2. Forcer un nouveau build de l'image Docker, si possible sans cache.
3. Confirmer que le `Base Directory` est bien `/applications/iramuteq-lite`.
4. Verifier que `IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL` vaut bien `0` en production.
5. Regarder les logs de build : si un package R echoue pendant la construction, l'image doit etre corrigee au build et non au premier lancement utilisateur.
6. Si les logs mentionnent `fs`, `libuv` ou `FactoMineR`, le probleme est dans l'environnement R de l'image Docker, pas dans l'import du corpus texte.
7. Si le nouveau test de fumee CHD casse pendant le build, le probleme est confirme dans l'image Docker elle-meme, avant meme l'ouverture de l'application dans le navigateur.

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
