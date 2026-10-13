# DésinfoLab

Observatoire collaboratif en français, sous **Python 3.11, Streamlit, FastAPI et PostgreSQL**. Les visiteurs proposent sans compte des sources, comptes, contenus et corrections de ces fiches. La création, la modification et la suppression des tags sont réservées à l’administration. Seule la validation administrative publie une fiche. Le simple référencement ne constitue jamais, à lui seul, une qualification comme source de désinformation.

## Démarrer avec Docker Compose

Prévoir Docker Engine avec le plugin Compose v2. Le dossier de construction est `applications/desinfolab` dans le dépôt VPS.

```sh
cd applications/desinfolab
cp .env.example .env
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m scripts.generer_secrets
```

Saisir un mot de passe administrateur d'au moins 14 caractères. Reporter les trois valeurs générées dans `.env` : `POSTGRES_PASSWORD`, `APP_SECRET`, `ADMIN_PASSWORD_HASH`. Ne pas modifier les secrets d'une base existante sans procédure de rotation ; changer seulement `POSTGRES_PASSWORD` dans `.env` ne modifie pas le rôle PostgreSQL déjà créé.

```sh
chmod 600 .env
docker compose up --build -d
docker compose ps
```

- Interface : <http://localhost:8501>
- Documentation API : <http://localhost:8000/docs>
- Santé API : <http://localhost:8000/sante>

Les ports sont liés à `127.0.0.1`. Le service `migrations` se termine avec le code 0 ; c'est son état normal. Les services web et API attendent sa réussite. PostgreSQL et les sauvegardes utilisent des volumes nommés distincts. Aucune fiche fictive ni qualification n'est insérée au démarrage ; les 14 plateformes sont préconfigurées.

La création du premier contenu se fait dans cet ordre : proposer une source, la valider dans Administration, proposer éventuellement un compte, le valider, puis proposer le contenu. Une contribution reste un objet privé même après son traitement ; seul son résultat validé est public.

## Déployer sur Coolify / VPS

1. Créer une application à partir du dépôt Git contenant ce dossier, avec le type **Docker Compose**. Base Directory : `/applications/desinfolab`. Compose Location : `/docker-compose.yml`, relative à cette base. Selon la version de Coolify, l'intitulé du champ peut varier : vérifier que le fichier sélectionné est celui de ce dossier.
2. Définir les variables de `.env.example` dans les secrets d'exécution Coolify ; ne pas committer `.env`.
3. Associer le domaine de l'interface au service **web**, port interne **8501**, et un domaine API au service **api**, port interne **8000**. Renseigner `PUBLIC_API_URL=https://api.votre-domaine.fr`.
4. Activer HTTPS et le transfert des WebSockets pour Streamlit. PostgreSQL ne doit pas avoir de domaine ou de port public.
5. Déployer et vérifier la réussite des migrations, les deux contrôles de santé et la création d'une sauvegarde. Les contrôles de santé sont définis dans Compose.
6. Vérifier le proxy : limiter les connexions et la taille des requêtes, désactiver ou réduire les journaux d'accès et leur rétention. Ces paramètres du VPS sont distincts de ceux de l'application.

Les ports hôtes du Compose sont facultatifs pour Coolify, qui joint les services par leur réseau interne. En cas de collision locale avec une autre application, modifier `WEB_PORT` et `API_PORT` ou retirer les deux blocs `ports` dans la configuration Coolify. Ne pas exposer PostgreSQL pour résoudre un problème de routage.

Le montage `./scripts/sauvegarder.sh` nécessite une construction depuis le dépôt : le fichier doit être présent à côté du Compose. Pour une ressource « Service » créée en collant uniquement du YAML, fournir aussi ce script ou employer le déploiement Git décrit ci-dessus.

