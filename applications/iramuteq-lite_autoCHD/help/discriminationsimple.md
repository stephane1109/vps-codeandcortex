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

Autrement dit, le mode lance **4 CHD ciblées** du même corpus.

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
- elle compare la manière dont ces mots séparent les classes

Le principe est simple :

- plus les mots significatifs tirent les classes dans des directions opposées
- plus les classes sont éloignées sur l'AFC
- plus la solution est jugée discriminante

Le `chi2` n'est donc pas remplacé.

Il sert toujours à repérer les termes caractéristiques.
L'AFC sert ensuite à lire si ces termes opposent bien les classes dans l'espace.

## Ce qui est affiché

Le mode affiche seulement les éléments utiles à la lecture du résultat :

- la configuration retenue
- le profil morphosyntaxique retenu
- la valeur `min_docfreq` retenue
- le nombre de classes retenues
- le score final de discrimination AFC
- les effectifs des classes

Les sous-calculs internes du score ne sont pas nécessaires pour l'interprétation courante.

## À quoi sert ce mode

Ce mode sert à obtenir plus vite une CHD où les classes sont **mieux opposées lexicalement**, sans tester manuellement plusieurs réglages.

L'idée est donc :

- lancer quelques variantes utiles
- comparer leur séparation sur l'AFC
- retenir automatiquement la plus discriminante
