# ScrapTikTok — interface Streamlit minimaliste

Saisir un hashtag, collecter les **légendes/descriptions** des publications TikTok,
puis télécharger un fichier **`.txt` en UTF-8**. L'interface fonctionne sur
ordinateur et mobile. Le navigateur Selenium s'exécute sur le serveur :
l'utilisateur n'a rien à installer.


### Session facultative pour Presse (30 octobre 2026)

Avec **Méthode Playwright** ou **Méthode Selenium**, ouvrir **Session TikTok —
cookies facultatifs**, puis importer un fichier `.txt` au format Netscape issu
de sa propre session TikTok. L'import est limité à 1 Mo et aux domaines TikTok ;
les cookies expirés sont ignorés. Les données restent dans la mémoire de cette
collecte, sont exclues des exports/archives/diagnostics, puis effacées à sa fin.
Le champ d'import est vidé après le lancement. Sans fichier, le mode anonyme
reste disponible. La présence de cookies ne prouve pas que la session est valide.

L'administrateur peut aussi monter un fichier Netscape en lecture seule hors
Git et hors exports, puis définir `SCRAPTIKTOK_COOKIES_FILE` avec son chemin
interne au conteneur. Ce réglage existait pour l'API web ; il est maintenant
appliqué avant la navigation Presse Selenium et Playwright. Le fichier fourni
dans l'interface est prioritaire et n'est jamais enregistré sur disque.
L'import d'interface ne concerne ni Research, ni les collectes par hashtags.

Playwright conserve les réponses natives `/api/post/item_list/` et
`/api/creator/item_list/`, vérifie chaque auteur et exclut les photos. Il peut
ainsi récupérer les vidéos et leurs métadonnées même si la grille HTML ne se
monte pas. Il ne fabrique pas de signature et ne rejoue pas ces requêtes.
La fenêtre de contrôle existante fonctionne maintenant avec Playwright :
captures, clics, déplacement du pointeur, défilement, Continuer et arrêt.
Une vérification est traitée manuellement dans le même navigateur, une fois
par source. Un HTTP 429 arrête le lot, sans intervention proposée ni autre média
sollicité. Une réponse vide est comptabilisée comme telle, pas comme une preuve
que le compte n'a pas de vidéos.

Les tests de pages simulées valident ces parcours ; ils ne prouvent pas que
TikTok accepte une session réelle depuis le VPS. Lors du contrôle du 30 octobre,
l'embed public de `@lemondefr` répondait HTTP 429. Une collecte réelle avec une
session valide reste nécessaire pour confirmer la résolution du blocage TikTok.

