# ScrapTikTok — interface Streamlit minimaliste

Saisir un hashtag, collecter les **légendes/descriptions** des publications TikTok,
puis télécharger un fichier **`.txt` en UTF-8**. L'interface fonctionne sur
ordinateur et mobile. Le navigateur Selenium s'exécute sur le serveur :
l'utilisateur n'a rien à installer.


## Moteurs Presse et médias (octobre 2026)

Dans **Collecte → Presse et médias**, sélectionner une seule méthode par collecte :

- **API web TikTok (secUid)** : méthode historique non officielle, maintenue avec
  récupération depuis l'embed du créateur, pagination sur
  `/api/creator/item_list/`, contrôle de l'auteur et arrêt immédiat après
  HTTP 429. Les restrictions TikTok ne sont pas contournées.
- **Research API officielle** : exige l'approbation préalable de TikTok et le droit
  `research.data.basic`. Collecte par `username`, jusqu'à 100 vidéos par
  page, période de 30 jours maximum par requête, fenêtres successives pour les
  intervalles plus longs, vérification stricte de l'auteur, export TXT/SQLite/ZIP.
  Sans période saisie, interroge les **30 derniers jours UTC** ; le nombre demandé
  est un objectif, pas une garantie d'exhaustivité. Recherche limitée à 60 pages
  par compte et par collecte.
- **Grille du profil (Selenium)** : méthode navigateur indépendante.

Après autorisation de la Research API, sélectionner cette méthode dans
**Presse et médias**, puis saisir les deux champs masqués directement dans
l'application : `TIKTOK_RESEARCH_CLIENT_KEY` et
`TIKTOK_RESEARCH_CLIENT_SECRET`. Les identifiants ne sont transmis qu'au
backend pour la collecte active, ne sont jamais exportés dans SQLite ou le ZIP,
et sont nettoyés après l'exécution. La connexion au service doit utiliser HTTPS.

Pour un usage administrateur, les mêmes valeurs peuvent **facultativement**
être placées dans les variables d'environnement Coolify. Les champs de
l'interface ont priorité sur ces variables lorsqu'ils sont tous deux remplis.
Ne jamais déposer les clés dans GitHub ou les logs.
L'endpoint d'authentification officiel est
`POST https://open.tiktokapis.com/v2/oauth/token/` (jeton client renouvelable),
et la requête vidéo est
`POST https://open.tiktokapis.com/v2/research/video/query/`.
L'écran `/healthz` ne publie **que la présence des identifiants
d'environnement**, jamais leur valeur ; l'absence de clés sur Coolify ne
bloque pas les champs de saisie de l'application. Leur présence ne prouve
pas que l'accès est autorisé.
Le refus officiel interrompt le lot sans basculement vers les API non officielles.

L'API développeur classique **Display API** n'est pas ajoutée : son accès
`video.list` requiert l'autorisation OAuth **de chaque propriétaire de compte**.
Une simple clé d'application ne permet pas de collecter tous les médias.

Research transmet les descriptions et compteurs avec leur provenance ; les
données absentes restent absentes. Les MP4 ne proviennent **pas** de la Research
API et restent liés à l'outil de téléchargement séparé. Lorsque l'utilisateur
demande les textes des commentaires, l'implémentation actuelle utilise encore
Selenium ; ce n'est pas une collecte de commentaires par Research API.
Les nouveaux posts et leurs compteurs peuvent être différés selon les règles
de publication des données Research de TikTok.

Documentation :
- https://developers.tiktok.com/docs/en/research-api-get-started
- https://developers.tiktok.com/docs/en/research-api-specs-query-videos
- https://developers.tiktok.com/docs/en/display-api-overview

## Utilisation

1. Saisir un hashtag, avec ou sans `#`, et choisir jusqu'à 300 publications.
2. Renseigner au moins un hashtag dans tous les modes, puis cliquer sur **Lancer la collecte**. Le deuxième hashtag reste facultatif (ET/OU).
3. Vérifier l'accès à TikTok dans l'image du navigateur serveur affichée sur la
   page. Cliquer ou faire glisser pour traiter les cookies ou un CAPTCHA.
   La collecte est anonyme : aucune connexion à un compte TikTok n’est proposée.
4. Cliquer sur **Les vidéos sont visibles, continuer**.
5. Suivre la progression, consulter l'aperçu et **Télécharger le fichier texte**.

Le fichier peut contenir seulement les textes, ou les textes avec leurs auteurs
et leurs liens, selon la case cochée. Les doublons sont supprimés par identifiant.
L'option **Texte généré par IA** ajoute, lorsqu'il est récupérable, le résumé
fourni par TikTok sous la légende. L'aperçu et le TXT distinguent alors deux
segments : `**** *source_original` puis `**** *source_ia`, avec les mêmes
variables sélectionnées pour la publication (profil, date, identifiant,
engagements, etc.). Aucun résumé n'est inventé si TikTok n'en fournit pas
ou si son extraction échoue : seul le segment original est conservé.
La lecture attend le chargement après « Plus » (jusqu'à 12 secondes par
publication). Même avec un moteur API, cette option ouvre la page dans le
navigateur pour rechercher le résumé. Un bilan indique combien de résumés ont
réellement été récupérés, avec un détail par URL. Une ancienne collecte sans
résumé doit être relancée après la mise à jour ; télécharger à nouveau son TXT
ne récupère pas rétroactivement les textes manquants.

