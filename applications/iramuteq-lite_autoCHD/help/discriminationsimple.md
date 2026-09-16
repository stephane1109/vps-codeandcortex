# Auto discriminante

Ce mode cherche **une seule configuration CHD plus discriminante**.

Il ne modifie ni la CHD, ni le calcul du `chi2`.
Il relance simplement quelques analyses ciblées du même corpus, puis retient celle où les classes s'opposent le mieux sur l'AFC.

## Principe

On peut le lire comme si un analyste refaisait plusieurs fois la même CHD avec de très légères variations, puis gardait la version où l'opposition entre classes est la plus lisible.

Le mode compare donc plusieurs résultats possibles, mais il ne renvoie **qu'un seul compromis final**.

## Paramètres à croiser

En mode Auto discriminante, l'utilisateur coche les paramètres qu'il veut faire varier. Les paramètres non cochés restent fixes pendant toutes les simulations.
Cette boîte n'apparaît que lorsque « Auto discriminante » est sélectionné dans « Nombre de classes ».

- `mincl (manuel)` : de `5` à `10`. Si cette option est cochée, chaque simulation utilise le mode manuel de `mincl` avec la valeur testée. Si elle n'est pas cochée, le réglage `mincl` choisi dans les paramètres CHD est conservé.
- `min_docfreq` : de `2` à `5`. Si cette option n'est pas cochée, la fréquence minimale saisie dans les paramètres généraux reste fixe.
- `Nombre de classes terminales de la phase 1` : de `3` à `10`. C'est exactement le même paramètre `k_iramuteq` que dans le mode Normal. Chaque valeur est testée par une simulation ; elle ne fixe pas le nombre final de classes.

Le filtrage morphosyntaxique reste ciblé sur `NOM + VER`, avec exclusion du verbe `être`. L'option `AUTRE_FORME` reste celle choisie par l'utilisateur.

Par défaut, `min_docfreq` et le nombre de classes terminales de la phase 1 sont cochés, tandis que `mincl` reste fixe. Avec `min_docfreq = 2…5` et une phase 1 de `3…10`, cela représente **32 CHD**.

Si les trois paramètres sont cochés avec toutes leurs bornes, la grille compte `6 × 4 × 8 = 192` CHD. L'interface l'indique avant le lancement, car ce calcul peut être long sur un corpus volumineux.

## Nombre de classes

L'utilisateur ne choisit pas le nombre final de classes.

Pour chaque valeur sélectionnée du nombre de classes terminales de la phase 1, l'application relance la même CHD, puis compare les résultats entre simulations. Le nombre de classes finalement retenu dépend donc de la CHD et des règles terminales, notamment `mincl`.

Quand `mincl` fait partie de la grille, le résultat final indique la valeur qui a contribué au meilleur compromis. Lorsqu'il reste fixe, le même réglage est conservé dans toutes les simulations.

Le résultat indique aussi le **nombre de classes terminales de la phase 1 à reprendre en mode Normal**. Pour reproduire exactement la solution automatique, utilisez le bouton « Reprendre cette configuration en mode Normal », puis relancez l'analyse. Ce paramètre ne fixe pas le nombre final de classes : la CHD et `mincl` le déterminent comme d'habitude.

Le graphique AFC final est construit avec tous les termes significatifs (`p.value <= 0.05`), exactement comme dans le mode Normal. Les termes utilisés en interne pour comparer les CHD testées restent réservés au calcul de la sélection et ne modifient pas le graphique final.

Le résultat final affiche donc :

- la configuration retenue
- le nombre de classes finales retenues
- le nombre de classes terminales de la phase 1 à reprendre en mode Normal
- les variables qui ont conduit à ce résultat

## Comment la sélection est faite

Pour chaque CHD testée :

- l'application calcule les termes caractéristiques avec le `chi2` habituel
- elle conserve les termes significatifs avec `p.value <= 0.05`
- elle récupère leurs coordonnées `x, y` sur le plan AFC
- elle calcule le centre lexical de chaque classe : la moyenne des coordonnées `x, y` de ses mots significatifs
- elle calcule les distances euclidiennes entre tous les centres de classes
- elle mesure aussi la dispersion des mots autour du centre de leur classe

