### Analyse morphosyntaxique avec Lexique (fr)

- Documentation OpenLexicon : <a href="https://openlexicon.fr/" target="_blank" rel="noopener noreferrer">OpenLexicon</a>

### Filtrage morphosyntaxique du lexique sélectionné

Les dictionnaires **lexique_fr**, **lexique_en**, **lexique_sp**, **lexique_it** et **lexique_de** utilisés ici proviennent d’**IRaMuTeQ**. Le filtrage repose sur leur colonne morphosyntaxique.

> Le fichier **lexique_de** actuellement fourni contient uniquement des mots-outils (`sw`). Il permet leur reconnaissance, mais ne fournit pas encore les catégories `NOM` et `VER` nécessaires à un filtrage morphosyntaxique complet. Pour une analyse grammaticale allemande, utilisez le mode spaCy avec un modèle allemand installé sur le serveur.

> Contrairement au logiciel IRaMuTeQ (où les catégories des formes sont interprétés comme `1 = active` et `2 = supplémentaire`), le filtrage proposé ici est **binaire**.

![Exemple : clés d'analyse logiciel IRaMuTeQ](images/cles_analyse_iramuteq.png)

Deux configurations principales dans l'interface sont possibles :
1. Si vous **ne cochez pas** le filtrage morphosyntaxique, **tout le corpus** est pris en compte.
2. Si vous **filtrez** sur des catégories morphosyntaxiques (voir la liste ci-dessous), l’analyse porte sur le **corpus filtré** par les catégories sélectionnées.

Option complémentaire :

- **Autre forme** : permet de repérer les termes qui n'ont pas de catégorie morphosyntaxique renseignée (cellule `c_morpho` vide).
  Cette option est utile pour compléter l’analyse avec des éléments non catégorisés, par exemple des **noms propres**.

Noms des catégories de Lexique_fr

- **NOM** : nom commun
- **NOM_SUP** : nom
- **VER** : verbe
- **VER_SUP** : verbe supplémentaire
- **AUX** : auxiliaire
- **ADJ** : adjectif
- **ADJ_SUP** : adjectif
- **ADJ_DEM** : adjectif démonstratif
- **ADJ_IND** : adjectif indéfini
- **ADJ_INT** : adjectif interrogatif
- **ADJ_NUM** : adjectif numéral
- **ADJ_POS** : adjectif possessif
- **ADV** : adverbe
- **ADV_SUP** : adverbe
- **PRE** : préposition
- **CON** : conjonction
- **ART_DEF** : article défini
- **ART_IND** : article indéfini
- **PRO_DEM** : pronom démonstratif
- **PRO_IND** : pronom indéfini
- **PRO_PER** : pronom personnel
- **PRO_POS** : pronom possessif
- **PRO_REL** : pronom relatif
- **ONO** : onomatopée
