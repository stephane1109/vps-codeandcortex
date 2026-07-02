### Analyse morphosyntaxique avec spaCy

- Documentation principale : <https://spacy.io/usage>
- Linguistic Features (POS, morphology) : <https://spacy.io/usage/linguistic-features>

### Traduction FR des POS (spaCy / Universal POS)

- **ADJ** : adjectif
- **ADP** : adposition (préposition)
- **ADV** : adverbe
- **AUX** : auxiliaire
- **CCONJ** : conjonction de coordination
- **DET** : déterminant
- **INTJ** : interjection
- **NOUN** : nom
- **NUM** : numéral
- **PART** : particule
- **PRON** : pronom
- **PROPN** : nom propre
- **PUNCT** : ponctuation
- **SCONJ** : conjonction de subordination
- **SYM** : symbole
- **VERB** : verbe
- **X** : autre / catégorie inconnue


### Paramétrage côté interface (Shiny)

Dans l’interface, la section **Paramétrages SpaCy** permet :

- d’activer le **filtrage morphosyntaxique (spaCy)**,
- de sélectionner les POS à conserver parmi la liste Universal POS,
- de combiner ce filtrage avec la lemmatisation selon les besoins analytiques.

### Conseils pratiques

- Pour une analyse thématique : commencer par `NOUN,VERB,ADJ`.
- Pour préserver les noms d’organisations/personnes : ajouter `PROPN`.
- Pour éviter le bruit grammatical : exclure en général `DET`, `PRON`, `CCONJ`, `SCONJ`, `PART`.
