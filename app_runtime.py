from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from ticket_gate import enforce_streamlit_access, keep_ticket_alive


APP_ID = (os.getenv("APP_TICKET_ID", "Analyse_MM") or "Analyse_MM").strip() or "Analyse_MM"
APP_LABEL = "Analyse MM"

# #### VARIABLE D'ENVIRONNEMENT A MODIFIER SI BESOIN
# APP_DATA_DIR controle l'emplacement des fichiers temporaires et des sorties.
# En local, l'application retombe sur /tmp/appdata.
# Sur le VPS, regle APP_DATA_DIR=/data/app dans Coolify pour garder un espace dedie.
APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/tmp/appdata")).resolve()


def apply_page_style() -> None:
    st.markdown(
        """
        <style>
          section.main > div.block-container,
          .main .block-container,
          .block-container,
          div[data-testid="stMainBlockContainer"],
          div[data-testid="stAppViewBlockContainer"] {
            padding-top: 0 !important;
            margin-top: 0 !important;
          }
          .block-container > div:first-child,
          div[data-testid="stMainBlockContainer"] > div:first-child,
          div[data-testid="stAppViewBlockContainer"] > div:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
          }
          h1,
          div[data-testid="stHeading"] h1 {
            margin-top: 0 !important;
            padding-top: 0 !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_app_data_dir() -> Path:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DATA_DIR


def enforce_access():
    ensure_app_data_dir()
    return enforce_streamlit_access(APP_ID, APP_LABEL)


def heartbeat():
    return keep_ticket_alive(APP_ID, APP_LABEL)