Documentation officielle consultée : [Docker Compose dans Coolify](https://coolify.io/docs/applications/builds/docker-compose), [contrôles de santé](https://coolify.io/docs/applications/configuration/health-checks).

## Utiliser l'observatoire

Les six pages sont : accueil et statistiques ; recherche et exploration ; fiches sources et contenus ; soumission ; exploration des tags ; administration.

Dans **Administration → Plateformes**, vous pouvez créer une plateforme, modifier son nom ou la supprimer après confirmation. Le renommage conserve les liens existants. La suppression est refusée si une source, un compte, un contenu publié ou une contribution en attente utilise la plateforme. Chaque changement est enregistré dans l’historique.

- **Sources** : nom, description, URL, pays, langue, plateforme principale, tags et références.
- **Comptes** : plateforme, pseudonyme, identifiant public, URL et source. L'identifiant est celui du compte référencé, jamais celui du contributeur.
- **Contenus** : titre, URL originale, date de publication facultative, description, média, source et compte facultatif. Si un compte est renseigné, sa source et sa plateforme doivent correspondre.
- **Tags** : thématiques, types de discours, qualifications factuelles, catégories et mots-clés. Le formulaire ne propose plus de champ famille ni de champ parent et l’explorateur présente une liste simple. La nature d'un tag publié est stable ; son nom, sa description et ses références sont modifiables uniquement dans Administration → Tags. Les nouveaux tags utilisent automatiquement le type thématique. Le type et les anciennes relations des tags existants restent conservés en base pour compatibilité.
- **Références** : article, publication scientifique, fact-checking ou autre, avec titre, URL et extrait/justification. Chaque qualification attachée à une source ou à un contenu exige au moins une référence portant explicitement son identifiant. La définition d'un tag de qualification exige elle aussi une référence.

Les tags existants restent consultables et sélectionnables par les visiteurs. Dans **Administration → Tags**, un administrateur crée ou modifie directement un tag, avec un motif enregistré dans l’historique. Dans « Modifier / supprimer un tag », la suppression est possible après confirmation si le tag n’est utilisé ni par une fiche, une référence, un autre tag ou une contribution en attente. L’historique conserve le tag supprimé et ses références. Les qualifications exigent toujours des références documentaires. Le formulaire public refuse toute création ou modification de tag, y compris depuis une ancienne session ; l’API reste en lecture seule. Les anciennes propositions de tags déjà en attente restent examinables par l’administration. Les boutons des fiches sources, comptes et contenus préremplissent les propositions de modification.

Les filtres de recherche se combinent avec ET. L'opérateur ET/OU s'applique au groupe de tags sélectionnés ; la thématique reste un filtre supplémentaire. L'option descendants inclut les sous-tags. Sur un compte, les tags, le pays et la langue sont ceux de sa source. Sur un contenu, les tags sont ceux du contenu, tandis que le pays et la langue sont ceux de sa source. Une source correspond à une plateforme si sa plateforme principale, un de ses comptes ou un de ses contenus y correspond. Les filtres de média et de dates appliqués à une source ou un compte doivent être satisfaits par **un même contenu** associé. Les contenus sans date sont exclus d'une recherche bornée par dates.

La sélection de lignes alimente un corpus conservé en mémoire de session et utilisable sur plusieurs pages. Chaque URL peut être ouverte ou copiée avec le bouton du bloc de code. TXT contient une URL originale par ligne ; CSV et JSON incluent les métadonnées, les tags et les références. Les champs CSV pouvant être interprétés comme des formules sont préfixés d'une apostrophe ; JSON conserve le texte exact. L'export complet porte sur tous les résultats filtrés, pas uniquement la page visible. Pour les très grands corpus, utiliser l'API d'export en flux, car les boutons Streamlit préparent les fichiers en mémoire.

## Modérer

Le mot de passe administrateur est stocké sous forme d'une empreinte scrypt, jamais en clair. La session serveur expire après 30 minutes. Un quota global persistant limite les essais de connexion à 30 par tranche de 10 minutes. Aucun compte contributeur n'existe.

L'administration permet de :

- examiner les propositions et les doublons détectés ;
- réviser les données en JSON avant de prendre une décision, avec motif conservé ;
- valider ou refuser avec justification ;
- fusionner un **ajout proposé** avec une fiche publiée de même type ;
- ajouter une plateforme ;
- consulter l'historique paginé et les états avant/après.

Une fusion conserve les champs principaux de la fiche cible et réunit ses tags et références avec ceux de la proposition. Elle ne remplace pas automatiquement le nom, l'URL, la source ou la plateforme ; les valeurs proposées restent dans l'historique. Pour modifier ces champs, proposer ensuite une correction de la fiche. Il ne s'agit pas d'une suppression/fusion de deux fiches déjà publiées.

Les modifications contrôlent la version de la fiche au moment de la soumission puis de la validation. En cas de conflit, l'administrateur compare la fiche actuelle à la proposition, révise cette dernière et coche explicitement la reprise de la version actuelle. La validation, les références, le statut et l'historique sont enregistrés dans une transaction unique. Les décisions concurrentes sont sérialisées sur PostgreSQL. Le changement de source ou de plateforme d'un compte ayant des contenus nécessite d'abord de réaffecter ces contenus à un autre compte approprié ou de retirer leur association.

Le contrôle documentaire est humain : la présence technique d'une URL de référence ne garantit ni sa validité scientifique, ni la pertinence de la qualification. La description ne doit pas servir à contourner les qualifications documentées. Aucun contenu web n'est récupéré pour vérifier automatiquement son propos.

## API publique et collecteurs Python/R

L'API ne propose aucune route de soumission ou de modération : toutes ses données documentaires sont validées. Aucun jeton administrateur n'est exposé à un client API.

| Route GET | Résultat |
| --- | --- |
| `/v1/statistiques` | Effectifs publiés |
| `/v1/plateformes` | Plateformes disponibles |
| `/v1/tags`, `/v1/tags/{id}` | Vocabulaire et références |
| `/v1/sources`, `/v1/comptes`, `/v1/contenus` | Recherche paginée |
| `/v1/sources/{id}` | Fiche, comptes et contenus associés |
| `/v1/comptes/{id}`, `/v1/contenus/{id}` | Fiche et références |
| `/v1/urls` | URL, plateforme et type de média, paginés |
| `/v1/export/txt`, `/v1/export/csv`, `/v1/export/json` | Export complet en flux |

Paramètres partagés : `texte`, `url`, `plateforme_id`, `type_media`, `tags` répété, `thematique_id`, `operateur=ET|OU`, `descendants`, `pays`, `langue`, `date_debut`, `date_fin`, `source_id`, `compte_id`. Les routes de listes acceptent `page` (1 par défaut) et `taille` (maximum 200). Les routes de corpus acceptent `entite=source|compte|contenu`, par défaut `contenu`. Les dates sont au format ISO `YYYY-MM-DD`.

```python
import requests

base = "https://api.votre-domaine.fr"
plateformes = requests.get(f"{base}/v1/plateformes", timeout=30).json()
youtube = next(p["id"] for p in plateformes if p["nom"] == "YouTube")
reponse = requests.get(f"{base}/v1/export/txt", params={"plateforme_id": youtube}, timeout=120)
reponse.raise_for_status()
urls = reponse.text.splitlines()  # À transmettre à un collecteur, sans téléchargement dans DésinfoLab.
```

```r
library(jsonlite)
plateformes <- fromJSON("https://api.votre-domaine.fr/v1/plateformes")
tiktok <- plateformes$id[plateformes$nom == "TikTok"]
urls <- readLines(paste0("https://api.votre-domaine.fr/v1/export/txt?plateforme_id=", tiktok), encoding = "UTF-8")
writeLines(urls, "corpus-tiktok.txt", useBytes = TRUE)
```

Les exports HTTP PostgreSQL utilisent une lecture cohérente `REPEATABLE READ` et des lots de 200 fiches ; aucune limite silencieuse de résultats. Les listes utilisent un ordre stable par identifiant. Les URL sont conservées telles que soumises après suppression des espaces de bord. La clé de doublon normalise le domaine, certains paramètres de suivi et les variantes YouTube usuelles ; elle n'effectue aucun accès réseau et ne résout pas les liens raccourcis TikTok ou les redirections.

## Confidentialité et limites de l'anonymat

Aucun nom, courriel, IP, identifiant de contributeur, agent utilisateur ou empreinte de navigateur n'est collecté par le code métier. Les propositions, leurs dates et les textes libres sont conservés pour la modération et la traçabilité ; ils peuvent contenir des renseignements identifiants si une personne en saisit volontairement. Les URL des sources/comptes ne doivent pas être confondues avec des identifiants de visiteurs.

La protection anti-abus associe un calcul à usage unique, un délai minimal de deux secondes, une expiration à trente minutes, un champ leurre et des compteurs **globaux** en PostgreSQL. Le jeton aléatoire du calcul n'est pas stocké dans la contribution et n'identifie pas une personne. Il est supprimé après un essai ; les jetons expirés sont purgés lors de la création de nouveaux défis. Ces défenses freinent les soumissions automatisées simples, sans constituer un CAPTCHA inviolable. Les quotas globaux peuvent être saturés par un tiers ; leur portée est le compromis choisi pour éviter le suivi individuel.

Streamlit conserve un état de connexion en mémoire et utilise ses mécanismes de session et de protection XSRF. Sa télémétrie est désactivée. Uvicorn ne produit pas de journaux d'accès. Les journaux PostgreSQL ne consignent pas les requêtes ; les logs Docker sont limités en taille. Les erreurs opérationnelles peuvent néanmoins produire des traces techniques, et **le proxy Coolify, le VPS, le navigateur ou les sites ouverts peuvent traiter des adresses IP**. Configurer séparément leurs journaux, délais de conservation et droits d'accès. DésinfoLab ne promet pas un anonymat réseau absolu.

Aucun téléchargement automatique de vidéo, suivi analytique, CAPTCHA tiers ou extraction distante n'est inclus.

## Sauvegardes et restauration

Le service `sauvegardes` produit un `pg_dump` au format personnalisé toutes les 24 heures (modifiable) avec rétention de 14 jours. Il écrit d'abord un fichier `.part`, vérifie la lisibilité de son catalogue, puis renomme le fichier atomiquement. Une erreur arrête le service, que Docker relance ; le contrôle de santé détecte l'absence de sauvegarde récente. Si l'intervalle dépasse 24 heures, ajuster aussi le contrôle de santé du Compose.

```sh
# Liste des sauvegardes
docker compose exec sauvegardes ls -lh /sauvegardes
# Copie d'une sauvegarde hors du volume ; remplacer le nom ci-dessous
docker compose cp sauvegardes:/sauvegardes/desinfolab-AAAAMMJJTHHMMSSZ.dump ./sauvegarde.dump
```

Le volume de sauvegarde local ne protège pas contre la perte du VPS. Prévoir une copie régulière hors serveur, avec chiffrement et contrôle d'accès. Les sauvegardes contiennent aussi les contributions en attente et l'historique ; leur confidentialité compte autant que celle de la base.

Tester la restauration vers une base vide, jamais directement dans la base en service :

```sh
# Créer une base de test vide avec le rôle configuré
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" desinfolab_restauration'
docker compose cp ./sauvegarde.dump db:/tmp/desinfolab.dump
docker compose cp ./scripts/restaurer.sh db:/tmp/restaurer.sh
docker compose exec db sh -c 'PGUSER="$POSTGRES_USER" sh /tmp/restaurer.sh /tmp/desinfolab.dump desinfolab_restauration'
```

Le script refuse une base qui contient déjà des tables publiques et restaure en une transaction. Après restauration, vérifier les effectifs, les fiches, les références et la version Alembic avant toute bascule. `docker compose down` conserve les volumes ; **`docker compose down -v` les supprime**.

## Développement, migrations et vérifications

```sh
pip install -r requirements-dev.txt
# Fournir une base PostgreSQL de développement et les secrets dans l'environnement.
export DATABASE_URL='postgresql+psycopg://utilisateur:mot_de_passe@localhost:5432/desinfolab'
alembic upgrade head
streamlit run app.py
# Dans un autre terminal avec le même environnement :
uvicorn desinfolab.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

`.env` est chargé par Docker Compose. Pour les commandes Python hors Compose, exporter explicitement les variables dans l'environnement ; le code n'importe pas automatiquement `.env`.

```sh
pytest -q                       # Tests isolés rapides, SQLite uniquement comme moteur de test.
TEST_DATABASE_URL='postgresql+psycopg://utilisateur:mot_de_passe@localhost:5432/base_tests' pytest -q
ruff check desinfolab tests scripts migrations app.py
alembic check                   # Vérifie la concordance du modèle et des migrations.
```

Les tests PostgreSQL créent un schéma aléatoire par test et le suppriment ensuite ; le rôle de test doit pouvoir créer des schémas. **Ne pas utiliser une base de production pour les tests.** Ils couvrent soumissions, modération, anonymat applicatif, tags, URL, recherche multicritère, export, API et parcours Streamlit via `AppTest`.

Le schéma SQL PostgreSQL complet est fourni dans `schema.sql`, généré depuis les migrations versionnées. Utiliser normalement `alembic upgrade head`, et ne pas exécuter le schéma initial sur une base déjà créée. Après un changement de modèle, créer une nouvelle migration ; ne pas modifier une migration déjà déployée. Avant une mise à jour, sauvegarder puis exécuter les tests et vérifier les parcours du cahier des charges dans `docs/COUVERTURE.md`.

Organisation : `modeles.py` (schéma), `validation.py` (saisies et URL), `securite.py` (accès et anti-abus), `contributions.py` (métier), `catalogue.py` (lecture/recherche), `exports.py`, `api.py`, `interface.py`, `migrations/`, `scripts/`, `tests/`.
