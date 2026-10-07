# CHD Rainette

Adaptation VPS de l'application `chdrainette`.

Cette version n'utilise plus Streamlit.
Le VPS sert maintenant :

- un backend **FastAPI**
- une interface **HTML / CSS / JavaScript** inspirée du graphisme de `iramuteq-lite`
- une exécution **R batch** pour la CHD
- une exploration web des résultats dans l'esprit de `rainette_explor(...)`

L'objectif est de conserver l'analyse Rainette, tout en évitant l'ouverture d'un second navigateur
Shiny séparé comme dans le script d'origine.

## Fonctionnalités conservées

- import d'un corpus texte compatible IRaMuTeQ
- découpage par taille fixe ou par ponctuation
- paramètre `k`
- seuil `min_split_segments`
- `min_docfreq`
- lemmatisation UDPipe optionnelle
- sélection des `UPOS`
- nuages de mots chi² et fréquence
- exports des segments par classe
- exports CSV des mots discriminants et segments

## Fonctionnalités ajoutées pour le VPS

- ticket utilisateur Redis dès l'ouverture de la page
- page web unique avec sidebar, navigation et logs
- rendu dynamique du graphe Rainette selon `k`, `measure`, `n_terms`, `same_scales`, `show_negative`, `text_size`
- exploration des segments par cluster avec filtre terme, taille d'extrait et échantillonnage
- génération du code R correspondant au graphe courant
- téléchargement direct des exports générés

