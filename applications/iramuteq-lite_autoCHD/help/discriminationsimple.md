# CHD distance optimisée

Ce mode cherche **une seule configuration CHD plus discriminante**.

Il ne modifie ni la CHD, ni le calcul du `chi2`.
Il relance simplement quelques analyses ciblées du même corpus, puis retient celle où les classes s'opposent le mieux sur l'AFC.

## Principe

On peut le lire comme si un analyste refaisait plusieurs fois la même CHD avec de très légères variations, puis gardait la version où l'opposition entre classes est la plus lisible.

Le mode compare donc plusieurs résultats possibles, mais il ne renvoie **qu'un seul compromis final**.

## Paramètres à croiser

Dans le mode CHD distance optimisée, l'utilisateur coche les paramètres qu'il veut faire varier. Les paramètres non cochés restent fixes pendant toutes les simulations.
Cette boîte n'apparaît que lorsque « CHD distance optimisée » est sélectionné dans « Nombre de classes ».

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

Seul le critère choisi dans l'interface est calculé et exporté pour chaque simulation. Il sélectionne la configuration finale.

### Quel critère choisir ?

`Distance directe des classes AFC` est le critère recommandé et choisi par défaut. Il suit directement ce que montre le graphique AFC : les points `Classe 1`, `Classe 2`, etc. sont placés par l'AFC, et le mode compare exactement leurs coordonnées `x, y` dans `ca$row$coord`. Il retient la CHD où la paire de classes la plus proche est la plus éloignée. Il n'y a alors ni centre de mots, ni moyenne, ni médiane, ni similarité cosinus supplémentaire.

`Score S lexical` reste disponible comme option complémentaire si vous voulez également tenir compte de la manière dont les mots significatifs sont regroupés autour de chaque classe. Deux classes éloignées mais dont les mots sont très dispersés seront alors moins favorisées qu'avec la distance directe.

Dans les deux cas, la CHD, le `chi2` et l'AFC ne sont pas modifiés. Le score `S` ne déplace pas les points sur le graphique AFC, mais il peut retenir une autre CHD car il ajoute la compacité lexicale comme critère de comparaison. Le choix intervient seulement après chaque CHD testée, pour comparer les résultats obtenus.

### Comment l'AFC calcule la position des classes

L'AFC utilise un tableau **classes × mots** : les lignes sont les classes et les colonnes sont les mots. Chaque cellule contient le nombre d'occurrences d'un mot dans une classe.

Dans le code, ce tableau est regroupé par classe avec `quanteda::dfm_group()`, puis l'AFC est calculée par :

```r
ca <- FactoMineR::CA(tab, graph = FALSE)
```

FactoMineR compare le profil lexical de chaque classe au profil moyen du corpus, calcule les écarts selon la distance du chi2, puis réalise une décomposition en valeurs singulières. Les coordonnées AFC des classes sont alors produites dans `ca$row$coord` ; les coordonnées des mots sont produites dans `ca$col$coord`.

Dans l'application :

```r
rowcoord <- ca$row$coord   # coordonnées des classes
colcoord <- ca$col$coord   # coordonnées des mots
```

La distance directe utilise donc directement les points des classes dans `ca$row$coord`. Elle ne recalcule pas la position d'une classe à partir des mots affichés et ne modifie aucune coordonnée. Les mots (`ca$col$coord`) et les classes (`ca$row$coord`) sont deux types de points différents, placés par la même AFC.

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

Dans l'onglet AFC, la table des mots projetés affiche les coordonnées `x` et `y` de tous les mots réellement projetés sur le plan AFC de la configuration retenue. Ces coordonnées sont celles calculées par l'AFC elle-même ; un mot absent du plan ne reçoit pas de valeur artificielle. Lorsque le mode CHD distance optimisée est utilisé, la carte « Mots repères pour nommer les axes AFC » apparaît également dans cet onglet.

## Comment la sélection est faite

Pour chaque CHD testée, l'application calcule les termes caractéristiques avec le `chi2` habituel, puis réalise une AFC classes × termes à partir des termes significatifs (`p.value <= 0.05`). Elle exécute ensuite uniquement le critère choisi dans l'interface.

Avec le réglage recommandé, le flux est donc simplement :

```ini
CHD → chi2 des termes significatifs → AFC → ca$row$coord → distance euclidienne entre classes
```

### 1. Distance directe des classes AFC

L'AFC place directement chaque classe dans `ca$row$coord`. Pour chaque classe `i`, les coordonnées utilisées sont donc :

```ini
x_i = ca$row$coord[i, 1]
y_i = ca$row$coord[i, 2]
```

![Distance euclidienne entre les positions de deux classes sur le plan AFC](images/auto-discriminante-distance-directe.svg)

Pour toutes les paires de classes, le mode calcule la distance euclidienne :