La méthode de lecture du bloc déplié a été confrontée aux
[tests et à l'implémentation de Rezepte](https://github.com/oliverzimmermann1986-debug/Rezepte/blob/main/app/core/tiktok_caption.py).
Les sous-titres et la légende renvoyés par le lecteur TikTok ne sont pas attribués
au résumé IA : il faut un titre ou un avis identifiant explicitement ce résumé.

Le bouton **Arrêter** conserve les textes déjà obtenus. Recharger la page permet
également de retrouver la collecte tant que la session est conservée.

La fenêtre TikTok s’ouvre automatiquement lorsqu’une vérification est détectée.
Pour les profils et médias, elle s’ouvre également si la page ne fournit aucun
lien lisible après le délai de chargement, ou si la pagination reste bloquée sans
signal de fin. La fenêtre intégrée apparaît automatiquement.
La collecte se met en pause sur la page courante ; **Continuer** relit cette page
et reprend le parcours dans la même session. Aucun identifiant n’est imposé.
Si TikTok ne fournit toujours pas de publications, le rapport conserve la cause
observée et les éventuels liens déjà obtenus. L’application ne peut pas forcer
TikTok à afficher un CAPTCHA ou à fournir des vidéos.

Le parcours initial collecte les descriptions écrites par les auteurs, hashtags compris.
Les nouveaux modules sont facultatifs : comptes de presse, engagement, commentaires,
réponses et analyses audiovisuelles. Les entrées CLI et FastAPI restent les mêmes.

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

## Sauvegarde progressive (facultative)

Dans l'onglet **Collecte**, cocher **Sauvegarde progressive des collectes**
avant de lancer la recherche. Tous les **10 posts traités**, et à la fin (même
après un arrêt ou une collecte partielle), ScrapTikTok écrit un ZIP de
récupération atomique dans `/app/data/sauvegardes_collectes/<id>.zip`.
Un seul ZIP est conservé par collecte, mis à jour à chaque point : les fichiers
précédents ne s'accumulent pas.

Le ZIP contient `textes.txt`, `publications.json`, `retenues.json`,
`commentaires.json`, `etat.json` (progression et statut) et `parametres.json`
(réglages et filtres). Il ne contient
ni les MP4, ni les cookies, ni les captures Selenium. L'option est désactivée
par défaut et **ne reprend pas automatiquement la collecte**.

Les archives peuvent être téléchargées dans **Collecte → Sauvegardes
progressives — récupérer un corpus**, y compris après un redémarrage du
serveur, tant que le navigateur possède le **cookie privé d'origine**.
Ce cookie a une durée de vie de 24 heures : après son expiration, les ZIP
restent récupérables sur le volume VPS, mais ne sont plus accessibles via
une nouvelle session Web. Télécharger donc le ZIP le lendemain matin.

La conservation des ZIP est indépendante de celle des sessions :
`CHECKPOINT_TTL_SECONDS=604800` (7 jours) par défaut. Ce paramètre est
configurable dans Coolify. **Un volume persistant sur `/app/data` est
nécessaire** pour survivre à un redéploiement ; il est déclaré dans
`compose.yaml`. Les sauvegardes sont purgées après expiration du délai.
Un échec de sauvegarde est signalé dans l'interface sans stopper la collecte.

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
python lancer_interface.py --port 8501
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

### Protection locale contre HTTP 429

Les valeurs publiées pour les API officielles TikTok ne s'appliquent pas
à l'API web interne ni à Selenium utilisés par ScrapTikTok.

Les **cinq variables d'environnement Coolify** `SCRAPTIKTOK_API_*`
définissent les seuils de sécurité du moteur API Presse, sans minoration ni
plafond supérieur imposés par le code. Exemple de réglage volontaire à 50 % :
300 requêtes/minute, 500 requêtes/heure, 500 requêtes/jour UTC,
50 000 objets API Presse/jour UTC, intervalle minimal de 0 seconde.
Ces budgets sont communs à toutes les sessions et ne comptent pas Selenium.
Si les variables sont absentes, le moteur utilise des valeurs de secours ;
pour une configuration de production explicite, définir les cinq variables.
Un refus TikTok HTTP 429 interrompt la recherche API Presse : aucune autre
vidéo ni aucun autre média n'est alors contacté.

Les anciennes variables par source
`SCRAPTIKTOK_MAX_POSTS_PER_SOURCE`, `SCRAPTIKTOK_MAX_SOURCES_PER_JOB`,
`SCRAPTIKTOK_MAX_COMMENTS_PER_VIDEO`, `SCRAPTIKTOK_MAX_SCROLLS`
et `SCRAPTIKTOK_API_MAX_PAGES_PER_SOURCE` sont ignorées.
Les limites techniques du formulaire et les durées maximales restent actives.

## Script en ligne de commande (facultatif)

L'interface utilise le même moteur que le script d'origine, qui reste disponible :

```bash
python scraptiktok.py cuisine --limit 50 --interactive
python scraptiktok.py --help
```

Le script CLI exporte en TXT, CSV et JSON dans `exports/`. L'interface web expose
uniquement le téléchargement TXT. Selenium Manager télécharge le pilote compatible
sur Mac ; le conteneur utilise directement les paquets Chromium/ChromeDriver Debian.

## Vérifications

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tests/smoke_controle.py
python tests/smoke_streamlit.py
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

Dans l’interface, renseigner le deuxième hashtag facultatif et choisir **ET**
(les deux hashtags dans la description) ou **OU** (au moins un des deux), puis
lancer la collecte. La limite saisie est **globale** pour l'ensemble des hashtags :
avec 50 posts, au plus 50 publications distinctes sont retenues pour lecture,
même si deux hashtags sont saisis (ET ou OU). Le budget est réparti entre les
hashtags et leurs variantes ; les doublons sont dédupliqués par identifiant.
Le nombre de textes exportés peut être inférieur après les filtres.
Le filtre compare des hashtags entiers, sans distinction de casse, en conservant
les accents. Les textes ne correspondant pas au filtre sont comptabilisés à part.
L’export TXT indique les hashtags et ET/OU dans son nom. Une recherche inaccessible
produit un résultat partiel explicite si l’autre a abouti. L’absence de résultat
ne signifie pas qu’aucune publication TikTok ne contient la combinaison : seuls
les contenus accessibles et consultés sont filtrés.

### Variables et commentaires dans le TXT

L'archive enrichie est créée automatiquement pour toute collecte lancée depuis
l'interface, y compris par hashtag sans commentaires. Aucune case d'activation
n'est nécessaire.

Dans la section « Variables à inclure avant chaque post dans le TXT », les cases
indépendantes sont **Date**, **Profil**, **ID vidéo**, **Nombre de vues**, **Nombre de likes**,
**Nombre de partages**, **Nombre de commentaires** et **Nombre de favoris**. Seules les variables cochées
figurent sur une ligne étoilée, dans cet ordre, au format `*nom_valeur`.
La date n’inclut pas l’heure. Exemple avec toutes les variables et les hashtags :

```text
*date_2026-10-08 *profil_@bfmtv *id_7694262098129603843 *vues_8000000 *likes_576000 *partages_42 *comment_123 *favoris_456
Texte de la publication.
#blocage #lycee #manifestation #lyceen #lyon

Commentaire 1 :
Texte d’un commentaire de cette publication.
```

Les nombres de partages, de commentaires et de favoris ci-dessus sont illustratifs.
`*partages_` utilise **shareCount**, jamais **repostCount**. `*comment_` utilise le
compteur total **commentCount** de TikTok, pas le nombre de textes récupérés.
`*favoris_` utilise le compteur **collectCount** (ajouts aux favoris). Ces
compteurs sont disponibles même si la collecte des textes de commentaires est décochée.
Une mesure absente est `indetermine` ; un vrai zéro reste `0`. Les valeurs estimées
sont écrites numériquement dans le TXT ; la mesure brute, la confiance et le statut
d’estimation restent dans les exports structurés. La date absente ou invalide est
`*date_indetermine`. Le numéro TikTok suit `*id_` à la place de l’URL, sur la même
ligne étoilée que les autres variables. La case « ID vidéo » remplace la case « URL ».

La case **Hashtags sous le texte** déplace les hashtags de la légende sur une ligne
après son texte, avant les éventuels commentaires. Ils ne sont plus des variables
étoilées et ne sont pas répétés dans le texte. Sans cette case, la légende reste
inchangée. Les données originales restent conservées dans l’archive.

Si « Collecter les textes des commentaires » est coché, les commentaires récupérés
figurent sous leur publication dans le même TXT. Les réponses récupérées sont
également ajoutées si leur option est cochée. Les exports séparés restent disponibles.
Aucun commentaire d’une publication exclue n’est inséré.

L’API accepte `variables_txt: ["date", "profil", "id", "vues", "likes", "partages",
"commentaires", "favoris", "hashtags"]`, ou toute sous-liste, y compris `[]`. L’ancienne clé
`republications` est convertie en `partages` pour les sélections déjà enregistrées,
sans réutiliser le compteur de republications. L’ancienne clé `url` est convertie
en `id`, pour préserver la sélection au changement de version. Une liste explicite remplace les
anciennes options d’en-tête. Les requêtes sans ce champ restent compatibles avec
`inclure_metadonnees_txt` et `include_sources`.

Dans l’archive, **`corpus_iramuteq.txt` est une copie exacte, octet pour octet, du
TXT téléchargeable `textes.txt`** : mêmes publications retenues, mêmes variables
cochées, même ordre, mêmes hashtags et mêmes commentaires inclus. Aucun nouvel
en-tête ni normalisation ne sont ajoutés lors de la création du ZIP. Une
régénération de l’archive après traitement vidéo conserve également ce TXT.
Les CSV, JSON et corpus séparés des commentaires restent disponibles.
Pour un lot autonome sans fichier `textes.txt`, le générateur de corpus historique
reste utilisé.

### Filtre français

La case est cochée à l’ouverture de l’interface ; la décocher conserve toutes les
langues. Elle s’applique après le filtre ET/OU, aux descriptions uniquement.
La détection s’effectue localement sur le serveur avec
[langdetect](https://github.com/Mimino666/langdetect), sans envoyer les textes à un
service externe. Liens, mentions, hashtags et symboles sont exclus du texte utilisé
pour la détection, mais l’export conserve la description originale intégrale.

Le filtre exclut une autre langue identifiée avec un score de modèle d’au moins 0,9.
Ce score n’est pas une garantie de justesse. Moins de quatre mots ou quinze lettres,
ou un score insuffisant, donnent une langue indéterminée : le texte est conservé
intégralement, sans être déclaré français. Aucun texte n’est éliminé pour sa longueur.
Les textes mixtes peuvent être mal classés. Les compteurs distinguent les autres
langues écartées des langues indéterminées conservées. L’export porte le suffixe `_fr.txt`.
La langue ne peut être évaluée qu’après lecture de la légende : ce filtre ne constitue
pas une recherche TikTok limitée à la langue française avant collecte. Une collecte
sans texte retenu affiche l’explication au lieu de proposer un fichier vide.
L’API conserve les langues par défaut ; envoyer `french_only: true` active le filtre.

Les résultats affichent les likes, vues, partages et nombres de commentaires observés.
Le bouton « Télécharger les compteurs CSV » donne toutes les publications retenues,
leurs légendes, leur statut linguistique et les mesures brutes avec leurs confiances.
Une valeur indisponible reste vide dans le CSV ; elle n’est jamais remplacée par zéro.
Le TXT reste sans compteurs numériques ajoutés ; les commentaires récupérés y figurent si leur collecte est cochée.

« Collecter les textes des commentaires » est visible dans le formulaire et activé
par défaut pour une nouvelle session Streamlit. Cette collecte facultative concerne
uniquement les publications retenues ; sa limite se règle dans « Exports et commentaires ».
Le nombre de commentaires annoncé par TikTok et le nombre de textes effectivement
accessibles sont distincts. Les textes récupérés ont leur propre téléchargement TXT
et restent dans les exports enrichis CSV/JSON/IRaMuTeQ.


## Comptes de presse, engagement et commentaires

Dans **Source**, choisir **Comptes de presse** ou **Autres comptes TikTok**.
Sélectionner les médias, ou saisir jusqu’à dix identifiants séparés par des virgules.
La limite s’applique par compte, tous hashtags confondus. Au moins un hashtag est
obligatoire ; le deuxième reste facultatif (ET/OU). Les modes Profils et
Presse/médias ouvrent une recherche vidéo pour chaque couple compte + hashtag :
par exemple `https://www.tiktok.com/search/video?q=manifestation%20lemondefr`.
Le compte coché figure donc dans la requête, pas seulement dans un filtre appliqué
à des résultats généraux. Le mode Hashtags conserve les pages `/tag/hashtag`.
La page d’accueil du profil n’est pas utilisée pour découvrir les publications.

Le moteur attend les liens chargés dynamiquement et fait défiler le conteneur
des publications. Seuls les auteurs correspondant exactement à la sélection
sont retenus ; les autres auteurs ne consomment pas la limite par compte.
Les identifiants sont dédoublonnés entre les pages et les hashtags. Trois
chargements sans nouveauté sont nécessaires avant un arrêt pour stagnation ;
le parcours est borné à 40 défilements par couple compte + hashtag pour le VPS.
Les hashtags ET/OU, dates et langue sont vérifiés sur les légendes après un
second contrôle de l’auteur à la lecture. Les likes, commentaires et exports
restent disponibles.

L’interface distingue **Découvertes**, **Retenues pour lecture**, **Traitées** et
**Exportées dans le TXT**. Le compteur d’export ne progresse qu’après écriture
réussie. Le détail par média affiche les requêtes effectivement ouvertes, les liens
retenus et les auteurs exclus. Si aucune publication n’est lue, les filtres de langue
et de légende sont indiqués comme non appliqués. Un objectif non atteint est signalé
**Collecte partielle**, y compris si TikTok annonce la fin de ses résultats. Le mode Hashtags conserve son parcours.
Le fonctionnement détaillé et les scénarios de test fournis sont décrits dans
[COLLECTE_PROFILS.md](COLLECTE_PROFILS.md).

Cette collecte n’est pas exhaustive et dépend des publications accessibles à TikTok.
En mode presse/comptes, la collecte fonctionne sans identifiants TikTok : elle
utilise le bouton de fermeture des invitations à se connecter lorsqu'il est disponible.
Une invitation n'empêche pas de cliquer sur **Continuer** ni de lire les publications
publiques déjà fournies par la page. Les vrais CAPTCHA restent interactifs.
Si une fenêtre de connexion apparaît et qu'aucun lien supplémentaire n'arrive après
les tentatives d'attente de chargement, les liens déjà lus sont conservés. Le journal signale cette
limite d'accès, sans assimiler six résultats au nombre total de publications du média.
Le moteur ne demande pas de connexion pour poursuivre le lot. Une légende inaccessible
sans compte est comptée parmi les erreurs de lecture.
Une vérification visible attend une intervention humaine ; aucune résolution
automatique de CAPTCHA n’est effectuée. Une erreur d’accès reste distincte d’un
filtre qui ne trouve aucune correspondance.
Le filtre français conserve son fonctionnement et son caractère facultatif.

L’inventaire `config/comptes_presse.json` contient 29 comptes sélectionnables. Les six
références éditoriales initiales sont conservées ; les ajouts fournis par l’utilisateur
sont identifiés comme tels, sans présumer de leur propriété éditoriale ni de leur
catégorie sociologique. Les catégories non vérifiées restent indéterminées. Les
identifiants sont conservés exactement, notamment leurs traits de soulignement.
Une collecte peut sélectionner jusqu’à 29 médias ; les limites par source et les
traitements séquentiels restent inchangés.

En **mode API Presse**, la légende et les compteurs déjà présents dans la
réponse `itemList` de chaque média sont directement repris dans le corpus,
sans rouvrir chaque vidéo avec Selenium. Si la légende manque, la lecture
habituelle de la vidéo reste possible. La collecte explicite des commentaires
continue d'utiliser le navigateur. Les compteurs absents restent inconnus :
ils ne sont pas remplacés par zéro. Une collecte de 50 posts sur trois médias
vise jusqu'à 150 posts, avec un objectif **par média**.

Comme dans le projet de référence `bajaam/tt-dlp`, un `secUid` public
confirmé par les publications du média est mémorisé dans
`/app/data/presse_identites.json` lorsque `DATA_DIR=/app/data`.
Le cache reste valable 30 jours et évite certaines nouvelles requêtes
d'identification, mais ni les budgets Coolify ni les refus TikTok HTTP 429
ne sont contournés. Après un HTTP 429, le lot s'arrête et exporte les
résultats déjà acquis ; aucun autre média n'est sollicité.

Dans Streamlit, choisir **Presse et médias** dans **Rechercher par** : les comptes
s’affichent directement sous forme de cases à cocher, sans liste déroulante cachée.
Le bouton **Tout cocher** sélectionne tous les médias ; chaque case reste modifiable.
La sélection reste conservée lors d’un changement de mode de recherche. Le compteur indique combien de médias sont sélectionnés. Le catalogue est relu à chaque interaction pour ne pas conserver une ancienne liste en session. Les hashtags de la recherche générale sont séparés des hashtags de la recherche par comptes, dont le premier est obligatoire.
L’inventaire est extensible : `id`, `nom`, `compte`,
`categorie`, `source_editoriale`, `statut_verification`. Les catégories sont dans
`config/categories_medias.json`. Une référence éditoriale n’est pas une garantie de
vérification actuelle : le rapport distingue l’identifiant observé, sa concordance,
le badge TikTok et la propriété éditoriale, qui reste indéterminée automatiquement.

Ouvrir **Engagement, commentaires et corpus enrichi** pour activer les commentaires
et les réponses. L’archive est automatique pour une collecte par comptes ; elle peut
également être activée pour les hashtags. Les compteurs proviennent en priorité du
JSON de la publication exacte, puis des éléments visibles : likes, vues, partages,
favoris et total de commentaires. Chaque mesure conserve valeur, texte brut, source,
confiance, caractère estimé et date d’observation. `1,2 K` vaut une estimation de 1 200 ;
un compteur absent vaut `null`, jamais zéro. Les scores sont heuristiques, non calibrés.

Le téléchargement « Compteurs CSV » et le fichier `engagement.csv` de l’archive
conservent les colonnes d’identification, l’URL, les compteurs et leurs valeurs `_brut`.
La colonne `id_` contient le numéro TikTok complet, également présent dans les CSV
par publication (ratios, commentaires, variables SHS et export en ligne de commande).
Dans `commentaires.csv`, `id` reste l’identifiant du commentaire, tandis que `id_`
et `url` identifient sa publication. Les tableaux agrégés par média restent inchangés.
Les 15 colonnes `_confiance`, `_source` et `_estime` des likes, vues, partages,
commentaires et favoris sont retirées de ce CSV. Ces informations restent
conservées dans `publications.json`.

La collecte ouvre le panneau des commentaires si nécessaire, attend son chargement
et fait défiler son conteneur réel. Elle lit les marqueurs placés sur le texte aussi
bien que ceux placés sur un conteneur, puis dédoublonne les commentaires. Un CAPTCHA
survenant pendant ce chargement utilise le contrôle manuel du navigateur existant.
Elle ne se connecte pas à TikTok et ne contourne pas une restriction d’accès.

Le détail par vidéo indique le nombre annoncé par TikTok, le nombre de textes
récupérés et le diagnostic : panneau introuvable, chargement incomplet, erreur TikTok,
CAPTCHA, invitation à se connecter, commentaires désactivés ou absence explicitement
affichée. Un fichier sans texte n’est donc plus assimilé automatiquement à zéro
commentaire. `*comment_` conserve le compteur total TikTok ; seule la case
« Collecter les textes des commentaires » active leur extraction.

Les champs conservés sont l’identifiant du commentaire (ou un identifiant local
signalé), l’identifiant de la vidéo, l’auteur, le texte, la date affichée, la date
d’observation, les likes observés et le lien parent/réponse lorsqu’il est disponible.
Les champs absents restent indéterminés et les données brutes restent dans le JSON.

La collecte des commentaires lit uniquement ce qui est accessible dans la page,
avec une limite par publication et un nombre de défilements borné. Les réponses
sont facultatives, les liens parent/enfant conservés lorsqu’ils sont observés. À défaut
d’ID TikTok, un ID local est signalé comme tel : deux textes identiques du même auteur
peuvent alors être confondus. Un résultat vide ne prouve pas l’absence de commentaires.
Les sélecteurs peuvent évoluer avec TikTok ; les statuts partiels restent explicites.

La case « Supprimer le @ devant les profils dans le TXT », cochée par défaut
au-dessus des téléchargements, écrit `*profil_bfmtv` au lieu de `*profil_@bfmtv`.
Ce choix est enregistré au lancement et peut être modifié après la collecte,
avant chaque téléchargement, sans relancer la collecte. Le marqueur redondant
`*compte_…` n’est pas ajouté : seul `*profil_…` identifie le profil sélectionné.
Il s’applique au TXT et aux fichiers identiques `textes.txt` et `corpus_iramuteq.txt`
de l’archive. Les CSV, les mentions dans les légendes et les commentaires restent
inchangés ; aucune nouvelle collecte n’est nécessaire.

**Télécharger le fichier texte** applique les variables choisies et inclut les
commentaires récupérés si leur collecte est cochée. **Télécharger l’archive
enrichie** fournit JSON brut, CSV (UTF-8 BOM, séparateur `;`), corpus IRaMuTeQ et journal.
Les filtres ET/OU et français s’appliquent aux légendes retenues dans TXT/IRaMuTeQ.
Les publications brutes et mesures restent séparées ; `retenue` identifie la sélection.
Les commentaires sont collectés pour les publications retenues. Leurs exports séparés
restent disponibles.
Les astérisques sont neutralisés uniquement dans le corps IRaMuTeQ, sans modifier le brut.

## Analyse vidéo conservée : Désordre visuel

**Vidéos similaires** (CLIP, DINOv2, FAISS et les comparateurs ORB/pHash)
a été retiré avec son API et ses dépendances. Le téléchargement MP4
et l'analyse **Désordre visuel** restent disponibles : mouvement,
instabilité, irrégularité, annotations, engagement et exports.
Ce module s'appuie sur OpenCV, NumPy, SciPy, Pandas et Matplotlib,
sans installer PyTorch ni télécharger de modèle sémantique.
Garder le volume `/app/data` persistant pour les analyses existantes.

## Architecture et validation

### Parcours de connexion séparés

Les trois modes de l’interface possèdent chacun leur module de pilotage Selenium :

- `connect_htag.py` : `ConnexionHashtag`, pages `/tag/` des hashtags saisis.
- `connect_presse.py` : `ConnexionPresse`, résolution des médias cochés dans
  l’inventaire, puis recherches vidéo ciblées pour chaque compte et hashtag.
- `connect_profil.py` : `ConnexionProfil`, normalisation des profils saisis avec
  ou sans `@`, puis recherches vidéo ciblées pour chaque compte et hashtag.

Le service de collecte choisit explicitement l’un de ces trois parcours. Presse
et Profils refusent une source absente de leur sélection ; le contrôle de l’auteur
à la découverte et avant les exports reste également actif. Ces modules pilotent
la connexion au navigateur : ils ne proposent pas d’identification à TikTok.

`collecte/session_navigateur.py` gère uniquement le cycle de vie commun : une
session Selenium anonyme par collecte, réutilisée pour toutes les recherches,
lectures et commentaires, puis détruite à la fin ou à l’arrêt. La validation
initiale est partagée entre les sources ; un nouveau CAPTCHA détecté reste
traité manuellement dans le même navigateur. Aucun import n’ouvre de navigateur.
Le défilement et la détection TikTok restent dans le moteur commun `scraptiktok.py`.
Le journal de chaque source indique le module utilisé, sans cookies ni identifiants.

Cette séparation permet de modifier un parcours indépendamment ; elle ne garantit
pas que TikTok fournisse tous les résultats. Les diagnostics de collecte partielle,
les filtres, les commentaires, les compteurs et les exports restent conservés.

Les fichiers JavaScript et CSS versionnés de Streamlit sont compressés en gzip
si le navigateur l'accepte, puis conservés dans son cache privé. Leur nom contient
une empreinte : une mise à jour charge les nouveaux fichiers. Le HTML, les données
de session, les exports et les captures restent servis avec `Cache-Control: no-store`.
L'interface Streamlit et le moteur FastAPI sont deux processus liés d'un même
lancement ; ce couple ne constitue pas deux collectes ou deux interfaces distinctes.

`collecte/` gère les sources et observations ; `stockage/` les sessions SQLite ;
`analyse_desordre/` le calcul vidéo différé ;
`corpus/` les exports. Aucun import lourd n’est requis pour démarrer FastAPI ou collecter
les textes. `requirements.txt` et `analyse_desordre/requirements.txt` définissent les dépendances nécessaires. Les points d’entrée et fonctions antérieures restent en place.

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tests/smoke_controle.py
```

Les tests Désordre visuel restent exécutables indépendamment du moteur de collecte. Les fixtures contrôlent compression, recadrage,
images différentes, ordre temporel, images fixes, séparation sémantique/réemploi,
valeurs indéterminées, exports, isolation des sessions et gestes navigateur existants.
Voir `AUDIT_EVOLUTION.md`. Ces tests ne mesurent pas la précision sur de vraies vidéos
journalistiques et ne valident pas l’accès actuel de TikTok depuis votre VPS.

Références techniques : [OpenCV et homographies](https://docs.opencv.org/4.12.0/d9/d0c/group__calib3d.html),
[yt-dlp](https://github.com/yt-dlp/yt-dlp),
[OpenCV](https://opencv.org/).


## Période de publication facultative

Ouvrir **Période de publication**, puis renseigner **Du** et/ou **Au**. Les deux jours
sont inclus, selon la date UTC de publication. Une seule borne est possible ;
**Effacer la période** rétablit la collecte sans filtre de date. Le choix est conservé
au rechargement de la session. Le filtre se combine avec les sources, ET/OU et le français.

La période s’applique aux publications effectivement consultées dans la limite choisie.
Elle ne constitue pas une recherche historique exhaustive dans TikTok : les publications
anciennes peuvent ne pas apparaître parmi les liens accessibles. Avec un filtre actif,
les dates absentes ou illisibles sont écartées et comptées séparément des dates hors période.
Les publications écartées ne figurent pas dans le TXT, les corpus, les mesures d’engagement,
les commentaires ni les lots vidéo. Le journal enrichi conserve leurs identifiants, dates
observées et motifs d’exclusion. Sans période, le fonctionnement antérieur est conservé.

L’API `/api/jobs` accepte `date_debut` et `date_fin` au format `AAAA-MM-JJ` (ou `null`).
Une période inversée ou une date invalide est refusée.


## Interface Streamlit de collecte

L’accueil utilise `streamlit_app.py` avec deux onglets **Collecte** et **Aide**.
Les options vidéo, les boutons de comparaison et l’aide audiovisuelle ont été retirés.
Les exports TXT/ZIP, les commentaires, ET/OU, les dates et le filtre français restent disponibles.
Les modules audiovisuels restent utilisables via l’API et le traitement par lots.

Les comptes sélectionnés sont tous transmis au moteur. En mode presse/comptes,
la recherche des publications démarre immédiatement, sans confirmation préalable
« Vérifiez les publications publiques » et sans demander de connexion.
Les liens repérés sont indiqués pendant la recherche. Les comptes accessibles
s’enchaînent automatiquement dans le même navigateur. Une
vérification TikTok réelle demande toujours une intervention. Le panneau **Médias
pris en compte par la collecte** affiche la sélection reçue par le moteur ; le message
indique la source courante et le nombre total. **Détail des sources** indique les liens trouvés et les sources
inaccessibles ; une vérification TikTok non terminée est distinguée d’une page sans
publication lisible. En mode presse/comptes, au moins un hashtag doit être renseigné. Chaque compte sélectionné est recherché avec chacun des hashtags, dans le même navigateur anonyme ; les autres auteurs sont exclus. Une redirection vers une page générale est signalée et ses liens ne sont pas collectés. Aucun repli vers un profil ou une recherche de hashtag général n’est effectué. Les CAPTCHA et les recherches bloquées ouvrent automatiquement la fenêtre ; les résultats partiels restent conservés. En mode hashtag, une page sans lien permet toujours une intervention manuelle. Les erreurs de navigation, de réseau et de navigateur sont distinguées dans le diagnostic de chaque source. Aucun cookie ni capture n’est exporté.

Le navigateur utilise le chargement `eager` puis attend explicitement les publications. Un délai dépassé n’autorise la lecture que si le document visible correspond exactement à la recherche ou à la publication demandée ; les anciennes pages sont rejetées. Voir la [documentation Selenium](https://www.selenium.dev/documentation/webdriver/drivers/options/#pageloadstrategy). Les compteurs de filtres et d’erreurs de lecture expliquent les
résultats vides sans les assimiler à l’absence de publications du média.

`lancer_interface.py` démarre FastAPI sur le port public et Streamlit sur un port local
privé. `interface/passerelle.py` relaie HTTP et WebSocket à la racine du domaine, avec cookie
privé, contrôle d’origine et protection HTTP optionnelle conservés. Aucun port additionnel
n’est à exposer. L’adresse reste `https://scraptiktok.codeandcortex.fr/` ; les anciens
liens `/interface/` redirigent vers `/`. Les téléchargements restent des routes FastAPI privées ; les données
utilisateur ne sont pas placées dans un cache Streamlit partagé. Une fenêtre intégrée
charge uniquement `/controle?collecte=<identifiant>` : aucun formulaire de recherche
ni option vidéo cachés. Ses actions visent la collecte affichée, même si un autre
onglet ouvre une collecte plus récente. Elle n’est pas recréée à chaque image.
Le CAPTCHA reste à traiter manuellement dans la fenêtre intégrée.
Une identification imposée par TikTok est signalée comme une limite d’accès anonyme.
L’image reste dans Streamlit ; aucun bouton d’ouverture dans un autre onglet n’est proposé.

Streamlit est l’unique interface utilisateur. Le formulaire HTML historique, son
JavaScript et sa feuille de style sont supprimés ; `/classique` renvoie 404.
L’ancien réglage `UI_STREAMLIT` ne sélectionne plus d’interface alternative.
`webapp.py` reste le serveur technique des collectes, des sessions privées, des
exports et du contrôle TikTok intégré. Le moteur CLI reste utilisable.
Démarrer l’application avec **`python lancer_interface.py`** ; Docker utilise
également ce lanceur. Lancer seulement Uvicorn ne démarre pas Streamlit.
Les dates, ET/OU, les commentaires, les exports et le filtre français sont conservés.

Streamlit apporte ses dépendances d’affichage (dont NumPy/Pillow), mais la collecte
ne charge pas OpenCV au démarrage de la collecte. CLIP a été supprimé.
Le Dockerfile installe directement les dépendances OpenCV nécessaires à Désordre visuel ; `INSTALL_VIDEO` n'est plus utilisé comme argument de construction.
En local : `pip install -r analyse_desordre/requirements.txt` et installer ffmpeg.
La CI vérifie les traitements de collecte, le contrôle d'accès et le
parcours Streamlit, avec une source synthétique hors TikTok. L’[audit des interfaces](AUDIT_INTERFACES.md)
décrit leur séparation et les limites de cette validation.

Références d’intégration : [fragments Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
et [contexte de session](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.context).

### Une session pour plusieurs sources

Les deux hashtags (ET comme OU) et les comptes sélectionnés utilisent le même
navigateur et ses cookies pendant toute la collecte. En mode hashtag, la vérification
initiale manuelle n’est demandée qu’une fois ; en mode presse/comptes, elle n'est pas
demandée. La deuxième source accessible est consultée
automatiquement. Si TikTok affiche un CAPTCHA, la collecte s’interrompt de nouveau
pour permettre l’intervention de l’utilisateur. Le mode presse/comptes ne met pas
le lot en attente d'une authentification TikTok.
La correction supprime les pauses systématiques ajoutées par l’application ; elle
ne supprime pas les vérifications décidées par TikTok.

Le parcours Chrome synthétique vérifie deux hashtags, une seule validation,
la conservation du cookie de test et l’export TXT/ZIP. Les tests unitaires vérifient
aussi qu’un nouveau blocage visible déclenche bien une intervention et que les
comptes de presse partagent la même session.

### Démarrage et arrêt cohérents

Le lanceur réserve le port public et refuse un port Streamlit déjà occupé : il ne
reprend jamais volontairement l’interface d’un ancien processus. FastAPI et
Streamlit sont deux services de la même application, avec un seul moteur de collecte.
Un arrêt normal (SIGTERM/SIGINT) ferme également le processus Streamlit. Si Streamlit
s’arrête pendant l’exécution, le moteur s’arrête à son tour pour permettre un
redémarrage complet par le superviseur Docker. Aucun réglage Redis n’est modifié.

`python tests/smoke_demarrage.py` vérifie avec de vrais processus le refus des doublons,
la fermeture des ports après SIGTERM et l’arrêt du moteur après perte de Streamlit.
Ce test est également exécuté par le point d’entrée navigateur de la CI.

## Collecte uniquement anonyme

Aucune option de connexion TikTok, aucun écran de connexion ouvert par le moteur et aucun profil Chrome persistant ne sont proposés. Hashtags, profils et médias utilisent un navigateur neuf, commun aux opérations d’une collecte, puis fermé à la fin. Une ancienne requête contenant l’option de connexion supprimée ne peut pas réactiver cette fonctionnalité.

Les invitations de TikTok sont fermées avec leur bouton lorsque c’est possible. Une restriction restante est signalée comme une collecte partielle ou une source inaccessible ; les textes déjà obtenus restent exportables. Le CAPTCHA peut toujours être traité manuellement dans la fenêtre intégrée à Streamlit. Le lien d’ouverture dans un autre onglet et les commandes API d’ouverture manuelle et de connexion ont été supprimés.


### Télécharger les vidéos MP4 (facultatif)

Cocher **Télécharger les vidéos (MP4)** avant de lancer la collecte (hashtags,
profils ou presse). L’option est désactivée par défaut. Le module indépendant
`telechargement_videos.py` utilise [yt-dlp](https://github.com/yt-dlp/yt-dlp#usage-and-options),
inclus dans les dépendances de base, sans charger les dépendances d’analyse vidéo.
Il télécharge les publications retenues après les filtres, après la fermeture de
Selenium. Avant cette fermeture, seuls les cookies techniques TikTok autorisés par
une liste fermée et le User-Agent sont repris depuis la session anonyme. Les cookies
de connexion (`sessionid`, `sid_tt`, etc.) sont exclus. Un fichier temporaire privé,
hors des exports, transmet les cookies techniques à yt-dlp puis est détruit après
chaque téléchargement. Le contexte en mémoire est effacé à la fin du lot. Aucune
connexion à un compte ni conservation de session authentifiée n’est ajoutée.
L’extra `curl-cffi` de yt-dlp apporte le support réseau de navigateur décrit dans sa
[documentation officielle](https://github.com/yt-dlp/yt-dlp#impersonation).

Le TXT conserve la nomenclature existante : `*id_123456789` correspond à
`videos/id_123456789.mp4` dans l’archive ZIP. Avec cette option, l’identifiant est
inclus même si la variable « ID vidéo » est décochée. Les autres variables, le choix
avec/sans @, les commentaires et les hashtags conservent leur fonctionnement.
Le corpus principal de l’archive reste identique au TXT téléchargé.

Les champs `video_id`, `video_url` (URL publique de la publication) et
`video_fichier` (chemin relatif dans l’archive) sont conservés dans les CSV par
publication et les JSON. `videos.csv` et `videos.json` détaillent le résultat par
publication. `video_fichier` reste vide/null en cas d’échec ; aucun fichier fictif
n’est annoncé. Le bilan MP4 apparaît dans les résultats Streamlit. Les erreurs sont
distinguées : connexion demandée, vérification TikTok, HTTP 403/429, problème réseau,
extraction de la page impossible ou format MP4 absent. `video_diagnostic` indique
la version de yt-dlp, son code de sortie, la disponibilité de curl-cffi et le nombre
de cookies techniques transmis. La sortie brute est lue dans un tampon mémoire
borné, puis effacée : aucune valeur de cookie ni URL signée n’entre dans les journaux,
les CSV ou les JSON. Ces diagnostics ne prouvent pas à eux seuls une cause unique.

Les doublons sont évités par identifiant dans la collecte et un MP4 déjà présent
est réutilisé dans la même session. Les téléchargements sont séquentiels : 120 s
et 256 Mio maximum par vidéo, 15 minutes et 2 Gio maximum pour le lot. Une réserve
disque est gardée pour le texte et la préparation du ZIP. Le bouton d’arrêt
interrompt aussi les téléchargements ; les textes et MP4 déjà obtenus restent
exportables. Les fichiers temporaires d’un échec sont supprimés. La durée de
conservation habituelle de la session s’applique également aux MP4.

Seuls les formats MP4 accessibles via yt-dlp sont récupérés. Une restriction TikTok,
un diaporama, un délai dépassé ou une limite de ressources est signalé et n’annule
pas la collecte textuelle. Le téléchargement ne garantit pas l’accès à chaque vidéo.

