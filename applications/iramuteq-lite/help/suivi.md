## Trajectoire lexicale

Cet onglet compare plusieurs entretiens ordonnés dans le temps.  
Le calcul principal est lexical : il repose sur les distributions de termes de chaque entretien après le même prétraitement.

Il n'est pas nécessaire de lancer une CHD avant ce test.  
La CHD et la LDA restent disponibles dans l'application, mais elles ne sont pas recalculées ici pour chaque séance.

## Variable de la trajectoire

La trajectoire lexicale s'appuie sur une variable étoilée du corpus, par exemple `*seance`, `*date`, `*mois`, `*annee` ou `*phase`.  
Vous pouvez aussi filtrer un sous-corpus, par exemple un patient, puis choisir les entretiens à comparer.

## Vocabulaire commun

Tous les entretiens retenus sont prétraités de la même manière.  
On construit ensuite un vocabulaire commun à partir de l'ensemble retenu.

La trajectoire lexicale réutilise les réglages courants du projet :
- nettoyage du texte
- dictionnaire `lexique_fr`
- choix `formes` / `lemmes`
- filtrage morphosyntaxique éventuel

L'interface rappelle explicitement le filtrage morphosyntaxique réellement utilisé dans le cadre de la trajectoire lexicale.

Chaque entretien est alors décrit par :
- ses fréquences absolues de termes
- puis ses fréquences relatives sur ce vocabulaire commun

Ces fréquences relatives servent de distributions de probabilité.

## Principe de la vectorisation

Chaque entretien devient un vecteur lexical :
- une colonne par terme du vocabulaire commun
- une valeur par fréquence relative

![Principe de la vectorisation](images/vectorisation_suivi.svg)

On ne compare donc pas les textes bruts directement.  
On compare leurs profils lexicaux.

## Divergence de Jensen-Shannon

La divergence de Jensen-Shannon compare deux distributions lexicales `P` et `Q`.  
On calcule d'abord la distribution moyenne `M = (P + Q) / 2`, puis on mesure l'écart entre `P` et `M`, et entre `Q` et `M`.

Lecture simple :
- valeur faible = entretiens lexicalement proches
- valeur forte = écart lexical plus marqué

Dans l'onglet :
- une courbe compare chaque entretien à l'entretien précédent
- une autre courbe compare chaque entretien à la première séance
- la matrice compare toutes les paires d'entretiens

## Indicateurs par entretien

`Tokens_total` : nombre total de mots après prétraitement.  
`Types_total` : nombre de mots différents.  
`Entropie_lexicale` : dispersion du vocabulaire.  
`Entropie_normalisee` : entropie ramenée entre `0` et `1`.  
`Redondance_relative` : `1 - entropie normalisée`.

Dans une approche longitudinale des entretiens, l'entropie informationnelle d'un mot est une mesure descriptive de la manière dont ce mot se répartit d'un entretien à l'autre au cours du suivi. Elle indique si le mot est fortement concentré sur un moment particulier de la trajectoire clinique, ou s'il est présent de façon plus diffuse et plus régulière dans l'ensemble des entretiens.

Une entropie faible signifie que le mot est surtout associé à un petit nombre d'entretiens, voire à un seul. Il apparaît alors comme localisé, spécifique à certains moments du suivi. Une entropie élevée signifie au contraire que le mot est distribué de manière plus équilibrée entre les entretiens, ce qui suggère une présence plus stable ou plus transversale dans le temps.

Lecture simple :
- entropie élevée = vocabulaire plus dispersé
- redondance élevée = vocabulaire plus resserré

## Termes qui évoluent

Les termes sont comparés à partir de leurs fréquences relatives.

`hausse` : le terme prend plus de place dans l'entretien suivant.  
`baisse` : le terme prend moins de place.  
`nouveau` : il apparaît alors qu'il était absent.  
`disparu` : il n'apparaît plus alors qu'il était présent.

Le tableau donne les deux fréquences relatives comparées et leur différence.

## Nuages de mots

Chaque nuage résume les termes les plus présents dans un entretien.  
Il aide à lire concrètement les déplacements lexicaux repérés par la divergence de Jensen-Shannon.

## Interprétation

Cet onglet aide à repérer :
- des continuités lexicales
- des déplacements progressifs
- des ruptures entre entretiens

Le résultat reste exploratoire, surtout avec peu d'entretiens ou des textes courts.
