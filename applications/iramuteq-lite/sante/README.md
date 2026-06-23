# Corpus de référence santé mentale

Ce dossier contient des corpus **entièrement fictifs** et les scripts de calcul liés au suivi longitudinal.

Fichiers :
- `santementale.txt` : corpus multi-patients de démonstration
- `santementale_individu.txt` : corpus longitudinal centré sur un seul patient
- `suivi_longitudinal_chd.R` : script R qui exploite les résultats de la CHD pour produire un suivi par entretien

Variables étoilées :
- `santementale.txt` : variables illustratives multiples pour tester CHD et AFC
- `santementale_individu.txt` : variable ordonnée `*seance_XX` pour tester le suivi longitudinal

Exports générés par `suivi_longitudinal_chd.R` :
- `sante/suivi_meta.csv`
- `sante/classes_par_unite_effectifs.csv`
- `sante/classes_par_unite_pourcentages.csv`
- `sante/termes_dominants_par_unite.csv`
- `sante/ruptures_lexicales.csv`
- `sante/evolution_classes.png`
- `sante/ruptures_lexicales.png`

Usages visés :
- CHD sur entretiens cliniques fictifs
- visualisation de l'évolution des classes d'un entretien à l'autre
- repérage des ruptures lexicales entre deux séances successives
- repérage des termes dominants par entretien

Important :
- ce dossier ne contient **aucune donnée réelle**
- il sert uniquement à tester les calculs, les rendus et le protocole d'analyse
