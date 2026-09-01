# Analyse discriminante optimisée

## Objectif

Dans cette version, le mode **Analyse discriminante optimisée** ne teste plus une grande grille exhaustive.

Il cherche un résultat plus discriminant avec une stratégie ciblée :

- le **plafond de classes** reste celui choisi dans l'interface ;
- la **borne minimale d'exploration** n'est pas demandée à l'utilisateur ;
- le **filtrage morphosyntaxique** est forcé sur `NOM + VER` ;
- le verbe `être` est exclu ;
- `min_docfreq` varie seulement de `2` à `5`.

Le but est d'obtenir plus vite un résultat où les classes s'opposent nettement sur l'AFC.

## Idée générale

On peut lire ce mode comme un **moteur d'échecs** :

- il ne joue pas tous les coups possibles ;
- il garde une famille de coups jugée utile ;
- puis il compare les positions produites pour retenir la meilleure.

On peut aussi garder la **métaphore du perceptron** au sens pédagogique :

- le système active plusieurs versions proches du corpus ;
- il observe laquelle sépare le mieux les classes ;
- il garde une seule configuration finale.

## Bornes d'exploration

Dans ce mode, l'utilisateur **ne choisit pas le `k` final**.

L'application retient automatiquement la partition la plus discriminante.

L'utilisateur fixe seulement le **plafond** de recherche :

- `k_iramuteq` : borne maximale des partitions explorées.

La borne minimale est **interne au mode** et fixée à `3` classes.

Autrement dit, si la limite choisie est `10`, l'application compare automatiquement `P3...P10`, puis retient la partition la plus discriminante.

## Paramètres fixes

Ces paramètres restent ceux choisis par l'utilisateur :

- `segment_size`, `rst1`, `rst2` ;
- `classif_mode` ;
- `svd_method` ;
- `iramuteq_max_formes` ;
- `lexique_utiliser_lemmes` ;
- `retirer_stopwords` ;
- `supprimer_ponctuation` ;
- `supprimer_chiffres` ;
- dictionnaire, nettoyage, apostrophes, tirets et autres réglages généraux.

Autrement dit, ce mode ne change pas toute l'analyse : il ne fait varier que ce qui sert ici à la discrimination.

## Paramètres testés automatiquement

La grille est maintenant volontairement courte.

Filtrage morphosyntaxique imposé :

- `filtrage_morpho = TRUE`
- `pos_lexique_a_conserver = NOM, VER`
- `morpho_exclure_etre_verbe = TRUE`
- `morpho_conserver_hors_lexique = FALSE`

Valeurs explorées :

- `min_docfreq = 2`
- `min_docfreq = 3`
- `min_docfreq = 4`
- `min_docfreq = 5`

Le nombre de configurations testé est donc :

- `4`

et non plus des centaines ou des milliers.

## Étape 1 : une CHD par configuration

Pour chaque valeur de `min_docfreq`, le mode lance une CHD normale jusqu'au `k` maximal demandé.

Il conserve ensuite les partitions possibles :

- `P3`
- `P4`
- ...
- `Pk`

La CHD d'origine et le calcul du `chi2` ne sont pas modifiés.

## Étape 2 : évaluation discriminante directe des partitions

Dans l'**Analyse discriminante optimisée**, les partitions `Pk` ne sont pas d'abord retenues par `B` comme en Auto CHD.

Le mode procède autrement :

- il conserve les partitions `P3...Pk` produites par la même CHD ;
- il évalue directement chaque partition sur l'AFC ;
- il compare ensuite ces partitions avec le score discriminant `A`.

La partition retenue dans une configuration est donc :

- `P* = argmax A(Pk)`.

Les indicateurs `H`, `D`, `L` et `B` sont toujours calculés, mais ils restent **complémentaires** :

- ils servent à décrire la structure de la partition ;
- `B` peut aider à départager un ex aequo ;
- ils ne pilotent pas la sélection principale dans ce mode.

## Étape 3 : tous les termes significatifs par classe sur l'AFC

L'Analyse discriminante optimisée repart de **tous les termes significatifs à `p.value <= 0.05`**, triés par `chi2` dans chaque classe.

Principe :

- dans chaque classe, on garde les formes caractéristiques dont la `p-value` est significative ;
- on trie ces formes par `chi2` décroissant ;
- on récupère leurs coordonnées `x, y` sur le plan AFC ;
- on observe comment ces termes se placent par rapport aux classes ;
- on préfère les configurations où ces termes tirent les classes dans des directions opposées.

Le graphique AFC final de ce mode projette justement ces termes retenus.

## Score discriminant AFC

Le score `A` combine plusieurs aspects géométriques :

- `A_theta` : opposition angulaire des classes ;
- `A_dist` : distance entre classes ;
- `A_rad` : éloignement des classes par rapport au centre ;
- `A_align` : alignement des termes à fort `chi2` avec leur classe ;
- `A_poles` : opposition des pôles lexicaux construits à partir de ces termes.

Le score global `A` est ensuite calculé à partir de ces composantes.

En pratique, il favorise les configurations où :

- les classes ne sont pas collées ;
- les classes ne regardent pas toutes dans la même direction ;
- les termes les plus discriminants soutiennent vraiment cette opposition.

En pratique :

- `A` sert à choisir la partition ;
- `B` reste un indicateur structurel secondaire.

## Résultat final

Le mode retient **un seul résultat final** :

- une configuration de prétraitement ;
- une partition `Pk` ;
- un graphe AFC avec les termes les plus discriminants ;
- les scores associés.

En résumé :

`Corpus -> 4 configurations ciblées -> CHD -> partitions Pk -> tous les termes significatifs par classe sur AFC -> meilleur compromis discriminant`
