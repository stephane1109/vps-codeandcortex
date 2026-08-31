# Analyse discriminante optimisee

Ce mode cherche **un seul meilleur compromis**.

Il ne change ni la CHD, ni le calcul du `chi2`.
Il relance seulement quelques configurations ciblees du meme corpus, puis compare leurs resultats sur l'AFC.

L'utilisateur ne choisit donc pas le `k` final :
il fixe seulement un cadre d'exploration, puis l'application retient automatiquement la partition la plus discriminante.

## Ce qui est teste

- filtrage morphosyntaxique : `NOM + VER`
- exclusion du verbe `etre`
- `AUTRE_FORME` desactive
- `min_docfreq` varie de `2` a `5`

## Comment le compromis est choisi

Pour chaque configuration :

- la CHD produit les partitions `P_k`
- tous les termes caracteristiques significatifs a `p.value <= 0.05` sont retenus
- ces termes sont tries par `chi2` dans chaque classe puis projetes sur l'AFC
- l'application retient la configuration dont les classes s'opposent le mieux

## Ce qui est affiche

- la configuration retenue
- la partition retenue
- le score discriminant `A`
- les parametres qui ont produit ce compromis
- les termes significatifs a `p.value <= 0.05` qui soutiennent ce resultat
