# Distance intertextuelle de Labbé

Cette analyse compare directement le vocabulaire de plusieurs textes constitués par les modalités d’une variable étoilée. Elle est indépendante de la CHD.

## Textes comparés

L’utilisateur choisit une variable étoilée du corpus. Chaque modalité de cette variable devient un texte agrégé.

Par exemple, avec `*journal`, toutes les UCE de chaque journal sont regroupées avant la comparaison.

Avant le calcul, l’utilisateur choisit explicitement :

- le dictionnaire utilisé ;
- l’activation ou non de la lemmatisation.

La table est construite avec le profil d’indexation du corpus IRaMuTeQ : dictionnaire d’expressions, apostrophes et tirets traités comme séparateurs, ponctuation retirée, puis conservation des formes atteignant la fréquence interne de `10`. Cette valeur est fixe pour reproduire le résultat du logiciel et n’est pas présentée comme un paramètre supplémentaire. Aucun filtre morphosyntaxique de la CHD n’est ajouté et les réglages de la dernière CHD ne sont pas repris silencieusement.

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

La fonction conserve le traitement interne du script fourni : après réduction du texte le plus long, certaines contributions sont retenues autour d’une fréquence ramenée à `1`. Ce traitement appartient à `compute.labbe` et n’est pas un paramètre demandé à l’utilisateur.

Une distance proche de `0` correspond à des profils lexicaux proches. Une distance plus élevée correspond à des profils plus différents.

La valeur ne mesure ni un pourcentage ni une significativité statistique. Elle résume l'écart lexical entre deux modalités après avoir ramené leurs textes à une longueur comparable. Elle s'interprète surtout relativement aux autres distances calculées dans le même corpus : la plus grande valeur désigne les deux modalités dont les profils lexicaux sont les plus différents.

## Résultats

L'analyse produit :

- la matrice symétrique complète des distances ;
- la table lexicale exacte fournie à `compute.labbe`, afin de pouvoir contrôler les effectifs ;
- le détail de chaque comparaison par paire ;
- un arbre non enraciné regroupant les profils lexicaux avec Ward.D2 ; les valeurs `W` sont des longueurs de branches de ce regroupement et non des distances brutes entre deux modalités ;
- une carte colorée contenant les distances brutes de Labbé ; pour les matrices jusqu'à 15 modalités, chaque valeur est écrite dans sa case et la paire maximale est encadrée en orange ;
- la configuration utilisée.

Dans le tableau des comparaisons, la paire ayant la distance la plus élevée est affichée en bleu. Dans la matrice complète, les deux cellules symétriques correspondant à cette même paire sont également mises en évidence. Une ligne et une colonne représentent chacune une modalité de la variable étoilée ; leur intersection contient leur distance de Labbé. La diagonale vaut toujours `0`, puisqu'une modalité y est comparée avec elle-même.

Le tableau affiché conserve les informations nécessaires à la lecture : les deux modalités comparées, leur distance, leur nombre de mots et le nombre de formes effectivement comparées. Le rapport des tailles et le coefficient de réduction restent disponibles dans le fichier CSV exporté pour la traçabilité technique, mais ne sont pas affichés dans l'interface car ils décrivent la même étape de mise à l'échelle du texte le plus long.

Références : [Cyril Labbé et Dominique Labbé, « La distance intertextuelle », *Corpus*, 2, 2003](https://journals.openedition.org/corpus/31) ; [script GNU/GPL de Pierre Ratinaud fourni avec IRaMuTeQ](https://gitlab.huma-num.fr/pratinaud/iramuteq/-/blob/master/Rscripts/distance-labbe.R). Le calcul de chaque paire reproduit la fonction officielle `compute.labbe`. La matrice est complétée symétriquement pour présenter les distances sous forme de tableau et de graphiques.
