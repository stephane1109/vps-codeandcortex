### Analyse morphosyntaxique avec Lexique (fr)

- Documentation OpenLexicon : <a href="https://openlexicon.fr/" target="_blank" rel="noopener noreferrer">OpenLexicon</a>

### Filtrage morphosyntaxique du lexique sélectionné

Les dictionnaires **lexique_fr**, **lexique_en**, **lexique_sp** et **lexique_it** utilisés ici proviennent d’**IRaMuTeQ**. Le filtrage repose sur leur colonne morphosyntaxique.

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

### Catégories POS spaCy

Lorsque la langue sélectionnée utilise spaCy, le filtrage morphosyntaxique repose sur les catégories POS universelles attribuées à chaque mot par le modèle de langue.

- Sans filtrage morphosyntaxique, toutes les catégories sont conservées.
- Avec le filtrage activé, seules les catégories POS cochées sont conservées.
- La sélection proposée par défaut est `NOUN`, `PROPN`, `VERB` et `ADJ`.
- La lemmatisation est indépendante du filtrage : elle remplace, si elle est activée, la forme du mot par son lemme spaCy.

- `NOUN` : nom commun, exporté comme `nom`.
- `PROPN` : nom propre, exporté comme `nom`.
- `VERB` : verbe, exporté comme `ver`.
- `AUX` : auxiliaire, exporté comme `aux`.
- `ADJ` : adjectif, exporté comme `adj`.
- `ADV` : adverbe, exporté comme `adv`.
- `ADP` : préposition ou postposition, exportée comme `pre`.
- `PRON` : pronom, exporté comme `pro`.
- `CCONJ` : conjonction de coordination, exportée comme `con`.
- `SCONJ` : conjonction de subordination, exportée comme `con`.
- `DET` : déterminant, exporté comme `AUTRE_FORME`.
- `INTJ` : interjection, exportée comme `AUTRE_FORME`.
- `NUM` : nombre, exporté comme `AUTRE_FORME`.
- `PART` : particule, exportée comme `AUTRE_FORME`.
- `PUNCT` : ponctuation, exportée comme `AUTRE_FORME`.
- `SYM` : symbole, exporté comme `AUTRE_FORME`.
- `X` : catégorie indéterminée, exportée comme `AUTRE_FORME`.

`AUTRE_FORME` ne signifie pas nécessairement que spaCy n’a pas reconnu le mot. Cette valeur indique aussi qu’aucune correspondance IRaMuTeQ Lab spécifique n’est actuellement définie pour la catégorie POS spaCy concernée.
