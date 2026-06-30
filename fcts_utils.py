"""Fonctions utilitaires partagées avec l'application Streamlit.

Chaque fonction inclut une description en Markdown pour documenter son objectif,
ses paramètres et son retour, afin de clarifier son intégration dans les onglets
thématiques.
"""

from __future__ import annotations

from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from analyses import count_connectors_by_label


def display_centered_chart(chart: alt.Chart) -> None:
    """## Afficher un graphique Altair centré

    - **Objectif** : insérer un graphique Altair dans la colonne centrale pour éviter
      qu'il ne soit collé aux bords de la page.
    - **Paramètres** :
      - `chart` : instance Altair déjà configurée.
    - **Retour** : `None` — le graphique est affiché avec `use_container_width=True`.
    """

    center_col = st.columns([1, 2, 1])[1]
    center_col.altair_chart(chart, use_container_width=True)


def build_annotation_style_block(label_style_block: str) -> str:
    """## Générer le bloc de styles pour les annotations HTML

    - **Objectif** : centraliser la feuille de style utilisée pour colorer et encadrer
      les connecteurs annotés dans les textes.
    - **Paramètres** :
      - `label_style_block` : CSS additionnel produit par `build_label_style_block`.
    - **Retour** : chaîne HTML contenant le bloc `<style>` prêt à être injecté.
    """

    return f"""
    <style>
    .connector-annotation {{
        background-color: #eef3ff;
        border-radius: 4px;
        padding: 2px 6px;
        margin: 0 2px;
        display: inline-block;
        border: 1px solid #c3d4ff;
    }}
    .connector-label {{
        color: #1a56db;
        font-weight: 700;
        margin-right: 6px;
    }}
    .connector-text {{
        color: #6b7280;
        font-weight: 500;
    }}
    .annotated-container {{
        line-height: 1.6;
        font-size: 15px;
        margin-bottom: 24px;
        white-space: pre-wrap;
    }}
    {label_style_block}
    </style>
    """


def parse_iramuteq(content: str) -> List[Dict[str, str]]:
    """## Parser un fichier IRaMuTeQ

    - **Objectif** : transformer le contenu brut d'un fichier IRaMuTeQ en liste de
      dictionnaires exploitables par Pandas.
    - **Paramètres** :
      - `content` : texte complet du fichier importé.
    - **Retour** : liste de dictionnaires contenant l'en-tête (`entete`), le texte
      associé (`texte`) et les variables/modèles détectés.
    """

    lines = content.splitlines()
    records: List[Dict[str, str]] = []
    index = 0

    while index < len(lines):
        line = lines[index].strip()

        if line.startswith("****"):
            tokens = line[4:].strip().split()
            variables: Dict[str, str] = {}

            for token in tokens:
                if token.startswith("*") and "_" in token:
                    name, modality = token[1:].split("_", maxsplit=1)
                    variables[name.strip()] = modality.strip()

            index += 1
            text_lines: List[str] = []

            while index < len(lines) and not lines[index].strip().startswith("****"):
                text_lines.append(lines[index])
                index += 1

            records.append(
                {
                    **variables,
                    "entete": line,
                    "texte": "\n".join(text_lines).strip(),
                }
            )
        else:
            index += 1

    return records


def build_dataframe(records: List[Dict[str, str]]) -> pd.DataFrame:
    """## Construire un DataFrame prêt pour les analyses

    - **Objectif** : convertir la liste d'enregistrements IRaMuTeQ en DataFrame.
    - **Paramètres** :
      - `records` : sortie de `parse_iramuteq`.
    - **Retour** : `pd.DataFrame` contenant l'ensemble des variables et du texte.
    """

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def build_variable_stats(
    dataframe: pd.DataFrame,
    variables: List[str],
    connectors: Dict[str, str],
    labels: List[str],
) -> pd.DataFrame:
    """## Calculer les occurrences par variable/modalité

    - **Objectif** : générer un tableau des occurrences de connecteurs par variable,
      modalité et label.
    - **Paramètres** :
      - `dataframe` : DataFrame filtré contenant le texte et les variables.
      - `variables` : variables IRaMuTeQ à analyser.
      - `connectors` : dictionnaire `connecteur -> label` sélectionné dans l'UI.
      - `labels` : liste des labels retenus pour l'affichage.
    - **Retour** : `pd.DataFrame` avec les colonnes `variable`, `modalite`, `label`,
      `occurrences`.
    """

    rows: List[Dict[str, str | int]] = []

    for variable in variables:
        if variable not in dataframe.columns:
            continue

        for modality, subset in dataframe.dropna(subset=[variable]).groupby(variable):
            modality_text = " ".join(subset["texte"].dropna())
            label_counts = count_connectors_by_label(modality_text, connectors)

            for label in labels:
                rows.append(
                    {
                        "variable": variable,
                        "modalite": modality,
                        "label": label,
                        "occurrences": label_counts.get(label, 0),
                    }
                )

    return pd.DataFrame(rows)


def render_connectors_reminder(connectors: Dict[str, str]) -> None:
    """## Rappeler les connecteurs sélectionnés

    - **Objectif** : afficher un résumé lisible des connecteurs actuellement actifs
      dans l'interface.
    - **Paramètres** :
      - `connectors` : dictionnaire `connecteur -> label` provenant du cache Streamlit.
    - **Retour** : `None` — un message d'information ou un résumé est écrit dans
      l'application.
    """

    if not connectors:
        st.info(
            "Aucun connecteur sélectionné pour les analyses. Rendez-vous dans l'onglet « Connecteurs » pour en choisir."
        )
        return

    connectors_by_label: Dict[str, List[str]] = {}
    for connector, label in connectors.items():
        connectors_by_label.setdefault(label, []).append(connector)

    label_summaries = [
        f"{label} ({len(names)})" for label, names in sorted(connectors_by_label.items())
    ]
    st.caption(
        "Connecteurs sélectionnés par catégorie — "
        + ", ".join(label_summaries)
        + f" — Total : {len(connectors)}"
    )
