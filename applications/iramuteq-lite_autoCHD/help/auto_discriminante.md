# Analyse discriminante optimisee

## Objectif

Le mode **Analyse discriminante optimisee** cherche a produire des classes qui s'opposent le plus nettement possible sur le plan AFC, sans modifier la CHD d'origine ni le calcul du `chi2`.

Il procede en deux temps :

- il lance plusieurs configurations ciblees du meme corpus ;
- il ne conserve qu'un seul resultat final : la configuration et la partition qui donnent la meilleure opposition lexicale.

## Idee generale

On peut se representer ce mode comme un **moteur d'echecs** :

- il n'explore pas tous les coups possibles ;
- il retient une petite famille de coups juges utiles ;
- il compare les positions obtenues ;
- il garde la meilleure combinaison globale.

On peut aussi utiliser la **metaphore du perceptron** au sens pedagogique :

- le systeme active plusieurs variantes proches du corpus ;
- il observe laquelle separe le mieux les classes dans l'espace AFC ;
- il retient la configuration la plus discriminante.

## Ce qui varie reellement

Dans cette version, la grille est volontairement reduite pour eviter les temps de calcul trop longs.

Le mode force :

- `filtrage_morpho = TRUE`
- `pos_lexique_a_conserver = NOM, VER`
- `morpho_exclure_etre_verbe = TRUE`
- `morpho_conserver_hors_lexique = FALSE`

Puis il fait varier seulement :

- `min_docfreq = 2`
- `min_docfreq = 3`
- `min_docfreq = 4`
- `min_docfreq = 5`

Le nombre de configurations teste est donc de **4**.

## Ce qui reste fixe

Les autres parametres restent ceux choisis dans l'interface :

- le minimum de classes a retenir ;
- le maximum de classes a explorer ;
- la segmentation ;
- la lemmatisation ;
- le retrait des stopwords ;
- la ponctuation ;
- la conservation ou suppression des chiffres ;
- la methode SVD ;
- le nombre maximal de formes ;
- les autres reglages du pipeline.

## Etape 1 : CHD et partitions

Pour chaque configuration candidate, l'application calcule une CHD normale jusqu'au nombre maximal de classes demande.

Elle conserve ensuite les partitions :

- `P3`
- `P4`
- ...
- `Pk`

La CHD et le `chi2` historique ne sont pas modifies.

## Etape 2 : lecture AFC directe de chaque partition

Dans ce mode, la partition n'est pas d'abord choisie par `B`.

Le mode :

- prend chaque partition `Pk` issue de la CHD ;
- relit cette partition sur l'AFC ;
- compare directement les partitions avec le score discriminant `A`.

La partition retenue est donc :

- `P* = argmax A(Pk)`.

Les scores `H`, `D`, `L` et `B` restent calcules pour documenter la structure de la partition, mais ils ne commandent pas la selection principale.

## Etape 3 : lecture AFC de tous les chi2 significatifs par classe

Pour chaque partition, le mode repart des formes caracteristiques deja obtenues par la CHD.

Il :

- garde seulement les formes dont la `p-value` est significative ;
- trie ces formes par `chi2` decroissant dans chaque classe ;
- garde tous les termes a `p.value <= 0.05` ;
- recupere leurs coordonnees `x, y` sur l'AFC ;
- compare leur orientation avec les classes.

Le graphique AFC final de ce mode projette ces termes retenus.

## Le score discriminant

Le score `A` combine plusieurs aspects geometriques :

- `A_theta` : opposition angulaire des classes ;
- `A_dist` : distance entre classes ;
- `A_rad` : eloignement des classes par rapport au centre ;
- `A_align` : alignement des termes a fort `chi2` avec leur classe ;
- `A_poles` : opposition des poles lexicaux formes par ces termes.

Plus `A` est eleve, plus les classes sont separees, opposees et soutenues par des termes fortement discriminants.

En pratique :

- `A` sert au choix final ;
- `B` reste un indicateur structurel complementaire.

## Resultat final

Au final, le mode retient :

- une configuration de pretraitement ;
- une partition `Pk` ;
- un AFC projete avec tous les termes `chi2` significatifs retenus a `p.value <= 0.05` ;
- les scores `A`, `A_theta`, `A_dist`, `A_rad`, `A_align`, `A_poles` ;
- ainsi que `H`, `D`, `L`, `B` pour garder la lecture structurelle de la partition.

Resume :

`Corpus -> 4 configurations ciblees -> CHD -> partitions Pk -> tous les chi2 significatifs par classe sur AFC -> resultat final le plus discriminant`
