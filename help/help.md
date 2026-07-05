### codeandcortex.fr - CHD Rainette

- <a href="https://www.codeandcortex.fr" target="_blank" rel="noopener noreferrer">codeandcortex.fr</a>
- <a href="https://www.codeandcortex.fr/comprendre-chd-methode-reinert/" target="_blank" rel="noopener noreferrer">Comprendre la CHD</a>
- <a href="https://cran.r-project.org/web/packages/rainette/vignettes/introduction_usage.html" target="_blank" rel="noopener noreferrer">Documentation officielle Rainette</a>

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

La doc officielle présente `rainette_explor()` comme un **gadget Shiny**. Dans cette version VPS, l'architecture a été refondue en vraie application Shiny native pour reprendre directement la logique de l'explorateur Rainette :

- onglet **Summary** avec les vrais réglages Rainette
- onglet **Cluster documents** avec la navigation dans les segments de classes
- bouton **Get R code** pour réexporter le code de la vue courante
- un fichier `analysis_bundle.rds` reste exporté pour réouvrir la même analyse dans une session R locale si besoin
