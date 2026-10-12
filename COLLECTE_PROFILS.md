# Collecte ciblée par profils et médias

Les modes **Profils** et **Presse/médias** recherchent chaque compte sélectionné
avec chaque hashtag saisi. Au moins un hashtag reste obligatoire.
Pour `lemondefr` et `manifestation`, la requête textuelle est `manifestation lemondefr` :

`https://www.tiktok.com/search/video?q=manifestation%20lemondefr`

Les caractères `@` et `#` ne sont pas imposés dans la requête textuelle envoyée à TikTok.
Le contrôle exact de l’auteur et des hashtags reste effectué dans l’application.

Le moteur ne parcourt plus un hashtag général en espérant y retrouver les médias
cochés. Il n’utilise pas non plus l’accueil du profil. Le mode **Hashtags** seul
conserve son parcours habituel sur `/tag/hashtag`.

## Sélection et session

- Chaque média coché est transmis au moteur et devient une source distincte.
- Une recherche est ouverte pour chaque hashtag, jusqu’au quota du compte.
- Seuls les liens dont l’auteur correspond exactement au compte ciblé sont retenus.
  Les mentions du compte dans une légende ne suffisent pas.
- Les identifiants TikTok sont dédoublonnés entre les recherches. Les publications
  d’autres auteurs ne consomment pas le quota du compte.
- La limite s’applique par compte, tous hashtags confondus, avant les filtres de
  légende, de date et de langue. Le quota peut être atteint dès le premier hashtag.
- L’auteur est à nouveau contrôlé à la lecture, avant les exports et les commentaires.
  Les opérateurs ET/OU sont vérifiés sur les hashtags effectivement présents dans
  les légendes. Une requête TikTok ne remplace jamais ces vérifications.

Toutes les recherches et lectures utilisent le même navigateur Selenium anonyme.
Il n’y a ni authentification proposée, ni nouveau navigateur pour chaque vidéo.
Les CAPTCHA visibles restent traités manuellement dans la fenêtre intégrée.
Le traitement signale les refus de TikTok et ne garantit aucun accès exhaustif.

## Chargement et diagnostics

`collecte/comptes.py` appelle le moteur commun `collect_links()` pour les requêtes
ciblées. Le défilement détecte le conteneur des publications, attend les chargements
dynamiques et ne s’arrête pas à six vidéos. Trois tentatives sans nouveau lien sont
nécessaires avant un arrêt pour stagnation ; chaque recherche est bornée à
40 défilements pour limiter la charge du VPS.

Une erreur de chargement TikTok autorise une recharge de la même requête. Il n’y a
aucun repli vers une page générale ou un profil. Une redirection vers une autre page
empêche de collecter les liens de cette page. Les résultats déjà découverts sont
conservés lorsqu’une autre recherche échoue.

Le détail de chaque média affiche les requêtes ouvertes, leurs liens retenus,
les exclusions d’auteurs et les diagnostics disponibles. Il indique aussi les auteurs
présents dans les liens reçus, le nombre de publications du compte ciblé avant filtrage,
le nombre de défilements et la raison d’arrêt. Un média absent des
résultats de recherche n’est pas présenté comme un compte vide. Un quota non
atteint donne une collecte partielle ; un quota atteint ne prouve pas que tout
l’historique du compte a été parcouru.

## Compteurs

| Compteur | Signification |
|---|---|
| Découvertes | Identifiants distincts repérés dans les recherches ciblées, tous auteurs confondus |
| Retenues pour lecture | Publications des comptes ciblés, dédoublonnées et plafonnées |
| Traitées | Publications dont la lecture a été tentée |
| Exportées dans le TXT | Textes retenus et effectivement écrits dans le TXT |

Les exclusions à la découverte sont distinguées de celles après lecture de
l’auteur réel. Si aucune publication n’est lue, le bilan n’affiche pas des filtres
de langue et de légende à zéro comme s’ils avaient été exécutés. Les commentaires
ne comptent pas comme des publications supplémentaires.

## Scénarios de non-régression fournis

`tests/test_ciblage_comptes.py` simule des requêtes compte + hashtag : plus de six
publications après plusieurs chargements, autres auteurs, deux hashtags dans la
même session, dédoublonnage, quota cumulé, erreur TikTok et redirection refusée.
Les scénarios presse ET/OU, partage de session, filtres d’auteurs, commentaires et
exports sont conservés et adaptés dans les tests existants.

Ces tests sont fournis pour exécution par l’utilisateur ; ils n’ont pas été lancés
lors de cette correction. Aucun essai réel sur TikTok ou changement Coolify n’a été effectué.
