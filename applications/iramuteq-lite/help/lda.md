## Analyse LDA

LDA n’est pas un « test » statistique au sens strict, mais un modèle probabiliste de modélisation thématique, utilisé pour faire émerger des thèmes latents dans un corpus. 
Dans la littérature, il relève surtout du topic modeling, à la frontière entre text mining, analyse de corpus et textométrie.
Le LDA est une **analyse probabiliste**.
Il ne range pas chaque mot dans une seule classe fixe.
Il estime la probabilité qu'un mot soit associé à chacun des **topics** du modèle.

Autrement dit :
- un même mot peut être lié à plusieurs topics
- chaque topic possède une probabilité d'apparition propre pour ce mot
Exemple :
Si vous lancez un LDA avec **3 topics**, un même mot aura **3 probabilités** :
- une probabilité d'appartenir au topic 1
- une probabilité d'appartenir au topic 2
- une probabilité d'appartenir au topic 3

On peut se représenter cela comme une répartition probabiliste du mot dans l'ensemble des topics du modèle.

## Deux niveaux de probabilité

Dans une LDA, on obtient en même temps deux lectures probabilistes différentes.

### `P(mot | topic)`

C'est la probabilité d'un mot dans un topic.

C'est ce que vous voyez dans :
- `pyLDAvis`
- les tableaux de mots
- les nuages de mots
- la heatmap mots × topics

Autrement dit, cette probabilité sert à décrire lexicalement un topic :
- quels mots le caractérisent le plus ;
- quels mots sont plus ou moins partagés avec d'autres topics.

### `P(topic | segment)`

C'est la probabilité d'un topic pour un segment de texte.

C'est ce qui est utilisé dans l'onglet `Segments de texte`.

Autrement dit, cette probabilité sert à répondre à une autre question :
- à quel topic ce segment est-il le plus fortement rattaché ?

### Pourquoi a-t-on besoin des deux ?

Le LDA ne sert pas à faire "un calcul sur un mot isolé".

Il produit en réalité deux niveaux complémentaires :
- les mots servent à interpréter et nommer les topics ;
- les segments servent à voir comment le corpus se répartit entre ces topics.

Donc :
- `P(mot | topic)` = lecture lexicale du topic ;
- `P(topic | segment)` = lecture textuelle du corpus.

## Paramètres principaux

### Unité d'analyse

- `Segment de texte` : le corpus est découpé en segments, puis le modèle travaille sur ces segments.
- `Document` : chaque entrée commençant par `****` est traitée comme un document complet.

### Nombre de thèmes (`k`)

Nombre de topics recherchés par le modèle.

### Mots affichés par thème (`n_terms`)

Nombre de termes montrés dans les nuages et les tableaux pour chaque topic.

Effet :
- plus la valeur est grande, plus on voit de termes secondaires ;
- plus la valeur est petite, plus la lecture des thèmes est resserrée.

Recommandation de départ :
- `8` à `15`.

## Lecture des scores

Dans les tableaux LDA, deux lectures peuvent être affichées pour un mot.

### Probabilité LDA réelle

Il s'agit de la vraie probabilité `P(mot | topic)` calculée par le modèle.
Important :
- cette probabilité est répartie sur tout le vocabulaire retenu par le LDA
- elle n'est donc pas renormalisée sur les seuls mots visibles dans le tableau
- il est donc normal que les valeurs paraissent faibles, surtout si le vocabulaire est large

Exemple :
Si le vocabulaire contient plusieurs centaines de termes, un mot très caractéristique d'un topic peut très bien avoir une probabilité réelle autour de `0.01`, `0.02` ou `0.03`.

### Score relatif (mots retenus)

Le score relatif est une aide de lecture.
Il reprend les **mots affichés dans le tableau du topic**, puis **renormalise leurs poids** uniquement sur cet ensemble réduit.
Autrement dit :
- la probabilité réelle regarde la place du mot dans tout le vocabulaire du topic
- le score relatif regarde la place du mot parmi les seuls mots retenus à l'affichage

### Pourquoi certaines cases peuvent être vides dans le tableau général

Deux fichiers différents peuvent alimenter l'affichage LDA :
- `top_terms.csv`
- `topic_term_matrix.csv`

#### `top_terms.csv`

Ce fichier contient seulement une sélection des meilleurs mots retenus pour chaque topic.
Exemple :
- `Topic 1` : 8 mots retenus
- `Topic 2` : 8 mots retenus
- `Topic 3` : 8 mots retenus

Donc ce fichier ne contient pas tout le vocabulaire du modèle, seulement les mots choisis pour l'affichage.

#### `topic_term_matrix.csv`

Ce fichier contient la vraie matrice complète `mot × topic` :
- une ligne = un mot
- une colonne = un topic
- chaque case = la probabilité du mot dans ce topic

C'est ce fichier qui permet d'afficher un tableau général complet, sans ambiguïté.

#### Pourquoi des cases vides apparaissent dans la matrice

Si l'application n'a pas accès à `topic_term_matrix.csv`, elle peut reconstruire un tableau général à partir de `top_terms.csv`.

