"""# Onglet TF-IDF

Ce module connecte l'onglet Streamlit responsable du calcul TF-IDF et de son
affichage pour le corpus filtré.

## Dépendances
- `tf_idf.py` : logique principale de calcul et de rendu TF-IDF réutilisée
  ici.
- Bibliothèques `streamlit` et `pandas` pour transmettre les données et les
  connecteurs filtrés à la fonction de rendu.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from tf_idf import render_tfidf_tab


def rendu_tfidf(tab, df: pd.DataFrame, filtered_connectors: Dict[str, str]) -> None:
    del tab, filtered_connectors
    render_tfidf_tab(df)
