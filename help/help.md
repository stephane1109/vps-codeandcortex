## www.codeandcortex.fr
<small>IRAMUTEQ LITE - Stéphane Meurisse - v0_3beta - 09-04-2026</small>

- <a href="https://www.codeandcortex.fr" target="_blank" rel="noopener noreferrer">codeandcortex.fr</a>
- <a href="https://www.codeandcortex.fr/comprendre-chd-methode-reinert/" target="_blank" rel="noopener noreferrer">Comprendre la CHD</a>


## IRaMuTeQ
IRaMuTeQ, développé par Pierre Ratinaud, est un logiciel libre devenu une référence pour l’analyse textuelle en sciences humaines et sociales. Il met en œuvre la méthode de Reinert (CHD), l’AFC, ainsi que l’analyse de similitudes de Vergès, et propose de nombreux traitements complémentaires pour explorer la structure lexicale d’un corpus. Un atout est son dictionnaire de lemmes, plus précis et performant que beaucoup d’alternatives, ce qui améliore la stabilité des classes. Le dictionnaire utilisé dans ce script est celui de **IRaMuTeQ - lexique_fr** (uniquement fr) ainsi que le dictionnaire des expressions.

- <a href="https://pratinaud.gitpages.huma-num.fr/iramuteq-website/" target="_blank" rel="noopener noreferrer">IRaMuTeQ</a>


## Méthode Reinert - CHD

La méthode de Reinert est une approche statistique d’analyse lexicale conçue pour dégager des « mondes lexicaux » dans un corpus. 
L’idée est de repérer des ensembles de segments de texte qui partagent des vocabulaires proches. 

La CHD, pour "Classification Hiérarchique Descendante", est l’algorithme de partitionnement associé à cette méthode. 
Il procède par divisions successives : on prend l’ensemble des segments, puis on le coupe en deux groupes maximisant leur différenciation lexicale. 
Ensuite, chaque groupe peut être à nouveau subdivisé, et ainsi de suite, jusqu’à obtenir un nombre de classes jugé pertinent ou une limite imposée par les paramètres.

## Tests et développement

