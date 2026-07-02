"""### Application Streamlit des opérateurs symboliques

Ce fichier gère l'interface utilisateur : chargement des données,
assemblage des onglets et préparation des données partagées.
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from connecteurs import get_selected_connectors  # noqa: E402
from addannotations import render_manual_annotations  # noqa: E402
from ticket_gate import enforce_streamlit_access  # noqa: E402
from onglets import (  # noqa: E402
    parse_upload,
    rendu_connecteurs,
    rendu_chi2,
    rendu_densite,
    rendu_donnees_brutes,
    rendu_donnees_importees,
    rendu_hash,
    rendu_lisibilite,
    rendu_ngram,
    rendu_anova,
    rendu_openlexicon,
    rendu_patterns,
    rendu_regex_motifs,
    rendu_simi_cosinus,
    rendu_sous_corpus,
    rendu_tfidf,
)

_dictionary_import = import_module("import")


APP_VERSION = "0.3.0-beta"


def _load_uploaded_content(
    uploaded_file: st.runtime.uploaded_file_manager.UploadedFile | None,
) -> str | None:
    """Load content from upload or from the current Streamlit session.

    Order of precedence:
    1. Fresh upload from the user.
    2. Content preserved in ``st.session_state`` during reruns.
    """

    if uploaded_file:
        try:
            content = uploaded_file.getvalue().decode("utf-8")
        except UnicodeDecodeError:
            st.error("Impossible de décoder le fichier téléversé en UTF-8.")
            return None

        st.session_state["uploaded_content"] = content
        st.session_state["uploaded_filename"] = uploaded_file.name

        return content

    # Pas d'upload en cours : chercher dans la session Streamlit
    cached_content = st.session_state.get("uploaded_content")
    if cached_content:
        return cached_content

    return None


def main() -> None:
    st.set_page_config(page_title="Symbolic Connectors", layout="wide")
    # #### VARIABLES D'ENVIRONNEMENT - CONTROLE D'ACCES REDIS POUR LE VPS
    # Variables a ajuster dans Coolify :
    # - REDIS_URL
    # - APP_TICKET_MAX_ACTIVE=1 pour garder l'application exclusive
    # - APP_TICKET_COST
    # - CAPACITE_SERVEUR
    # - APP_TICKET_TTL_SECONDS
    enforce_streamlit_access("symbolic_connectors", "Symbolic Connectors")

    st.title("Symbolic Connectors")
    st.markdown(
        "Symbolic Connectors : ce titre renvoie au courant symbolique en IA, "
        "qui s’appuie sur une logique de programme et de règles (par opposition au "
        "connexionnisme, plus proche de l’analogie avec le cerveau).\n\n"
        "Le nom convient bien à l’objectif de cette application : repérer, dans les "
        "réponses des grands modèles de langage (LLM), des traces de “langage machine”, "
        "en particulier des structures linguistiques proches de la programmation. "
        "(logique conditionnelle - si, alors, sinon, ou, et…).\n\n"
        "Pour des raisons d’interopérabilité, le corpus doit être formaté selon les "
        "exigences d’IRaMuTeQ : chaque texte commence par une ligne d’en-tête du type "
        "`**** *variable_modalité`.\n\n"
        "Pour l’instant, l’application repose sur un fichier `connecteurs.json` "
        "(visible dans le repertoire Github : `/dictionnaires/connecteurs.json`) "
        "et sur des règles regex. À terme, l’idéal serait de généraliser l’approche "
        "avec une bibliothèque NLP (par exemple spaCy et/ou BERT), afin de rendre la "
        "détection moins rigide que des motifs regex. Mais je suis limité par l’hébergement "
        "sur Streamlit Cloud (version gratuite), qui impose des ressources restreintes. "
        "Toutefois, les stopwords sont filtrés avec NLTK (léger), et l’onglet « patterns » "
        "s’appuie sur spaCy."
    )
    st.caption("[www.codeandcortex.fr](https://www.codeandcortex.fr)")
    st.caption(f"Version {APP_VERSION} (dév en cours - 03-01-2026)")
    st.markdown("---")
    st.write(
        "Téléversez un fichier texte IRaMuTeQ. Chaque article doit démarrer par "
        "une ligne de variables, par exemple `**** *model_gpt *prompt_1`."
    )

    mode_choice = st.radio(
        "Mode de travail",
        ["Analyser un corpus", "Annoter un texte"],
        horizontal=True,
    )

    if mode_choice == "Annoter un texte":
        st.info(
            "Importez un texte brut pour l'annoter puis définissez vos labels avant de "
            "générer le fichier JSON."
        )
        render_manual_annotations()
        return

    _dictionary_import.render_dictionary_selector()
    uploaded_file = st.file_uploader("Fichier IRaMuTeQ", type=["txt"])  # type: ignore[assignment]
    content = _load_uploaded_content(uploaded_file)

    tabs = st.tabs(
        [
            "Import",
            "Connecteurs",
            "Données brutes",
            "Sous corpus",
            "Densité",
            "ANOVA",
            "OpenLexicon",
            "Hash",
            "Regex motifs",
            "Patterns",
            "Test de lisibilité",
            "N-gram",
            "TF-IDF",
            "Simi cosinus",
            "Test du chi2",
        ]
    )

    if content is None:
        upload_message = (
            "Téléversez un fichier texte IRaMuTeQ pour accéder aux analyses disponibles dans les onglets."
        )

        with tabs[0]:
            st.subheader("Données importées")
            st.info(upload_message)

        for tab in tabs[1:]:
            with tab:
                st.info(upload_message)

        return

    records, df = parse_upload(content)

    if not records:
        st.warning("Aucune entrée valide trouvée dans le fichier fourni.")
        return

    with tabs[1]:
        rendu_connecteurs(tabs[1])

    filtered_connectors = get_selected_connectors()

    with tabs[0]:
        rendu_donnees_importees(tabs[0], df, filtered_connectors)

    with tabs[2]:
        donnees_brutes = rendu_donnees_brutes(tabs[2], df, filtered_connectors)

    if donnees_brutes is None:
        return

    filtered_df, selected_variables, combined_text = donnees_brutes

    with tabs[3]:
        rendu_sous_corpus(tabs[3], records, filtered_connectors)

    with tabs[4]:
        rendu_densite(tabs[4], df, filtered_connectors)

    with tabs[5]:
        rendu_anova(tabs[5], filtered_df, filtered_connectors)

    with tabs[6]:
        rendu_openlexicon(tabs[6], df, filtered_connectors)

    with tabs[7]:
        rendu_hash(tabs[7], filtered_df, filtered_connectors, combined_text)

    with tabs[8]:
        rendu_regex_motifs(tabs[8], combined_text, filtered_connectors)

    with tabs[9]:
        rendu_patterns(tabs[9], filtered_df, combined_text, selected_variables)

    with tabs[10]:
        rendu_lisibilite(tabs[10], df, filtered_connectors)

    with tabs[11]:
        rendu_ngram(tabs[11], filtered_df, filtered_connectors)

    with tabs[12]:
        rendu_tfidf(tabs[12], df, filtered_connectors)

    with tabs[13]:
        rendu_simi_cosinus(tabs[13], df)

    with tabs[14]:
        rendu_chi2(tabs[14], filtered_df, filtered_connectors)


if __name__ == "__main__":
    main()
