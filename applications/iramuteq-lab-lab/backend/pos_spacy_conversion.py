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


def convertir_pos_spacy(pos_spacy: str) -> str:
    """Convertit un POS spaCy ; les catégories non mappées restent identifiables."""
    return POS_SPACY_VERS_IRAMUTEQ.get(
        (pos_spacy or "").upper(),
        "AUTRE_FORME",
    )
