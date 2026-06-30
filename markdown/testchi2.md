# Test du chi carré d'indépendance

Le test du chi carré d'indépendance permet de vérifier si deux variables qualitatives (catégorielles) sont indépendantes dans un tableau de contingence.

## Hypothèses
- **H0 (indépendance)** : la distribution des fréquences d'une variable est identique quel que soit le niveau de l'autre variable.
- **H1 (dépendance)** : la distribution diffère selon les niveaux de l'autre variable.

## Conditions d'application
- Observations indépendantes.
- Effectifs attendus raisonnables (règle fréquente : au moins 5 dans la majorité des cellules). Si ce n'est pas respecté, préférer des regroupements de modalités ou un test exact.

## Calculs principaux
1. Calculer les effectifs attendus à partir des marges du tableau.
2. Calculer la statistique :
   \[
   \chi^2 = \sum_{i,j} \frac{(O_{ij} - E_{ij})^2}{E_{ij}}
   \]
   où \(O_{ij}\) sont les effectifs observés et \(E_{ij}\) les effectifs attendus.
3. Les degrés de liberté sont \((lignes - 1) \times (colonnes - 1)\).
4. La p-value est obtenue à partir de la loi du \(\chi^2\) avec ces degrés de liberté.

## Interprétation
- **p-value < seuil (ex. 0,05)** : rejet de H0, association statistiquement significative entre les variables.
- **p-value ≥ seuil** : on ne rejette pas H0, pas de preuve d'association.

> La p-value mesure la probabilité d'observer une statistique aussi extrême si les variables étaient indépendantes. Elle ne donne pas la force du lien.

# V de Cramér

Le V de Cramér mesure l'intensité de l'association entre deux variables qualitatives, indépendamment de la taille de l'échantillon.

\[
V = \sqrt{\frac{\chi^2}{N \times (\min(lignes, colonnes) - 1)}}
\]

- \(N\) est le nombre total d'observations.
- Les valeurs vont de 0 (aucune association) à 1 (association parfaite).

## Pourquoi combiner p-value et V de Cramér ?
- La p-value dit si l'association est **statistiquement** détectable.
- Le V de Cramér dit si l'association est **forte ou faible**. Une p-value significative avec un V faible indique une association statistiquement significative mais peu intense.

## Référentiel indicatif pour le V de Cramér
Les seuils ci-dessous sont des repères usuels (ils peuvent varier selon la discipline) :

| V de Cramér | Interprétation indicative |
|-------------|---------------------------|
| < 0,10      | Négligeable / très faible |
| 0,10–0,30   | Faible                    |
| 0,30–0,50   | Modérée                   |
| > 0,50      | Forte                     |

> Pour les tables fortement asymétriques ou des échantillons très grands, interpréter ces seuils avec prudence et compléter par une analyse de contexte (taille des effectifs, pertinence substantielle).

# Synthèse d'utilisation
1. Vérifier les conditions (effectifs attendus, échantillon, plan d'échantillonnage).
2. Calculer le test du chi carré et la p-value.
3. Interpréter la p-value (significativité statistique) puis le V de Cramér (force de l'association).
4. Présenter les deux informations pour distinguer « significatif » (détection) et « fort/faible » (intensité).
