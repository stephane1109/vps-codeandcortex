# Auto CHD

## Objectif

Le mode **Auto CHD** ajoute une couche d'évaluation automatique du nombre de classes à la CHD existante d'iRAMUTEQ-Lite.

- Le calcul CHD historique n'est pas modifié.
- Le calcul du `χ²` existant n'est pas remplacé.
- Le mode **Manuel** reste disponible et conserve son comportement actuel.

En pratique, le mode auto ne change pas l'algorithme de partitionnement. Il réutilise les partitions déjà produites par la CHD, puis compare leur qualité structurelle.

## Principe général

Le flux de calcul est le suivant :

1. Le corpus est segmenté et prétraité avec les options habituelles.
2. La CHD est lancée normalement jusqu'à une borne maximale `k`.
3. Les partitions successives `P2`, `P3`, `P4`, ..., `Pk` sont récupérées.
4. Chaque partition est évaluée avec le vecteur `X(P) = (H, D, L)`.
5. Un score global `B` est calculé pour chaque partition.
6. La partition retenue est celle qui maximise `B`.

Formules utilisées :

- `X(Pk) = (H, D, L)`
- `B(Pk) = (H + D + L) / 3`
- `Gk = B(Pk) - B(Pk-1)`

Le score `G` est un indicateur complémentaire. Il sert à lire le gain entre deux partitions successives, mais il n'entre pas dans le calcul initial de `B`.

## Différence entre Manuel et Automatique

- **Mode Manuel** : l'utilisateur choisit directement le nombre de classes avant l'analyse. La sortie finale correspond à ce réglage.
- **Mode Automatique** : l'utilisateur choisit seulement un **nombre maximal de classes à explorer**. La CHD produit alors les partitions successives disponibles, qui sont ensuite comparées automatiquement.

En mode auto, la classe finale n'est donc pas définie par `mincl`, mais par la partition `Pk` retenue après évaluation.

## Détail des scores

### `H` : homogénéité interne

`H` mesure la cohérence lexicale interne des classes.

- Pour chaque classe, on construit un profil lexical moyen.
- Chaque segment est comparé à ce profil moyen.
- La similarité utilisée est une similarité cosinus sur une matrice binaire segment x termes.
- On calcule ensuite une moyenne par classe.
- La valeur finale `H` est la moyenne non pondérée des classes.

Plus `H` est élevé, plus les segments d'une même classe se ressemblent lexicalement.

### `D` : distinction entre classes

`D` mesure la séparation minimale entre les classes.

- Pour chaque classe, on construit un profil lexical global.
- On calcule ensuite la divergence de Jensen-Shannon entre toutes les paires de classes.
- On retient la plus petite distance observée.

Formellement :

- `D = min JS(Ci, Cj)`

Plus `D` est élevé, plus la séparation minimale entre classes est bonne. Une valeur faible indique que deux classes sont trop proches lexicalement.

### `L` : diffusion lexicale

`L` vérifie que l'identité lexicale d'une classe est bien répartie dans ses segments.

- Les formes caractéristiques sont celles déjà identifiées par la CHD via le `χ²`.
- Pour chaque classe, on conserve les formes à `χ²` positif et avec `p <= seuil`.
- On retient les formes les plus caractéristiques.
- Pour chacune, on utilise `docprop`, c'est-à-dire la proportion de segments de la classe contenant cette forme.
- On calcule la médiane par classe, puis on retient la plus petite médiane entre les classes.

Formellement :

- `L = min(L1, ..., Lk)`

Plus `L` est élevé, plus les formes caractéristiques d'une classe sont diffusées dans ses segments, au lieu d'être portées par quelques segments atypiques.

## Score global `B`

Le score structurel est une moyenne simple des trois composantes :

- `B = (H + D + L) / 3`

Dans cette première version :

- il n'y a pas de pondération ;
- `H`, `D` et `L` contribuent à parts égales ;
- les scores sont bornés entre `0` et `1`.

La partition automatique retenue est :

- `P* = argmax B(Pk)`

## Paramètres utilisés

### Paramètres visibles côté interface

- **`iramuteq_classes_mode`** :
  - `manuel` : comportement historique ;
  - `auto` : active l'évaluation automatique des partitions.

