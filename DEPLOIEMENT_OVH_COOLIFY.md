# Déploiement ScrapTikTok sur le VPS OVH / Coolify

L'utilisateur ouvre une page web, saisit son hashtag et télécharge un fichier
`.txt`. Python, Selenium et Chromium s'exécutent **sur le VPS**. Aucun logiciel,
ChromeDriver ou terminal n'est nécessaire sur son ordinateur.

## Coolify

Créer une application depuis le dépôt GitHub existant :

| Réglage | Valeur |
| --- | --- |
| Dépôt | `stephane1109/vps-codeandcortex` |
| Branche | **`deploy-scraptiktok`** |
| Build pack | Dockerfile |
| Base directory | **`/`** |
| Dockerfile | `/Dockerfile` (relatif à la base directory) |
| Port interne / Ports Exposes | `8501` |
| Healthcheck HTTP | `/healthz` sur le port `8501` |
| Domaine | Le sous-domaine HTTPS que vous affectez à cette application |

Comme les autres branches `deploy-…`, `deploy-scraptiktok` contient l'application
à la racine. Le code source existe également dans `applications/scraptiktok` sur
`main` ; cette autre branche exige une Base directory `/applications/scraptiktok`.
Les mises à jour de `main` ne sont pas automatiquement reportées sur la branche
de déploiement.

Ne pas remplacer la commande de démarrage. Le conteneur lance Chromium avec
un écran virtuel Xvfb et l'application web. Il n'y a aucun port VNC à ouvrir.
Ne pas déployer ce dossier comme un site statique.

Variables recommandées :

```dotenv
COOKIE_SECURE=1
MAX_CONCURRENT_JOBS=1
RESULT_TTL_SECONDS=3600
IDLE_TIMEOUT_SECONDS=300
JOB_TIMEOUT_SECONDS=1800
CHECKPOINT_TTL_SECONDS=604800
```

Pour un accès réservé, définir également `APP_ACCESS_USER` et
`APP_ACCESS_PASSWORD` dans les secrets Coolify. Le navigateur demandera ce
mot de passe avant d'afficher l'application. Il est facultatif ; l'isolation des
sessions reste active sans lui. Il n'y a pas d'intégration au système de tickets
Redis du dashboard dans cette version.

Prévoir **2 Go de RAM et 2 vCPU disponibles** pour une collecte simultanée.
Le navigateur a besoin de davantage de mémoire qu'une application de texte seule.
Une collecte simultanée est autorisée par défaut ; les autres utilisateurs
reçoivent un message indiquant que le serveur est occupé. Ne pas augmenter
`MAX_CONCURRENT_JOBS` sans augmenter les ressources disponibles.

Un volume persistant sur `/app/data` est nécessaire pour les sauvegardes progressives facultatives. Il conserve les ZIP de récupération dans `sauvegardes_collectes/`, indépendamment des sessions temporaires, pendant 7 jours par défaut (variable `CHECKPOINT_TTL_SECONDS`). Sans ce volume, un redéploiement peut effacer ces sauvegardes.

Un volume persistant sur `/app/data` est facultatif pour une collecte sans sauvegarde progressive. Les textes sont supprimés
automatiquement après une heure par défaut. Après un redémarrage de l'application,
les sessions précédentes ne sont plus accessibles et les fichiers orphelins sont
nettoyés à l'expiration. Les sessions TikTok sont temporaires, sans profil partagé.

## Utilisation depuis le VPS

1. Ouvrir le domaine de l'application, saisir le hashtag et lancer la collecte.
2. L'image du navigateur **du VPS** apparaît dans la page.
3. Dans cette image intégrée, traiter les cookies ou le CAPTCHA (cliquer/glisser).
   La collecte est anonyme : aucun identifiant TikTok n’est demandé. Une restriction
   d’accès restante est signalée ; aucune connexion à un compte n’est proposée.
4. Une fois les publications visibles, cliquer sur « Les vidéos sont visibles,
   continuer ». La collecte s'effectue sur le serveur.
5. Télécharger le fichier texte. Le bouton « Arrêter » conserve les textes acquis.

Le navigateur du serveur est retransmis par captures successives et gestes
Selenium. Ce n'est pas une vidéo instantanée : attendre environ une seconde
après chaque action. Les captures ne sont pas conservées sur disque. Un CAPTCHA
se résout manuellement ; le logiciel n'utilise aucun service de contournement.