$$
d(i,j) = \\sqrt{(x_i - x_j)^{2} + (y_i - y_j)^{2}}
$$

Le score direct est la plus petite de ces distances :

$$
D_{direct} = \\min_{i < j} d(i,j)
$$

Cette méthode ne reconstruit aucun centre lexical : elle n'utilise ni moyenne ni médiane des mots. Pour une CHD donnée, on calcule donc une distance pour chaque paire de classes : Classe 1–Classe 2, Classe 1–Classe 3, Classe 2–Classe 3, etc. On conserve ensuite la plus petite distance de cette liste. Elle correspond à la paire de classes la moins séparée dans cette CHD.

Le critère `D_direct` compare ensuite cette valeur minimale entre les CHD testées. La CHD retenue est celle dont la paire la moins séparée est malgré tout la plus éloignée. Autrement dit, le mode cherche à éviter qu'une seule paire de classes reste trop proche ; il ne retient pas simplement la paire la plus éloignée.

Le segment diagonal du schéma est la distance euclidienne entre les deux points de classes. Les pointillés correspondent aux deux écarts qui la composent : la différence horizontale entre leurs coordonnées `x` et la différence verticale entre leurs coordonnées `y`.

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
s_proche(i) = min_{j ≠ i} s(i,j)
```

Le score qui choisit la CHD est :

```ini
S = médiane_i(s_proche(i))
```

![Voisins lexicaux les plus proches et médiane qui forme le score S](images/auto-discriminante-s-robuste.svg)

Dans l'exemple du schéma, les cinq valeurs sont `2,13 ; 2,13 ; 3,72 ; 4,86 ; 7,27`. La médiane est donc la troisième valeur, `3,72`. Les deux premières valeurs sont identiques parce que les classes 1 et 2 sont mutuellement les plus proches : le même score de paire est alors lu depuis chacune des deux classes.

`S` n'est donc **pas** la plus faible séparation parmi toutes les paires de classes. Le minimum intervient d'abord séparément pour chaque classe, afin de trouver son voisin lexical le plus proche ; le résultat final est ensuite la médiane de ces valeurs. Une paire n'influence `S` que si elle est le voisin lexical le plus proche d'une ou de deux classes : son influence dépend donc de l'ensemble des voisins les plus proches, et `S` n'est jamais défini comme le minimum global.

Les distances entre paires sont nécessaires uniquement pour trouver le voisin le plus proche de chaque classe. Elles ne sont ni affichées, ni utilisées comme un second score.

À ne pas confondre : `D_direct` est le **minimum global** des distances euclidiennes entre toutes les paires de classes AFC ; `S` est la **médiane des minima par classe** entre centres lexicaux. Ce sont deux critères différents.

Plus `S` est élevé, plus les classes sont lexicalement opposées. Ce n'est ni un pourcentage, ni une `p.value`, ni un nouveau `chi2` : c'est un indicateur relatif servant à choisir la meilleure CHD parmi les configurations testées.

Avec le critère `Score S lexical`, le mode retient la solution qui maximise `S`. Avec le critère `Distance directe des classes AFC`, il retient celle qui maximise `D_direct`. En cas d'égalité, il retient la solution avec le moins de classes, puis celle dont la phase 1 est la plus courte.

Toutes les combinaisons des paramètres cochés sont ensuite comparées selon le critère choisi dans l'interface.

Avec le critère direct, il n'y a pas de calcul d'angle, de `theta`, de similarité cosinus, de moyenne, de médiane ou de pondération ajoutée.

Le `chi2` existant n'est donc pas modifié : il sert seulement à repérer les mots caractéristiques significatifs. L'AFC fournit soit les positions directes des classes, soit les coordonnées des mots nécessaires au calcul de `S`.

## Mots repères pour nommer les axes AFC

Dans le résultat de la configuration retenue, l'application affiche jusqu'à trois mots repères par classe. Ce sont des termes caractéristiques significatifs (`p.value <= 0.05`) présents sur l'AFC finale.

Ces mêmes termes sont ajoutés au graphique AFC final, même s'ils ne font pas partie des 120 termes les plus fréquents normalement affichés. Chaque ligne du tableau correspond donc à une étiquette visible sur ce graphique.

Pour chaque terme, les coordonnées `x` et `y` sont celles du graphique AFC. Le classement utilise `max(|x|, |y|)` : un mot très éloigné de l'origine est plus utile pour lire et nommer un axe. L'interface indique aussi son axe dominant et son pôle `+` ou `-`.

Une coordonnée AFC n'est pas limitée à `1`. L'application ne recherche donc pas littéralement la valeur `1` : elle retient les mots ayant la plus grande valeur absolue sur l'un des deux axes. Ces mots sont des repères d'interprétation ; ils ne changent ni la CHD, ni les coordonnées AFC, ni la sélection automatique.
