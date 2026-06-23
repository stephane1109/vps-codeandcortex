## Divergence de Jensen-Shannon

Ce test est proposé ici dans un cadre **expérimental** de suivi d'entretiens.  
Il peut servir à explorer une série d'entretiens cliniques, par exemple avec des patients en santé mentale, mais aussi d'autres suivis dans le temps, comme des demandeurs d'emploi engagés dans un projet.

Il ne s'agit pas d'un outil de diagnostic.  
L'intérêt est de décrire **comment le lexique se déplace d'un entretien à l'autre**.

## Deux couches possibles

L'onglet propose maintenant deux lectures distinctes :

- `Trajectoire lexicale brute`
  - JSD calculée sur les mots ou les lemmes après le prétraitement courant
  - c'est la couche la plus fidèle au discours réel

- `Trajectoire émotionnelle`
  - JSD calculée non plus sur les mots eux-mêmes, mais sur une distribution d'émotions reconnues dans le texte
  - cette lecture repose sur un lexique émotionnel optionnel :
    - `FEEL`
    - `NRC Emotion Lexicon`

La trajectoire émotionnelle ne remplace pas la trajectoire lexicale brute.  
Elle ajoute une couche d'interprétation plus synthétique, utile quand on veut suivre :
- la peur
- la tristesse
- la colère
- la honte
- l'apaisement

Le résumé en valence positive / négative reste **secondaire** :
- il peut être utile pour une vue d'ensemble
- mais il est souvent trop pauvre s'il est utilisé seul

## FEEL

`FEEL` est un lexique émotionnel français. Dans ce projet, il est chargé à partir du fichier `dictionnaires/FEEL.csv`. Quand il est sélectionné dans la `Trajectoire émotionnelle`, l'application ne calcule plus la divergence de Jensen-Shannon sur les mots eux-mêmes, mais sur une **distribution d'émotions** reconnues dans chaque entretien.

Il est important de préciser que `FEEL` n'est **pas** un modèle neuronal contextualisé. Ce n'est pas un système à embeddings, et il n'utilise pas de mécanisme d'attention comme un modèle de type `CamemBERT`. Dans ce projet, `FEEL` fonctionne comme un **lexique annoté** : on dispose d'un peu plus de `14 000` entrées lexicales associées à une polarité et à une ou plusieurs émotions.

Autrement dit :
- `FEEL` reconnaît surtout des mots présents dans une liste annotée
- il projette ensuite ces mots vers des catégories émotionnelles
- il ne modélise pas le contexte complet de la phrase

Cela veut dire qu'il est plus simple et plus léger qu'un modèle contextualisé moderne, mais aussi plus limité. En particulier, il ne tient pas vraiment compte :
- de l'ironie
- de la négation complexe
- des ambiguïtés de sens selon la phrase
- des changements de valeur d'un mot selon le contexte discursif

Donc oui, au sens large, on peut dire que `FEEL` est une approche moins moderne qu'un modèle comme `CamemBERT` pour l'analyse fine du sens, parce qu'il ne détermine pas la polarité ou l'émotion à partir du **contexte de la phrase**, mais surtout à partir d'une correspondance lexicale entre un mot et une annotation émotionnelle.

Référence :
- Amine Abdaoui, Jérôme Azé, Sandra Bringay et Pascal Poncelet. *FEEL: French Expanded Emotion Lexicon*. Language Resources and Evaluation, LRE 2016, pp. 1-23.

