# ScrapTikTok — interface web et export texte

Saisir un hashtag, collecter les **légendes/descriptions** des publications TikTok,
puis télécharger un fichier **`.txt` en UTF-8**. L'interface fonctionne sur
ordinateur et mobile. Le navigateur Selenium s'exécute sur le serveur :
l'utilisateur n'a rien à installer.

## Utilisation

1. Saisir un hashtag, avec ou sans `#`, et choisir jusqu'à 300 publications.
2. Cliquer sur **Lancer la collecte**.
3. Vérifier l'accès à TikTok dans l'image du navigateur serveur affichée sur la
   page. Cliquer ou faire glisser pour traiter les cookies, la connexion ou un
   CAPTCHA. Le champ de saisie et les touches sous l'image permettent d'écrire
   dans un champ TikTok sélectionné ; le QR code de connexion est aussi utilisable.
4. Cliquer sur **Les vidéos sont visibles, continuer**.
5. Suivre la progression, consulter l'aperçu et **Télécharger le fichier texte**.

Le fichier peut contenir seulement les textes, ou les textes avec leurs auteurs
et leurs liens, selon la case cochée. Les doublons sont supprimés par identifiant.
Le bouton **Arrêter** conserve les textes déjà obtenus. Recharger la page permet
également de retrouver la collecte tant que la session est conservée.

Cette version collecte les descriptions écrites par les auteurs, hashtags compris.
Elle ne collecte pas les commentaires, les transcriptions audio ou les textes
incrustés dans les images.

## Déployer sur le VPS / Coolify

Le dossier contient le `Dockerfile`, Chromium, son pilote compatible et un écran
virtuel Xvfb. Le navigateur serveur se commande depuis l'interface ; aucun accès
VNC ni terminal utilisateur n'est nécessaire.

