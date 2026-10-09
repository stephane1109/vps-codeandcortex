# ScrapTikTok — interface Streamlit minimaliste

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


## Comptes de presse, engagement et commentaires

Dans **Source**, choisir **Comptes de presse** ou **Autres comptes TikTok**.
Sélectionner les médias, ou saisir jusqu’à dix identifiants séparés par des virgules.
La limite de publications s’applique à chaque compte. Les recommandations d’autres
auteurs sont exclues ; les publications communes sont dédoublonnées par ID TikTok.
Un ou deux hashtags peuvent filtrer les légendes des comptes, avec le même ET/OU.
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
La sélection reste conservée lors d’un changement de mode de recherche. Le compteur indique combien de médias sont sélectionnés. Le catalogue est relu à chaque interaction pour ne pas conserver une ancienne liste en session. Les hashtags de la recherche générale sont séparés des filtres facultatifs de la recherche par comptes.
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

La collecte des commentaires lit uniquement ce qui est accessible dans la page,
avec une limite par publication et un nombre de défilements borné. Les réponses
sont facultatives, les liens parent/enfant conservés lorsqu’ils sont observés. À défaut
d’ID TikTok, un ID local est signalé comme tel : deux textes identiques du même auteur
peuvent alors être confondus. Un résultat vide ne prouve pas l’absence de commentaires.
Les sélecteurs peuvent évoluer avec TikTok ; les statuts partiels restent explicites.

**Télécharger le fichier texte** conserve l’export initial. **Télécharger l’archive
enrichie** fournit JSON brut, CSV (UTF-8 BOM, séparateur `;`), corpus IRaMuTeQ et journal.
Les filtres ET/OU et français s’appliquent aux légendes retenues dans TXT/IRaMuTeQ.
Les publications brutes, mesures et commentaires restent séparés et non filtrés ;
`retenue` identifie la sélection. Les corpus commentaires et transcriptions sont distincts.
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

`collecte/` gère les sources et observations ; `stockage/` les sessions SQLite ;
`video/` et `audio/` les traitements différés ; `analyse/` les mesures dérivées ;
`corpus/` les exports. Aucun import lourd n’est requis pour démarrer FastAPI ou collecter
les textes. `requirements.txt` reste le profil texte ; `requirements-video.txt` est
facultatif. Les points d’entrée et fonctions antérieures restent en place.

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tests/smoke_browser.py
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

Les comptes sont visités l’un après l’autre : l’affichage du Monde au début ne signifie
pas que les autres médias sont exclus. Le message indique la source courante et le
nombre total. **Détail des sources** indique les liens trouvés et les sources
inaccessibles ; une vérification TikTok non terminée est distinguée d’une page sans
publication lisible. Les compteurs de filtres et d’erreurs de lecture expliquent les
résultats vides sans les assimiler à l’absence de publications du média.

`lancer_interface.py` démarre FastAPI sur le port public et Streamlit sur un port local
privé. `interface/passerelle.py` relaie HTTP et WebSocket à la racine du domaine, avec cookie
privé, contrôle d’origine et protection HTTP optionnelle conservés. Aucun port additionnel
n’est à exposer. L’adresse reste `https://scraptiktok.codeandcortex.fr/` ; les anciens
liens `/interface/` redirigent vers `/`. Les téléchargements restent des routes FastAPI privées ; les données
utilisateur ne sont pas placées dans un cache Streamlit partagé. Une fenêtre intégrée
réutilise le contrôleur de navigateur testé : elle n’est pas recréée à chaque image.
Le CAPTCHA reste à traiter par l’utilisateur, dans le navigateur du serveur.

L’entrée `webapp.py`, le moteur CLI et les modules restent utilisables. L’ancienne
interface est conservée à `/classique`, notamment pour le contrôleur intégré et les
tests de non-régression. Lancer directement Uvicorn affiche encore cette interface ;
utiliser **`python lancer_interface.py`** pour l’accueil Streamlit. La commande Docker
est déjà mise à jour. Le navigateur distant, les dates, ET/OU et le filtre français sont
conservés ; ET/OU se choisit maintenant directement dans le formulaire Streamlit.

Streamlit apporte ses dépendances d’affichage (dont NumPy/Pillow), mais la collecte
ne charge pas OpenCV, Whisper ou CLIP. `INSTALL_VIDEO=0` garde ces moteurs absents.
Le déploiement Docker standard installe la comparaison de base (SHA-256/pHash/ORB)
sans modèle lourd : `INSTALL_VIDEO=base`. Le profil `1` conserve les dépendances
avancées. La disponibilité est vérifiée à partir des outils réellement installés.
En local : `pip install -r requirements-video-base.txt` et installer ffmpeg ; aucun
drapeau supplémentaire n’est nécessaire.
La CI teste les trois profils Docker, l’ancienne fenêtre de contrôle et le nouveau
parcours Streamlit, avec une source synthétique hors TikTok.

Références d’intégration : [fragments Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
et [contexte de session](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.context).

### Une session pour plusieurs sources

Les deux hashtags (ET comme OU) et les comptes sélectionnés utilisent le même
navigateur et ses cookies pendant toute la collecte. La vérification initiale
manuelle n’est demandée qu’une fois. La deuxième source accessible est consultée
automatiquement. Si TikTok affiche réellement une nouvelle connexion ou un CAPTCHA,
la collecte s’interrompt de nouveau pour permettre l’intervention de l’utilisateur.
La correction supprime les pauses systématiques ajoutées par l’application ; elle
ne supprime pas les vérifications décidées par TikTok.

Le parcours Chrome synthétique vérifie deux hashtags, une seule validation,
la conservation du cookie de test et l’export TXT/ZIP. Les tests unitaires vérifient
aussi qu’un nouveau blocage visible déclenche bien une intervention et que les
comptes de presse partagent la même session.
