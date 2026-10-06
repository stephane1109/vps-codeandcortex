# Distance intertextuelle de Labbé

Cette analyse compare directement le vocabulaire de plusieurs textes constitués par les modalités d’une variable étoilée. Elle est indépendante de la CHD.

## Textes comparés

L’utilisateur choisit une variable étoilée du corpus. Chaque modalité de cette variable devient un texte agrégé.

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

La constitution du vocabulaire réduit suit les seuils appliqués par la fonction officielle `compute.labbe` d’IRaMuTeQ autour d’une fréquence ramenée à `1`.

Une distance proche de `0` correspond à des profils lexicaux proches. Une distance plus élevée correspond à des profils plus différents.

La fréquence minimale des formes filtre le vocabulaire avant les comparaisons. La valeur `1` conserve toutes les formes présentes dans la table lexicale du corpus.

## Résultats

L'analyse produit :

- la matrice symétrique complète des distances ;
- le détail de chaque comparaison par paire ;
- un arbre non enraciné, sans halos, indiquant la longueur Ward.D2 sur chaque branche qui aboutit à un texte ;
- une carte colorée des distances ;
- la configuration utilisée.

Références : [Cyril Labbé et Dominique Labbé, « La distance intertextuelle », *Corpus*, 2, 2003](https://journals.openedition.org/corpus/31) ; [script GNU/GPL de Pierre Ratinaud fourni avec IRaMuTeQ](https://gitlab.huma-num.fr/pratinaud/iramuteq/-/blob/master/Rscripts/distance-labbe.R). Le calcul de chaque paire reproduit la fonction officielle `compute.labbe`. La matrice est complétée symétriquement pour présenter les distances sous forme de tableau et de graphiques.
