"""# Onglet OpenLexicon

Ce module affiche l'onglet Streamlit dédié aux analyses lexicales basées sur
OpenLexicon, en réutilisant le rendu normalisé du lexique.

## Dépendances
- `lexiconnorm.py` : rendu de l'onglet d'analyse OpenLexicon et calculs
  associés.
- `fcts_utils.py` : rappel des connecteurs actuellement sélectionnés.
- Bibliothèques `streamlit` et `pandas` pour la gestion de l'interface et des
  données tabulaires.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from fcts_utils import render_connectors_reminder
from lexiconnorm import render_lexicon_norm_tab


def rendu_openlexicon(tab, df: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    render_connectors_reminder(filtered_connectors)
    render_lexicon_norm_tab(df, filtered_connectors)
