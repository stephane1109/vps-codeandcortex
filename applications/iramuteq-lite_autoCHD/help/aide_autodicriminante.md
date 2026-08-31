# Aide CHD optimisee par AFC

## Objectif

Dans cette version, le mode **CHD optimisee par AFC** ne teste plus une grande grille exhaustive.

Il cherche un resultat plus discriminant avec une strategie ciblee :

- le **plafond de classes** reste celui choisi dans l'interface ;
- le **minimum de classes** reste celui choisi dans l'interface ;
- le **filtrage morphosyntaxique** est force sur `NOM + VER` ;
- le verbe `etre` est exclu ;
- `min_docfreq` varie seulement de `2` a `5`.

Le but est d'obtenir plus vite un resultat ou les classes s'opposent nettement sur l'AFC.

## Idee generale

On peut lire ce mode comme un **moteur d'echecs** :

- il ne joue pas tous les coups possibles ;
- il garde une famille de coups jugee utile ;
- puis il compare les positions produites pour retenir la meilleure.

On peut aussi garder la **metaphore du perceptron** au sens pedagogique :

- le systeme active plusieurs versions proches du corpus ;
- il observe laquelle separe le mieux les classes ;
- il garde une seule configuration finale.

## Parametres fixes

Ces parametres restent ceux choisis par l'utilisateur :

- `k_min` : nombre minimal de classes a retenir ;
- `k_iramuteq` : nombre maximal de classes a explorer ;
- `segment_size`, `rst1`, `rst2` ;
- `classif_mode` ;
- `svd_method` ;
- `iramuteq_max_formes` ;
- `lexique_utiliser_lemmes` ;
- `retirer_stopwords` ;
- `supprimer_ponctuation` ;
- `supprimer_chiffres` ;
- dictionnaire, nettoyage, apostrophes, tirets et autres reglages generaux.

Autrement dit, ce mode ne change pas toute l'analyse : il ne fait varier que ce qui sert ici a la discrimination.

## Parametres testes automatiquement

La grille est maintenant volontairement courte.

Filtrage morphosyntaxique impose :

- `filtrage_morpho = TRUE`
- `pos_lexique_a_conserver = NOM, VER`
- `morpho_exclure_etre_verbe = TRUE`
- `morpho_conserver_hors_lexique = FALSE`

Valeurs explorees :

- `min_docfreq = 2`
- `min_docfreq = 3`
- `min_docfreq = 4`
- `min_docfreq = 5`

Le nombre de configurations teste est donc :

- `4`

et non plus des centaines ou des milliers.

## Etape 1 : une CHD par configuration

Pour chaque valeur de `min_docfreq`, le mode lance une CHD normale jusqu'au `k` maximal demande.

Il conserve ensuite les partitions possibles :

- `P2`
- `P3`
- `P4`
- ...
- `Pk`

La CHD d'origine et le calcul du `chi2` ne sont pas modifies.

## Etape 2 : selection automatique de la partition

Dans chaque configuration, chaque partition `Pk` est d'abord evaluee par le score structurel classique :

- `H` = homogeneite interne ;
- `D` = distinction minimale entre classes ;
- `L` = diffusion lexicale ;
- `B = (H + D + L) / 3`.

La meilleure partition de la configuration est donc :

- `P* = argmax B(Pk)` pour Auto CHD ;
- puis, dans le mode AFC discriminant, cette partition est aussi relue par l'AFC.

## Etape 3 : les 10 meilleurs chi2 significatifs par classe sur l'AFC

Le mode AFC discriminant repart des **termes significatifs dont le `chi2` est le plus fort, en gardant jusqu'a 10 termes par classe**.

Principe :

- dans chaque classe, on garde les formes caracteristiques dont la `p-value` est significative ;
- on trie ces formes par `chi2` decroissant ;
- on garde jusqu'a `10` termes par classe ;
- on recupere leurs coordonnees `x, y` sur le plan AFC ;
- on observe comment ces termes se placent par rapport aux classes ;
- on prefere les configurations ou ces termes tirent les classes dans des directions opposees.

Le graphique AFC final de ce mode projette justement ces termes retenus.

## Score discriminant AFC

Le score `A` combine plusieurs aspects geometriques :

- `A_theta` : opposition angulaire des classes ;
- `A_dist` : distance entre classes ;
- `A_rad` : eloignement des classes par rapport au centre ;
- `A_align` : alignement des termes a fort `chi2` avec leur classe ;
- `A_poles` : opposition des poles lexicaux construits a partir de ces termes.

Le score global est ensuite une combinaison stricte de ces composantes.

En pratique, il favorise les configurations ou :

- les classes ne sont pas collees ;
- les classes ne regardent pas toutes dans la meme direction ;
- les termes les plus discriminants soutiennent vraiment cette opposition.

## Resultat final

Le mode retient **un seul resultat final** :

- une configuration de pretraitement ;
- une partition `Pk` ;
- un graphe AFC avec les termes les plus discriminants ;
- les scores associes.

En resume :

`Corpus -> 4 configurations ciblees -> CHD -> partitions Pk -> top 10 chi2 significatifs par classe sur AFC -> meilleur compromis discriminant`
