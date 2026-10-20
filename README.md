# ScrapTikTok — interface Streamlit minimaliste

Saisir un hashtag, collecter les **légendes/descriptions** des publications TikTok,
puis télécharger un fichier **`.txt` en UTF-8**. L'interface fonctionne sur
ordinateur et mobile. Le navigateur Selenium s'exécute sur le serveur :
l'utilisateur n'a rien à installer.

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
lancer la collecte. Chaque recherche examine jusqu’à la limite choisie
par hashtag ; les publications communes sont dédoublonnées par identifiant.
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
Les CSV, JSON et corpus séparés des commentaires/transcriptions restent disponibles.
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
Ce choix peut être modifié après la collecte, avant chaque téléchargement.
Il s’applique au TXT et aux fichiers identiques `textes.txt` et `corpus_iramuteq.txt`
de l’archive. Les CSV, les mentions dans les légendes et les commentaires restent
inchangés ; aucune nouvelle collecte n’est nécessaire.

**Télécharger le fichier texte** applique les variables choisies et inclut les
commentaires récupérés si leur collecte est cochée. **Télécharger l’archive
enrichie** fournit JSON brut, CSV (UTF-8 BOM, séparateur `;`), corpus IRaMuTeQ et journal.
Les filtres ET/OU et français s’appliquent aux légendes retenues dans TXT/IRaMuTeQ.
Les publications brutes et mesures restent séparées ; `retenue` identifie la sélection.
Les commentaires sont collectés pour les publications retenues. Leurs exports séparés
et les corpus de transcriptions restent disponibles.
Les astérisques sont neutralisés uniquement dans le corps IRaMuTeQ, sans modifier le brut.

## Traitement audiovisuel facultatif

Les options vidéo ont été retirées de l’interface. Les modules restent accessibles
par l’API ou le traitement par lots, avec le profil vidéo décrit dans le guide de déploiement et une collecte enrichie. La détection de réemploi
s’exécute sans annotation manuelle. OCR, audio, Whisper et embeddings sont des options
indépendantes ; aucun modèle n’est téléchargé sans activer l’autorisation correspondante.
Le téléchargement vidéo se fait avec yt-dlp sur les URL publiques validées, sans exporter
les cookies du navigateur. Une vidéo inaccessible reste indéterminée, même si sa légende
a été collectée dans une session connectée. Les carrousels photo ne sont pas traités comme
vidéos et peuvent apparaître comme non analysables.

Les résultats distinguent :

- **Fichier identique** : même SHA-256 du fichier complet.
- **Réemploi de séquence** : présélection pHash, ORB + homographie RANSAC, puis alignement
  temporel monotone d’au moins trois images sur deux secondes, à vitesse et lacunes bornées.
  Deux pHash distincts sont requis pour écarter les images fixes répétées.
- **Vidéos visuellement quasi identiques** : une séquence validée couvre au moins 85 %
  des deux durées intégrales et les extractions ne sont pas tronquées.
- **Similarité sémantique** : cosinus des embeddings CLIP, enregistré séparément. Elle
  ne crée jamais une arête de réemploi ni un groupe de séquences communes.
- **Indéterminé** : médias ou indices exploitables insuffisants. « Non détecté » ne
  signifie pas « absent » ; échantillonnage, recadrage, logos, surimpressions et montage
  peuvent produire des erreurs. Les seuils doivent être évalués sur le corpus étudié.

Les groupes sont des composantes connexes de réemplois : A partageant un plan avec B
et B un autre plan avec C ne prouve pas que A et C soient identiques. La circulation
inter-médias indique la publication la plus ancienne parmi celles observées, jamais
une origine ou une relation de copie prouvée. Aucun jugement de plagiat n’est produit.

Les caractéristiques sont calculées automatiquement : coupes par histogrammes,
mouvement Farnebäck, silhouettes HOG, visages frontaux Haar, texte OCR, présence de
piste audio, silence énergétique, segments Whisper. Un visage frontal est un indice
visuel ; il ne prouve pas une adresse au spectateur. Aucun âge, genre, identité,
origine, émotion ou orientation politique n’est inféré. Les formats sont des règles
observables (`visage_frontal`, `texte_incruste`, `montage_multiplans`, `indetermine`),
pas une classification validée des genres journalistiques.

