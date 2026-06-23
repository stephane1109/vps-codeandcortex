# anomalies.py
# Détection d'anomalies multimodales (texte, audio, synchronisation/non-verbal)
# Cherche des valeurs extrêmes, ruptures locales et transitions brusques via z robustes.

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import streamlit as st

_ZSCALE = 0.6744897501960817  # constante pour MAD -> écart-type normal


# =========================
# Fonctions utilitaires
# =========================


def _serie_numerique(serie: pd.Series | Sequence[float]) -> pd.Series:
    """Convertit en série numérique float64 et masque NaN/inf."""
    if serie is None:
        return pd.Series(dtype="float64")
    s = pd.to_numeric(pd.Series(serie), errors="coerce")
    s = s.astype("float64")
    s[~np.isfinite(s)] = np.nan
    return s


def robust_z_scores(serie: pd.Series | Sequence[float]) -> pd.Series:
    """Calcule des z-scores robustes via médiane et MAD (Median Absolute Deviation)."""
    s = _serie_numerique(serie)
    if s.empty:
        return s
    med = np.nanmedian(s)
    abs_dev = np.abs(s - med)
    mad = np.nanmedian(abs_dev)
    if not np.isfinite(mad) or mad < 1e-12:
        # MAD nul -> toutes les valeurs identiques, renvoyer z=0
        return pd.Series(np.zeros(len(s), dtype="float64"), index=s.index)
    return pd.Series(_ZSCALE * (s - med) / mad, index=s.index)


def sliding_local_deviation(serie: pd.Series | Sequence[float], fenetre: int = 5) -> pd.Series:
    """Amplitude locale (|valeur - médiane glissante|) sur une fenêtre centrée."""
    s = _serie_numerique(serie)
    if s.empty:
        return s
    fenetre = int(max(3, fenetre))
    rolling_med = s.rolling(window=fenetre, center=True, min_periods=1).median()
    return (s - rolling_med).abs()


@dataclass
class ParametresAnomalies:
    z_extreme: float = 3.2
    z_diff: float = 3.0
    z_local: float = 3.0
    fenetre_local: int = 5


# =========================
# Détection sur une série
# =========================


def _enrichir_evenement(
    df: pd.DataFrame,
    idx,
    axe: str,
    signal: str,
    type_evt: str,
    commentaire: str,
    valeur: float | None,
    score: float | None,
    colonne_temps: str | None,
    delta: float | None = None,
) -> dict:
    evt = {
        "axe": axe,
        "signal": signal,
        "type": type_evt,
        "index": idx,
        "valeur": valeur,
        "score_z": score,
        "commentaire": commentaire,
    }
    if colonne_temps and colonne_temps in df.columns:
        t = df.loc[idx, colonne_temps]
        evt["temps"] = float(t) if np.isfinite(t) else np.nan
    if delta is not None:
        evt["delta"] = delta
    return evt


def anomalies_sur_serie(
    df: pd.DataFrame,
    colonne: str,
    axe: str,
    params: ParametresAnomalies,
    colonne_temps: str | None = None,
) -> list[dict]:
    """Collecte les anomalies (extrêmes, ruptures successives, ruptures locales)."""
    if df is None or colonne not in df.columns:
        return []
    s = _serie_numerique(df[colonne])
    if s.dropna().empty:
        return []

    evenements: list[dict] = []

    # Valeurs extrêmes
    z = robust_z_scores(s)
    mask_extreme = np.abs(z) >= float(params.z_extreme)
    for idx in s.index[mask_extreme]:
        score = float(z.loc[idx])
        direction = "hausse" if score > 0 else "baisse"
        commentaire = f"Valeur extrême ({direction}, z={score:.2f})."
        evenements.append(
            _enrichir_evenement(
                df,
                idx,
                axe,
                colonne,
                "valeur_extreme",
                commentaire,
                float(s.loc[idx]),
                score,
                colonne_temps,
            )
        )

    # Ruptures entre segments successifs (différence première)
    diff = s.diff()
    z_diff = robust_z_scores(diff)
    mask_diff = np.abs(z_diff) >= float(params.z_diff)
    for idx in diff.index[mask_diff]:
        delta = float(diff.loc[idx])
        if not np.isfinite(delta):
            continue
        score = float(z_diff.loc[idx])
        direction = "hausse" if delta > 0 else "baisse"
        commentaire = f"Rupture entre segments successifs ({direction}, Δ={delta:.3f}, z={score:.2f})."
        evenements.append(
            _enrichir_evenement(
                df,
                idx,
                axe,
                colonne,
                "rupture_segment",
                commentaire,
                float(s.loc[idx]) if np.isfinite(s.loc[idx]) else None,
                score,
                colonne_temps,
                delta=delta,
            )
        )

    # Ruptures locales via médiane glissante
    dev_local = sliding_local_deviation(s, fenetre=int(params.fenetre_local))
    z_local = robust_z_scores(dev_local)
    mask_local = z_local >= float(params.z_local)
    for idx in dev_local.index[mask_local]:
        amplitude = float(dev_local.loc[idx])
        if not np.isfinite(amplitude):
            continue
        score = float(z_local.loc[idx])
        commentaire = (
            f"Déviation locale forte (fenêtre={int(params.fenetre_local)}, "
            f"|valeur - médiane|={amplitude:.3f}, z={score:.2f})."
        )
        evenements.append(
            _enrichir_evenement(
                df,
                idx,
                axe,
                colonne,
                "rupture_locale",
                commentaire,
                float(s.loc[idx]) if np.isfinite(s.loc[idx]) else None,
                score,
                colonne_temps,
                delta=amplitude,
            )
        )

    return evenements


