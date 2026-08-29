# Rapport de bug Auto CHD - corpustest

Date: 2026-08-27

Corpus teste:
- `corpustest/psychiatrie-darmanin-clean.txt`

Commande de test:
- `Rscript backend/r/run_iramuteq_batch.R --input corpustest/psychiatrie-darmanin-clean.txt --config ... --output-dir ... --status-file ... --results-file ...`

## Scenarios executes

| Scenario | k max | Filtrage morpho | AUTRE_FORME | Partition retenue |
|---|---:|---|---|---|
| Standard | 8 | non | oui | P2 |
| Standard | 10 | non | oui | P2 |
| NOM + VER | 8 | oui | non | P2 |
| NOM + VER | 10 | oui | non | P2 |
| NOM + VER | 8 | oui | oui | P2 |
| NOM + VER | 10 | oui | oui | P2 |

## Conclusion principale

Le bug signale par l'utilisateur n'a pas ete reproduit sur `corpustest`: avec le code local actuel, le mode Auto CHD ne choisit pas systematiquement `k max`.

Sur les 6 scenarios testes, la partition retenue est toujours `P2`, y compris quand `k max = 10` et en filtrage `NOM + VER`.

## Resultats de score

| Scenario | B(P2) | B(P8) | B(P10) | Observation |
|---|---:|---:|---:|---|
| Standard | 0.3338 | 0.2467 | 0.2551 | P2 reste au-dessus des partitions fines |
| NOM + VER sans AUTRE_FORME | 0.3678 | 0.2649 | 0.2767 | P2 reste meilleur meme avec lexique rarifie |
| NOM + VER avec AUTRE_FORME | 0.3463 | 0.2863 | 0.2988 | AUTRE_FORME remonte un peu les partitions fines sans depasser P2 |

## Findings

### 1. Majeur - biais des classes singleton dans le scoring auto

Fichiers:
- `iramuteqlite/autoCHD.R:197`
- `iramuteqlite/autoCHD.R:349`

Constat:
- Le corpus test produit des partitions contenant tres tot une classe singleton.
- Exemple en scenario standard `k max = 10`: `P2 = 1 segment + 629 segments`.
- Si une classe singleton est consideree comme "parfaitement homogene" ou "diffusee" par construction, elle peut artificiellement favoriser les partitions fines quand le lexique devient tres sparse.

Impact:
- Ce biais peut expliquer, sur d'autres corpus plus sensibles que `corpustest`, un comportement du type "plus je monte `k max`, plus l'algorithme colle a la borne".

Etat:
- Le code local teste contient deja un garde-fou: une classe avec moins de 2 segments recoit `H = 0` et `L = 0`.

### 2. Moyen - le log "Nombre de mots conserves" est trompeur en filtrage morphosyntaxique

Fichiers:
- `backend/r/run_iramuteq_batch.R:950`
- `backend/r/run_iramuteq_batch.R:1151`

Constat:
- Le filtrage morphosyntaxique est applique sur `dfm_obj`.
- Le message de log "Nombre de mots conserves pour l'analyse apres pretraitements" est calcule sur `tok`, qui n'est pas refiltre de la meme facon.
- En test, ce compteur reste a `22177` dans les scenarios standard, `NOM + VER`, et `NOM + VER + AUTRE_FORME`, alors que la DFM change fortement:
- standard: `3125` termes
- `NOM + VER`: `1963` termes
- `NOM + VER + AUTRE_FORME`: `2443` termes

Impact:
- L'interface laisse croire que le volume lexical conserve ne change pas, alors que la matrice analysee change bien.
- Cela peut faire croire a tort que le filtrage `NOM + VER` n'est pas pris en compte.

### 3. Moyen - sur ce corpus, L s'annule pour toutes les partitions

Fichier:
- `iramuteqlite/autoCHD.R:349`

Constat:
- Dans les 6 scenarios, `L = 0` pour `P2 ... Pk`.
- La cause immediate est structurelle: `L` retient le minimum inter-classes, et les partitions testees contiennent soit une classe singleton, soit une classe sans formes caracteristiques significatives suffisantes.

Impact:
- Sur `corpustest`, le score structurel devient de fait tres proche de `(H + D) / 3`.
- Ce n'est pas un crash, mais une neutralisation pratique d'un tiers du score.

Statut:
- C'est surtout une limite de calibration du critere sur des partitions avec singleton, plutot qu'un bug de selection pur.

### 4. Faible - warnings repetes pendant l'export du dendrogramme

Message observe:
- `In min(-diff(our_dend_heights)) : no non-missing arguments to min; returning Inf`

Constat:
- Le warning apparait sur chaque run teste.
- Les exports sont tout de meme generes (`dendrogramme_chd.png`, `dendrogramme_chd_factoextra.png`).

Impact:
- Pas de blocage fonctionnel observe.
- Le point reste a tracer pour durcir le rendu et nettoyer les logs.

## Lecture des tests

Les tests ne valident donc pas l'hypothese "Auto CHD choisit toujours k max" sur `corpustest`.

En revanche, ils confirment trois choses utiles pour le debug:
- les partitions contiennent des singletons tres tot;
- le compteur de mots affiche ne reflete pas exactement le lexique reellement analyse apres filtrage morpho;
- `L` peut etre neutralise sur tout un jeu de partitions quand la regle du minimum rencontre une classe singleton ou peu caracterisee.

## Sorties utiles

Exemples de repertoires de sortie:
- `/tmp/iramuteq_autochd_out_k10_retest`
- `/tmp/iramuteq_autochd_morpho_nv_k10_noautre_retest`
- `/tmp/iramuteq_autochd_morpho_nv_k10_autre_retest`

Fichiers a consulter:
- `auto_chd_metrics.csv`
- `auto_chd_summary.json`
- `stats_par_classe.csv`
- `status.json`
