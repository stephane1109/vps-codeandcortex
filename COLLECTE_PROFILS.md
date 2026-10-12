# Collecte par compte et média : recherche vidéo exclusive

Les modes **Profils** et **Presse/médias** interrogent exclusivement :

`https://www.tiktok.com/search/video?q=%40nomducompte`

`collecte/comptes.py` normalise l'identifiant puis appelle `collect_links()`.
Celui-ci délègue les comptes à `collecte/recherche_comptes.py` avant toute navigation.
Il n'existe aucun repli vers `https://www.tiktok.com/@compte` ni vers une page de
hashtag dans ce parcours. Une redirection vers un profil n'est pas analysée.
La lecture des textes ouvre ensuite les URL individuelles des vidéos découvertes.

Les hashtags ET/OU, dates et langue sont toujours filtrés sur les publications
lues ; likes, commentaires, variables TXT et archive enrichie restent conservés.
Le mode **Hashtags** garde ses propres pages `/tag/` et son défilement existant.

## Chargement et sélection

- La première page peut contenir six résultats ou uniquement d'autres auteurs.
  Cela ne termine pas la découverte.
- `pagination_recherche.py` repère le conteneur défilant des résultats, puis utilise
  la molette Selenium par portions d'écran. Le conteneur est relu à chaque étape.
  `DEFILER_PUBLICATIONS_JS` propose le même déplacement progressif en repli.
- Chaque attente scrute les liens HTML et les données reçues dynamiquement.
  L'observateur Selenium lit uniquement les réponses de la recherche courante,
  sans rejouer de requête ni générer de signature.
- Un bouton de pagination suivant est actionné s'il est disponible dans la page.
  Les champs `cursor` et `has_more`/`hasMore` observés sont conservés au journal.
- Les objets vidéo fournissent leur auteur réel. Leur identité prime sur un lien
  HTML contradictoire de même identifiant. Le compte doit correspondre exactement,
  sans distinction de casse ; un compte au nom voisin est exclu. L'auteur est de
  nouveau contrôlé lors de la lecture de la publication.
- Les publications sont dédoublonnées par identifiant TikTok, même si leurs cartes
  disparaissent du DOM ou si leurs URL contiennent des paramètres différents.
- Le parcours attend au moins trois chargements sans nouveauté avant de conclure
  à une stagnation. Une progression dans une grille encore défilable ou de nouveaux
  résultats d'autres auteurs prolonge le parcours. Les CAPTCHA gardent la fenêtre
  automatique ; les résultats déjà collectés sont conservés.

Le plafond de publications s'applique par compte avant les filtres des légendes.
Un budget de sécurité d'au moins quatre défilements par publication demandée,
ainsi que les délais d'expiration de session existants, bornent les ressources du
VPS. Un arrêt avant l'objectif est signalé **Collecte partielle**. Même un signal
`has_more=false` décrit uniquement la fin accessible de cette recherche, jamais
l'historique exhaustif du compte. Atteindre la limite demandée n'est pas non plus
une preuve d'exhaustivité.

## Compteurs

| Compteur | Signification |
| --- | --- |
| Découvertes | Identifiants distincts de tous les auteurs vus dans les recherches |
| Retenues pour lecture | Publications dont l'auteur correspond aux comptes sélectionnés |
| Traitées | Publications lues ou ayant fait l'objet d'une tentative de lecture |
| Exportées dans le TXT | Publications réellement écrites dans le TXT après les filtres |

L'écriture atomique du TXT doit réussir avant que le compteur d'export soit mis à
jour. Les commentaires ne sont pas comptés comme des publications supplémentaires.
Les quatre compteurs sont affichés dans Streamlit et conservés dans `journal.json`.

## Validation fournie

`tests/test_recherche_comptes.py` couvre notamment six résultats initiaux suivis
de deux chargements sans nouveauté, puis douze et dix-huit résultats, le chargement
asynchrone, les autres auteurs, les doublons et la pagination disponible.
`tests/test_compteurs_recherche.py` couvre les filtres, likes, commentaires, erreurs
de lecture et d'écriture. Les scénarios antérieurs ont été adaptés à la source
unique de recherche.

Ces tests sont fournis mais **non exécutés**, conformément à la consigne de
l'utilisateur. Aucun essai TikTok ni intervention Coolify n'a été réalisé.

Références de mise en œuvre : [molette Selenium](https://www.selenium.dev/documentation/webdriver/actions_api/wheel/)
et [format des réponses de recherche TikTok-Api](https://github.com/davidteather/TikTok-Api/blob/main/TikTokApi/api/search.py).
