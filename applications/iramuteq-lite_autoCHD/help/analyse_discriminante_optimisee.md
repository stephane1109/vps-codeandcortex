# Analyse discriminante optimisee

Ce mode cherche **un seul meilleur compromis**.

Il ne change ni la CHD, ni le calcul du `chi2`.
Il relance seulement quelques configurations ciblees du meme corpus, puis compare leurs resultats sur l'AFC.

## Ce qui est teste

- filtrage morphosyntaxique : `NOM + VER`
- exclusion du verbe `etre`
- `AUTRE_FORME` desactive
- `min_docfreq` varie de `2` a `5`

## Comment le compromis est choisi

Pour chaque configuration :

- la CHD produit les partitions `P_k`
- les termes caracteristiques significatifs sont tries par `chi2`
- jusqu'a `10` termes par classe sont projetes sur l'AFC
- l'application retient la configuration dont les classes s'opposent le mieux

## Ce qui est affiche

- la configuration retenue
- la partition retenue
- le score discriminant `A`
- les parametres qui ont produit ce compromis
- les termes significatifs qui soutiennent ce resultat