### 1. Construire un centre lexical par classe

Chaque mot significatif (`p.value <= 0.05`) d'une classe possède une position sur le plan AFC. Pour une classe `i`, l'application calcule le centre de ces positions : `C_i = (moyenne des x, moyenne des y)`.

![Des mots significatifs aux centres lexicaux sur le plan AFC](images/auto-discriminante-s-centres.svg)

Le point central ne représente donc pas un nouveau mot : c'est le centroïde lexical de la classe sur l'AFC.

### 2. Comparer une paire de classes

Pour chaque classe, l'application calcule le centre moyen de ses mots significatifs sur le plan AFC (`x`, `y`), puis compare toutes les paires de classes :

```ini
s(i,j) = distance entre les centres i et j / somme de leurs dispersions lexicales
```

![Distance entre deux centres AFC et dispersions lexicales](images/auto-discriminante-s-paire.svg)

La distance au numérateur est la distance euclidienne entre les deux centres. Chaque dispersion au dénominateur est la médiane des distances entre les mots significatifs de la classe et son centre. Ainsi, deux classes éloignées avec des mots bien regroupés obtiennent une valeur `s(i,j)` élevée.

### 3. Construire le score robuste S

Pour chaque classe `i`, le mode repère ensuite sa classe concurrente la plus proche :

```ini
s_proche(i) = minimum des s(i,j)
```

Le score qui choisit la CHD est :

```ini
S_robuste = médiane des s_proche(i)
```

![Voisins lexicaux les plus proches et médiane qui forme S robuste](images/auto-discriminante-s-robuste.svg)

Il décrit donc la séparation du voisin lexical le plus proche pour une classe typique. Cette médiane évite qu'une seule paire particulièrement proche impose mécaniquement une solution à trois classes.

La **pire paire AFC** reste affichée séparément : c'est le minimum de tous les `s(i,j)`. Elle sert de garde-fou pour signaler deux classes potentiellement trop proches, sans diriger seule la sélection.

Plus `S_robuste` est élevé, plus les classes sont lexicalement opposées. Ce n'est ni un pourcentage, ni une `p.value`, ni un nouveau `chi2` : c'est un indicateur relatif servant à choisir la meilleure CHD parmi les configurations testées.

Une valeur de pire paire AFC `>= 1` indique que même la paire de classes la plus proche est séparée au moins de la somme de leurs dispersions lexicales médianes. C'est un repère de lecture, pas une condition de sélection.

Dans chaque configuration, le mode retient la solution qui maximise `S_robuste`. En cas d'égalité, la pire paire AFC la plus élevée départage les solutions ; s'il y a encore égalité, le mode retient la solution avec le moins de classes.

Toutes les combinaisons des paramètres cochés sont ensuite comparées selon la même règle : la meilleure séparation robuste AFC est toujours prioritaire.

Il n'y a pas de calcul d'angle, de `theta`, de similarité cosinus, ni de pondération ajoutée.

Le `chi2` existant n'est donc pas modifié : il sert seulement à repérer les mots caractéristiques significatifs. L'AFC sert ensuite à mesurer la distance entre les centres lexicaux des classes.

## Ce qui est affiché

Le mode affiche seulement les éléments utiles à la lecture du résultat :

- la configuration retenue
- le profil morphosyntaxique retenu
- la valeur `mincl` retenue
- la valeur `min_docfreq` retenue
- le nombre de classes retenues
- la séparation robuste AFC entre les classes
- la pire paire AFC comme garde-fou
- les effectifs des classes

Les sous-calculs internes du score ne sont pas nécessaires pour l'interprétation courante.

## À quoi sert ce mode

Ce mode sert à obtenir plus vite une CHD où les classes sont **mieux opposées lexicalement**, sans tester manuellement plusieurs réglages.

L'idée est donc :

- lancer quelques variantes utiles
- comparer leur séparation sur l'AFC
- retenir automatiquement la plus discriminante
