"""# Onglet Sous-corpus

Ce module présente l'onglet Streamlit permettant d'extraire automatiquement
les segments marqués IRaMuTeQ pour constituer un sous-corpus téléchargeable.

## Dépendances
- `souscorpus.py` : construction de la liste de segments correspondant aux
  connecteurs sélectionnés.
- `fcts_utils.py` : rappel des connecteurs actifs pour contextualiser
  l'extraction.
- Bibliothèque Streamlit pour l'affichage, la zone de texte et le bouton de
  téléchargement.
"""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

from fcts_utils import render_connectors_reminder
from souscorpus import build_subcorpus


def rendu_sous_corpus(tab, records: List[dict], filtered_connectors: Dict[str, str]) -> None:
    render_connectors_reminder(filtered_connectors)
    st.write(
        "Extraction automatique des segments dont la première ligne contient les marqueurs "
        "IRaMuTeQ (encodage commençant par `**** *`). Le sous-corpus peut être copié, "
        "téléchargé au format texte pour être réutilisé pour d'autres analyses."
    )

    subcorpus_segments = build_subcorpus(records, filtered_connectors)

    if not subcorpus_segments:
        st.info(
            "Aucun segment avec encodage `**** *` n'a été trouvé dans le fichier téléversé."
        )
        return

    subcorpus_text = "\n\n".join(subcorpus_segments)
    st.text_area(
        "Segments du sous-corpus", subcorpus_text, height=260, key="subcorpus_text"
    )

    st.download_button(
        label="Télécharger le sous-corpus (TXT)",
        data=subcorpus_text,
        file_name="sous_corpus.txt",
        mime="text/plain",
    )
