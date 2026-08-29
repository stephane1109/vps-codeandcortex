# Auto discriminante

## Objectif

Le mode **Auto discriminante** ne cherche pas seulement le meilleur nombre de classes pour une CHD donnee.
Il cherche la **meilleure combinaison de pretraitements discriminants**, puis, a l'interieur de chaque combinaison, il laisse **Auto CHD** choisir la meilleure partition `P2...Pk`.

Autrement dit :

`Corpus -> grille de configurations -> Auto CHD par configuration -> score discriminant -> meilleure combinaison`

Ce mode est utile quand on veut obtenir des classes :

- plus opposees lexicalement ;
- mieux separees ;
- moins desequilibrees ;
- plus proches d'une logique de "centroides bien distincts".

## Idee generale

On peut se representer ce mode comme un **moteur d'echecs** qui compare plusieurs suites de coups avant de retenir la position la plus forte.

- une configuration de pretraitement = une suite de coups possible ;
- chaque configuration produit une CHD differente ;
- pour chaque CHD, Auto CHD compare `P2`, `P3`, `P4`... jusqu'a `Pk` ;
- le mode retient ensuite la combinaison qui donne la structure la plus discriminante.

On peut aussi utiliser une **metaphore de perceptron** :

- ce n'est pas un vrai perceptron au sens technique ;
- c'est une image pedagogique ;
- le systeme "passe en revue" plusieurs activations possibles du corpus ;
- puis il garde la combinaison qui separe le mieux les classes dans l'espace lexical.

## Profils d'exploration

Le mode propose maintenant trois niveaux d'exploration pour eviter des temps de calcul inutilement longs.

### `Rapide`

Ce profil teste :

- tous les profils morphosyntaxiques ;
- `stopwords` : `oui/non` ;
- `chiffres` : `oui/non` ;
- `min_docfreq` : `1`, `2`, `3` et la valeur courante si elle est differente.

En revanche, il **garde vos reglages courants** pour :

- la lemmatisation ;
- la ponctuation.

Il est utile pour un premier balayage quand vous cherchez vite des classes opposees.

### `Equilibree`

Ce profil teste :

- tous les profils morphosyntaxiques ;
- la lemmatisation : `oui/non` ;
- `stopwords` : `oui/non` ;
- `chiffres` : `oui/non` ;
- `min_docfreq` : `1`, `2`, `3` et la valeur courante si elle est differente.

En revanche, il **garde votre reglage courant** pour :

- la ponctuation.

C'est le meilleur compromis entre finesse et temps de calcul. C'est donc le profil recommande.

### `Complete`

Ce profil teste exhaustivement toute la grille discriminante, y compris la ponctuation.

## Ce qui est teste
Selon le profil choisi, le mode explore tout ou partie de la **grille discriminante** suivante :

- profils morphosyntaxiques : `sans morpho`, `NOM`, `NOM+VER`, `NOM+ADJ+VER`
- inclusion de `AUTRE_FORME` quand le filtrage morpho est actif
- exclusion optionnelle de `etre` quand les verbes sont conserves
- lemmatisation `lexique_utiliser_lemmes` : `oui/non`
- retrait des stopwords : `oui/non`
- suppression de la ponctuation : `oui/non`
- suppression des chiffres : `oui/non`
- `min_docfreq` : `1`, `2`, `3` et la valeur courante si elle est differente

## Ce qui reste fixe

Pour garder un temps de calcul encore exploitable, les parametres structurels de la CHD restent ceux choisis par l'utilisateur :

- segmentation (`segment_size`, `rst1`, `rst2`)
- type de classification terminale
- methode SVD
- nombre maximal de formes
- autres options qui ne servent pas directement a la discrimination lexicale

Le mode **n'explore donc pas toutes les options de l'application sans limite**.
Il explore, selon le profil choisi, tout ou partie de la **grille discriminante utile**.

## Etape 1 : Auto CHD dans chaque configuration

Pour chaque configuration candidate, l'application lance une CHD jusqu'a la borne `k` demandee.
Elle conserve alors les partitions possibles :

- `P2`
- `P3`
- `P4`
- ...
- `Pk`

Puis elle calcule pour chaque partition :