# =========================
# Analyse par axe
# =========================


def analyser_axe(
    df: pd.DataFrame | None,
    colonnes: Iterable[str],
    axe: str,
    params: ParametresAnomalies,
    colonne_temps: str | None = None,
) -> pd.DataFrame:
    """Retourne un DataFrame d'anomalies pour un axe donné."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["axe", "signal", "type", "index", "valeur", "score_z", "commentaire", "temps", "delta"])

    evenements: list[dict] = []
    for col in colonnes:
        evenements.extend(anomalies_sur_serie(df, col, axe, params, colonne_temps=colonne_temps))

    if not evenements:
        return pd.DataFrame(columns=["axe", "signal", "type", "index", "valeur", "score_z", "commentaire", "temps", "delta"])
    df_evt = pd.DataFrame(evenements)
    # Tri par temps si dispo, sinon par index
    if "temps" in df_evt.columns and df_evt["temps"].notna().any():
        df_evt = df_evt.sort_values(by=["temps", "signal", "type"], kind="mergesort").reset_index(drop=True)
    else:
        df_evt = df_evt.sort_values(by=["index", "signal", "type"], kind="mergesort").reset_index(drop=True)
    return df_evt


# =========================
# Interface Streamlit
# =========================


def _suggestions_colonnes(df: pd.DataFrame, mots_cles: Sequence[str]) -> list[str]:
    if df is None or df.empty:
        return []
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not mots_cles:
        return numeric_cols
    suggestions = [c for c in numeric_cols if any(mk in c.lower() for mk in mots_cles)]
    return suggestions or numeric_cols


def ui_anomalies(
    df_texte: pd.DataFrame | None = None,
    df_audio: pd.DataFrame | None = None,
    df_sync: pd.DataFrame | None = None,
    temps_texte: str | None = "t_debut",
    temps_audio: str | None = "t_debut",
    temps_sync: str | None = "t",
) -> None:
    """Page Streamlit pour explorer les anomalies multimodales."""
    st.title("Détection d'anomalies multimodales")
    st.markdown(
        """
        Cette page cherche automatiquement les **variations anormales** sur trois axes :
        - **Texte** : ratios de temps verbaux, poussées de déictiques ou marqueurs de planification,
          ruptures entre segments successifs.
        - **Audio** : pics ou chutes d'intensité, débits de parole inhabituels, pauses anormalement longues/denses.
        - **Synchronisation & non-verbal** : désynchronisations image/voix, sauts d'unités d'action (AUs) ou
          d'orientation de tête.

        Les détections s'appuient sur des *scores z robustes* (médiane + MAD), des différences entre segments
        et des fenêtres glissantes pour repérer des ruptures locales. Les seuils sont ajustables ci-dessous.
        """
    )

    with st.expander("Paramètres de détection"):
        z_extreme = st.slider("Seuil |z| pour valeurs extrêmes", 2.0, 6.0, value=3.2, step=0.1)
        z_diff = st.slider("Seuil |z| pour ruptures successives", 2.0, 6.0, value=3.0, step=0.1)
        z_local = st.slider("Seuil |z| pour ruptures locales", 2.0, 6.0, value=3.0, step=0.1)
        fenetre_local = st.number_input("Taille de la fenêtre glissante", min_value=3, max_value=101, value=5, step=1)

    params = ParametresAnomalies(
        z_extreme=float(z_extreme),
        z_diff=float(z_diff),
        z_local=float(z_local),
        fenetre_local=int(fenetre_local),
    )

    def _section(axe: str, df_source: pd.DataFrame | None, temps_col: str | None, mots_cles: Sequence[str]):
        st.subheader(axe)
        if df_source is None or df_source.empty:
            st.info("Aucune donnée fournie pour cet axe.")
            return
        suggestions = _suggestions_colonnes(df_source, mots_cles)
        colonnes = st.multiselect(
            "Colonnes à surveiller",
            options=df_source.select_dtypes(include=["number"]).columns.tolist(),
            default=suggestions,
            key=f"cols_{axe}"
        )
        if not colonnes:
            st.warning("Sélectionnez au moins une colonne numérique.")
            return

        df_evt = analyser_axe(df_source, colonnes, axe, params, colonne_temps=temps_col)
        if df_evt.empty:
            st.success("Aucune anomalie détectée avec les paramètres courants.")
            return
        st.dataframe(df_evt, use_container_width=True)

    _section("Texte", df_texte, temps_texte, ["ratio", "deict", "planif", "verbe"])
    _section("Audio", df_audio, temps_audio, ["intens", "debit", "pause", "energy", "pitch"])
    _section("Synchronisation & non-verbal", df_sync, temps_sync, ["delta", "sync", "au", "orientation", "tete"])


__all__ = [
    "ParametresAnomalies",
    "robust_z_scores",
    "sliding_local_deviation",
    "anomalies_sur_serie",
    "analyser_axe",
    "ui_anomalies",
]
