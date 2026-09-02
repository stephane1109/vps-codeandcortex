# Analyse discriminante optimisée

## Objectif

Le mode **Analyse discriminante optimisée** cherche à produire des classes qui s'opposent le plus nettement possible sur le plan AFC, sans modifier la CHD d'origine ni le calcul du `chi2`.

Il procède en deux temps :

- il lance plusieurs configurations ciblées du même corpus ;
- il ne conserve qu'un seul résultat final : la configuration et la solution en classes qui donnent la meilleure opposition lexicale.

Repères essentiels :

- `k_iramuteq` fixe le plafond des classes explorées ;
- la borne minimale est interne au mode et fixée à `3` classes ;
- `min_docfreq` est la variable testée automatiquement dans ce mode.

## Ce qui varie réellement

Dans cette version, la grille est volontairement réduite pour éviter les temps de calcul trop longs.

Le mode force :

- `filtrage_morpho = TRUE`
- `pos_lexique_a_conserver = NOM, VER`
- `morpho_exclure_etre_verbe = TRUE`
- `morpho_conserver_hors_lexique` reprend le choix utilisateur

Puis il fait varier seulement :

- `min_docfreq = 2`
- `min_docfreq = 3`
- `min_docfreq = 4`
- `min_docfreq = 5`

## Ce qui reste fixe

Les autres paramètres restent ceux choisis dans l'interface :

- le plafond de classes à explorer ;
- la segmentation ;
- la lemmatisation ;
- le retrait des stopwords ;
- la ponctuation ;
- la conservation ou suppression des chiffres ;
- la méthode SVD ;
- le nombre maximal de formes ;
- les autres réglages du pipeline.

## Étape 1 : CHD et solutions en classes

Pour chaque configuration candidate, l'application calcule une CHD normale jusqu'au nombre maximal de classes demandé.

Elle conserve ensuite les solutions en classes :

- `P3`
- `P4`
- ...
- `Pk`

La CHD et le `chi2` historique ne sont pas modifiés.

## Étape 2 : lecture AFC directe de chaque solution en classes

Dans ce mode, la solution finale n'est pas d'abord choisie par `B`.

Le mode :

- prend chaque solution `Pk` issue de la CHD ;
- relit cette solution sur l'AFC ;
- compare directement les solutions en classes avec le score discriminant `A`.

La solution retenue est donc :

- `P* = argmax A(Pk)`.

## Étape 3 : lecture AFC de tous les chi2 significatifs par classe

Pour chaque solution en classes, le mode repart des formes caractéristiques déjà obtenues par la CHD.

Il :

- garde seulement les formes dont la `p-value` est significative ;
- trie ces formes par `chi2` décroissant dans chaque classe ;
- garde tous les termes à `p.value <= 0.05` ;
- récupère leurs coordonnées `x, y` sur l'AFC ;
- compare leur orientation avec les classes.

Le graphique AFC final de ce mode projette ces termes retenus.

## Le score discriminant

Le score `A` combine plusieurs aspects géométriques :

- `A_theta` : opposition angulaire des classes ;
- `A_dist` : distance entre classes ;
- `A_rad` : éloignement des classes par rapport au centre ;
- `A_align` : similarité cosinus d'alignement entre les termes à fort `chi2` et leur classe ;
- `A_poles` : opposition des pôles lexicaux formés par ces termes.

Plus `A` est élevé, plus les classes sont séparées, opposées et soutenues par des termes fortement discriminants.

En pratique :

- `A` sert au choix final ;
- `B` reste un indicateur structurel complémentaire.

Résumé :

`Corpus -> 4 configurations ciblées -> CHD -> solutions de 3 a k classes -> tous les chi2 significatifs par classe sur AFC -> resultat final le plus discriminant`