`variables_shs.json/csv` conservent mesures, confiances et règles. Les variables
illustratives sont ajoutées sous la forme `**** *media_... *format_... *reemploi_...`
aux corpus IRaMuTeQ. Les modalités inconnues valent `indetermine`.
La nomenclature est documentée dans `config/variables_shs.json`, les règles numériques
et leurs seuils dans `analyse/codage_automatique.py` et les configurations vidéo.

## Lots, cache et ressources

Par défaut : un traitement audiovisuel à la fois, sans collecte concurrente, CPU sur
un thread, 20 vidéos, 190 paires, 120 images/vidéo, dimension maximale 384 pixels,
1 image/seconde, 180 secondes/vidéo, 150 Mo/fichier, 30 minutes/lot. Les vidéos sont
alternées entre médias pour couvrir plusieurs comptes même dans un petit lot. Les
comparaisons chargent seulement deux jeux d’empreintes à la fois ; les vidéos décodées
sont traitées successivement. Les images ORB candidates sont bornées à 400 par paire ;
la troncature est signalée. Les limites ne permettent pas de conclure à l’absence de
réemploi sur tout un corpus. OCR examine au plus 12 images, silhouettes/visages 20.

`config/parametres_video.json` définit les ressources et options ;
`config/seuils_similarite.json` définit les seuils de comparaison. L’interface lance
un sous-processus interrompable, y compris ses téléchargements et commandes ffmpeg.
Le serveur arrête un traitement abandonné selon `IDLE_TIMEOUT_SECONDS` : garder la
page ouverte pendant l’analyse. Le CLI est adapté aux traitements administrateur :

```bash
python -m video.lots --session data/sessions/IDENTIFIANT
python -m video.lots --session data/sessions/IDENTIFIANT --parametres mon_lot.json --debut 20
```

Le JSON de surcharge accepte seulement les bornes prévues. Pour des vidéos déjà
présentes, déposer `videos/ID_TIKTOK.mp4` ; le téléchargement est désactivé par défaut
en CLI (`telecharger_videos: true` pour l’autoriser). `--debut` décale la sélection
alternée par médias. Chaque exécution réécrit les résultats analytiques du lot courant ;
exporter son archive avant le lot suivant. Les comparaisons portent sur les vidéos du
lot courant, pas automatiquement entre lots. Augmenter les limites dans leurs bornes
pour inclure les publications à comparer ensemble. Code de sortie 0 : lot complet ;
2 : partiel. Un module facultatif indisponible conserve un statut détaillé indéterminé.

Le cache SQLite associe SHA-256, paramètres et version de l’algorithme. Il est borné à
100 vidéos, purgé avec `RESULT_TTL_SECONDS` par le serveur, et n’enregistre pas un résultat
avec module activé en échec. `stockage/historique.py` donne accès à l’historique par
propriétaire depuis Python ; il n’ajoute pas d’accès public à la base. Les résultats
web restent accessibles seulement durant la session en mémoire ; un redémarrage
conserve les fichiers du volume, mais ne restaure pas leur accès dans l’interface.

