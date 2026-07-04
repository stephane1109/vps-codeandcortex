### codeandcortex.fr - CHD Rainette

- <a href="https://www.codeandcortex.fr" target="_blank" rel="noopener noreferrer">codeandcortex.fr</a>
- <a href="https://www.codeandcortex.fr/comprendre-chd-methode-reinert/" target="_blank" rel="noopener noreferrer">Comprendre la CHD</a>
- <a href="https://cran.r-project.org/web/packages/rainette/vignettes/introduction_usage.html" target="_blank" rel="noopener noreferrer">Documentation officielle Rainette</a>

### Base de cette reconstruction

Cette application VPS repart du script source historique `chdrainette` :

- import IRaMuTeQ
- découpage du corpus
- DFM `quanteda`
- CHD `rainette`
- statistiques discriminantes
- nuages de mots
- concordancier HTML
- exports CSV / TXT / ZIP

### Ce qui a été volontairement retiré

- spaCy
- reticulate
- NER
- cooccurrences

L'objectif est d'avoir une base plus robuste et plus simple à déployer sur le VPS.

### Paramètres principaux

- **Mode de découpage** : `segment_size` ou `ponctuation`
- **segment_size** : taille des segments avant analyse
- **k** : nombre de classes demandé
- **min_segment_size** : taille minimale d'un segment pour Rainette
- **min_split_members** : effectif minimal pour continuer à scinder une classe
- **min_docfreq** : fréquence documentaire minimale des termes
- **max_p** : seuil de p-value pour les termes discriminants
- **top_n** : nombre de termes affichés dans les nuages de mots

### Langue et stopwords

Le choix de langue sert à :

- estimer grossièrement la langue du corpus
- charger les stopwords `quanteda`

### À propos de `rainette_explor()`

La doc officielle présente `rainette_explor()` comme un **gadget Shiny**. Dans cette version VPS :

- la CHD est affichée dans l'application avec `rainette_plot()`
- le vrai gadget n'est pas injecté dans l'interface serveur
- un fichier `analysis_bundle.rds` est exporté
- un script `ouvrir_rainette_explor.R` est fourni pour ouvrir le vrai gadget dans une session R locale
