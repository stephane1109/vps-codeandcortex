# scraptiktok

Script Python/Selenium pour collecter les **légendes/descriptions des publications
TikTok accessibles dans Chrome à partir d'un hashtag**. Il parcourt la page du
hashtag puis ouvre chaque publication, sans télécharger les vidéos.

Les « textes » désignent ici la description écrite par l'auteur, hashtags compris.
Les commentaires, la transcription audio, les sous-titres et le texte incrusté
dans l'image ne sont pas collectés.

## Installation sur macOS

Prérequis : Python **3.10 ou plus récent**, Google Chrome et une connexion Internet.

```bash
cd "/Users/stephanemeurisse/Documents/OVH - VPS/VPS/applications/scraptiktok"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

[Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/)
gère automatiquement le pilote ChromeDriver compatible. Le premier lancement
peut nécessiter son téléchargement. Pour utiliser un pilote déjà installé,
ajouter `--driver /chemin/vers/chromedriver`.
Le cache est local au dossier `.selenium-cache/`. Par défaut, un ancien
ChromeDriver présent dans le `PATH` est ignoré pour éviter les conflits de version.
Les variables `SE_CACHE_PATH` et `SE_SKIP_DRIVER_IN_PATH`, si définies par
l'utilisateur, restent prioritaires.

## Première collecte

```bash
python scraptiktok.py cuisine --limit 50 --interactive --profile-dir .chrome-profile
```

1. Chrome s'ouvre sur `https://www.tiktok.com/tag/cuisine`.
2. Dans cette fenêtre, traiter les cookies, une éventuelle connexion ou un CAPTCHA
   et vérifier que les publications du hashtag sont visibles.
3. Revenir au terminal et appuyer sur **Entrée** pour démarrer la collecte.
4. Les fichiers apparaissent dans `exports/`. `Ctrl+C` conserve les résultats acquis.

Remplacer `cuisine` par le hashtag voulu. Avec le préfixe `#`, utiliser des
guillemets : `python scraptiktok.py "#tourisme" --interactive`.

Le profil est facultatif. Utiliser un profil **dédié** (pas le profil personnel
habituel de Chrome), et une seule collecte à la fois pour ce profil. Il conserve
la session localement ; ne pas le publier. Les profils, exports et environnements
Python locaux sont exclus de Git.

## Exports

Chaque exécution crée un nom horodaté et sauvegarde les trois formats après chaque
publication :

- **CSV** : séparateur `;`, encodage UTF-8 avec BOM pour Excel ; une ligne par
  publication traitée, y compris celles en erreur.
- **JSON** : textes bruts, métadonnées, liste des URL découvertes et bilan de la collecte.
- **TXT** : URL et légende, séparées par une ligne vide, uniquement pour les textes obtenus.

Champs : identifiant, URL, auteur, description, hashtags, date de publication
(si disponible), date de collecte, source et statut. Les dates sont en UTC.
Les statuts par publication sont `ok`, `empty_caption` (légende vide confirmée
dans les données de la page) et `error` (échec de lecture). Une erreur ne devient
jamais une légende vide prétendument réussie.

Les cellules CSV commençant par un caractère de formule sont précédées d'une
apostrophe pour leur ouverture dans un tableur. JSON et TXT conservent le texte brut.

Le JSON contient `discovery_stop` (`limit`, `max_scrolls`, `no_new_links` ou
`blocked`) et `run_status`. `completed` signifie que les liens découverts ont été
traités, **pas** que toutes les publications du hashtag ont été récupérées.

## Options

```bash
python scraptiktok.py --help
python scraptiktok.py tourisme --limit 100 --delay 4 --timeout 30 --max-scrolls 50 --interactive
python scraptiktok.py cuisine --limit 10 --output-dir ./exports/essai
```

| Option | Effet | Défaut |
| --- | --- | --- |
| `--limit` | Maximum de publications à lire | 50 |
| `--max-scrolls` | Maximum de défilements sur le hashtag | 30 |
| `--idle-rounds` | Arrêt après N défilements sans nouveau lien | 3 |
| `--delay` | Pause entre les pages et les défilements, en secondes | 3 |
| `--timeout` | Attente maximale par navigation ou lecture, en secondes | 20 |
| `--interactive` | Pause initiale et intervention manuelle après un échec de lecture | Désactivé |
| `--headless` | Chrome sans fenêtre | Désactivé |
| `--profile-dir` | Profil Chrome dédié et persistant | Profil temporaire |
| `--output-dir` | Dossier des exports | `exports/` à côté du script |
| `--chrome-binary` | Chemin de Chrome/Chromium | Détection automatique |
| `--driver` | Chemin de ChromeDriver | Selenium Manager |

Codes de sortie : `0` collecte terminée sur les liens découverts ; `1` échec global ;
`2` collecte partielle ou arguments invalides ; `130` interruption par Ctrl+C.
Un JSON de bilan est créé même lorsqu'aucune publication n'est accessible.

## VPS Linux

Installer Python et Chrome/Chromium sur le serveur, puis les mêmes dépendances.
Exécuter sous un utilisateur ordinaire disposant des droits d'écriture sur les
exports et le cache Selenium :

```bash
python scraptiktok.py cuisine --limit 20 --headless --delay 4
```

`--headless` et `--interactive` sont incompatibles. Si TikTok demande une action
humaine, utiliser Chrome avec une interface graphique ; le script ne résout pas
les CAPTCHA automatiquement. La collecte depuis l'IP d'un VPS peut échouer même
si elle fonctionne sur un ordinateur personnel.

## Limites et dépannage

- TikTok peut ne renvoyer aucun résultat, imposer une connexion ou refuser l'accès.
  Commencer par une petite collecte avec `--interactive`.
- Les résultats dépendent de ce que la page rend accessible et ne constituent
  pas un inventaire exhaustif ou chronologique du hashtag.
- La description est d'abord lue dans les données JSON intégrées à la page, en
  cherchant exactement l'ID de la publication. À défaut, le script utilise le
  texte affiché (`page_dom`), qui peut être tronqué par l'interface. Aucun endpoint
  privé n'est appelé directement.
- Les sélecteurs et formats TikTok peuvent changer. Ils sont regroupés dans
  `DISCOVER_JS`, `PAGE_JS`, `BLOCKED_JS` et `extract_record` dans le script.
- Le défilement s'arrête après plusieurs attentes sans nouveauté ; augmenter
  `--timeout` pour une connexion lente. Les doublons sont éliminés par identifiant.
- Consulter le JSON pour distinguer un blocage, une légende vide et une erreur.
  Adapter l'usage aux règles d'accès de TikTok et aux droits portant sur les textes.

Les attentes dynamiques utilisent
[WebDriverWait](https://www.selenium.dev/documentation/webdriver/waits/).

## Vérifications locales

```bash
python -m unittest discover -s tests -v
```

Ces tests vérifient l'extraction depuis des données synthétiques, les exports,
les erreurs et les interruptions. Ils ne prouvent pas l'accès à TikTok depuis
votre réseau ; vérifier celui-ci avec une petite collecte dans Chrome.

Lors de la vérification du 6 octobre 2026, le démarrage de Chrome et l'extraction
sur une page de test locale ont réussi. La page TikTok `#cuisine` a présenté un
CAPTCHA avant d'afficher ses publications : la collecte réelle de légendes reste
à valider après intervention manuelle avec `--interactive`.
