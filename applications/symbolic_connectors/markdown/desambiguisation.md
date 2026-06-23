# Désambiguïsation des connecteurs spaCy

Ce document résume la syntaxe spaCy pour ajouter des contraintes grammaticales (`LEMMA`, `POS`, `MORPH`) dans les patrons du `Matcher`, ainsi que des conseils sur leur usage.

## Syntaxe spaCy des contraintes
- **Clé / token pattern** : chaque élément d’un pattern est un dictionnaire appliqué à un token.
- **LEMMA** : `{ "LEMMA": "ou" }` pour matcher le lemme.
- **POS** (part-of-speech) : `{ "LEMMA": "ou", "POS": "CCONJ" }`.
- **MORPH** : se déclare avec une chaîne de traits morphologiques ou un dictionnaire ; la version courante est la chaîne, par exemple `{ "LEMMA": "où", "POS": "PRON", "MORPH": "Case=Loc" }`. On peut combiner plusieurs traits : `"MORPH": "Number=Sing|Gender=Fem"`.

### Exemple complet de désambiguïsation « ou » vs « où »
```python
matcher.add(
    "OU_CONJ",
    [[{"LEMMA": "ou", "POS": "CCONJ"}]]
)
matcher.add(
    "OU_PRON_ADVERB",
    [[{"LEMMA": "où", "POS": {"IN": ["PRON", "ADV"]}, "MORPH": "Case=Loc"}]]
)
```

### Exemple pour une expression multi-mots
```python
matcher.add(
  "AU_CAS_OU",
  [
    [
      {"LOWER": "au"},
      {"LOWER": "cas"},
      {"LOWER": "où", "POS": "SCONJ", "MORPH": "Case=Loc"}
    ]
  ]
)
```

## Faut-il ajouter des contraintes partout ?
- **Non, ce n’est pas obligatoire** : gardez les entrées simples pour les connecteurs non ambigus.
- Ajoutez les contraintes (`LEMMA`/`POS`/`MORPH`) seulement là où elles réduisent les faux positifs (homographes comme « ou/où », « quand/quant », etc.).
- Pour les expressions multi-mots, chaque token du pattern peut avoir ses propres contraintes. Exemple : le dernier token de « au cas où » porte la contrainte morphologique.

## Intégration avec un fichier JSON de connecteurs
- Vous pouvez enrichir seulement certaines entrées. Les autres peuvent rester au format simple `chaîne → catégorie`.
- Lors du chargement, si une entrée possède un champ `spaCy_pattern`, utilisez-le pour `Matcher.add`; sinon, générez un pattern minimal basé sur le texte exact (par exemple `{"LOWER": "sinon"}`).
- Conservez vos clés existantes (par exemple `"sinon": "ALTERNATIVE"`) et n’ajoutez des contraintes que pour les items ambigus.

### Exemple d’écriture pour « ou » dans un JSON

- **Entrée simple (non désambiguïsée)** :

```json
"ou": "ALTERNATIVE"
```

- **Entrée enrichie pour guider spaCy** (recommandé si vous souhaitez distinguer « ou »/« où ») :

```json
"ou": {
  "category": "ALTERNATIVE",
  "spaCy_pattern": [
    [
      { "LEMMA": "ou", "POS": "CCONJ" }
    ]
  ]
}
```

Vous pouvez ajouter une entrée séparée pour « où » avec un autre `spaCy_pattern` (par exemple `LEMMA="où"`, `POS` dans `PRON/ADV`, `MORPH="Case=Loc"`) si vous voulez des catégories distinctes.
