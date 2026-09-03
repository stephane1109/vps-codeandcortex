# Analyse discriminante optimisée

Ce mode cherche **un seul meilleur compromis**.

Il ne change ni la CHD, ni le calcul du `chi2`.
Il relance seulement quelques configurations ciblées du même corpus, puis compare leurs résultats sur l'AFC.

L'utilisateur ne choisit donc pas le `k` final :
il fixe seulement une limite maximale d'exploration, puis l'application compare automatiquement les solutions en classes à partir de `3` classes et retient la plus discriminante.

## Ce qui est testé

- filtrage morphosyntaxique : `NOM + VER`
- exclusion du verbe `etre`
- option `AUTRE_FORME` conservée selon le choix utilisateur
- `min_docfreq` varie de `2` à `5`

## Comment le compromis est choisi

Pour chaque configuration :

- la CHD produit plusieurs solutions de `3` à `k` classes
- tous les termes caractéristiques significatifs à `p.value <= 0.05` sont retenus
- ces termes sont triés par `chi2` dans chaque classe puis projetés sur l'AFC
- l'application retient la configuration dont les classes s'opposent le mieux

## Ce qui est affiché

- la configuration retenue
- la solution retenue
- le score discriminant `A`
- les paramètres qui ont produit ce compromis
- les termes significatifs à `p.value <= 0.05` qui soutiennent ce résultat