Dans ce cas :
- si un mot n'a été retenu que dans `Topic 1`
- mais pas dans la sélection visible de `Topic 2`, `Topic 3`, etc.
alors les autres colonnes peuvent apparaître vides.

Conclusion :
- `topic_term_matrix.csv` = tableau général complet
- `top_terms.csv` = tableau partiel fondé sur les meilleurs mots retenus

## Paramètres de préparation du corpus

### Taille des segments LDA

Taille minimale utilisée pour construire les segments lorsque l'unité d'analyse est `segment`.


### Segmenter à partir de la ponctuation forte

Quand cette option est activée, le découpage privilégie les séparateurs forts (`.`, `!`, `?`, etc.).


### Retirer les stopwords

Supprime les mots-outils fréquents via la liste française de `quanteda::stopwords("fr")`.


### Filtrer par catégories morphosyntaxiques

Conserve uniquement les mots appartenant aux catégories sélectionnées dans le lexique morphosyntaxique.

### Catégories à conserver

Liste des catégories morphosyntaxiques autorisées (`NOM`, `VER`, `ADJ`, etc.).


## Paramètres avancés

### Fréquence documentaire minimale (`min_df`)

Un terme doit apparaître dans au moins ce nombre d'unités d'analyse pour être retenu.


### Fréquence documentaire maximale (`max_df`)

Part maximale des unités d'analyse dans lesquelles un terme peut apparaître avant d'être exclu.

Effet :
- `0.95` : élimine seulement les termes presque omniprésents ;
- `0.85` ou `0.90` : filtrage plus fort des termes trop généraux ;
- trop bas : peut enlever des termes encore utiles.

### Nombre maximal d'itérations (`max_iter`)

Nombre maximal de passes d'optimisation du modèle LDA.
Le modèle n'est pas calculé "en une seule fois".
LDA estime de manière itérative des variables latentes :
- la distribution des thèmes dans les documents ;
- la distribution des mots dans les thèmes.

Autrement dit, `max_iter` ne sert pas à "entraîner un classifieur" sur des exemples annotés, mais à laisser à l'algorithme suffisamment de cycles pour stabiliser son estimation statistique.


### Type de n-grammes retenus (`ngram_range`)

Dans l'interface, ce paramètre est présenté sous deux choix simples :
- `Unigramme`
- `Bigramme`


## Réseau topics × mots

Le réseau topics × mots est une autre manière de lire les résultats LDA.
Il repose sur deux familles de nœuds :
- à gauche : les `topics` (`Topic 1`, `Topic 2`, etc.)
- à droite : les `mots`

Autrement dit, ce réseau relie deux types d'objets différents :
- les topics
- les mots

### Comment le lire

Une arête `topic -> mot` est tracée lorsqu'un mot est retenu comme important dans un topic.
Autrement dit :
- le topic représente un ensemble de mots probables
- le mot apparaît relié au topic s'il fait partie des mots les plus représentatifs retenus à l'affichage

### Poids visuel du lien

Le lien n'exprime pas une distance géométrique.
Son poids visuel repose sur le **score du modèle**, c'est-à-dire la probabilité `P(mot | topic)`.

Concrètement :
- plus le lien est épais et visible, plus le mot est important pour le topic
- un mot relié à plusieurs topics peut jouer un rôle de pont lexical entre ces topics

### Contrôles disponibles

La carte du réseau propose un réglage d'affichage.

#### Mots retenus par topic

Vous pouvez choisir combien de mots sont gardés pour dessiner le réseau :
- `10`
- `20`
- `30`

## Graphique pyLDAvis

Le graphique `pyLDAvis` permet d'explorer les topics de manière interactive.
Il comporte deux grandes zones :
- à gauche : la carte des topics
- à droite : les termes associés au topic sélectionné

### Partie gauche : carte des topics

Chaque cercle correspond à un topic.
- la position du cercle représente une projection des distances entre topics
- la taille du cercle représente l'importance relative du topic dans le corpus

Attention :
Les axes du graphique n'ont pas une interprétation sémantique directe.
Ils servent surtout à visualiser les proximités et les écarts entre topics.

### Partie droite : termes du topic sélectionné

Quand vous cliquez sur un topic, la partie droite affiche les mots qui lui sont associés.
Les barres signifient :
- barre bleue : fréquence globale du mot dans l'ensemble du corpus
- barre rouge : poids estimé du mot dans le topic sélectionné

Cela permet de distinguer :
- les mots fréquents dans tout le corpus
- les mots plus caractéristiques d'un topic particulier

### Curseur lambda (`λ`)

Le curseur `lambda` ne modifie pas le calcul du modèle LDA.
Il modifie seulement la manière de classer les mots affichés pour le topic sélectionné.
- `λ = 1` : on privilégie les mots les plus probables dans le topic
- `λ` plus faible : on privilégie davantage les mots les plus distinctifs
- `λ ≈ 0.6` : souvent un bon compromis entre fréquence et spécificité
