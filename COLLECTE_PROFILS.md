# Collecte par profils et médias depuis les hashtags

Les modes **Profils** et **Presse/médias** parcourent désormais les mêmes pages
`https://www.tiktok.com/tag/hashtag` que le mode **Hashtags**. Au moins un hashtag
est obligatoire ; le deuxième est facultatif, avec ET/OU.
Ils n'ouvrent plus la recherche `/search/video?q=%40compte` ni l'accueil du profil.

Chaque hashtag est chargé une seule fois pour tous les médias sélectionnés,
dans le même navigateur anonyme. La validation initiale et les CAPTCHA suivent
le fonctionnement du mode Hashtags. Aucune connexion à TikTok n'est proposée.

## Sélection des publications

- Les liens des résultats chargés dynamiquement sont examinés à chaque défilement.
- L'identifiant d'auteur dans le lien doit correspondre exactement à un compte
  sélectionné, sans distinction de casse. Une simple mention du média ne suffit pas.
- Les autres auteurs n'utilisent pas le quota. Le défilement continue même si les
  premières vidéos n'appartiennent à aucun média coché.
- Le plafond s'applique par compte, tous hashtags confondus, avant les filtres de
  légende, de langue et de date. Les identifiants TikTok sont dédoublonnés entre
  les pages et les hashtags.
- L'auteur effectivement lu dans la publication est contrôlé une seconde fois.
  Les opérateurs ET/OU sont ensuite appliqués aux hashtags de sa légende.
- Les likes, commentaires, variables TXT et archive enrichie sont conservés.

Le moteur utilise le défilement des hashtags existant, qui repère un conteneur
défilant autour des publications et utilise le défilement de page à défaut.
Il attend les nouveaux liens à chaque chargement. Trois attentes consécutives
sans nouvel identifiant terminent le parcours ; les six premières vidéos ne
constituent pas un critère d'arrêt. Le budget est de 40 défilements par hashtag.

Un média peu présent dans les résultats accessibles peut fournir moins de
publications que demandé. Le statut est alors **Collecte partielle**. Cela
ne signifie pas que son compte est vide. Atteindre le quota ne garantit pas non
plus l'historique exhaustif du compte. Les erreurs TikTok, de navigateur et
d'extraction restent distinctes dans les diagnostics.

## Compteurs

| Compteur | Signification |
| --- | --- |
| Découvertes | Identifiants distincts de tous les auteurs vus dans les hashtags |
| Retenues pour lecture | Liens des comptes sélectionnés, après dédoublonnage et quota |
| Traitées | Publications lues ou ayant fait l'objet d'une tentative de lecture |
| Exportées dans le TXT | Publications effectivement écrites après les filtres |

L'écriture atomique du TXT précède la mise à jour du compteur d'export.
Les commentaires ne comptent pas comme des publications supplémentaires.
Le bilan de chaque hashtag inclut les comptes retenus et les nombres cumulés
de liens par compte.

## Organisation et cas de non-régression

`collecte/comptes.py` partage le parcours entre les profils et les médias ;
`collecte/hashtags.py` appelle le moteur commun `collect_links()`.
Les modules historiques de recherche vidéo sont conservés, mais ne sont plus
appelés par ces modes de l'application.

`tests/test_presse_hashtags.py` couvre les chargements au-delà de six vidéos,
deux attentes sans nouveauté, les autres auteurs, les doublons entre hashtags,
les quotas par compte et le mode Hashtags général.
Les cas d'intégration couvrent ET/OU, la session partagée, les erreurs,
les commentaires et les exports.

Tests fournis **sans exécution**. Aucun essai TikTok ni intervention Coolify.
