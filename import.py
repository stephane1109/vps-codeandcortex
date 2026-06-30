"""Gestion de l'import d'un dictionnaire JSON de connecteurs.

Ce module permet de choisir entre le dictionnaire par défaut et un
fichier JSON fourni par l'utilisateur. Les dictionnaires personnalisés
sont stockés dans l'état de session pour être réutilisés lors des
reruns Streamlit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import streamlit as st

APP_DIR = Path(__file__).parent
DEFAULT_DICTIONARY_PATH = APP_DIR / "dictionnaires" / "connecteurs.json"

_CUSTOM_CONNECTORS_KEY = "custom_connectors_dict"
_DICTIONARY_CHOICE_KEY = "dictionary_choice"
_DICTIONARY_LABEL_KEY = "dictionary_label"


def _validate_connectors_payload(payload: object) -> Dict[str, str]:
    """Valider la structure du dictionnaire JSON fourni par l'utilisateur."""

    if not isinstance(payload, dict):
        raise ValueError("Le fichier JSON doit contenir un objet {clé: label}.")

    connectors: Dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError("Chaque entrée doit utiliser des chaînes pour la clé et la valeur.")

        # On retire uniquement les espaces et tabulations pour permettre les connecteurs
        # constitués de retours à la ligne ("\n" ou "\r\n"). Un strip() classique
        # supprimerait ces clés et empêcherait leur détection.
        key = raw_key.strip(" \t")
        if not key:
            continue

        connectors[key] = raw_value.strip() or raw_value

    if not connectors:
        raise ValueError("Aucun connecteur valide n'a été trouvé dans le fichier JSON fourni.")

    return connectors


def _decode_uploaded_json(uploaded_file) -> Dict[str, str] | None:
    try:
        payload = json.loads(uploaded_file.getvalue().decode("utf-8"))
    except UnicodeDecodeError:
        st.error("Impossible de décoder le dictionnaire en UTF-8.")
        return None
    except json.JSONDecodeError:
        st.error("Le fichier téléversé n'est pas un JSON valide.")
        return None

    try:
        return _validate_connectors_payload(payload)
    except ValueError as exc:  # pragma: no cover - feedback utilisateur
        st.error(str(exc))
        return None


def render_dictionary_selector() -> None:
    """Afficher le sélecteur de dictionnaire dans la page d'accueil."""

    st.subheader("Dictionnaire de connecteurs")

    option_labels = {
        "default": "Utiliser le dictionnaire fourni (dictionnaires/connecteurs.json)",
        "custom": "Importer mon dictionnaire JSON",
    }
    current_choice = st.session_state.get(_DICTIONARY_CHOICE_KEY, "default")

    choice_key = st.radio(
        "Quel dictionnaire voulez-vous utiliser ?",
        list(option_labels.keys()),
        format_func=lambda key: option_labels[key],
        index=0 if current_choice == "default" else 1,
        key="dictionary_choice_radio",
    )
    st.session_state[_DICTIONARY_CHOICE_KEY] = choice_key

    dictionary_label = "connecteurs.json"

    if choice_key == "custom":
        uploaded_dictionary = st.file_uploader(
            "Téléversez un fichier JSON structuré sous la forme {\"connecteur\": \"LABEL\"}",
            type=["json"],
            key="dictionary_uploader",
            help="Chaque clé doit être un connecteur et chaque valeur l'étiquette associée.",
        )
        if uploaded_dictionary:
            connectors = _decode_uploaded_json(uploaded_dictionary)
            if connectors:
                st.session_state[_CUSTOM_CONNECTORS_KEY] = connectors
                dictionary_label = uploaded_dictionary.name
                st.success(f"{len(connectors)} connecteurs chargés depuis {uploaded_dictionary.name}.")
            else:
                st.session_state.pop(_CUSTOM_CONNECTORS_KEY, None)
        else:
            connectors = st.session_state.get(_CUSTOM_CONNECTORS_KEY)
            if connectors:
                dictionary_label = st.session_state.get(_DICTIONARY_LABEL_KEY, "dictionnaire personnalisé")
                st.info(
                    f"{len(connectors)} connecteurs personnalisés déjà chargés seront réutilisés."
                )
            else:
                st.warning("Aucun dictionnaire personnalisé chargé. Le dictionnaire par défaut sera utilisé.")
    else:
        st.session_state.pop(_CUSTOM_CONNECTORS_KEY, None)

    st.session_state[_DICTIONARY_LABEL_KEY] = dictionary_label


def uses_custom_dictionary() -> bool:
    """Indiquer si l'utilisateur a sélectionné un dictionnaire personnalisé."""

    return bool(
        st.session_state.get(_DICTIONARY_CHOICE_KEY) == "custom"
        and st.session_state.get(_CUSTOM_CONNECTORS_KEY)
    )


def get_custom_connectors() -> Dict[str, str]:
    """Retourner le dictionnaire personnalisé stocké en session, le cas échéant."""

    return st.session_state.get(_CUSTOM_CONNECTORS_KEY, {})


def get_dictionary_label() -> str:
    """Libellé du dictionnaire actuellement sélectionné (pour l'affichage)."""

    return st.session_state.get(_DICTIONARY_LABEL_KEY, "connecteurs.json")


def get_default_dictionary_path() -> Path:
    """Chemin du dictionnaire fourni par l'application."""

    return DEFAULT_DICTIONARY_PATH