Le script a d'abord été développé sur un petit corpus Europresse, puis mis à l'épreuve sur des corpus plus volumineux (jusqu'à environ 1000 articles).
Le principal retour d'expérience est le suivant : plus le corpus est propre, plus l'exécution est rapide et plus les résultats sont stables.
Un point important peut déjà être signalé : un corpus contenant des volumes de texte mixtes en français et en anglais, même avec seulement quelques paragraphes dans une autre langue, fait échouer la CHD ou produire des résultats incohérents.
À titre indicatif, une analyse sur un corpus d'articles de presse de 775 articles prend, avec l'option « catégories morphosyntaxiques » activée et le dictionnaire d'expressions activé, environ 14 minutes : le temps de boire un bon café.
Les options d'activation des dictionnaires sont coûteuses en calcul, mais la barre de progression vous donne un repère pendant le traitement.

## Onglet "Annotation"

En plus du dictionnaire d'expressions d'origine, vous pouvez créer vos propres annotations dans l'onglet **Annotation**.
- Ces annotations personnelles permettent d'ajouter ou de normaliser des expressions selon vos besoins.
- Elles sont enregistrées dans votre dictionnaire utilisateur `add_expression_fr.csv`.
- En pratique, vous pouvez donc conserver le dictionnaire d'origine intact, tout en construisant votre propre couche d'annotations adaptée à votre corpus.


## Quelques defintions


### DFM (définition et construction)
- **DFM (Document-Feature Matrix)** : matrice où chaque ligne = un segment, chaque colonne = un terme, chaque cellule = nombre d’occurrences du terme dans le segment.
- Construction : segmentation → tokenisation/nettoyage → retrait optionnel des stopwords → filtrage `min_docfreq` (`dfm_trim`) pour retirer les termes.

### Segments vides (dans la DFM)
- Un **segment vide** est un segment dont la somme de ligne vaut 0 dans la DFM.
- En clair : c'est un segment de texte pour lequel **aucun terme ne survit** après les filtres (stopwords, fréquence minimale `min_docfreq`, nettoyage, etc.).
- Ces segments sont supprimés avant la CHD.

### Définitions IRaMuTeQ des effectifs (table CHD)
- **Eff. s.t. (effectif des segments de texte)** : nombre de segments de texte de la classe qui contiennent au moins une fois la forme.
- **Eff. total (effectif total des segments de texte)** : nombre de segments de texte dans tout le corpus classé qui contiennent au moins une fois la forme.

### Segments non classés (Classe 0 / NA)
- Un **segment non classé** est un segment qui n'est pas affecté à une classe terminale à l'issue de la CHD (valeur de classe `0` ou `NA`).
- Dans l'application, ces segments sont **exclus des calculs CHD/AFC finaux** et des statistiques de classes.
- Conséquence pratique : les effectifs `Eff. s.t.` et `Eff. total` sont calculés sur le **corpus classé** (segments avec classe `> 0`) et non sur l'ensemble brut des segments importés.

### Paramètres de l’analyse
- **segment_size** : taille des segments pour la segmentation (valeur UI par défaut: 40).
- **Fréquence minimale des termes (`min_docfreq`)** : valeur recommandée **3** (comme dans le logiciel). Une forme doit apparaître dans au moins 3 segments pour être conservée.
- **max_p (p-value)** + **Filtrer l'affichage par p-value** : ce seuil filtre l'affichage des tableaux/stats/concordancier/nuages
- **top_n (wordcloud)** : nombre de termes affichés dans les nuages de mots par classe.

#### Paramètres CHD spécifiques IRaMuTeQ-lite
- **Nombre de classes terminales de la phase 1 (`k_iramuteq`)** : nombre de classes cibles pour la phase de partition.
  - **mincl (auto/manuel)** : seuil minimal d'UCE pour conserver une classe terminale (mode automatique ou valeur manuelle). Ce paramètre semble etre différent de la logique "rainette"
- **Type de classification terminale** :
  - `simple` : segmentation avec `segment_size`.
  - `double` : segmentation en deux passes avec **rst1** puis **rst2**.
- **Méthode SVD (`iramuteq_svd_method`)** : `irlba` (défaut) ou `svdR`.
- **Nombre maximum de formes analysées (`iramuteq_max_formes`)** : limite le nombre de termes conservés pour la CHD.
- **Calcul des statistiques CHD (`iramuteq_stats_mode`)** : choix du mode de calcul des stats (vectorisé/classique).

### Options de nettoyage du texte
- **Nettoyage caractères (regex)** (`nettoyage_caracteres`) : supprime les caractères non autorisés par la regex interne (ex : @).
- **Supprimer la ponctuation** (`supprimer_ponctuation`) : active `remove_punct` lors de la tokenisation quanteda. La ponctuation est retirée des tokens utilisés pour les analyses (CHD, stats).
- **Supprimer les chiffres (0-9)** (`supprimer_chiffres`) : supprime les chiffres avant tokenisation.
- **Traiter les élisions FR** (`supprimer_apostrophes`) : enlève les élisions en début de mot (`c'`, `j'`, `l'`, `m'`, `n'`, `s'`, `t'`, `d'`, `qu'`) pour ramener par ex. `c'est` vers `est`.
- **Remplacer les tirets par des espaces** (`remplacer_tirets_espaces`) : transforme `mot-compose` en `mot compose` avant tokenisation.
- **Retirer les stopwords** (`retirer_stopwords`) : enlève les mots-outils français via la liste `quanteda::stopwords("fr")`.
- **Passage en minuscules** : appliqué automatiquement avant la construction des tokens/termes (option non configurable).

#### Stopwords en mode IRaMuTeQ-lite
- En mode **IRaMuTeQ-lite**, la source de lemmatisation est forcée sur **Lexique (fr)**.
- Quand l'option **Retirer les stopwords** est activée, le filtrage se fait avec les stopwords **français de quanteda**.

#### Effet sur le concordancier HTML
- Quand **Supprimer la ponctuation** est cochée, la ponctuation est bien retirée dans les **données d’analyse**.
- Le **concordancier HTML** contient la ponctuation dans le texte affiché.

### Dictionnaire et lemmatisation (calcul IRaMuTeQ-lite)
- **Source de lemmatisation** : en mode IRaMuTeQ-lite, la source active est **Lexique (fr)**.
- **Lemmatisation via lexique_fr** (`lexique_utiliser_lemmes`) : remplace les formes par leur lemme (`forme → c_lemme`) avant la DFM.
- **Dictionnaire d'expressions** (`expression_utiliser_dictionnaire`) : applique les remplacements `dic_mot → dic_norm` en amont du pipeline (avant nettoyage, tokenisation, lemmatisation et filtrage morphosyntaxique).
- <a href="https://openlexicon.fr/" target="_blank" rel="noopener noreferrer">OpenLexicon</a>

### Filtrage morphosyntaxique
- **Filtrage morphosyntaxique** (`filtrage_morpho`) : filtre les formes selon la colonne `c_morpho` du lexique_fr.
- **Catégories conservées** (`pos_lexique_a_conserver`) : sélection des étiquettes autorisées (ex: NOM, VER, ADJ, etc...).

## Aide AFC : calcul, affichage des termes, rôle de `top_termes`

### 1/ Comment l’AFC est calculée dans le script

L’AFC classes × termes est calculée en 3 étapes :
1. Construction de la table de contingence **Classes × Termes** depuis le DFM.
2. Exécution de l’AFC avec `FactoMineR::CA(tab, graph = FALSE)`.
3. Récupération des coordonnées des classes (`rowcoord`) et des termes (`colcoord`) pour le tracé.

### 2/ Qu’est-ce que `top_termes` ?

`top_termes` est **une limite d’affichage graphique** des mots sur le plan AFC. Par défaut : `top_termes = 120`

### 3/ Le CSV contient-il seulement `top_termes` ?

Le CSV `stats_termes.csv` exporte la table `rv$afc_obj$termes_stats` (jeu complet de stats AFC disponible), sans appliquer la réduction `top_termes`.
