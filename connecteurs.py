"""### Gestion du dictionnaire de connecteurs

Ce module encapsule le chargement des connecteurs, la sélection par
l'utilisateur et la persistance dans l'état de session Streamlit. Il sert
d'interface entre les fichiers de dictionnaires et les autres onglets de
l'application."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Dict, Iterable, List

import streamlit as st

from analyses import load_connectors

CONNECTORS_STATE_KEY = "connecteurs_selectionnes"
_dictionary_import = import_module("import")


def get_connectors_path() -> Path:
    """Retourner le chemin du dictionnaire de connecteurs."""

    return _dictionary_import.get_default_dictionary_path()


def load_available_connectors(path: Path | None = None) -> Dict[str, str]:
    """Charger les connecteurs disponibles depuis le fichier de dictionnaire."""

    if _dictionary_import.uses_custom_dictionary():
        return _dictionary_import.get_custom_connectors()

    return load_connectors(path or get_connectors_path())


def set_selected_connectors(connectors: Dict[str, str]) -> None:
    """Enregistrer les connecteurs sélectionnés dans l'état de session."""

    st.session_state[CONNECTORS_STATE_KEY] = connectors


def get_selected_connectors() -> Dict[str, str]:
    """Récupérer les connecteurs sélectionnés depuis l'état de session."""

    return st.session_state.get(CONNECTORS_STATE_KEY, {})


def get_selected_labels(connectors: Iterable[str]) -> List[str]:
    """Retourner les labels distincts triés pour les connecteurs fournis."""

    return sorted(set(connectors))
