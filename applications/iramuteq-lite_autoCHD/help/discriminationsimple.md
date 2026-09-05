# Discrimination simple

Ce mode cherche **une seule configuration CHD plus discriminante**.

Il ne modifie ni la CHD, ni le calcul du `chi2`.
Il relance simplement quelques analyses ciblées du même corpus, puis retient celle où les classes s'opposent le mieux sur l'AFC.

## Principe

On peut le lire comme si un analyste refaisait plusieurs fois la même CHD avec de très légères variations, puis gardait la version où l'opposition entre classes est la plus lisible.

Le mode compare donc plusieurs résultats possibles, mais il ne renvoie **qu'un seul compromis final**.

## Ce qui est testé automatiquement

Dans ce mode, la grille est volontairement courte :

- `min_docfreq = 2`
- `min_docfreq = 3`
- `min_docfreq = 4`
- `min_docfreq = 5`

Le reste est fixé ainsi :

- filtrage morphosyntaxique sur `NOM + VER`
- exclusion du verbe `être`
- `AUTRE_FORME` conservé ou non selon le choix utilisateur

Autrement dit, le mode exécute successivement **4 CHD ciblées** du même corpus.

## Nombre de classes

L'utilisateur ne choisit pas le nombre final de classes.

Il fixe seulement :

- `k_iramuteq` : la borne maximale des classes explorées

Ensuite, pour chaque CHD testée, l'application compare automatiquement les solutions en classes à partir de `3` classes jusqu'à cette borne maximale.

Le résultat final affiche donc :

- la configuration retenue
- le nombre de classes retenues
- les variables qui ont conduit à ce résultat

## Comment la sélection est faite

Pour chaque CHD testée :

- l'application calcule les termes caractéristiques avec le `chi2` habituel
- elle conserve les termes significatifs avec `p.value <= 0.05`
- elle récupère leurs coordonnées `x, y` sur le plan AFC
- elle calcule le centre lexical de chaque classe : la moyenne des coordonnées `x, y` de ses mots significatifs
- elle calcule les distances euclidiennes entre tous les centres de classes
- elle mesure aussi la dispersion des mots autour du centre de leur classe

Pour chaque paire de classes, l'application calcule :

`distance entre les deux centres / dispersion lexicale des deux classes`.

Le score retenu est la plus petite de ces séparations relatives. Ainsi, toutes les classes doivent être distinctes par rapport à leur propre nuage de mots, qu'il y ait 3, 4, 5 ou 6 classes.

En cas d'égalité, la moyenne des séparations relatives départage les deux solutions.

Il n'y a pas de calcul d'angle, de `theta`, de similarité cosinus, ni de pondération ajoutée.

Le `chi2` existant n'est donc pas modifié : il sert seulement à repérer les mots caractéristiques significatifs. L'AFC sert ensuite à mesurer la distance entre les centres lexicaux des classes.

## Ce qui est affiché

Le mode affiche seulement les éléments utiles à la lecture du résultat :

- la configuration retenue
- le profil morphosyntaxique retenu
- la valeur `min_docfreq` retenue
- le nombre de classes retenues
- la séparation relative AFC entre les classes
- les effectifs des classes

Les sous-calculs internes du score ne sont pas nécessaires pour l'interprétation courante.

## À quoi sert ce mode

Ce mode sert à obtenir plus vite une CHD où les classes sont **mieux opposées lexicalement**, sans tester manuellement plusieurs réglages.

L'idée est donc :

- lancer quelques variantes utiles
- comparer leur séparation sur l'AFC
- retenir automatiquement la plus discriminante
