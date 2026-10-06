# Déploiement ScrapTikTok sur le VPS OVH / Coolify

L'utilisateur ouvre une page web, saisit son hashtag et télécharge un fichier
`.txt`. Python, Selenium et Chromium s'exécutent **sur le VPS**. Aucun logiciel,
ChromeDriver ou terminal n'est nécessaire sur son ordinateur.

## Coolify

Créer une application depuis le dépôt GitHub existant :

| Réglage | Valeur |
| --- | --- |
| Dépôt | `stephane1109/vps-codeandcortex` |
| Branche | `main` |
| Build pack | Dockerfile |
| Base directory | `/applications/scraptiktok` |
| Dockerfile | `/Dockerfile` (relatif à la base directory) |
| Port interne / Ports Exposes | `8501` |
| Healthcheck HTTP | `/healthz` sur le port `8501` |
| Domaine | Le sous-domaine HTTPS que vous affectez à cette application |

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
