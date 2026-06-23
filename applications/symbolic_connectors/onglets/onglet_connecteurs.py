"""# Onglet Connecteurs

Ce module affiche l'onglet Streamlit permettant de charger le dictionnaire
de connecteurs, de sélectionner les étiquettes à conserver et de visualiser
leurs occurrences dans le corpus.

## Dépendances
- `analyses.py` : annotation HTML des connecteurs et génération des styles
  associés.
- `connecteurs.py` : accès au chemin du dictionnaire, sélection et filtrage
  des connecteurs et labels.
- `fcts_utils.py` : rappel visuel des connecteurs sélectionnés dans l'UI.
- Bibliothèque Streamlit et `json` pour l'affichage interactif du fichier
  `connecteurs.json`.
"""
from __future__ import annotations

import json
from importlib import import_module
from typing import Dict
from textwrap import dedent

import streamlit as st

from analyses import annotate_connectors_html, build_label_style_block, count_connectors, generate_label_colors
from connecteurs import (
    get_connectors_path,
    get_selected_connectors,
    get_selected_labels,
    load_available_connectors,
    set_selected_connectors,
)
from fcts_utils import render_connectors_reminder

_dictionary_import = import_module("import")


def rendu_connecteurs(tab) -> None:
    render_connectors_reminder(get_selected_connectors())
    connectors_path = get_connectors_path()

    with tab.expander("Afficher le dictionnaire actif"):
        dictionary_label = _dictionary_import.get_dictionary_label()
        st.caption(f"Source actuelle : `{dictionary_label}`")
        try:
            if _dictionary_import.uses_custom_dictionary():
                st.json(_dictionary_import.get_custom_connectors())
            else:
                with connectors_path.open(encoding="utf-8") as handle:
                    st.json(json.load(handle))
        except FileNotFoundError:
            st.error(
                "Le fichier de connecteurs est introuvable. Vérifiez la présence de "
                "`dictionnaires/connecteurs.json`."
            )
        except json.JSONDecodeError:
            st.error(
                "Impossible de lire le dictionnaire fourni : le fichier ne contient pas un JSON valide."
            )

    try:
        available_connectors = load_available_connectors(connectors_path)
    except FileNotFoundError:
        st.error(
            "Le fichier de connecteurs est introuvable. Vérifiez la présence de "
            "`dictionnaires/connecteurs.json`."
        )
        available_connectors = {}

    if not _dictionary_import.uses_custom_dictionary():
        allowed_labels = {"ALTERNATIVE", "CONDITION", "ALORS", "AND", "RETOUR À LA LIGNE"}
        available_connectors = {
            connector: label
            for connector, label in available_connectors.items()
            if label in allowed_labels
        }

    if not available_connectors:
        st.warning(
            "Aucun connecteur valide disponible dans le dictionnaire fourni. "
            "Ajoutez des entrées ou ajustez les filtres pour continuer."
        )
        return

    all_labels = sorted(set(available_connectors.values()))
    previously_selected = get_selected_labels(
        get_selected_connectors().values()
    ) or all_labels

    selected_labels = st.multiselect(
        "Labels de connecteurs à inclure",
        all_labels,
        default=previously_selected,
        help="Les connecteurs des labels sélectionnés seront utilisés dans tous les onglets.",
        key="connectors_labels_multiselect",
    )

    st.markdown(
        dedent(
            """
            Les connecteurs logiques peuvent être regroupés selon leur fonction, tout en tenant compte de leur stabilité d’interprétation en contexte.
            - Le connecteur « CONDITION » (si…) renvoie aux expressions introduisant une condition et reste généralement assez stable dans son usage et son interprétation.
            - Le connecteur « ALTERNATIVE » (sinon) doit, en revanche, être mobilisé avec prudence, car certaines formes peuvent être ambiguës : par exemple, l’expression « soit » peut marquer une alternative dans la structure « soit… soit… », mais aussi fonctionner comme un adverbe d’affirmation (« Bon, soit ; admettons. »). Dans ce cas, le recours à une bibliothèque NLP permettrait d’affiner la désambiguïsation.
            - Le connecteur « ALORS » relève des connecteurs de conséquence et demeure lui aussi relativement stable dans son utilisation et son interprétation.
            - Le connecteur « AND » est à utiliser avec précaution, car il peut produire une surreprésentation dans le texte, notamment lorsque sa fréquence ne correspond pas à une fonction argumentative réelle.
            - Le connecteur « retour à la ligne » (marqué par un <br> dans le code) est à considérer comme expérimental et doit être utilisé avec prudence, car il relève davantage d’une segmentation typographique que d’un connecteur logique au sens strict.
            """
        )
    )

    filtered_connectors = {
        connector: label
        for connector, label in available_connectors.items()
        if label in selected_labels
    }

    set_selected_connectors(filtered_connectors)

    st.success(f"{len(filtered_connectors)} connecteurs sélectionnés pour les analyses.")
    render_connectors_reminder(filtered_connectors)