## Docker sans Coolify

Depuis le dossier `applications/scraptiktok` cloné sur le VPS :

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

Le service écoute sur `127.0.0.1:8501`. Ajouter un reverse proxy HTTPS vers ce
port, ou utiliser un tunnel SSH depuis l'ordinateur pour un essai privé :

```bash
ssh -L 8501:127.0.0.1:8501 utilisateur@adresse-du-vps
```

Puis ouvrir `http://localhost:8501`. Garder `COOKIE_SECURE=0` pour cet essai HTTP.
Avec un domaine HTTPS, passer `COOKIE_SECURE=1` et conserver les en-têtes
`Cookie` et `Authorization` à travers le reverse proxy. L'application s'expose
à la racine de son domaine, pas dans un sous-chemin.

## Vérification après déploiement

- `/healthz` doit répondre `{"status":"ok"}`.
- Faire une collecte de 1 à 5 publications. Vérifier que l'image TikTok se charge,
  que les clics fonctionnent et que le fichier téléchargé contient les textes.
- Si Chromium ne démarre pas : vérifier les logs et la mémoire. Le conteneur
  installe Chromium et son pilote ensemble, sans téléchargement de pilote à
  l'exécution. Il tourne sous un utilisateur non root ; `--no-sandbox` est activé
  uniquement par la variable du conteneur, à cause des restrictions usuelles
  des namespaces dans Docker. Ne pas utiliser `--privileged`.
- Si TikTok refuse l'IP du VPS, la collecte peut rester inaccessible même après
  une connexion ou un CAPTCHA. Une interface et Docker ne garantissent pas
  l'autorisation d'accès par TikTok ; le test réel doit être fait depuis ce VPS.
- Une fenêtre abandonnée est arrêtée après 5 minutes sans nouvelles de la page ;
  la durée totale d'une collecte est limitée à 30 minutes par défaut.

La limite de navigateurs est gérée dans un seul processus : conserver **un worker
Uvicorn et une réplique**. Une architecture à plusieurs répliques nécessiterait
un registre de sessions partagé.


## Vidéos : téléchargement MP4 et Désordre visuel uniquement

L'onglet **Vidéos similaires** et ses dépendances lourdes ont été supprimés.
Le Dockerfile installe directement FFmpeg, OpenCV et les dépendances du module
**Désordre visuel**, sans PyTorch, CLIP, DINOv2, FAISS, Whisper ou OCR.
`INSTALL_VIDEO` n'est plus un argument de construction et peut être retiré
de Coolify. Aucun paramètre vidéo ne doit être nécessaire pour déployer.

Conserver **REDIS_URL**, les autres variables du ticket applicatif et le volume
persistant **`/app/data`**. Les MP4 et les analyses existantes ne sont pas
effacés par la modification du code. Redéployer la branche `deploy-scraptiktok`.

Les budgets de requêtes API Presse sont **entièrement définis dans
Coolify** par les cinq variables `SCRAPTIKTOK_API_*` : aucune borne haute
additionnelle ni réduction automatique de 50 % n'est imposée.
Un exemple prudent : 300/minute, 500/heure, 500/jour UTC,
50 000 enregistrements/jour UTC, intervalle minimal 0 seconde.
Les requêtes Selenium ne sont pas couvertes par ces compteurs.

## Accueil Streamlit minimaliste

Le conteneur lance maintenant `lancer_interface.py` : le port public reste **8501**,
le contrôle de santé reste **`/healthz`**, et la branche reste **`deploy-scraptiktok`**.
Redéployer avec la commande du Dockerfile, sans commande Uvicorn personnalisée.
La page `/` initialise la session et affiche directement Streamlit, sans suffixe dans
l’adresse. Les anciens liens `/interface/` redirigent vers `/`. Streamlit écoute uniquement
sur `127.0.0.1:8502`, relayé par FastAPI : ne pas exposer le port 8502 dans Coolify.
Le reverse proxy doit transmettre les WebSocket, les cookies, Host et Authorization.
Le contrôle de santé vérifie désormais les deux services.

