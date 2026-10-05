# Distance intertextuelle de Labbé

Cette analyse compare le vocabulaire de plusieurs textes ou modalités à partir de la matrice lexicale déjà produite par la CHD. Elle ne modifie ni la CHD, ni les lemmes, ni les catégories morphosyntaxiques retenues.

## Textes comparés

L'utilisateur choisit :

- les classes CHD ;
- ou une variable étoilée, dont chaque modalité devient un texte agrégé.

Par exemple, avec `*journal`, toutes les UCE de chaque journal sont regroupées avant la comparaison.

## Calcul

Pour comparer deux textes de longueurs différentes :

1. le texte le plus long est ramené à la taille du plus court ;
2. la fréquence de chaque forme du grand texte est multipliée par le coefficient `U = N petit / N grand` ;
3. les écarts absolus entre les fréquences des deux textes sont additionnés ;
4. cette somme est normalisée pour produire une distance comprise entre `0` et `1`.

Sous une forme simplifiée, pour le petit texte `A` et le grand texte réduit `B'` :

```text
D(A,B) = somme |fA - fB'| / (longueur A + longueur retenue de B')
```

Le vocabulaire réduit contient toutes les formes présentes dans le petit texte, ainsi que les formes du grand texte dont la fréquence ramenée à la petite taille atteint au moins `1`.

Une distance proche de `0` correspond à des profils lexicaux proches. Une distance plus élevée correspond à des profils plus différents.

La fréquence minimale des formes filtre le vocabulaire avant les comparaisons. La valeur `1` conserve toutes les formes présentes dans la matrice finale de la CHD.

## Résultats

L'analyse produit :

- la matrice symétrique complète des distances ;
- le détail de chaque comparaison par paire ;
- un dendrogramme Ward.D2 ;
- une carte colorée des distances ;
- la configuration utilisée.

## Précautions

Les petits textes et les textes de tailles très différentes demandent une interprétation prudente. IRAMUTEQ Lab signale les modalités de moins de 1 000 occurrences et les paires dont le rapport de tailles est inférieur à `1:10`, sans empêcher le calcul.

Références : [Cyril Labbé et Dominique Labbé, « La distance intertextuelle », *Corpus*, 2, 2003](https://journals.openedition.org/corpus/31) ; [script GNU/GPL de Pierre Ratinaud fourni avec IRaMuTeQ](https://gitlab.huma-num.fr/pratinaud/iramuteq/-/blob/master/Rscripts/distance-labbe.R). L'implémentation de Lab conserve cette méthode, avec une matrice complète et un traitement symétrique du seuil de fréquence attendue.