Téléchargement du modèle / lexique :
- [http://advanse.lirmm.fr/feel.php](http://advanse.lirmm.fr/feel.php)

Concrètement :
- les mots du texte sont rapprochés des entrées de `FEEL.csv`
- chaque entretien est résumé par une distribution d'émotions
- la divergence de Jensen-Shannon compare ensuite ces distributions émotionnelles entre entretiens

Avec FEEL, les catégories émotionnelles principales sont :
- `joie`
- `peur`
- `tristesse`
- `colere`
- `degout`
- `surprise`

Cette lecture est plus synthétique que la trajectoire lexicale brute. Elle est utile pour repérer un déplacement émotionnel global, mais elle reste moins fidèle au détail du discours que l'analyse directe des mots, des termes contributifs et du concordancier.

Le résumé `positive / negative` peut aussi être affiché, mais il doit être lu comme une simplification secondaire. Avec FEEL, certaines émotions comme `surprise` ne se résument pas toujours proprement à une simple valence.

## NRC

`NRC Emotion Lexicon` suit la même démarche générale que FEEL dans l'application :
- les mots du texte sont rapprochés d'un lexique émotionnel
- chaque entretien est résumé par une distribution d'émotions
- la divergence de Jensen-Shannon compare ensuite ces distributions entre entretiens

Dans ce projet, NRC est chargé à partir des fichiers déjà présents dans `dictionnaires/`.

Ce que NRC apporte en plus par rapport à FEEL :
- une ressource plus largement diffusée et plus standardisée dans les usages de recherche
- un résumé `positive / negative` généralement mieux structuré
- des catégories comme `confiance` et `anticipation`, qui enrichissent la lecture émotionnelle au-delà des seules émotions de base

En pratique :
- `FEEL` est souvent plus immédiat pour une lecture émotionnelle francophone simple
- `NRC` apporte une couche plus large et un résumé de valence souvent plus exploitable

Les deux restent des lexiques projetés sur le texte. Ils produisent donc une lecture émotionnelle synthétique du discours, mais ne remplacent ni la trajectoire lexicale brute, ni l'interprétation clinique du praticien.

## Lexiques émotionnels attendus

Pour activer la trajectoire émotionnelle, l'application utilise dans ce projet :

- `FEEL.csv` pour FEEL
- les fichiers NRC compatibles déjà présents dans `dictionnaires/` pour NRC

Le parseur accepte plusieurs formats simples :

- format long :
  - `term,emotion,weight`
  - ou `mot,emotion,poids`

- format large :
  - une colonne de terme
  - puis une colonne par émotion (`joie`, `tristesse`, `peur`, `colere`, etc.)

Si aucun lexique émotionnel n'est présent, la couche émotionnelle reste indisponible, mais la trajectoire lexicale brute continue de fonctionner normalement.

## Encodage conseillé des dates et des séances

Dans le corpus, la trajectoire lexicale s'appuie sur une **variable étoilée** portée par chaque ligne `****`.

Les noms reconnus en priorité par le script sont :
- `*seance`
- `*date`
- `*temps`
- `*mois`
- `*annee`
- `*phase`

Exemples simples de lignes compatibles :
- `**** *patient_P01 *seance_01`
- `**** *patient_P01 *seance_02`
- `**** *patient_P01 *date_2026-04-16`
- `**** *patient_P01 *date_16/04/2026`
- `**** *patient_P01 *mois_2026-04`
- `**** *patient_P01 *annee_2026`
- `**** *patient_P01 *phase_1`

Formats de modalités actuellement reconnus pour l'ordre chronologique :
- date complète : `2026-04-16`, `2026/04/16`, `16/04/2026`, `16-04-2026`, `2026.04.16`, `16.04.2026`, `2026_04_16`, `16_04_2026`
- année-mois : `2026-04`, `2026/04`, `2026_04`, `2026.04`
- mois-année : `04-2026`, `04/2026`, `04_2026`, `04.2026`
- année seule : `2026`
- séance numérotée : `01`, `2`, `10`, ou plus largement `seance_01`, `seance_2`, `seance_10`

Recommandation pratique :
- pour des séances : `*seance_01`, `*seance_02`, `*seance_03`
- pour des dates : `*date_2026-04-16`
- pour des mois : `*mois_2026-04`
- pour des années : `*annee_2026`

Une variable comme `*am_2026-04` peut aussi fonctionner si elle est choisie manuellement dans les paramètres, mais elle n'est pas prioritaire dans la détection automatique. Les noms les plus sûrs restent donc `*seance`, `*date`, `*mois` et `*annee`.

## Filtres de sous-corpus conseillés

Pour isoler une partie du corpus avant de calculer la trajectoire lexicale, les variables les plus pratiques sont :

- `*journal`
- `*source`
- `*locuteur`
- `*patient`
- `*service`

Exemples :

- `**** *journal_lemonde *date_2026-04-16`
- `**** *source_europresse *mois_2026-04`
- `**** *locuteur_patient01 *seance_03`
- `**** *patient_P01 *phase_2`

## Repère historique

La divergence de Jensen-Shannon est une mesure issue de la théorie de l'information.  
Elle prolonge la divergence de Kullback-Leibler, en proposant une comparaison plus stable et symétrique entre deux distributions.

Elle est souvent utilisée quand on veut comparer deux profils probabilistes :
- distribution de mots
- distribution de thèmes
- distribution de signaux

Dans l'application, elle sert à comparer des **distributions lexicales d'entretiens**.

## Entropie et divergence de Jensen-Shannon

La divergence de Jensen-Shannon mobilise directement la notion d'**entropie**.

### 1. L'entropie

En théorie de l'information, l'entropie mesure le degré d'**incertitude**, de **dispersion** ou d'**imprévisibilité** d'une distribution.

Lecture simple :
- entropie faible = la distribution est concentrée sur peu d'éléments
- entropie élevée = la distribution est plus répartie et plus diversifiée

Dans le cas d'un entretien, on peut la lire comme une mesure de la dispersion du vocabulaire :
- si peu de mots dominent fortement, l'entropie est plus faible
- si le lexique est plus étalé sur de nombreux mots, l'entropie est plus élevée

L'entropie d'un seul entretien ne se calcule pas par rapport à un corpus de référence externe. Elle se calcule à partir de la **distribution des mots de cet entretien lui-même** :
- on compte les termes présents dans l'entretien après prétraitement
- on transforme ces comptages en fréquences relatives
- puis on mesure à quel point cette distribution est concentrée ou dispersée

Le référentiel est donc interne à l'entretien :
- si quelques mots occupent une grande partie du discours, l'entropie est plus faible
- si le poids lexical est réparti sur beaucoup de mots, l'entropie est plus élevée

Exemple très simple :
- entretien A : `angoisse` 40 %, `sommeil` 35 %, `travail` 20 %, `sortir` 5 %
- entretien B : `angoisse` 25 %, `sommeil` 25 %, `travail` 25 %, `sortir` 25 %

L'entretien B a une entropie plus élevée, parce que la distribution de ses mots est plus équilibrée.

L'entropie décrit donc surtout la **structure interne d'un entretien**. Elle ne mesure pas, à elle seule, le changement entre deux entretiens.

### 2. La divergence

La divergence de Jensen-Shannon compare deux distributions `P` et `Q` en passant par leur moyenne `M`, puis en comparant l'entropie de `M` à celles de `P` et `Q`.

Sous forme simplifiée :
- `JSD(P, Q) = H(M) - 1/2 H(P) - 1/2 H(Q)`

Dans l'application, elle mesure l'écart entre **deux entretiens** :
- divergence faible = les deux entretiens ont des profils lexicaux proches
- divergence élevée = les deux entretiens diffèrent davantage

La divergence crée donc un **signal d'écart** entre deux séances, mais elle ne dit pas à elle seule ce que signifie cet écart sur le plan clinique. L'interprétation revient au médecin, à partir du contexte, des termes contributifs et du concordancier.

La divergence de Jensen-Shannon est une **mesure informationnelle non paramétrique** ; elle décrit un écart entre deux distributions sans constituer à elle seule un test paramétrique.

La divergence de Jensen-Shannon n'est pas un test paramétrique. C'est :
- une mesure d'écart
- entre deux distributions de probabilité

Elle ne repose pas sur des hypothèses paramétriques du type :
- normalité
- variance homogène
- modèle linéaire gaussien

C'est plutôt un indice informationnel :
- plus la valeur est faible, plus les deux distributions se ressemblent
- plus la valeur est élevée, plus elles diffèrent

La nuance importante :
- la JSD seule mesure
- elle ne « teste » pas au sens inférentiel classique

Donc si l'on veut un raisonnement du type :
- cet écart est-il plus grand que ce qu'on attendrait au hasard ?

il faut lui ajouter un cadre statistique externe. En elle-même, la JSD reste une mesure descriptive et comparative.

### Exemple chiffré très simple

Prenons un mini vocabulaire de trois mots :
- `peur`
- `sommeil`
- `travail`

Supposons deux entretiens :

- entretien `P`
  - `peur = 0,50`
  - `sommeil = 0,30`
  - `travail = 0,20`

- entretien `Q`
  - `peur = 0,10`
  - `sommeil = 0,40`
  - `travail = 0,50`

#### Étape 1. Calculer l'entropie de chaque entretien

On calcule d'abord l'entropie de chaque distribution :
- `H(P) = - Σ p_i log2(p_i) ≈ 1,4855`
- `H(Q) = - Σ q_i log2(q_i) ≈ 1,3610`

Lecture :
- `P` est un peu plus dispersé que `Q`
- mais les deux entretiens restent encore relativement structurés autour de quelques mots

#### Étape 2. Construire la distribution moyenne

On calcule ensuite la moyenne :
- `M = (P + Q) / 2`

Ici :
- `M = (0,30 ; 0,35 ; 0,35)`

Puis on calcule son entropie :
- `H(M) ≈ 1,5813`

#### Étape 3. Calculer la divergence de Jensen-Shannon

La formule est :
- `JSD(P, Q) = H(M) - 1/2 H(P) - 1/2 H(Q)`

Donc ici :
- `JSD(P, Q) ≈ 1,5813 - 0,5 × 1,4855 - 0,5 × 1,3610`
- `JSD(P, Q) ≈ 0,1581`

Cette valeur ne dit pas ce que signifie cliniquement le changement. Elle dit seulement qu'il existe un **écart mesurable** entre les deux profils lexicaux.

#### Décomposition intuitive avec un mot

On ne calcule pas la JSD sur un mot isolé. La JSD porte sur **toute la distribution**. En revanche, chaque mot contribue plus ou moins à l'écart final.

Dans cet exemple :
- le mot `peur` passe de `0,50` à `0,10`
- il contribue davantage à la divergence que `sommeil`, qui reste plus stable (`0,30` à `0,40`)

Contribution approximative de chaque mot à la JSD :
- `peur ≈ 0,1050`
- `sommeil ≈ 0,0052`
- `travail ≈ 0,0479`

On voit donc que :
- l'écart global vient surtout du recul de `peur`
- puis de la montée de `travail`
- `sommeil` change peu et contribue peu

#### À quoi cela sert

L'intérêt de la JSD n'est pas de dire :
- amélioration
- aggravation
- désorganisation

Son intérêt est de dire :
- `entre ces deux entretiens, le profil lexical a changé`
- `ce changement vient surtout de tels mots`

Autrement dit :
- l'**entropie** décrit la structure interne d'un entretien
- la **divergence** décrit l'écart entre deux entretiens
- les **termes contributifs** aident à comprendre d'où vient cet écart

Dans un suivi clinique, la JSD peut donc servir d'**indicateur de déplacement discursif**. L'interprétation du sens de ce déplacement reste du côté du clinicien.

## Fonctionnement

Après le même prétraitement pour tous les entretiens :
- nettoyage du texte
- dictionnaire `lexique_fr`
- choix `formes` / `lemmes`
- filtrage morphosyntaxique éventuel

on construit un **vocabulaire commun** sur les entretiens retenus.

Chaque entretien devient ensuite une distribution de probabilité :
- on compte les termes
- puis on transforme ces comptages en fréquences relatives

La divergence de Jensen-Shannon compare alors deux entretiens `P` et `Q` en passant par une distribution moyenne `M = (P + Q) / 2`.

## Paramètres

`Variable étoilée de la trajectoire`  
Définit l'unité ordonnée de la trajectoire, par exemple `*seance`, `*date`, `*mois`, `*annee` ou `*phase`. Ce sont les noms privilégiés dans l'interface et dans la détection automatique.

`Variable de filtre`  
Permet de restreindre le calcul à un sous-corpus, par exemple `*journal`, `*source`, `*locuteur`, `*patient` ou `*service`.

`Sous-corpus`  
Choisit la modalité concrète du filtre, par exemple un patient particulier, un journal précis ou une source donnée.

`Ordre chronologique`  
Définit le sens de lecture de la série. Il agit sur la comparaison entre séances successives et sur la comparaison à la première séance.

`Unité lexicale`  
Choisit l'objet comparé dans la distribution lexicale :
- `grammes / unigrammes` = mots pris un par un
- `bigrammes` = suites de deux mots consécutifs après prétraitement

`Termes évolutifs par comparaison`  
Définit combien de termes sont affichés dans les tableaux d'évolution et de contribution pour chaque comparaison.

`Source de lemmatisation`, `nettoyage`, `stopwords`, `filtrage morphosyntaxique`  
Ces réglages sont repris du projet.

## Ordre chronologique

L'ordre chronologique indique dans quel sens les entretiens sont rangés avant la comparaison.

Exemple :
- ordre croissant : séance 1 -> séance 2 -> séance 3
- ordre décroissant : séance 3 -> séance 2 -> séance 1

Ce paramètre est surtout utile quand la variable de la trajectoire a un vrai sens temporel ou ordinal :
- `*seance`
- `*date`
- `*mois`
- `*annee`
- `*phase`

Il agit sur deux lectures :
- la comparaison entre entretiens successifs
- la comparaison de chaque entretien à la première séance de l'ordre choisi

Dans un suivi clinique classique, on utilisera le plus souvent l'ordre croissant.

## Colonnes des tableaux

### Cadre de la trajectoire lexicale

Le tableau `Cadre de la trajectoire lexicale` rappelle :
- la variable utilisée pour ordonner les entretiens
- l'ordre retenu
- le prétraitement réellement appliqué
- le filtrage morphosyntaxique
- le filtre éventuel
- le nombre d'entretiens retenus
- la taille du vocabulaire commun
- une note exploratoire si le corpus est faible

### Indicateurs par entretien

`Ordre`  
Position de l'entretien dans la série.

`Unite`  
Modalité suivie : séance, date, mois, année ou phase.

`Tokens_total`  
Nombre total de mots après prétraitement.

`Types_total`  
Nombre de mots différents.

`Entropie_lexicale`  
Mesure la dispersion interne du vocabulaire de la séance. Plus elle est élevée, plus le lexique est diversifié.

`Entropie_normalisee`  
Version ramenée entre `0` et `1`, pour comparer plus facilement des entretiens de tailles différentes.

`Redondance_relative`  
Valeur complémentaire de l'entropie normalisée : `1 - entropie normalisée`. Plus elle est élevée, plus le discours est concentré sur un lexique resserré.

### Divergence de Jensen-Shannon entre séances successives

`Unite_depart`  
Séance de départ.

`Unite_arrivee`  
Séance suivante.

`Divergence_Jensen_Shannon`  
Mesure l'écart entre les distributions lexicales des deux séances. Plus la valeur est élevée, plus le déplacement lexical entre les deux séances est marqué.

### Divergence de Jensen-Shannon par rapport à la première séance

`Unite_reference`  
Première séance de l'ordre choisi.

`Unite_comparee`  
Séance comparée à cette référence.

`Divergence_Jensen_Shannon`  
Mesure l'écart lexical avec la première séance.

### Termes qui évoluent

Ce tableau décrit le **sens du changement lexical** entre deux entretiens.  
Il est utile pour voir ce qui apparaît, disparaît, augmente ou recule dans le discours.

`Mode_comparaison`  
Indique si la comparaison porte sur la séance précédente ou sur la première séance.

`Unite_depart`  
Entretien de départ.

`Unite_arrivee`  
Entretien d'arrivée.

`Type_evolution`  
Nature du changement : `nouveau`, `hausse`, `baisse`, `disparu`.

`Terme`  
Mot observé.

`Frequence_relative_depart`  
Poids relatif du terme dans l'entretien de départ.

`Frequence_relative_arrivee`  
Poids relatif du terme dans l'entretien d'arrivée.

`Difference_relative`  
Écart entre les deux fréquences relatives. Cette valeur aide à voir l'amplitude du changement.

### Contribution des termes à la divergence

Ce tableau montre **quels termes expliquent le plus la divergence de Jensen-Shannon** entre deux entretiens.

Il n'y a donc pas doublon :
- le tableau des termes qui évoluent décrit la direction du changement
- le tableau de contribution explique quels mots portent le plus l'écart global

`Mode_comparaison`  
Indique si la lecture porte sur la séance précédente ou sur la première séance.

`Unite_depart`  
Entretien de départ.

`Unite_arrivee`  
Entretien d'arrivée.

`Terme`  
Mot qui contribue à l'écart global.

`Frequence_relative_depart`  
Poids relatif du terme dans l'entretien de départ.

`Frequence_relative_arrivee`  
Poids relatif du terme dans l'entretien d'arrivée.

`Difference_relative`  
Écart de poids lexical entre les deux entretiens.

`Contribution_Jensen_Shannon`  
Part du terme dans la divergence globale. Plus cette valeur est élevée, plus le terme explique la différence entre les deux distributions.

Un clic sur le terme ouvre le `concordancier JSD`, c'est-à-dire les segments des deux entretiens où ce terme apparaît.

### Frise des émergences

La frise des émergences propose une lecture temporelle de l'évolution lexicale.

Elle organise les termes les plus changeants :
- en lignes
- les transitions entre entretiens en colonnes
- et le type d'évolution en couleur

Elle permet donc de voir rapidement :
- quels termes apparaissent à un moment donné
- quels termes montent ou reculent au fil de la trajectoire
- à quel endroit de la série se concentrent les émergences et les disparitions

### Barres divergentes des termes évolutifs

Ce graphique place les termes en recul à gauche de zéro et les termes en hausse à droite.

Il permet de voir rapidement :
- le sens du déplacement lexical
- l'amplitude du changement pour chaque terme
- l'équilibre global entre termes qui montent et termes qui reculent

### Waterfall des contributions

Le waterfall montre, pour une comparaison donnée, comment les termes les plus contributifs s'additionnent pour fabriquer l'écart global.

Chaque barre correspond à la contribution d'un mot à la divergence de Jensen-Shannon :
- les premières barres montrent les mots les plus explicatifs
- la somme cumulée monte à mesure que l'on ajoute les termes
- la dernière barre rappelle le total expliqué par les termes affichés

Ce rendu est utile pour répondre à une question simple :
- quels mots fabriquent concrètement la divergence entre deux entretiens ?

### Détection des ruptures

Ce sous-onglet relit la série des divergences entre périodes successives pour repérer les moments où le déplacement lexical devient plus saillant.

La logique est simple :
- on part des divergences successives déjà calculées
- on repère les pics locaux
- on les compare au niveau moyen de la série

La détection repose sur la divergence brute et son profil dans la série.

Une rupture détectée n'est pas une preuve absolue. C'est un signal interprétatif qui attire l'attention sur une comparaison plus marquée que les autres, avec ses termes explicatifs principaux.

## Rupture et pré-rupture

Dans un suivi clinique, l'intérêt ne se limite pas à repérer :
- `voici la séance où le langage change fortement`

Le point souvent plus important est aussi :
- `qu'est-ce qui, juste avant, annonce ce changement ?`

La divergence de Jensen-Shannon peut donc être lue comme un **détecteur de moment de bascule**. Elle ne donne pas à elle seule la signification clinique de la rupture, mais elle aide à localiser les endroits de la trajectoire où le discours se reconfigure davantage.

Cette perspective ouvre une lecture en deux temps :
- repérer la séance de rupture
- puis relire la séance précédente, ou les segments qui précèdent, pour voir ce qui prépare cette rupture

Dans cette logique, le moment **pré-rupture** peut être particulièrement intéressant. On peut y chercher :
- des termes qui commencent à émerger
- un déplacement émotionnel
- des changements de formulation
- une modification du rapport à soi, aux autres ou à la situation

Le test ne démontre pas directement une `structure cognitive` ou un `cadre métacognitif`. En revanche, il peut aider à repérer des **indices discursifs compatibles avec une reconfiguration du cadre de pensée**, que le clinicien pourra ensuite interpréter.

Autrement dit :
- la JSD repère le déplacement
- les termes contributifs et le concordancier aident à comprendre d'où vient ce déplacement
- la lecture clinique peut alors se concentrer sur la zone de pré-rupture et sur la rupture elle-même

### Matrice de divergence de Jensen-Shannon

Chaque ligne et chaque colonne correspond à un entretien.  
Chaque cellule donne la divergence de Jensen-Shannon entre les deux entretiens croisés.

## Ce que l'on peut dire avec ce test

Ce test permet de dire :
- si deux entretiens sont lexicalement proches
- si un entretien s'éloigne du précédent
- si un entretien s'éloigne de la première séance
- si la trajectoire semble progressive ou plus brusque

Lecture simple :
- valeur faible = profils lexicaux proches
- valeur élevée = écart lexical plus marqué

On peut donc repérer :
- des continuités
- des déplacements progressifs
- des ruptures de vocabulaire

La divergence de Jensen-Shannon sert donc à mesurer l'écart entre deux séances.  
L'entropie lexicale normalisée sert à mesurer la dispersion interne de chaque séance.  
La redondance relative sert à mesurer le degré de concentration du discours.

## Limites

La divergence de Jensen-Shannon ne dit pas à elle seule :
- pourquoi le changement a lieu
- si ce changement est positif ou négatif
- quelle interprétation clinique il faut retenir

Elle indique seulement qu'il y a **plus ou moins d'écart** entre deux distributions lexicales.

Le résultat doit donc être relu avec :
- les termes en hausse et en recul
- la table de contribution des termes à la divergence
- les nuages de mots
- le contexte clinique ou social des entretiens
