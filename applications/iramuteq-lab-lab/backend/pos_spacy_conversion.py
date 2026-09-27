"""Correspondance entre les POS universels spaCy et IRaMuTeQ-Lab."""

POS_SPACY_VERS_IRAMUTEQ = {
    "NOUN": "nom",
    "PROPN": "nom",
    "VERB": "ver",
    "AUX": "aux",
    "ADJ": "adj",
    "ADV": "adv",
    "ADP": "pre",
    "PRON": "pro",
    "CCONJ": "con",
    "SCONJ": "con",
}

POS_SPACY_UNIVERSELS = frozenset({
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "PUNCT",
    "SCONJ",
    "SYM",
    "VERB",
    "X",
})

# Compatibilité avec les anciennes configurations enregistrées avec des codes
# IRaMuTeQ. Les nouvelles analyses transmettent directement les POS spaCy.
POS_IRAMUTEQ_VERS_SPACY = {
    "ADJ_DEM": {"ADJ"},
    "ADJ_IND": {"ADJ"},
    "ADJ_INT": {"ADJ"},
    "ADJ_NUM": {"NUM"},
    "ADJ_POS": {"ADJ"},
    "ADJ_SUP": {"ADJ"},
    "NOM": {"NOUN", "PROPN"},
    "NOM_SUP": {"PROPN"},
    "VER": {"VERB"},
    "VER_SUP": {"VERB"},
    "AUX": {"AUX"},
    "ADJ": {"ADJ"},
    "ADV": {"ADV"},
    "ADV_SUP": {"ADV"},
    "ART_DEF": {"DET"},
    "ART_IND": {"DET"},
    "PRE": {"ADP"},
    "PRO": {"PRON"},
    "PRO_DEM": {"PRON"},
    "PRO_IND": {"PRON"},
    "PRO_PER": {"PRON"},
    "PRO_POS": {"PRON"},
    "PRO_REL": {"PRON"},
    "CON": {"CCONJ", "SCONJ"},
    "ONO": {"INTJ"},
}


def convertir_pos_spacy(pos_spacy: str) -> str:
    """Convertit un POS spaCy ; les catégories non mappées restent identifiables."""
    return POS_SPACY_VERS_IRAMUTEQ.get(
        (pos_spacy or "").upper(),
        "AUTRE_FORME",
    )


def normaliser_selection_pos_spacy(values) -> set[str]:
    """Normalise une sélection POS spaCy et accepte les anciens codes IRaMuTeQ."""
    resultat: set[str] = set()
    for value in values:
        normalized = (value or "").strip().upper()
        if normalized in POS_SPACY_UNIVERSELS:
            resultat.add(normalized)
        else:
            resultat.update(POS_IRAMUTEQ_VERS_SPACY.get(normalized, set()))
    return resultat