- **`k_iramuteq`** :
  - en mode manuel : nombre de classes demandé ;
  - en mode auto : nombre maximal de classes à explorer.

- **`iramuteq_stats_mode`** :
  - mode de calcul des statistiques CHD utilisées pour les formes caractéristiques ;
  - ce paramètre intervient notamment dans le calcul de `L`.

- **`iramuteq_max_formes`** :
  - limite le nombre de formes conservées pour la CHD ;
  - influe donc indirectement sur les partitions et sur les scores auto.

- **`segment_size`**, **`classificationMode`**, **`rst1`**, **`rst2`** :
  - ces paramètres déterminent la segmentation ;
  - ils influencent directement la structure des segments et donc la qualité des partitions évaluées.

- **`min_docfreq`** :
  - filtre les termes trop rares avant la CHD ;
  - modifie le vocabulaire effectivement analysé.

- **Options de nettoyage et de dictionnaire** :
  - suppression de ponctuation ;
  - suppression des chiffres ;
  - traitement des apostrophes ;
  - remplacement des tirets ;
  - retrait des stopwords ;
  - lemmatisation ;
  - dictionnaire d'expressions ;
  - filtrage morphosyntaxique.

Toutes ces options agissent en amont et modifient le corpus utilisé par la CHD et par Auto CHD.

### Paramètres internes du mode auto

Les paramètres suivants sont actuellement définis dans le code :

- **`auto_top_n_diffusion = 20`** :
  - nombre maximal de formes caractéristiques retenues par classe pour le calcul de `L`.

- **`auto_p_seuil = 0.05`** :
  - seuil de significativité utilisé pour filtrer les formes caractéristiques dans le calcul de `L`.

Ces paramètres ne changent pas le calcul de la CHD elle-même. Ils servent uniquement à l'évaluation automatique des partitions.

## Paramètres non utilisés pour choisir la partition auto

- **`mincl`** :
  - reste utile en mode manuel ;
  - n'est pas utilisé pour sélectionner la partition finale en mode auto.

Le mode auto choisit directement une partition `Pk` parmi les partitions produites par la CHD.

## Gestion des limites du corpus

Sur certains corpus, la CHD ne peut pas produire autant de partitions que demandé.

Dans ce cas :

- le mode **Automatique** réduit la borne demandée jusqu'au plus grand `k` réellement exploitable ;
- cette réduction est signalée dans les logs et dans le résumé exporté ;
- le mode **Manuel** conserve son comportement actuel, y compris si le `k` demandé est trop élevé pour le corpus.

Exemple :

- si l'utilisateur demande `k = 10` en mode auto ;
- mais que la CHD ne peut calculer proprement que jusqu'à `k = 6` ;
- alors Auto CHD teste `P2` à `P6`, puis choisit la meilleure partition parmi celles-ci.

## Sorties produites en mode auto

Le mode auto ajoute des sorties spécifiques :

- le nombre de classes retenu automatiquement ;
- les valeurs `H`, `D`, `L`, `B` et `G` pour chaque partition testée ;
- un graphique avec le nombre de classes en abscisse et `B` en ordonnée.

Fichiers exportés :

- `auto_chd_metrics.csv` : tableau des partitions testées ;
- `auto_chd_summary.json` : résumé structuré de la sélection ;
- `auto_chd_b_score.png` : courbe du score `B`.

## Lecture des résultats

- Une valeur `B` élevée indique un bon compromis entre cohérence interne, séparation minimale et diffusion lexicale.
- Une valeur `G` positive indique qu'ajouter une classe améliore la structure par rapport à la partition précédente.
- Une valeur `G` faible ou négative suggère qu'une classe supplémentaire n'apporte pas de gain structurel clair.
- Une petite classe n'est pas rejetée automatiquement sur sa seule taille : le critère `L` vérifie surtout la diffusion de son identité lexicale.

## Résumé

Le mode Auto CHD est une surcouche d'aide à la décision.

- Il ne remplace pas la CHD historique.
- Il n'altère pas le calcul du `χ²`.
- Il compare les partitions successives produites par la CHD.
- Il choisit automatiquement la partition qui maximise le score `B`.
- Il conserve le mode manuel inchangé.