Références examinées : [OpenCLI #2568](https://github.com/jackwener/OpenCLI/issues/2568),
[TikTok-Api #1311](https://github.com/davidteather/TikTok-Api/issues/1311),
[observations OpenTok](https://github.com/caixax/opentok/blob/main/docs/TIKTOK-API.md).
Ces rapports décrivent des observations, pas une garantie de fonctionnement.

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
- **Méthode Playwright** : navigateur distinct, sans basculement implicite
  vers une autre méthode. La découverte attend jusqu'à 20 secondes les premiers
  liens, puis vérifie les nouvelles publications après chaque défilement, y
  compris le dernier. Les liens déjà reçus restent conservés si la suite échoue.

Les moteurs navigateur réexaminent une rubrique Vidéos apparue tardivement et
retentent de façon bornée un clic resté sans effet avant le chargement de React.
Ils distinguent les erreurs de navigateur, les vérifications TikTok et les
profils sans liens après attente. Les diagnostics des nouvelles collectes
indiquent `playwright-presse-v4-navigation` ou `selenium-presse-v3-reseau`.
Playwright recherche la rubrique Vidéos même si l'accueil affiche une erreur :
il suit le lien réellement présent, ou sélectionne l'onglet sur place. Selenium
conserve aussi les vidéos du bon auteur reçues par le réseau avant l'apparition
de la grille HTML. Les photos et publications d'autres comptes restent exclues.
Ces corrections sont couvertes par des tests de régression, dont des pages
dynamiques dans un vrai navigateur. Elles ne garantissent pas la fourniture
des publications par TikTok dans une session donnée.
Playwright respecte désormais le réglage `SCRAPTIKTOK_HEADLESS` déjà utilisé par
Selenium ; l’image Docker fournit Xvfb lorsque ce réglage vaut `0`.
La correction des attentes ne supprime pas une limitation HTTP 429 de l'API
web secUid ; aucune relance en rafale ni changement de méthode ne la contourne.

Références : [chargement et hydratation Playwright](https://playwright.dev/python/docs/navigations#hydration)
et [attentes explicites Selenium](https://www.selenium.dev/documentation/webdriver/waits/).


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
Lorsque l'option IA est décochée, la légende complète fournie dans les données
TikTok est utilisée immédiatement ; le dépliage reste réservé au repli sur un
texte affiché potentiellement tronqué. Pour les hashtags, les débuts de lecture
restent espacés de trois secondes au minimum, mais le temps passé à lire une
page compte dans cet intervalle. La fin du défilement est confirmée sur un délai
cumulé de 20 secondes sans nouveau lien, plutôt que trois attentes de 20 secondes.

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

La même règle linguistique de `language_filter.py` s'applique aux collectes
Hashtags, Presse et médias, et Autres comptes TikTok. Une légende détectée en
français est conservée. Les légendes courtes, composées de hashtags, ambiguës ou
bilingues restent également dans le TXT, avec la modalité
`retenue_langue_indeterminee`. Une prédiction étrangère élevée ne suffit plus
à exclure une publication : la légende doit comporter au moins dix mots et
45 lettres, présenter une probabilité d'au moins 0,99, ne pas fournir plusieurs
indices grammaticaux français et être classée dans la même langue étrangère
dans ses deux moitiés, chacune avec une probabilité d'au moins 0,80.
À défaut, la langue est indéterminée et la publication est conservée.

Seules les légendes suffisamment étayées comme étrangères sont écartées sous
le motif `autre_langue`. Les compteurs distinguent ces exclusions des légendes
indéterminées conservées. La voix et le texte incrusté dans la vidéo ne sont
pas analysés. Le tableau conserve toutes les publications consultées et leur
décision ; l'export porte le suffixe `_fr.txt`. La langue ne peut être évaluée
qu'après lecture de la légende : ce filtre ne constitue pas une recherche
TikTok limitée à la langue française avant collecte. L'API conserve les langues
par défaut ; envoyer `french_only: true` active le filtre.

Le pays d'enregistrement du compte (`region_code`) n'établit pas la langue de
la légende. Il n'autorise donc pas à contourner le filtre, même pour les comptes
français importés depuis un CSV.

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

L'onglet principal **Collecte de compte** est indépendant de **Collecte**.
Son interface complète réside dans `collcompte.py` : recherche territoriale,
croisement des hashtags, inventaires, résultats justificatifs, pagination,
arrêt, poursuite et exports. L'ancien module
`interface/decouverte_territoriale_ui.py` reste un point d'entrée compatible.

Dans l'onglet **Collecte**, choisir **Presse et médias** ou
**Autres comptes TikTok**. Ce dernier mode est réservé à la collecte de profils
et conserve ses paramètres et analyses habituels.
Dans **Collecte de compte**, l'option All transmet tous les profils sélectionnés
vers **Collecte → Autres comptes TikTok** sans découpage manuel en lots.
Les comptes sont ensuite parcourus par le moteur choisi, sous réserve de ses
contraintes d'accès et de quotas. Le transfert active le mode Autres comptes
dans le formulaire, sans lancer automatiquement de collecte.
Dans **Collecte → Autres comptes TikTok**, on peut aussi importer un ou plusieurs
CSV de comptes provenant d'une collecte antérieure, sans relancer la découverte.
Les colonnes `username` (export `comptes.csv` de ScrapTikTok), `compte`,
`profil`, `author` et `url_compte` sont acceptées, ainsi que les fichiers à une
colonne d'identifiants sans en-tête. Les séparateurs `;`, `,` et les tabulations
sont reconnus. Les comptes sont normalisés et dédoublonnés ; les identifiants
invalides sont signalés. Le bouton de chargement remplace seulement la liste
des comptes à examiner dans le formulaire, sans modifier les filtres, exports
ou collectes déjà sauvegardés. Ce chargement lance une nouvelle collecte de
profils : un CSV de comptes ne contient pas le curseur d'une collecte interrompue.

**La découverte territoriale et la collecte de profils sont deux corpus distincts.**
La première identifie les auteurs à partir de vidéos vérifiant territoire ET
hashtags. Le CSV conserve les auteurs et la première preuve vidéo, mais il
ne transfère pas automatiquement la sélection des cinq hashtags, l'opérateur
ET/OU, la période ni le critère Toulouse à la collecte de profils.

Les collectes **Hashtags**, **Autres comptes TikTok**, **Presse et médias**
(lorsque le croisement est activé) et **Collecte de compte** proposent désormais
l'opérateur `OU` par défaut dans l'interface et les modèles de l'API. Le choix
explicite `ET` reste disponible et est préservé lorsqu'on rouvre une collecte
ayant ce paramètre. `OU` signifie qu'au moins un des hashtags demandés doit
être présent **dans chaque vidéo** ; `ET` exige la présence de tous les hashtags
**dans cette même vidéo**, pas dans l'ensemble des publications d'un compte.
Le mode **Autres comptes TikTok** conserve un opérateur indépendant de celui
du mode Hashtags pour éviter qu'un choix précédent soit réutilisé par erreur.

Avec la **Research API officielle**, ScrapTikTok transmet à TikTok le compte
et la combinaison exacte de hashtags dès la requête de découverte
(`username EQ` ET `hashtag_name IN` pour OU, ou plusieurs `hashtag_name EQ`
pour ET). Il revérifie ensuite les hashtags officiels et ceux de la légende
à l'export, comme pour les autres modes. Il ne doit plus rechercher
des milliers de publications du compte sans contrainte de hashtags puis
les éliminer au moment de constituer le TXT. La période sélectionnée
dans la seconde collecte doit être identique à celle de la découverte
territoriale si l'on souhaite retrouver les vidéos de départ.

Pour les autres moteurs, les hashtags restent vérifiés après la lecture
des publications accessibles. La couverture d'un profil et l'exhaustivité
de la Research API ne sont pas garanties, notamment lors d'erreurs 5xx.
Le mode Hashtags conserve ses propres critères indépendants.

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

L’inventaire `config/comptes_presse.json` contient désormais 75 comptes
sélectionnables, après retrait des variantes `@liberationfr` et `@m6info`
lors de demandes antérieures. Le compte `@liberation.fr`
et tous les autres médias sont conservés. L'Humanité (`@lhumanitefr`) est
présent dans la presse écrite nationale. Mediapart (`@mediapartfr`) a été
reclassé en presse nationale, sous-groupe presse écrite. "L’info en 60
secondes" (`@iuzdrmqevnu`) a été ajouté à la presse indépendante.
Politis (`@politis_fr`) a été reclassé en presse nationale, dans le
sous-groupe affiché « Presse nationale », sans modification d'identifiant.
France 24 (`@france24`) a été ajouté dans les chaînes de télévision nationales.
Onze comptes France 3 ont été ajoutés à la presse régionale :
`@france3nouvelleaquitaine`, `@france3grandest`, `@france3bretagne`,
`@france3bfc`, `@france3normandie`, `@f3cvdl`,
`@france3hautsdefrance`, `@france3paris_idf`, `@france3pdl`,
`@france3paca` et `@france_3_aura`. Le compte `@france3occitanie`
déjà présent a été conservé.
L'interface regroupe les comptes en presse nationale
(26, avec les deux sous-groupes affichés « Chaînes de télévision nationales »
et « Presse nationale »), presse régionale (32), presse indépendante (7)
et autres
médias ou statut à confirmer (10), dont @noahdecrypte (Noah Décrypte) et @marc.verdenet (Marc Verdenet). Les comptes @lehuffpostfr, @cquoilinfo,
@hugodecrypte et @brutofficiel sont classés en presse indépendante sans
suppression ni changement d'identifiant. La liste des comptes est affichée
sans interligne entre les cases à cocher dans chaque groupe. Les six références éditoriales initiales
et les identifiants historiques sont préservés. Les comptes fournis par
l’utilisateur sont signalés comme tels lorsque leur propriété sur TikTok
n’a pas été vérifiée. Les identifiants différents sont conservés comme
entrées distinctes conservées lorsque cela est pertinent. Pour M6 Info,
seul `@m6info_` est conservé ; la variante `@m6info` a été retirée à la
demande de l'utilisateur. Le compte CNews utilise `@cnews` ; son identifiant
interne `cnewsofficiel` demeure inchangé pour préserver les sélections antérieures.
`@liberation.fr` demeure présent ; la variante `@liberationfr` a été
retirée à la demande de l'utilisateur. Les liens fournis pour `@lobs`
pointaient vers d’autres comptes : leur propriété doit être vérifiée avant
exploitation scientifique. Une collecte peut sélectionner
jusqu'au nombre de médias présents dans l’inventaire ; les autres bornes
techniques et le traitement séquentiel restent inchangés.

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

## Collecte anonyme par défaut

Le moteur n’ouvre aucun écran de connexion et ne conserve aucun profil Chrome persistant. Presse accepte désormais un import facultatif de cookies, décrit au début de ce document. Hashtags, profils et médias utilisent un navigateur neuf, commun aux opérations d’une collecte, puis fermé à la fin. Une ancienne requête contenant l’option de connexion supprimée ne peut pas réactiver cette fonctionnalité.

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

## Collecte Research programmée et base SQLite persistante

Dans le moteur « Research API officielle », cocher « Collecte pluri-journalière
(SQLite, reprise automatique) », définir la **période des publications** puis
le **début et la fin d'exécution**. Le bouton « Programmer la collecte Research »
crée un plan. Les contrôles « Afficher mes collectes Research programmées »
permettent de consulter la progression, de suspendre, reprendre ou arrêter
définitivement une collecte et de télécharger les résultats.

La base permanente `DATA_DIR/collectes_research.sqlite3` conserve les plans,
les positions par source et journée, les publications, commentaires, journaux
et compteurs de requêtes. Contrairement à `scraptiktok.sqlite`, liée aux
sessions temporaires, **elle n'est pas supprimée par la purge des résultats**.
Les identifiants des vidéos et commentaires servent de clés de dédoublonnage.
La date de première et de dernière collecte est également conservée.
Les publications sont enregistrées au fil de l'exécution ; la fin d'un lot
permet d'avancer à la journée ou à la source suivante. Une interruption sur
un lot incomplet entraîne une nouvelle tentative le lendemain à partir de
la même journée et de la même source. Cette reprise préserve les données déjà
stockées, mais peut consommer à nouveau des requêtes et n'est pas une reprise
garantie au curseur exact de TikTok.

La collecte programmée exige une configuration permanente des variables
`TIKTOK_RESEARCH_CLIENT_KEY` et `TIKTOK_RESEARCH_CLIENT_SECRET` dans
**Coolify**. Les clés et jetons ne sont jamais écrits dans SQLite ni les ZIP.
La collecte reprend sans connexion du navigateur grâce au planificateur du
service FastAPI, à condition que le conteneur et son volume soient actifs.
### Sauvegarde automatique PostgreSQL

Avec `RESEARCH_POSTGRES_DSN` renseigné dans Coolify, les collectes ponctuelles
créent leur entrée dans `scraptiktok_collectes` **avant** le lancement du
moteur. Les vidéos et commentaires sont archivés progressivement dans
`scraptiktok_publications` et `scraptiktok_commentaires` : après chaque
média traité et toutes les dix publications consultées, puis lors de la
finalisation. L'archivage utilise des insertions ou mises à jour idempotentes
et n'enregistre aux points intermédiaires que les nouvelles observations.
Le statut et les compteurs sont visibles pendant la collecte dans Streamlit.
Une sauvegarde PostgreSQL initiale impossible empêche le lancement du job,
afin de ne pas consommer de quota TikTok sans archivage disponible.

L'option « Sauvegarde progressive ZIP » est indépendante de ce mécanisme.
Pour les **collectes Research programmées**, la sauvegarde permanente par
publication est d'abord assurée dans SQLite ; PostgreSQL est synchronisé
après chaque lot programmé, dans les tables `research_plans`,
`research_publications` et `research_commentaires`. Le programme
conserve son bouton de synchronisation manuelle.

Le quota de précaution `RESEARCH_QUOTA_LOCAL_JOUR` est de 900 requêtes par
jour UTC par défaut (maximum 1 000). Il couvre les requêtes Research effectuées
par cette instance, mais n'englobe pas les autres applications partageant
éventuellement le quota officiel de l'organisation. Le dépassement suspend
les nouveaux appels Research jusqu'au jour UTC suivant.

Les résultats cumulés restent disponibles à l'export en SQLite relationnel
(tables publications et commentaires avec colonnes interrogeables), CSV, JSON,
TXT et ZIP. L'accès est contrôlé au moyen du cookie historique privé de
l'utilisateur. Ce mode ne télécharge pas de MP4 et ne lance pas Selenium pour
les textes IA. Les traitements restent soumis à `MAX_CONCURRENT_JOBS` et au
délai maximal de chaque lot `JOB_TIMEOUT_SECONDS`. La date de fin d'exécution
interrompt également les lots actifs, même si le corpus est incomplet.

SQLite convient à une instance de ScrapTikTok avec écriture séquentielle,
volume persistant et export à la demande. Pour des écritures simultanées depuis
plusieurs conteneurs ou des comptes utilisateurs partagés, préférer PostgreSQL
avec une migration explicite et des sauvegardes administrées, plutôt que
de partager le même fichier SQLite entre instances.

### Consultation tabulaire directement dans les tables PostgreSQL

La table **`scraptiktok_publications` elle-même** possède une colonne
par variable TikTok : profil, date, URL, région, vérification, abonnés,
compteurs numériques et bruts, classes, durée, langue, hashtags, textes,
indicateurs IA, état de la collecte des commentaires et informations MP4.
Chaque ligne reste une vidéo, identifiée par `collecte_id` et `publication_id`.

Les nouvelles colonnes utilisent `GENERATED ALWAYS AS (...) STORED`.
PostgreSQL les renseigne **pour les lignes déjà enregistrées**, puis les
actualise automatiquement lors de chaque insertion ou modification du JSONB.
La colonne `donnees` d'origine est conservée pour éviter toute perte et
permettre de retrouver les valeurs non encore dépliées. Les valeurs absentes
deviennent `NULL`, et ne sont jamais forcées à zéro. Il n'est pas nécessaire
de changer le code d'insertion des publications.

La migration additive est lancée à l'initialisation PostgreSQL au démarrage
de ScrapTikTok et vérifiée à l'ouverture d'une nouvelle collecte. Si le
schéma est déjà complet, aucune commande ALTER TABLE n'est exécutée.
Sur une grosse table, la première migration peut prendre du temps : PostgreSQL
doit réécrire la table pour les colonnes calculées stockées. Sauvegarder la
base et ne pas redéployer pendant une collecte active.

Dans pgAdmin : **Databases → postgres → Schemas → public → Tables**,
puis ouvrir `scraptiktok_publications` et afficher les lignes. Cette table
dispose directement des colonnes, sans passage par une vue ou une requête SQL.
Les champs `collecte_id`, `publication_id`, `retenue` et `donnees`
restent présents, suivis des variables ajoutées.

Les vues de compatibilité `scraptiktok_publications_tableau` et
`scraptiktok_commentaires_tableau` restent disponibles sous **Views**.
Les commentaires détaillés restent dans `scraptiktok_commentaires`,
reliés aux vidéos, pour ne pas dupliquer les publications.

L'export CSV/JSON et les données déjà sauvegardées sont conservés.

### Téléchargement des résultats d'une collecte

Dans l'onglet **Collecte**, le champ obligatoire **Nom de la collecte**
situé en haut de la page fournit automatiquement le nom de l'archive ZIP.
Il n'est pas nécessaire de renseigner un deuxième champ.

Une fois la collecte ponctuelle terminée, un seul bouton
**Télécharger les résultats** remplace les téléchargements séparés TXT,
compteurs CSV, commentaires et archive. Le ZIP conserve tous les fichiers
précédemment enregistrés, y compris `publications.csv`,
`engagement.csv`, `publications.json`, les autres CSV/JSON/TXT,
les MP4 disponibles si leur collecte était activée, ainsi que les
commentaires TXT et le diagnostic de collecte disponibles.

Chaque collecte Research programmée propose également un bouton
**Télécharger les résultats** ; son ZIP contient
`publications.csv`, `commentaires.csv`, `collecte.json`,
`textes.txt`, `corpus.sqlite3` et `journal_research.json`.
L'archive est nommée d'après la collecte, avec les caractères impropres
aux noms de fichiers remplacés par des underscores.

Les sauvegardes de récupération intermédiaires, et les deux sauvegardes
distinctes de l'historique d'analyse, conservent leurs propres commandes :
elles remplissent des fonctions indépendantes du téléchargement final.

### Fichiers publications.csv : variables complètes

Les collectes ponctuelles conservent par défaut les colonnes
historiques de `publications.csv` et `engagement.csv`. Chaque variable
du formulaire dispose maintenant de deux cases indépendantes sur la même
ligne : **TXT** ajoute la modalité à l'en-tête IRaMuTeQ et **CSV** ajoute
la ou les colonnes descriptives correspondantes à `publications.csv`
et `engagement.csv`. Le recodage en classe est un choix distinct de la
valeur numérique réelle ; les deux peuvent être activés simultanément,
dans chacun des deux formats. Le choix s'applique aussi à l'export de
republications lorsqu'il existe. Les identifiants de liaison techniques
(`publication_id`) sont toujours conservés pour réimporter les tableaux
et joindre les commentaires. Les archives anciennes, qui n'ont pas de
`variables_csv`, continuent de produire toutes leurs colonnes historiques.
Les exports de profils, commentaires et ratios conservent leurs propres
structures ; la colonne `ville_etude` des commentaires suit aussi son
choix CSV. Les JSON gardent les données collectées indépendamment du
choix de présentation des tableaux.

Les indicateurs proposés comprennent identifiants, dates, profil, `region_code`,
`is_verified`, abonnés, vues, likes, partages, commentaires, favoris, durée,
valeurs numériques et classes, taux d'engagement, catégories de presse.
Les intervalles de recodage sont conservés dans les aides des lignes.
Pour le compteur `follower_count`, la sélection d'au moins une case
TXT ou CSV de récupération, de valeur brute ou de classe déclenche la
requête Research correspondante. L'option de récupération et celle de
valeur brute renvoient au même compteur : il n'est pas dupliqué.
La récupération des textes des commentaires reste indépendante.

Une case cochée dans l'interface ne garantit pas que TikTok fournisse la
valeur correspondante : dans ce cas, la cellule CSV reste vide. Les vrais
zéros sont conservés. La collecte des textes des commentaires reste dans
`commentaires.csv` pour respecter la relation plusieurs commentaires /
une publication. Les exports téléchargés après mise à jour utilisent le
nouveau schéma ; les ZIP anciens déjà téléchargés ne changent pas.

### Ville du corpus pour IRaMuTeQ

En mode **Autres comptes TikTok**, le champ **Ville associée au corpus**
permet de déclarer la provenance sociologique du lot de comptes. La saisie
`Toulouse` est normalisée en `toulouse` ; cocher TXT ajoute
`*ville_toulouse` avant chaque texte original ou résumé IA dans le TXT
IRaMuTeQ. Cocher CSV ajoute `ville_etude` aux exports correspondants,
avec la valeur `toulouse`. Les deux choix sont indépendants.
La ville est préremplie lors du transfert d'un inventaire territorial
ou d'un CSV de comptes possédant une provenance unique. Les CSV mixtes
ne reçoivent pas arbitrairement une seule ville.

La variable décrit le **critère de constitution du corpus**, non la
résidence de chaque auteur ni la géolocalisation de ses vidéos. La
fonction de découverte TikTok utilise une mention de ville dans les
vidéos et éventuellement une référence de lieu indirecte. La modalité
ne doit pas être utilisée pour conclure à une localisation vérifiée.

### Commentaires Research et analyse sociométrique

L'endpoint Research API `/v2/research/video/comment/list/` ne donne pas
de `username` stable du commentateur. La colonne `auteur` des commentaires
Research reste donc vide par conception, même si tous les textes et les ID
ont été collectés correctement. TikTok documente un `display_name` parfois
présent dans les réponses, sans le proposer dans la liste des champs
demandables ; une nouvelle colonne facultative `nom_affiche` le conserve
lorsqu'il est réellement fourni, sans l'assimiler à un identifiant unique.
Ce champ ne peut pas servir à calculer un réseau d'auteurs fiables.

Dans **Analyse sociométrique à partir de fichiers CSV**, la présence de
commentaires Research est signalée, ainsi que les liens de réponse
potentiels. Les trois analyses historiques restent sélectionnables :
**Auteurs–vidéos**, **Vidéos–vidéos : commentateurs communs** et
**Commentaires : graphe des réponses**. Aucune sélection automatique du
graphe des réponses ne modifie le choix de l'utilisateur. Ce dernier
peut exploiter `id` et `parent_id` si les réponses ont été collectées.
Les graphes auteurs–vidéos et vidéos–vidéos ne sont pas inférés à partir
des noms affichés. Pour de nouvelles collectes avec Research, l'option de
collecte des réponses doit être activée si un graphe des réponses est
attendu ; elle ne permet pas de retrouver les identités des commentateurs.
Les archives historiques ne peuvent pas être enrichies automatiquement
en `username` par cette API.

Un troisième choix **Réseau de similarité de l'engagement** permet d'importer
directement un ou plusieurs `engagement.csv` ou `publications.csv`, sans
commentaires. Chaque nœud représente une vidéo et chaque lien une proximité
des compteurs sélectionnés : `vues` (`view_count`), `likes`
(`like_count`), `commentaires` (`comment_count`) et `partages`
(`share_count`). Chaque variable suit la transformation `log(1+x)`,
puis un centrage-réduction ; la similarité vaut
`1/(1+distance euclidienne moyenne quadratique)`. Le seuil de similarité,
le nombre de voisins et le nombre maximal de vidéos sont paramétrables.
Les vidéos dont une métrique sélectionnée manque sont exclues du calcul,
sans remplacer les valeurs absentes par zéro ; les dimensions constantes
ne déterminent aucune distance. Le nombre de vidéos éventuellement écartées
par limitation est affiché. Les exports CSV, GraphML et GEXF sont conservés,
avec matrice d'adjacence jusqu'à 250 nœuds. La comparaison est limitée
à 1 000 vidéos par calcul pour contrôler le coût quadratique.

Pour éviter les blocages de Streamlit, le calcul se lance désormais
uniquement en cliquant sur **Calculer le réseau de similarité**. Un
changement de seuil, de variables ou de taille du corpus n'exécute pas
l'analyse automatiquement ; les résultats ne sont réutilisés que si les
paramètres sont identiques. L'algorithme compare toujours les paires
nécessaires, mais ne conserve en mémoire que les meilleurs voisins
sélectionnés pour chaque vidéo, plutôt qu'une liste quadratique de paires.
Le bilan indique le nombre de comparaisons et les paires au seuil.

L'aperçu graphique est facultatif et désactivé après chaque nouveau
calcul pour éviter les charges de la simulation physique PyVis. Lorsqu'il
est activé, Graphviz est proposé avant PyVis et le rendu est limité à
80 nœuds par défaut, avec un maximum réglable de 200 ; l'export conserve
le réseau complet. Les exports CSV, GraphML, GEXF et matrice restent
disponibles sans activer l'aperçu et sont générés à la demande lors
du téléchargement, sans préparer tous les fichiers à chaque rerun.

**Attention à l'interprétation** : ce réseau statistique représente des
similarités de volumes d'engagement, non des liens sociaux ou des audiences
communes. Les quatre compteurs TikTok sont des indicateurs agrégés, sans
identité ni coactivité des personnes qui ont visionné ou réagi.

### Dossier local de téléchargement et noms de fichiers

Le serveur ScrapTikTok ne peut pas choisir le dossier de téléchargement
sur le Mac de l'utilisateur : le navigateur décide où enregistrer les
fichiers. Dans Firefox sur macOS, ouvrir **Paramètres → Général →
Fichiers et applications → Téléchargements → Enregistrer les fichiers
dans**, puis sélectionner le dossier local souhaité. Ce paramétrage
s'applique à tous les téléchargements de Firefox, pas uniquement à
ScrapTikTok. Le stockage PostgreSQL automatique reste sur le VPS :
seuls les fichiers téléchargés par l'utilisateur arrivent dans ce dossier.

Les téléchargements ZIP PostgreSQL, Research et ponctuels reprennent
le nom de la collecte. Les exports individuels incluent le nom de la
collecte puis le type de résultat (par exemple
`sauvegarde_test_3_annotations.csv`). Les sauvegardes de l'historique
ajoutent `_collecte` ou `_analyse` ; les CSV concaténés incluent
le type de fusion et la date. Aucun chemin local propre à un utilisateur
n'est enregistré dans le dépôt ou envoyé au serveur.

### Sauvegardes PostgreSQL, SQLite et concaténation de CSV

L'onglet **Base de données** rassemble désormais trois opérations distinctes.

**1. PostgreSQL — archives durables.** Les collectes ponctuelles sont
archivées automatiquement. Les collectes Research n'apparaissent dans
PostgreSQL qu'après synchronisation depuis SQLite. Choisir une collecte,
puis sélectionner **Télécharger tous les résultats (ZIP)**. Un seul fichier
regroupe les tableaux et variables des publications et commentaires en
CSV et JSON, les métriques (`engagement.csv`, `ratios_engagement.csv`,
`comparaison_medias.csv`), les corpus TXT, une version tabulaire SQLite
et les résultats annexes encore récupérables dans l'historique. Les MP4
originaux sont inclus uniquement si l'archive de la session est encore
accessible et s'ils ont réellement été téléchargés. L'archive conserve
également `informations_export.json` qui décrit les fichiers présents.
Les quatre boutons de téléchargement séparé ont été retirés de
l'interface, mais leurs API restent disponibles pour compatibilité.

ScrapTikTok ne supprime **pas automatiquement** les collectes PostgreSQL.
Leur conservation dépend de la persistance du serveur PostgreSQL, des
actions manuelles et des éventuelles règles d'administration extérieures.
Le ZIP exporte un corpus et **ne constitue pas** une sauvegarde complète
restaurable de l'instance PostgreSQL. Effectuer séparément des sauvegardes
physiques/logiques (par exemple `pg_dump`, puis `pg_restore`) pour la
reprise après une panne.

L'onglet PostgreSQL est volontairement réduit à trois opérations :
**choisir une collecte**, **télécharger tous ses résultats dans un ZIP**
et, si nécessaire, **supprimer la collecte** avec confirmation de son nom
exact. L'ancienne consultation paginée (publications/commentaires),
les champs de recherche et la commande de migration exceptionnelle de
l'historique local ne sont plus affichés. Les API de compatibilité restent
disponibles pour ne pas casser les autres fonctions.

Une collecte nommée `sauvegarde_test_3` n'est **pas** une table :
c'est un enregistrement de `scraptiktok_collectes` (ou de
`research_plans` pour une collecte Research). Pour supprimer une
collecte précise, sélectionner cette collecte dans l'application,
déplier **Supprimer cette collecte de PostgreSQL**, saisir son nom exact
et confirmer. Seul son identifiant est ciblé. Ses publications et ses
commentaires sont effacés par les relations `ON DELETE CASCADE`,
sans supprimer les tables ni les autres collectes. La suppression
n'affecte pas les éventuelles archives locales ou SQLite encore présentes.
Un programme Research en cours doit être arrêté avant de supprimer sa copie
PostgreSQL, afin d'éviter sa recréation immédiate.

Dans pgAdmin, la suppression manuelle équivalente s'effectue en
recherchant d'abord `collecte_id` dans `scraptiktok_collectes`,
puis en supprimant la seule ligne correspondant à cet identifiant.
Ne jamais utiliser `DROP TABLE` pour supprimer une collecte.


**2. SQLite — collectes Research programmées.** Cocher
**Afficher mes collectes SQLite Research**, choisir un programme, puis
**Télécharger cette collecte SQLite (ZIP)**. Le ZIP contient une copie
`corpus.sqlite3`, des CSV, des JSON et un TXT. La copie est **un extrait
tabulaire des données**, et non le fichier opérationnel
`collectes_research.sqlite3` contenant le calendrier de reprise.
**Copier cette collecte SQLite dans PostgreSQL** synchronise ses résultats
dans les tables `research_*` sans supprimer SQLite. Le moteur de collecte
continue de dépendre du fichier opérationnel situé dans `DATA_DIR`.

La sauvegarde temporaire de l'historique des analyses est conservée
**30 jours par défaut**, configurables via
`SCRAPTIKTOK_ANALYSIS_RETENTION_DAYS`. Elle est indépendante de la
persistance du fichier SQLite Research et des archives PostgreSQL.

**3. Concaténer des publications CSV.** Charger jusqu'à 20 fichiers CSV
(de 10 Mo maximum chacun, 100 000 lignes au total), issus de PostgreSQL,
SQLite, ou du ZIP des collectes. L'outil accepte les séparateurs virgule
et point-virgule, réunit les colonnes, conserve les identifiants TikTok
comme chaînes, compte les doublons et propose de privilégier le premier
ou le dernier enregistrement en cas de conflit. Télécharger ensuite le
**CSV concaténé**. Cette opération n'écrit aucune ligne dans PostgreSQL
ni dans SQLite ; elle est distincte de la fusion des tableaux d'analyse
multimodale. Les commentaires détaillés restent dans leurs propres fichiers.

### Archivage PostgreSQL facultatif

Si une base PostgreSQL est déjà accessible depuis Coolify, définir
`RESEARCH_POSTGRES_DSN` dans les variables secrètes du service. ScrapTikTok
conserve SQLite comme base principale pour le calendrier, la reprise et les
exports, et réplique les publications/commentaires de chaque programme vers
PostgreSQL. La réplication est rejouable avec « Synchroniser vers PostgreSQL »
dans la liste des collectes programmées. Les données y sont stockées dans
`research_plans`, `research_publications` et `research_commentaires`,
avec clés uniques et colonnes JSONB. L'absence ou l'indisponibilité de PostgreSQL
n'interrompt pas la collecte SQLite. Aucun serveur PostgreSQL n'est créé
automatiquement par cette option : une instance et des identifiants de base
doivent être configurés séparément dans Coolify.