- Dépôt : `stephane1109/vps-codeandcortex`, branche **`deploy-scraptiktok`**.
- Base directory : **`/`** (l'application est à la racine de cette branche).
- Build pack : **Dockerfile** ; fichier : `/Dockerfile`, relatif à la base directory.
- Port interne : **8501** ; healthcheck : **`/healthz`**.
- Affecter un domaine HTTPS ; définir `COOKIE_SECURE=1`.
- Prévoir 2 Go de RAM / 2 vCPU disponibles pour une collecte simultanée.

Les réglages, variables et diagnostics sont dans
[DEPLOIEMENT_OVH_COOLIFY.md](DEPLOIEMENT_OVH_COOLIFY.md).

Le code source reste aussi dans `applications/scraptiktok` sur `main`.
Si vous choisissez volontairement `main` dans Coolify, utilisez alors
`/applications/scraptiktok` comme Base directory. La branche de déploiement doit
être mise à jour explicitement lors des prochaines modifications du code source.

Sans Coolify :

```bash
cp .env.example .env
docker compose up -d --build
```

Le port est lié à `127.0.0.1:8501` ; le guide explique le reverse proxy et le
tunnel SSH pour accéder à l'interface depuis son ordinateur.

## Lancer l'interface sur le Mac

Python 3.10+ et Chrome sont requis. Depuis ce dossier :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn webapp:app --host 127.0.0.1 --port 8501
```

Ouvrir `http://localhost:8501`. Le navigateur de collecte s'exécute sans fenêtre
locale par défaut ; son image apparaît dans l'interface. Docker utilise Chromium
avec un écran virtuel sur le VPS.

## Sessions, fichiers et ressources

- Un navigateur temporaire est dédié à chaque collecte. Aucun profil TikTok partagé.
- Une session ne peut ni voir les captures ni télécharger les résultats d'une autre.
- Une collecte simultanée par défaut ; limite réglable avec `MAX_CONCURRENT_JOBS`.
- Les fichiers texte sont dans `data/`, exclus de Git ; nettoyage après une heure
  par défaut (`RESULT_TTL_SECONDS`). Captures et saisies ne sont pas enregistrées.
- Une session abandonnée est arrêtée après 5 minutes sans nouvelles de l'interface
  (`IDLE_TIMEOUT_SECONDS`). Durée maximale d'une collecte : 30 minutes
  (`JOB_TIMEOUT_SECONDS`).
- Après un redémarrage serveur, les anciennes sessions ne sont plus accessibles.
- Protection HTTP facultative : `APP_ACCESS_USER` et `APP_ACCESS_PASSWORD`.
- Conserver un worker Uvicorn et une réplique : les sessions sont gérées en mémoire.

## Limites de TikTok

TikTok peut imposer une connexion, un CAPTCHA ou refuser l'IP du VPS. Les gestes
manuels sont transmis par Selenium ; il n'y a ni résolution automatique de CAPTCHA
ni garantie de contourner un refus d'accès. Le test de collecte réelle doit donc
être effectué depuis le réseau du VPS après déploiement.

Les résultats dépendent de ce que la page rend accessible, sans garantie
d'exhaustivité ou d'ordre chronologique. Le script lit d'abord les données JSON
intégrées à chaque page en vérifiant l'ID de la publication, puis son texte affiché
si nécessaire. Ce second mode peut restituer une légende tronquée. Les sélecteurs
TikTok peuvent changer. Adapter l'usage aux règles d'accès et aux droits sur les textes.

## Script en ligne de commande (facultatif)

L'interface utilise le même moteur que le script d'origine, qui reste disponible :

```bash
python scraptiktok.py cuisine --limit 50 --interactive --profile-dir .chrome-profile
python scraptiktok.py --help
```

Le script CLI exporte en TXT, CSV et JSON dans `exports/`. L'interface web expose
uniquement le téléchargement TXT. Selenium Manager télécharge le pilote compatible
sur Mac ; le conteneur utilise directement les paquets Chromium/ChromeDriver Debian.

## Vérifications

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tests/smoke_browser.py
```

Le test de navigateur lance l'application, utilise de vrais navigateurs Chrome,
vérifie le rendu responsive, la capture du navigateur serveur, les gestes humains
(clic, glisser, saisie), la collecte et le téléchargement TXT avec accents et emoji.
Il utilise des pages **synthétiques**, sans accès à TikTok ni résolution de CAPTCHA.
Ces fixtures n'existent que pendant le test et ne sont pas exposées en production.

Le workflow GitHub `ScrapTikTok / Docker` construit l'image Linux et exécute les tests
ainsi que ce parcours dans le conteneur. Un résultat vert valide l'application et
son environnement Linux ; il ne garantit pas l'accès à TikTok depuis une IP donnée.

### Croiser deux hashtags

Dans l’interface, renseigner le deuxième hashtag facultatif puis lancer la collecte.
Une boîte de dialogue propose **ET** (les deux hashtags dans la description) ou
**OU** (au moins un des deux). Chaque recherche examine jusqu’à la limite choisie
par hashtag ; les publications communes sont dédoublonnées par identifiant.
Le filtre compare des hashtags entiers, sans distinction de casse, en conservant
les accents. Les textes ne correspondant pas au filtre sont comptabilisés à part.
L’export TXT indique les hashtags et ET/OU dans son nom. Une recherche inaccessible
produit un résultat partiel explicite si l’autre a abouti. L’absence de résultat
ne signifie pas qu’aucune publication TikTok ne contient la combinaison : seuls
les contenus accessibles et consultés sont filtrés.

### Filtre « Français uniquement »

La case est cochée à l’ouverture de l’interface ; la décocher conserve toutes les
langues. Elle s’applique après le filtre ET/OU, aux descriptions uniquement.
La détection s’effectue localement sur le serveur avec
[langdetect](https://github.com/Mimino666/langdetect), sans envoyer les textes à un
service externe. Liens, mentions, hashtags et symboles sont exclus du texte utilisé
pour la détection, mais l’export conserve la description originale intégrale.

Le filtre retient la langue `fr` avec un score de modèle d’au moins 0,9. Ce score
n’est pas une garantie de justesse. Moins de quatre mots ou quinze lettres, ou un
score insuffisant, donnent une langue incertaine et excluent le texte. Les textes
mixtes peuvent être mal classés. Deux compteurs distinguent les autres langues des
textes trop courts ou incertains. L’export porte le suffixe `_fr.txt`. Une collecte
sans texte retenu affiche l’explication au lieu de proposer un fichier vide.
L’API conserve les langues par défaut ; envoyer `french_only: true` active le filtre.
