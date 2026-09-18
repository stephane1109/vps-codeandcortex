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

- `mincl (manuel)` : de `5` à `10`. Si cette option est cochée, chaque simulation utilise le mode manuel de `mincl` avec la valeur testée. Si elle n'est pas cochée, le mode `mincl` choisi dans les paramètres CHD est conservé.
- `min_docfreq` : de `2` à `5`. Si cette option n'est pas cochée, la fréquence minimale saisie dans les paramètres généraux reste fixe.
- `Nombre de classes terminales de la phase 1` : de `3` à `10`. C'est exactement le même paramètre `k_iramuteq` que dans le mode Normal. Chaque valeur est testée par une simulation ; elle ne fixe pas le nombre final de classes.

Dans ce mode, le filtrage morphosyntaxique est fixé à `NOM + VER`, avec exclusion du verbe `être`. Les formes `AUTRE_FORME` sont automatiquement conservées.

Par défaut, `min_docfreq` et le nombre de classes terminales de la phase 1 sont cochés, tandis que `mincl` reste fixe. Avec `min_docfreq = 2…5` et une phase 1 de `3…10`, cela représente **32 CHD**.

Si les trois paramètres sont cochés avec toutes leurs bornes, la grille compte `6 × 4 × 8 = 192` CHD. L'interface l'indique avant le lancement, car ce calcul peut être long sur un corpus volumineux.

## Critère de sélection

L'utilisateur choisit aussi le critère qui départage les simulations :

- `Score S lexical` : compare les centres construits à partir des mots significatifs et leurs dispersions lexicales.
- `Distance directe des classes AFC` : compare les positions réelles de `Classe 1`, `Classe 2`, etc. dans `ca$row$coord`, sur les axes 1 et 2 de l'AFC.

Les deux valeurs sont calculées et exportées. Seul le critère choisi dans l'interface sélectionne la configuration finale.

### Seuil mincl automatique

Lorsque le mode `mincl` est réglé sur `Automatique`, `mincl` ne fait pas partie des paramètres croisés. Pour chaque CHD, le moteur calcule son seuil interne à partir du nombre de segments et des classes disponibles à cette étape : `arrondi(segments / classes)` en classification simple, ou `arrondi(segments / (2 × classes))` en classification double. La valeur affichée, par exemple `90`, est donc un **seuil automatique appliqué**, et non une valeur choisie ou testée par l'utilisateur.

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
- le critère de sélection utilisé

## Comment la sélection est faite

Pour chaque CHD testée, l'application réalise une AFC classes × termes à partir des termes significatifs (`p.value <= 0.05`). Elle calcule ensuite les deux mesures ci-dessous. Le choix fait dans l'interface détermine celle qui retient la CHD.

### 1. Distance directe des classes AFC

L'AFC place directement chaque classe dans `ca$row$coord`. Pour chaque classe `i`, les coordonnées utilisées sont donc :

```ini
x_i = ca$row$coord[i, 1]
y_i = ca$row$coord[i, 2]
```

Pour toutes les paires de classes, le mode calcule la distance euclidienne :

```ini
d(i,j) = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)
```

Le score direct est la plus petite de ces distances :

```ini
D_direct = min d(i,j)
```

Cette méthode ne reconstruit aucun centre lexical : elle n'utilise ni moyenne ni médiane des mots. Une solution est meilleure lorsque même ses deux classes les plus proches restent éloignées sur le plan AFC.

### 2. Score S lexical

#### Construire un centre lexical par classe

Chaque mot significatif (`p.value <= 0.05`) d'une classe possède une position sur le plan AFC. Pour une classe `i`, l'application calcule le centre de ces positions : `C_i = (moyenne des x, moyenne des y)`.

![Des mots significatifs aux centres lexicaux sur le plan AFC](images/auto-discriminante-s-centres.svg)

Le point central ne représente donc pas un nouveau mot : c'est le centroïde lexical de la classe sur l'AFC.

#### Comparer une paire de classes

Pour chaque classe, l'application calcule le centre moyen de ses mots significatifs sur le plan AFC (`x`, `y`), puis compare toutes les paires de classes :

```ini
s(i,j) = distance entre les centres i et j / somme de leurs dispersions lexicales
```

![Distance entre deux centres AFC et dispersions lexicales](images/auto-discriminante-s-paire.svg)

La distance au numérateur est la distance euclidienne entre les deux centres. Chaque dispersion au dénominateur est la médiane des distances entre les mots significatifs de la classe et son centre. Ainsi, deux classes éloignées avec des mots bien regroupés obtiennent une valeur `s(i,j)` élevée.

#### Construire le score S

Pour chaque classe `i`, le mode repère ensuite sa classe concurrente la plus proche :

```ini
s_proche(i) = minimum des s(i,j)
```

Le score qui choisit la CHD est :

```ini
S = médiane des s_proche(i)
```

![Voisins lexicaux les plus proches et médiane qui forme le score S](images/auto-discriminante-s-robuste.svg)

Dans l'exemple du schéma, les cinq valeurs sont `2,13 ; 2,13 ; 3,72 ; 4,86 ; 7,27`. La médiane est donc la troisième valeur, `3,72`. Les deux premières valeurs sont identiques parce que les classes 1 et 2 sont mutuellement les plus proches : le même score de paire est alors lu depuis chacune des deux classes.

Il décrit donc la séparation du voisin lexical le plus proche pour une classe typique. Cette médiane évite qu'une seule paire particulièrement proche impose mécaniquement une solution à trois classes.

Les distances entre paires sont nécessaires uniquement pour trouver le voisin le plus proche de chaque classe. Elles ne sont ni affichées, ni utilisées comme un second score.

Plus `S` est élevé, plus les classes sont lexicalement opposées. Ce n'est ni un pourcentage, ni une `p.value`, ni un nouveau `chi2` : c'est un indicateur relatif servant à choisir la meilleure CHD parmi les configurations testées.

Avec le critère `Score S lexical`, le mode retient la solution qui maximise `S`. Avec le critère `Distance directe des classes AFC`, il retient celle qui maximise `D_direct`. En cas d'égalité, il retient la solution avec le moins de classes, puis celle dont la phase 1 est la plus courte.

Toutes les combinaisons des paramètres cochés sont ensuite comparées selon le critère choisi dans l'interface.

Il n'y a pas de calcul d'angle, de `theta`, de similarité cosinus, ni de pondération ajoutée.

Le `chi2` existant n'est donc pas modifié : il sert seulement à repérer les mots caractéristiques significatifs. L'AFC fournit soit les positions directes des classes, soit les coordonnées des mots nécessaires au calcul de `S`.
