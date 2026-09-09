# Rapport de comparaison CHD

## IRaMuTeQ Lite et IRaMuTeQ Lab AutoCHD

Date du rapport : 9 septembre 2026.

Ce rapport compare l'application historique iramuteq-lite et la variante
iramuteq-lite_autoCHD (IRaMuTeQ Lab AutoCHD). Il porte sur le calcul CHD
manuel, le pretraitement et la reproductibilite des resultats.

## Conclusion

Le coeur historique de la CHD est conserve dans IRaMuTeQ Lab AutoCHD. Les
fichiers qui calculent l'AFC de partition, les divisions de classes, les
classes terminales, le pretraitement et les statistiques chi2 sont identiques
a IRaMuTeQ Lite.

La seule correction appliquee au calcul manuel est la reproductibilite de la
methode SVD irlba. Cette methode initialise son calcul avec un vecteur
aleatoire : sans graine fixe, deux executions du meme corpus peuvent affecter
certains segments a des classes differentes. IRaMuTeQ Lab AutoCHD fixe cette
graine avant la CHD. Le calcul CHD, les chi2 et la regle mincl ne sont pas
modifies.

## Comparaison du code

| Fichier ou couche | Etat de la comparaison | Effet sur la CHD manuelle |
| --- | --- | --- |
| iramuteqlite/anacor.R | Identique | Calcul AFC historique identique. |
| iramuteqlite/CHD.R | Identique | Divisions hierarchiques identiques. |
| iramuteqlite/chdtxt.R | Identique | Regles de classes terminales identiques. |
| iramuteqlite/stats_chd.R | Identique | Calcul des chi2 identique. |
| iramuteqlite/nettoyage_iramuteq.R | Identique | Pretraitement lexical identique. |
| iramuteqlite/chd_iramuteq.R | Meme code historique, plus une graine fixe pour irlba | Stabilise les executions identiques. |
| iramuteqlite/chd_engine_iramuteq.R | Etendu | Le branchement manuel appelle le calcul historique; les branches supplementaires ne sont utilisees que par Discrimination simple. |
| backend/r/run_iramuteq_batch.R | Etendu | Ajoute le routage des modes et un cache de lexique; en manuel, les valeurs saisies sont transmises au moteur CHD. |
| Interface | Etendue | Ajoute le choix Manuel ou Discrimination simple; le mode manuel ne lance pas de simulation supplementaire. |

Les modules autoCHD.R et discriminationsimple.R sont charges pour le mode
Discrimination simple. Ils ne sont pas appeles lorsque le mode Manuel est
selectionne.

## Tests reproductibles

Corpus utilise : corpustest/psychiatrie-darmanin-clean.txt.

Caracteristiques obtenues apres pretraitement dans les tests : 23 textes,
630 segments et 3 125 formes. Le fichier importe porte la somme MD5
a2a229aeca6da5537a82cae95273110f.

| Configuration | IRaMuTeQ Lite | IRaMuTeQ Lab AutoCHD | Resultat |
| --- | --- | --- | --- |
| k = 10, mincl = 5 manuel, SVD svdR | 8 classes | 8 classes | Les affectations et les statistiques sont identiques octet pour octet. |
| k = 10, mincl automatique, SVD irlba | 5 classes, avec deux affectations de segments observees sur trois essais | 5 classes, meme affectation sur trois essais | Lab supprime la variation aleatoire. |
| k = 5, mincl automatique, SVD irlba | 3 classes, deux affectations observees sur trois essais | 3 classes, meme affectation sur trois essais | Le resultat a trois classes est reproductible dans Lab. |

Pour le premier test, les exports segments_par_classe.txt et
stats_par_classe.csv ont les memes empreintes dans les deux applications.

Pour le dernier test, les trois executions Lab AutoCHD ont produit la meme
empreinte SHA-256 pour l'affectation des segments :
dd8916a23ce08d011d338292761c093e314cf8b3870aa41bd34e4468de6c6cd2.

## Pourquoi le nombre de classes varie selon les parametres

k est une borne du nombre de divisions explorees par l'arbre, pas une valeur
forcee du nombre final de classes. Il influence toutefois les feuilles que la
CHD peut produire. Avec le corpus de test, k = 5 ouvre moins de divisions que
k = 10, ce qui conduit respectivement a 3 et 5 classes en mincl automatique.

mincl est ensuite la regle qui conserve ou regroupe les classes terminales :

| Regle | Effet observe sur le corpus de test |
| --- | --- |
| mincl automatique | Le seuil est calcule a partir du corpus et des feuilles de l'arbre. |
| mincl = 5 manuel | Les petites classes d'au moins cinq segments sont conservees; avec k = 10, cela donne 8 classes dans le test. |

Ainsi, passer de k = 5 a k = 10, ou de mincl automatique a mincl = 5
manuellement, peut modifier le nombre final de classes sans que le calcul CHD
historique ait change.

## Correctif de reproductibilite

Dans chd_iramuteq.R, Lab AutoCHD execute set.seed(20260909L) juste avant
l'appel CHD lorsque irlba est choisie. Cette operation fixe seulement le point
de depart aleatoire de irlba et rend les resultats repetables.

La correction ne modifie pas :

- la matrice segments x termes;
- le pretraitement lexical;
- les calculs chi2 et p.value;
- les regles find.terminales et mincl;
- le nombre maximal de divisions demande par k.

## Limites et recommandation

Les comparaisons ont ete executees localement avec le corpus de test fourni.
Un corpus different, ou des options de pretraitement differentes, peut
legitimement produire un autre nombre de classes.

Pour reproduire le resultat a trois classes sur ce corpus, utiliser le mode
Manuel, k = 5, mincl automatique, la classification simple et irlba. La
version Lab donnera a present toujours la meme affectation pour cette
configuration.

Le commit de reproductibilite doit etre redeploye par Coolify pour etre actif
sur le domaine public.