L’interface est consacrée à la collecte textuelle : le menu des options vidéo et
les boutons de comparaison ont été retirés. L’aide explique la sélection des médias,
la visite successive des profils et les exports. Les profils de dépendances vidéo
restent disponibles pour l’API et les traitements par lots.

En local : `python lancer_interface.py --port 8510`, puis ouvrir l’accueil à ce port.
Le port privé suivant (8511) doit être libre ; `STREAMLIT_PORT` peut le remplacer.
Ne pas ouvrir directement le port Streamlit : passer par l’accueil initialise le
cookie de session et applique la protection d’accès. Conserver un seul processus
FastAPI et une seule réplique du conteneur.


## Accès partagé Redis

Le contrôle d’accès reprend celui d’Europresse vers IRaMuTeQ. Les variables
`REDIS_URL`, `APP_TICKET_*` et `CAPACITE_SERVEUR` sont lues à l’exécution depuis
Coolify. Conserver les valeurs configurées, notamment `APP_TICKET_ID=scraptiktok`,
`APP_TICKET_MAX_ACTIVE=8`, `APP_TICKET_COST=1` et `CAPACITE_SERVEUR=10`.
Ne pas enregistrer le mot de passe Redis dans Git.

La barre latérale affiche le ticket actif, la file d’attente et la libération/reprise
de l’accès. Libérer l’accès arrête aussi les traitements de la session ; une
libération externe ou l’expiration du ticket est détectée par le moteur.
Le nombre de tickets d’accès et la limite de navigateurs simultanés sont distincts.
Les exports existants restent accessibles par leurs liens privés jusqu’à expiration.

Le déploiement utilise le Dockerfile Python/Chromium. `NIXPACKS_NODE_VERSION`
n’est pas lu par cette application ni par son Dockerfile ; il est sans effet avec
ce mode de construction. Aucune installation de Node.js n’est nécessaire.



## Apify : moteur Presse indépendant

ScrapTikTok peut lancer à distance l'Actor Apify
`clockworks/tiktok-profile-scraper` depuis la section
« Presse et médias » → « Méthode Apify (API) ». Seule l'exécution de
l'Actor se fait sur les serveurs Apify : le choix des médias,
la validation des auteurs, les filtres, les exports et les analyses
restent dans ScrapTikTok sur ce VPS.

Créer un compte sur https://console.apify.com/ et récupérer un jeton dans
**Settings → Integrations → API tokens**. Deux configurations possibles :
saisir le jeton dans le champ masqué Streamlit à chaque collecte ou
ajouter `APIFY_API_TOKEN` aux secrets de l'application dans Coolify.
Ne jamais committer cette valeur ni l'inclure dans des URL de requêtes.

Le plafond financier **par exécution de l'Actor et par média** est défini
par `APIFY_MAX_CHARGE_USD` (1.0 USD par défaut). Le nombre maximum
de résultats facturables est également limité à `limit`, via le
paramètre API `maxItems`. Le service reste potentiellement payant :
les coûts réels et l'éligibilité d'un plan dépendent d'Apify.
Le moteur ne relance pas automatiquement les exécutions payantes en échec.
En cas d'annulation ou de dépassement de délai, ScrapTikTok demande
l'interruption de l'Actor distant, sans garantie de remboursement des
opérations déjà facturées.

L'Actor reçoit un profil à la fois, trie les vidéos par date décroissante,
et ne télécharge ni MP4, ni jaquettes, ni sous-titres. Les champs Apify
`id`, `text`, `createTime`, `authorMeta.name`, `webVideoUrl`,
`playCount`, `diggCount`, `commentCount`, `shareCount` et
`collectCount` sont adaptés au schéma ScrapTikTok.
Les publications d'autres comptes et les diaporamas sont écartés.
Les filtres de période, le croisement hashtags, la sélection de médias,
l'analyse et les exports existants restent actifs.

Les commentaires et le texte IA sont des options distinctes qui,
lorsqu'elles sont cochées, peuvent nécessiter le navigateur Selenium
sur le VPS. Apify Profile Scraper ne fournit pas à lui seul de résumé
natif `itemCustomTDK`. Les tests automatisés du moteur Apify sont
**simulés** pour ne pas déclencher de frais. Une collecte réelle
nécessite un jeton valide et un redéploiement Coolify de la branche
`deploy-scraptiktok`.
