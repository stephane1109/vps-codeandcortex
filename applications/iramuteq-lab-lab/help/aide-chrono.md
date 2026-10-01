# Analyse chronologique croisée

Cette analyse complémentaire étudie l’évolution des classes d’une CHD selon deux variables étoilées du même corpus.

Elle ne recalcule pas la CHD et ne modifie ni les classes, ni les χ² lexicaux des termes.

## Préparer le corpus

Chaque texte doit contenir une variable temporelle et une variable de comparaison dans son en-tête IRaMuTeQ :

```text
**** *annee_2024 *quotidien_liberation
Texte de l’article...
```

Dans cet exemple :

- `annee` est la variable temporelle ;
- `quotidien` est la variable de comparaison ;
- `2024` et `liberation` sont leurs modalités.

Chaque texte doit posséder une seule modalité pour chacune des deux variables sélectionnées.

## Calcul des pourcentages

Après la CHD, chaque UCE classée conserve les variables étoilées du texte dont elle provient.

Pour chaque période, chaque modalité de comparaison et chaque classe, l’application calcule :

```text
pourcentage = UCE de la classe / ensemble des UCE du groupe × 100
```

Le groupe correspond à un couple comme `2024 × Libération`. Cette normalisation permet de comparer des sources dont les volumes de textes sont différents.

## Test chronologique

Pour chaque modalité de comparaison, l’application croise les périodes avec les classes et calcule un test χ².

Ce χ² chronologique est différent du χ² lexical de la CHD :

- le χ² lexical relie un mot à une classe ;
- le χ² chronologique relie la répartition des classes aux périodes.

Le tableau indique également le V de Cramér, qui décrit l’intensité de cette association.

## Lire les écarts

Les résidus standardisés comparent les effectifs observés aux effectifs attendus :

- une valeur supérieure ou égale à `1,96` indique une classe surreprésentée ;
- une valeur inférieure ou égale à `-1,96` indique une classe sous-représentée ;
- une valeur comprise entre ces limites reste proche de l’effectif attendu.

Sur la carte des écarts, le bleu représente une surreprésentation et le rouge une sous-représentation.

## Précautions

Une évolution peut provenir du contenu éditorial, mais aussi d’un changement du nombre d’articles, de leur longueur ou de la composition des sources. Les tableaux d’effectifs et de pourcentages doivent donc être lus ensemble.

Lorsque plusieurs effectifs attendus sont inférieurs à `5`, le résultat du χ² doit être interprété avec prudence.

## Exports

L’analyse produit les effectifs, les pourcentages, les tests χ², les résidus, deux graphiques, la configuration utilisée et un résumé reproductible au format JSON.
