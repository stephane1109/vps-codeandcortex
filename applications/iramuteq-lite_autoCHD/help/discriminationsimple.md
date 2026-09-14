# Discrimination simple

Ce mode cherche **une seule configuration CHD plus discriminante**.

Il ne modifie ni la CHD, ni le calcul du `chi2`.
Il relance simplement quelques analyses ciblées du même corpus, puis retient celle où les classes s'opposent le mieux sur l'AFC.

## Principe

On peut le lire comme si un analyste refaisait plusieurs fois la même CHD avec de très légères variations, puis gardait la version où l'opposition entre classes est la plus lisible.

Le mode compare donc plusieurs résultats possibles, mais il ne renvoie **qu'un seul compromis final**.

## Ce qui est testé automatiquement

Dans ce mode, la grille croise deux paramètres :

- `min_docfreq = 2`
- `min_docfreq = 3`
- `min_docfreq = 4`
- `min_docfreq = 5`
- `k max = 3` jusqu'au plafond choisi dans l'interface, avec un maximum de `10`

Le reste est fixé ainsi :

- filtrage morphosyntaxique sur `NOM + VER`
- exclusion du verbe `être`
- `AUTRE_FORME` conservé ou non selon le choix utilisateur

Avec un plafond à `10`, le mode exécute donc **32 CHD ciblées** : les quatre valeurs de `min_docfreq` sont combinées avec les huit plafonds `k max` de `3` à `10`.

Le `mincl` et le type de classification terminale restent ceux choisis dans les paramètres CHD ; ils ne font pas partie de cette grille de simulation.

## Nombre de classes

L'utilisateur ne choisit pas le nombre final de classes.

Il fixe seulement :

- `k_iramuteq` : la borne maximale des classes explorées, comprise entre `3` et `10`

Ensuite, l'application relance une CHD pour chaque valeur de `k max` comprise entre `3` et cette borne, et compare les solutions réalisables ayant au moins trois classes.

Chaque solution est reconstruite avec les mêmes règles terminales que le mode manuel : `mincl` et le type de classification choisi. Le seuil `mincl` est conservé depuis les paramètres CHD et n'est pas une variable de recherche de ce mode.

Le résultat indique aussi la **limite CHD à reprendre en manuel**. Pour reproduire exactement la solution automatique, utilisez le bouton « Reprendre cette configuration en manuel », puis relancez l'analyse. Cette limite ne fixe pas le nombre final de classes : la CHD et `mincl` le déterminent comme d'habitude.

Le graphique AFC final est construit avec tous les termes significatifs (`p.value <= 0.05`), exactement comme dans le mode Manuel. Les termes utilisés en interne pour comparer les CHD testées restent réservés au calcul de la sélection et ne modifient pas le graphique final.

Le résultat final affiche donc :

- la configuration retenue
- le nombre de classes finales retenues
- la limite CHD à reprendre en manuel
- les variables qui ont conduit à ce résultat

## Comment la sélection est faite

Pour chaque CHD testée :

- l'application calcule les termes caractéristiques avec le `chi2` habituel
- elle conserve les termes significatifs avec `p.value <= 0.05`
- elle récupère leurs coordonnées `x, y` sur le plan AFC
- elle calcule le centre lexical de chaque classe : la moyenne des coordonnées `x, y` de ses mots significatifs
- elle calcule les distances euclidiennes entre tous les centres de classes
- elle mesure aussi la dispersion des mots autour du centre de leur classe

Pour chaque classe, l'application calcule le centre moyen de ses mots significatifs sur le plan AFC (`x`, `y`), puis compare toutes les paires de classes :

```ini
S = distance entre deux centres / somme des dispersions lexicales
```

La valeur affichée est la plus faible de ces séparations : ici, même les deux classes les plus proches sont séparées de `4,091` fois leur dispersion lexicale combinée.

Plus `S` est élevé, plus les classes sont lexicalement opposées. Ce n'est ni un pourcentage, ni une `p.value`, ni un nouveau `chi2` : c'est un indicateur relatif servant à choisir la meilleure CHD parmi les configurations testées.

Une valeur `S >= 1` indique que même la paire de classes la plus proche est séparée au moins de la somme de leurs dispersions lexicales médianes. C'est un repère de lecture, pas une condition de sélection.

Dans chaque configuration, le mode retient la solution qui maximise `S` : une solution à trois classes est donc retenue si elle est plus discriminante qu'une solution à cinq classes. En cas d'égalité de `S`, la moyenne des séparations départage les solutions ; s'il y a encore égalité, le mode retient la solution avec le moins de classes.

Toutes les configurations `min_docfreq x k max` sont ensuite comparées selon la même règle : la meilleure séparation relative AFC est toujours prioritaire.

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
