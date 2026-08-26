# Named Entity Recognition NER (spaCy + règles JSON)

## Fonctionnement
1. spaCy détecte des entités (PER, ORG, LOC, etc...) mais le résultat nécessite bien souvent des corrections
2. Dans le script un mini-filtrage a été ajouté pour supprimer des faux positifs (ponctuation seule, cas bruités, etc...)
3. Vous pouvez ajouter un fichier au format **.json**, ses règles seront appliquées : exclusions et ajouts
   
## Installer spaCy sous R (spacyr + reticulate)
En pratique, **reticulate est nécessaire** parce que **spacyr** s'appuie dessus pour dialoguer avec Python depuis R.

Dans la plupart des cas, vous n'avez pas besoin d'installer `reticulate` à la main :

```r
install.packages("spacyr")
library(spacyr)

spacy_install(lang_models = "fr_core_news_sm")
spacy_initialize(model = "fr_core_news_sm")
```

`install.packages("spacyr")` installe généralement les dépendances requises (dont `reticulate`), puis `spacy_install()` crée un environnement Python isolé avec spaCy.

Si vous voulez diagnostiquer un problème Python ou contrôler précisément l'environnement, installez et chargez explicitement `reticulate`, puis vérifiez la configuration :

```r
install.packages("reticulate")
install.packages("spacyr")

library(reticulate)
py_config()

library(spacyr)
spacy_install(lang_models = "fr_core_news_sm")
spacy_initialize(model = "fr_core_news_sm")
```

En résumé : **oui, `reticulate` est requis**, mais **non, vous n'avez pas forcément besoin de l'installer manuellement** si l'installation standard de `spacyr` fonctionne.

![Import NER](import_ner.png)


## Format attendu du fichier JSON
- Le fichier doit être au **format `.json`**.
Exemple totalement farfellu montrant que vous pouvze exclure et inclure des mots, créer un nouveau label

```json
{
  "exclude_texts": ["ça", "«", "»"],
  "exclude_labels": ["MISC"],
  "include": [
    {"text": "OpenAI", "label": "ORG"},
    {"text": "ChatGPT", "label": "PRODUCT"},
    {"text": "regarder", "label": "VERBE"},
    {"text": "commencer", "label": "VERBE"}
  ]
}
```


## Peut-on créer ses propres labels ?
Oui. Il faut écrire les **LABELS en MAJUSCULES**

- Les entités détectées *nativement* par spaCy gardent les labels du modèle (`PER`, `ORG`, `LOC`, etc.).
- Les entités ajoutées via `include` peuvent utiliser **n'importe quel label** (ex: `VOTRE_LABEL_1`, `VOTRE_LABEL_2`,...).
- Ces labels personnalisés apparaissent ensuite dans la sortie NER (`ent_label`).

Exemple: `{"text": "commencer", "label": "ACTION"}` forcera la présence de `commencer` avec le label `ACTION` si le mot est trouvé dans le texte.

## Labels spaCy déjà existants
Les labels disponibles dépendent du **modèle spaCy chargé**.

### Labels du modèle FR utilisé dans ce projet (`fr_core_news_md`)
- `PER` : personne
- `ORG` : organisation
- `LOC` : lieu
- `MISC` : catégorie diverse (autres entités)

### Labels NER officiels spaCy (Si je ne me trompe pas avec des modeles "lg" on bénéficie de catégories étendus)
- `PERSON`: People, including fictional.
- `NORP`: Nationalities or religious or political groups.
- `FAC`: Buildings, airports, highways, bridges, etc.
- `ORG`: Companies, agencies, institutions, etc.
- `GPE`: Countries, cities, states.
- `LOC`: Non-GPE locations, mountain ranges, bodies of water.
- `PRODUCT`: Objects, vehicles, foods, etc. (Not services.)
- `EVENT`: Named hurricanes, battles, wars, sports events, etc.
- `WORK_OF_ART`: Titles of books, songs, etc.
- `LAW`: Named documents made into laws.
- `LANGUAGE`: Any named language.
- `DATE`: Absolute or relative dates or periods.
- `TIME`: Times smaller than a day.
- `PERCENT`: Percentage, including ”%“.
- `MONEY`: Monetary values, including unit.
- `QUANTITY`: Measurements, as of weight or distance.
- `ORDINAL`: “first”, “second”, etc.
- `CARDINAL`: Numerals that do not fall under another type.

## Signification des champs JSON
- `exclude_texts` : liste de textes d'entité à **rejeter** (insensible à la casse).
- `exclude_labels` : liste de labels d'entité à **rejeter** (ex. `MISC`).
- `include` : liste d'entités à **forcer**.
  - `text` : texte recherché dans le document.
  - `label` : label assigné à l'entité ajoutée.

## Expressions utilisées (important)
Pour `include`, le script utilise une regex Python de la forme :

- `\b<text>\b` avec `re.IGNORECASE`.

Cela veut dire :
- recherche **insensible à la casse** ;
- correspondance sur des **bornes de mot** (`\b`) ;
- évite de matcher au milieu d'un mot.

Exemple : `"text": "Paris"` matche `Paris` mais pas `parisien`.
