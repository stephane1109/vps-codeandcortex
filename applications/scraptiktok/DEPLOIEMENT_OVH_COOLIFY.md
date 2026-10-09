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

Un volume persistant sur `/app/data` est facultatif. Les textes sont supprimés
automatiquement après une heure par défaut. Après un redémarrage de l'application,
les sessions précédentes ne sont plus accessibles et les fichiers orphelins sont
nettoyés à l'expiration. Les sessions TikTok sont temporaires, sans profil partagé.

## Utilisation depuis le VPS

1. Ouvrir le domaine de l'application, saisir le hashtag et lancer la collecte.
2. L'image du navigateur **du VPS** apparaît dans la page.
3. Dans cette image, traiter les cookies ou le CAPTCHA (cliquer/glisser). Pour
   se connecter, le QR code TikTok est utilisable ; pour un champ de saisie,
   cliquer dessus puis utiliser la zone « Écrire dans le champ sélectionné ».
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


## Activer les modules vidéo (facultatif)

Le déploiement standard inclut désormais la comparaison SHA-256, pHash, ORB et
temporelle : l’argument de construction par défaut est **`INSTALL_VIDEO=base`**.
Il installe ffmpeg et `requirements-video-base.txt`, sans PyTorch, Whisper ou CLIP.
Le port, Chromium/Xvfb, le volume et la commande restent inchangés. Un redéploiement
de la branche à jour installe ces outils ; si Coolify contient une valeur explicite
`INSTALL_VIDEO=0`, la retirer ou la remplacer par `base` avant de reconstruire.

Trois profils restent disponibles à la construction :
- `base` (défaut) : collecte textuelle et comparaison des fichiers/séquences ;
- `0` : textes uniquement, sans dépendances vidéo ;
- `1` : profil audiovisuel avancé, avec OCR, Whisper et OpenCLIP, utilisable via l’API
  et la commande de traitement par lots.

La disponibilité affichée dépend des dépendances réellement présentes. Ajouter une
variable à l’exécution n’installe aucune bibliothèque. Les options d’administration
ne sont pas présentées dans l’interface utilisateur.

Avec Compose, le profil standard est obtenu par `docker compose up -d --build`.
Les lots restent bornés, avec une seule analyse à la fois. Pour le profil avancé,
prévoir au moins 4 Go de RAM et 2 vCPU comme point de départ, puis mesurer la
consommation ; les modèles et les fichiers demandent également de l’espace disque.
`INSTALL_VIDEO=1 MEM_LIMIT=4g docker compose up -d --build` conserve ce profil avancé.

Conserver un volume sur `/app/data`. Pour garder les poids entre déploiements, un volume
supplémentaire sur `/home/app/.cache` peut être monté avec des droits d’écriture pour
l’utilisateur `app`. Les modèles sont facultatifs et ne sont pas téléchargés au build.
Whisper utilise le cache local si le téléchargement n’est pas autorisé. Pour OpenCLIP,
indiquer un fichier de poids local dans `config/parametres_video.json` lorsque les
réseaux externes sont interdits ; le nom d’un modèle distant nécessite l’option de
 téléchargement, même si la bibliothèque possède déjà une copie en cache.

`RESULT_TTL_SECONDS` s’applique également aux sessions enrichies et au cache analysé.
Pour un corpus de recherche à conserver sept jours, définir `604800` et dimensionner
le disque en conséquence. Après redémarrage, récupérer les anciens dossiers depuis
le volume si nécessaire : l’interface ne restaure pas les sessions précédentes.
La base SQLite n’est jamais exposée par HTTP et reste exclue des archives.

Les archives détaillent les échecs de téléchargement, les traitements tronqués et les
modalités indéterminées. L’accès yt-dlp est indépendant de la session Selenium ; les
vidéos nécessitant une connexion peuvent rester indisponibles. Le traitement des textes
continue de fonctionner sans les dépendances audiovisuelles.


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