- `H` = homogeneite interne
- `D` = distinction minimale entre classes
- `L` = diffusion lexicale
- `B` = score structurel

Formules :

- `B = (H + D + L) / 3`
- `P* = argmax B(Pk)`

La meilleure partition de la configuration est donc d'abord choisie par **Auto CHD**.

## Etape 2 : score discriminant entre configurations

Une fois la meilleure partition de chaque configuration obtenue, le mode Auto discriminante compare les configurations entre elles avec trois composantes :

- `B` : qualite structurelle globale de la partition retenue
- `D` : distance minimale entre deux classes
- `E` : equilibre des classes

### `H` : homogeneite interne

`H` mesure a quel point les segments d'une meme classe se ressemblent lexicalement.

- pour chaque classe, on construit un profil lexical moyen ;
- chaque segment est compare a ce profil ;
- on calcule ensuite une moyenne par classe ;
- la valeur finale est la moyenne non ponderee des classes.

Plus `H` est eleve, plus chaque classe est coherent de l'interieur.

### `D` : distinction entre classes

`D` mesure la separation minimale entre les classes.

- on construit le profil lexical de chaque classe ;
- on calcule la divergence de Jensen-Shannon entre toutes les paires ;
- on retient la plus petite distance.

Formule :

- `D = min JS(Ci, Cj)`

Plus `D` est eleve, plus les classes s'opposent nettement.

### `L` : diffusion lexicale

`L` verifie que l'identite lexicale d'une classe ne repose pas sur quelques segments isoles.

- on repart des formes caracteristiques deja calculees avec le `chi2` de la CHD ;
- on garde les formes caracteristiques les plus fortes ;
- on regarde dans combien de segments de la classe elles apparaissent ;
- on prend une mediane par classe ;
- puis le minimum entre classes.

Formule :

- `L = min(L1, ..., Lk)`

Plus `L` est eleve, plus les formes caracteristiques sont vraiment diffusees dans la classe.

### `B` : score structurel

`B` est le compromis de base entre :

- coherence interne (`H`)
- separation (`D`)
- diffusion (`L`)

Formule :

- `B = (H + D + L) / 3`

### `E` : equilibre des classes

`E` mesure si la partition retenue evite un desequilibre excessif.

- il est calcule a partir de l'entropie normalisee des effectifs de classes ;
- il vaut `1` quand les classes sont relativement equilibrees ;
- il baisse quand une partition est ecrasee par une ou deux classes dominantes.

`E` n'interdit pas les petites classes, mais il limite les faux bons resultats bases sur une separation forte avec des classes tres desequilibrees.

### `S` : score discriminant final

Le score final du mode Auto discriminante est :

- `S = (B * D * E)^(1/3)`

Cette moyenne geometrique est volontairement stricte :

- si la structure est bonne mais que les classes sont peu opposees, `S` baisse ;
- si la distinction est forte mais que les classes sont trop desequilibrees, `S` baisse ;
- si une configuration est bonne partout, `S` monte.

Le mode retient donc :

- la configuration qui maximise `S`

## Role du `chi2`

Oui, le `chi2` existant de la CHD est bien pris en compte.

Il intervient dans `L` :

- les formes caracteristiques sont celles deja identifiees par la CHD ;
- Auto discriminante ne remplace pas ce calcul ;
- il s'appuie dessus pour verifier la diffusion des formes dans chaque classe.

## Lecture pratique des sorties

La sortie du mode fournit :

- la configuration retenue
- le nombre de classes retenu dans cette configuration
- `H`, `D`, `L`, `B`, `E`, `S`
- le tableau de toutes les configurations testees
- un graphique des meilleurs scores discriminants

En pratique :

- si vous cherchez surtout la meilleure structure interne, utilisez **Auto CHD**
- si vous cherchez les classes qui **s'opposent le mieux**, utilisez **Auto discriminante**

## Point d'attention

Ce mode peut etre nettement plus long que le mode Auto CHD classique, surtout sur les gros corpus.

Il faut le voir comme une **recherche sur une grille discriminante**, pas comme un simple changement de `k`.

Si le corpus est volumineux :

- commencez par `Rapide` ;
- passez a `Equilibree` si vous voulez affiner ;
- gardez `Complete` pour les verifications finales ou les corpus courts.