Les sessions enrichies sont dans `data/sessions/<id>/` : `publications.json`,
`engagement.csv`, `commentaires.csv`, `videos/`, `images/`, `empreintes/`,
`groupes_visuels.json`, `comparaisons.json`, `variables_shs.csv/json`, corpus,
`journal.json`, `traitement_video.json` et `archive.zip`. L’archive contient les
exports et empreintes JSON ; les fichiers vidéo/audio/images, profils, logs et base
globale sont exclus. Tout `data/` reste hors Git et hors contexte Docker.

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
`video/` et `audio/` les traitements différés ; `analyse/` les mesures dérivées ;
`corpus/` les exports. Aucun import lourd n’est requis pour démarrer FastAPI ou collecter
les textes. `requirements.txt` reste le profil texte ; `requirements-video.txt` est
facultatif. Les points d’entrée et fonctions antérieures restent en place.

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tests/smoke_controle.py
```

Les tests vidéo sont ignorés dans le profil texte et exécutés dans le profil vidéo.
La CI construit les deux images Linux. Les fixtures contrôlent compression, recadrage,
images différentes, ordre temporel, images fixes, séparation sémantique/réemploi,
valeurs indéterminées, exports, isolation des sessions et gestes navigateur existants.
Voir `AUDIT_EVOLUTION.md`. Ces tests ne mesurent pas la précision sur de vraies vidéos
journalistiques et ne valident pas l’accès actuel de TikTok depuis votre VPS.

Références techniques : [OpenCV et homographies](https://docs.opencv.org/4.12.0/d9/d0c/group__calib3d.html),
[yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[OpenCLIP](https://github.com/mlfoundations/open_clip).


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
ne charge pas OpenCV, Whisper ou CLIP. `INSTALL_VIDEO=0` garde ces moteurs absents.
Le déploiement Docker standard utilise `INSTALL_VIDEO=semantique` : DINOv2/FAISS sur CPU, SHA-256/pHash/ORB et CLIP facultatif. Le profil `base` conserve uniquement la recherche de réemploi, sans PyTorch ; le profil `1` ajoute OCR/Whisper. La disponibilité est vérifiée à partir des outils réellement installés.
En local : `pip install -r requirements-video-base.txt` et installer ffmpeg ; aucun
drapeau supplémentaire n’est nécessaire.
La CI teste les trois profils Docker, le contrôleur dédié et le
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

## Multimodale — Vidéos similaires

L’onglet **Multimodale** lance le moteur existant après une collecte enrichie.
L’intervalle vaut une seconde par défaut. Le processus enchaîne des lots de
20 publications et reprend les vidéos déjà indexées et les paires en attente.
La collecte accepte désormais 1 000 publications par source. Une interruption
ou la limite de temps du processus peut demander de cliquer sur **Lancer /
reprendre l’analyse**. Une vidéo en erreur ne bloque pas les lots suivants.

Le profil Docker `INSTALL_VIDEO=base` suffit : OpenCV sur CPU, sans PyTorch,
CUDA ni téléchargement de modèle. Les options audio, transcription, OCR et
embeddings restent disponibles avec le profil facultatif `1` et ses outils.
Conserver un volume local persistant monté sur **`/app/data`** dans Coolify
(le fichier Compose le fait déjà). Aucun nouveau service n’est nécessaire.

### Index, preuves et limites

- L’index SQLite et ses vignettes sont enregistrés sous `data/index_visuel/`,
  séparés par propriétaire et profil de traitement. Ils survivent à la purge
  des sessions et des MP4. Les collectes doivent partager la même identité
  privée du navigateur pour être comparées ; une nouvelle identité ne donne
  pas accès aux anciens corpus. La perte du volume supprime l’index.
- Chaque image fournit un pHash global et dix fenêtres à 80 % ou 60 % des
  dimensions. Quatre bandes de 16 bits, sondées à un bit près, proposent les
  candidats. Jusqu’à sept bits de distance, ce sondage retrouve les voisins
  **hors plafonnement** ; au-delà, la recherche est approximative. Elle ne
  compare pas exhaustivement toutes les vidéos.
- Une première cohérence temporelle élimine les paires isolées. ORB est calculé
  seulement sur les images candidates, puis conservé compressé dans SQLite.
  RANSAC confirme la géométrie et la couverture spatiale ; une seconde
  vérification temporelle exige plusieurs images et une diversité de la zone
  appariée, pour limiter les logos, bandeaux et images fixes.
- Les options d’embeddings utilisent aussi des candidats indexés par projections
  aléatoires déterministes. Leurs liens sémantiques restent séparés dans le
  réseau et ne suffisent jamais à établir un réemploi visuel.
- Les budgets sont explicites : 256 voisins par interrogation de bande,
  64 candidats par image, 400 confirmations ORB par paire et 2 000 paires par
  lot par défaut. Un dépassement est signalé comme recherche partielle.
  Le traitement conserve au plus les images d’une vidéo en mémoire, avec
  180 images / 180 secondes / 384 pixels par défaut. Une vidéo plus longue
  est signalée comme tronquée. Les limites sont réglables dans le JSON existant.
- Les passages sont mesurés à la résolution de l’échantillonnage. Les scores
  sont heuristiques, non calibrés. Une absence de preuve reste `indetermine`,
  particulièrement pour les vidéos très courtes, peu texturées ou fortement
  transformées. Il ne s’agit pas d’une reconnaissance de l’audio seul.

**Supprimer les MP4 après indexation** est facultatif et désactivé par défaut.
Les vignettes conservées permettent de confirmer de futures correspondances
sans le fichier original. L’index n’a pas de purge automatique : sa taille est
à surveiller sur le volume du VPS. Les exports n’incluent pas la base privée.

Le résultat **Vidéos similaires** affiche les URL, médias, deux intervalles et
la confiance pour chaque lien direct. Un groupe est une composante connexe,
jamais une preuve d’identité de tous ses membres. Son identifiant est
reproductible pour les mêmes membres et change si le groupe fusionne/s’agrandit.
Les fichiers `comparaisons.json`, `groupes_visuels.json` et
`correspondances_visuelles.csv` conservent ces preuves dans le ZIP.
`groupe_visuel` et `reemploi_visuel` enrichissent les publications JSON, les
compteurs CSV et les corpus IRaMuTeQ. Le texte source est conservé ; les en-têtes
identifiés sont enrichis, et `corpus_visuel_iramuteq.txt` fournit un corpus avec
identifiants si les en-têtes du TXT avaient été désactivés.

### Vérification locale

```sh
PYTHONPATH=.:tests python -m unittest test_index_visuel test_empreintes test_comparaison_temporelle test_groupes_visuels test_extraction_video
```

Les tests couvrent la compression JPEG, le réencodage MP4, les copies binaires,
un recadrage ne conservant que 36 % de la surface, un extrait décalé, des
contenus différents avec bandeau commun, les images fixes, le cache ORB,
la persistance entre collectes et le nettoyage des MP4. Le test de charge
porte sur **1 000 publications à empreintes synthétiques** ; il ne constitue
pas une mesure de durée de traitement de 1 000 téléchargements TikTok réels
sur le VPS. Les API externes et les temps de téléchargement ne sont pas simulés
comme des garanties de performances.

### Complément CLIP : scènes et contenus similaires

Dans Multimodale, cocher **Rechercher des scènes et contenus similaires (IA)** et
**Autoriser le téléchargement des modèles facultatifs**, puis lancer l'analyse.
Les modèles sont réutilisés pendant le traitement ; le cache Hugging Face réside
dans `/app/data/modeles/huggingface` (à conserver dans le volume de données).
Un chemin de poids locaux peut remplacer le téléchargement dans la configuration.
Si Coolify impose déjà `INSTALL_VIDEO=base` comme argument de construction,
le remplacer par `semantique` et reconstruire l'image. Le profil `1` convient aussi.

Cette seconde recherche compare la représentation CLIP du contenu visuel, même
sans images identiques. Elle reste distincte des séquences réutilisées et ne
prouve ni un même événement, ni un même lieu. Elle ne compare pas les paroles.
La moyenne d'au plus 12 images réparties dans la vidéo représente le contenu ;
les candidats sont recherchés dans l'index persistant par projections, sans
comparaison exhaustive. Un passage court ou une transformation importante peut
être manqué. Le seuil cosinus est réglable dans l'interface (0,75 par défaut) ;
il s'agit d'un seuil heuristique, pas d'une probabilité calibrée.

Les résultats ont leur propre tableau avec URL et score, ainsi que les fichiers
`similarites_semantiques.csv` et `similarites_semantiques.json` dans le ZIP.
Ils ne créent pas de groupe de réemploi. Le diagnostic distingue les modèles
indisponibles de l'absence de correspondance. CLIP augmente la mémoire requise
et le temps CPU ; sa sélection reste facultative.

## Moteur principal DINOv2 — 20 octobre 2026

`facebook/dinov2-small` produit un vecteur CLS normalisé de 384 composantes pour
chaque image (3 secondes par défaut, intervalle configurable). Aucune moyenne
vidéo n'est calculée par DINOv2. CLIP reste facultatif, dans sa section distincte.
Le téléchargement du modèle est proposé par défaut dans l'interface ; le cache
local fonctionne sans réseau lorsque l'autorisation est désactivée.

L'index FAISS HNSW à produit scalaire est persistant et privé par propriétaire et
profil d'échantillonnage. SQLite conserve les vecteurs, horodatages et JPEG ;
FAISS est reconstruit par blocs après modification et réutilisé sinon. Un verrou
empêche deux écrivains concurrents. Les MP4 peuvent être nettoyés après succès.
Une analyse incomplète conserve ses fichiers pour permettre une reprise.
Les images d'une même publication sont exclues des voisins ; chaque vidéo
a au plus dix autres publications, classées par le meilleur score d'une paire
d'images. Les voisins affichés ne sont jamais filtrés par seuil. HNSW est une
recherche approchée, pas une comparaison exhaustive de toutes les vidéos.

Le regroupement est désactivé par défaut : choisir un seuil après inspection des
scores. Les groupes sont des composantes de liens directs, pas une preuve que
tous leurs membres sont identiques. La progression monotone des horodatages
et la diversité des images distinguent une ressemblance ponctuelle d'une
séquence temporellement cohérente. Cette cohérence seule ne prouve pas un
réemploi. SHA-256, pHash/ORB et RANSAC restent des contrôles complémentaires ;
aucun résultat DINOv2 ne dépend de leur validation.

Le tableau « Vidéos similaires » permet de sélectionner une publication puis
de consulter ses dix voisins, les miniatures, les positions et les URL TikTok.
Exports : `similarites_dino.json`, `similarites_dino.csv`, `groupes_dino.json`,
`miniatures_dino/`, `audit_video.json` et `diagnostic_visuel.json` dans le ZIP.
Le diagnostic distingue MP4 présents, téléchargements effectués, vidéos
décodées, images décodées, embeddings calculés, traitements désactivés et
modèles indisponibles. Les fichiers déjà présents ne sont pas comptés comme de
nouveaux téléchargements. Les compteurs historiques survivent au nettoyage.

### Référence mesurée sur CPU

Le test `tests/reference_dinov2.py` crée six vidéos depuis deux MP4 locaux :
source Brut 7697829530844663072 (24–42 s), réencodage H.264 CRF32, extrait
30–39 s, recadrage central à 70 %, autre magasin filmé entre 70 et 88 s,
et vidéo de rue 7697724586003057953 (0–6 s). Les médias ne sont pas redistribués.

| Rang | Comparaison avec la référence | Cosinus maximal | Temporalité |
|---|---|---|---|
| 1 | Extrait raccourci | 0,9963 | Cohérente |
| 2 | Copie réencodée | 0,9916 | Cohérente |
| 3 | Recadrage | 0,8669 | Cohérente |
| 4 | Autre magasin, type de scène comparable | 0,4735 | Ponctuelle |
| 5 | Rue sans rapport avec le magasin | 0,1326 | Ponctuelle |

Les trois copies connues sont les trois premiers résultats. Les cinq voisins
sont affichés, y compris le score faible. Ce petit jeu ne calibre pas un seuil
universel ; aucun seuil de regroupement n'est imposé. Résultats bruts :
`tests/reference_dinov2_scores.json`. L'essai complet de lot a décodé six vidéos,
calculé 29 embeddings et exporté 30 liens orientés (cinq voisins par vidéo),
sans ORB. La référence a pris environ 38 secondes sur le poste local, ce qui
ne prédit pas la durée sur le VPS.

Validation locale : tests d'index à 1 000 publications (vecteurs de test),
reprise inter-sessions, absence de modèle, désactivation, cohérence temporelle,
interface et accès privé aux miniatures. Pas de traitement neuronal de 1 000
vidéos réelles réalisé. Docker absent localement : aucune construction Docker
ni exécution Coolify revendiquée. La CI Linux inclut le profil `semantique`.

### Déploiement

Reconstruire `deploy-scraptiktok` avec `INSTALL_VIDEO=semantique` (défaut) ou `1`.
`base` conserve les contrôles de copie mais n'installe pas DINOv2. Conserver
`/app/data` pour les modèles Hugging Face et les index inter-lots. PyTorch,
Transformers et FAISS sont utilisés sur CPU ; CUDA n'est pas nécessaire.

Sources techniques : [fiche DINOv2-small](https://huggingface.co/facebook/dinov2-small),
[index FAISS](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).

### Vue globale des paires et rapprochement avec CLIP

Chaque vidéo est une source de recherche. Pour les lots de 50 publications au
maximum, toutes les paires du lot sont désormais calculées à partir des
embeddings normalisés (matrice d'une paire vidéo à la fois). Dix vidéos donnent
45 paires distinctes si toutes ont des embeddings ; les voisins inter-lots
peuvent s'ajouter. Pour les grands lots, FAISS conserve dix voisins par vidéo.
Le tableau global élimine les doublons A/B et B/A et indique la couverture du lot.
Une paire sélectionnée présente jusqu'à trois couples d'images, leurs temps et
la cohérence temporelle. Les miniatures supplémentaires nécessitent une reprise
de l'analyse sur les anciens résultats.

Le score CLIP global est ajouté à chaque paire DINOv2 lorsque les embeddings
CLIP sont disponibles pour les deux vidéos, sans appliquer le seuil de la
section CLIP à ce score. Sinon il reste absent, jamais remplacé par zéro.
DINOv2 n'explique pas en mots le détail responsable. La localisation décrite ci-dessous compare des régions ; elle ne détecte pas automatiquement des objets.
Exports supplémentaires : `paires_dino.json` et `paires_dino.csv`.


## Localiser les régions proches

Dans Multimodale → Vidéos similaires, sélectionner une paire puis cliquer sur
**Localiser les régions proches** sous un couple d'images. Jusqu'à six régions
portent le même numéro et la même couleur dans les deux images. Le tableau
indique leur cosinus local, distinct du score global et d'une probabilité.

Les tokens spatiaux de `facebook/dinov2-small` sont normalisés puis comparés
par voisinage réciproque ; les marqueurs sont espacés pour éviter les amas.
Aucun seuil ne transforme ces rapprochements en preuve. Les tokens incorporent
le contexte de l'image : ce n'est ni une segmentation d'objet, ni une carte
expliquant causalement le score CLS. Textes, textures et couleurs peuvent se
rapprocher même entre scènes différentes.

Le calcul couvre l'ensemble de la miniature, sans recadrage central. Le grand
côté est redimensionné à 336 pixels, les dimensions arrondies au multiple de
14, et les coordonnées sont rapportées à l'image affichée. La précision reste
limitée par la miniature conservée (224 pixels au plus à l'origine).

Le calcul est à la demande, dans un sous-processus CPU à un thread, limité à
120 secondes, sans téléchargement supplémentaire de modèle. Les poids doivent
être présents dans le cache utilisé par l'analyse DINOv2. Un seul traitement
vidéo peut s'exécuter à la fois ; arrêt et libération de session l'interrompent.
Les descripteurs sont conservés dans `cache_regions_dino/` et les images et
rapports dans `regions_dino/`, privés à la collecte et invalidés par le contenu
des miniatures. La mémoire du modèle est libérée à la sortie du processus.
Les résultats locaux calculés après l'archive initiale ne sont pas ajoutés à
cette archive ; ils restent consultables dans l'interface pendant la session.

Référence reproductible avec les MP4 du test DINOv2 :
`python tests/reference_regions_dino.py --reference /private/tmp/reference-dinov2 --sortie /tmp/regions_scores.json`.
Les mesures de `tests/reference_regions_dino_scores.json` portent sur un
recadrage connu et une scène différente ; elles ne définissent aucun seuil
universel. Les tests unitaires couvrent aussi les coordonnées, l'invalidation
du cache, la confidentialité et l'indisponibilité du modèle.
