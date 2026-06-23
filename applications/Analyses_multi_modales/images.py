# images.py
# Affichage des images synchronisées avec texte aligné mot-à-mot.
# Corrige l’effet “début de segment répété” et gère les pauses (aucun mot à proximité).

from __future__ import annotations
import numpy as np
import pandas as pd
import streamlit as st

# =========================
# utilitaires internes
# =========================

def _get_image_bytes_by_name(name: str) -> bytes | None:
    """récupérer les octets d’une image depuis st.session_state['images_store']."""
    for it in st.session_state.get("images_store", []) or []:
        if it.get("name") == name:
            return it.get("bytes")
    return None

def _normaliser_df_mots(df_mots: pd.DataFrame) -> pd.DataFrame:
    """
    s’assure que df_mots possède au minimum les colonnes:
    ['t_debut_mot','t_fin_mot','mot','idx_global']
    et qu’elle est triée par t_debut_mot.
    """
    if df_mots is None or df_mots.empty:
        return pd.DataFrame(columns=["t_debut_mot", "t_fin_mot", "mot", "idx_global"])
    df = df_mots.copy()
    # colonnes tolérées dans timestamp.py: t_debut, t_fin, word/mot
    if "t_debut_mot" not in df.columns:
        if "t_debut" in df.columns:
            df = df.rename(columns={"t_debut": "t_debut_mot"})
        else:
            df["t_debut_mot"] = np.nan
    if "t_fin_mot" not in df.columns:
        if "t_fin" in df.columns:
            df = df.rename(columns={"t_fin": "t_fin_mot"})
        else:
            df["t_fin_mot"] = np.nan
    if "mot" not in df.columns:
        if "word" in df.columns:
            df = df.rename(columns={"word": "mot"})
        else:
            df["mot"] = ""
    if "idx_global" not in df.columns:
        df = df.reset_index(drop=True)
        df["idx_global"] = np.arange(len(df), dtype=int)

    # ordonner
    df = df.sort_values(by=["t_debut_mot", "t_fin_mot", "idx_global"], kind="mergesort").reset_index(drop=True)
    return df

def _trouver_mot_proche(df_mots: pd.DataFrame, t_image: float, tol: float = 0.6) -> tuple[int | None, float | None]:
    """
    renvoie (idx_global, delta) du mot le plus proche de t_image si |delta| <= tol, sinon (None, None).
    Utilise une recherche par insertion sur t_centre_mot = (t_debut_mot + t_fin_mot)/2.
    """
    if df_mots is None or df_mots.empty or not np.isfinite(t_image):
        return None, None

    t0 = df_mots["t_debut_mot"].to_numpy(dtype=float)
    t1 = df_mots["t_fin_mot"].to_numpy(dtype=float)
    t_c = np.where(np.isfinite(t0) & np.isfinite(t1), 0.5 * (t0 + t1), t0)

    # recherche dichotomique
    pos = np.searchsorted(t_c, t_image)
    candidats = []
    if 0 <= pos - 1 < len(t_c): candidats.append(pos - 1)
    if 0 <= pos < len(t_c): candidats.append(pos)
    if 0 <= pos + 1 < len(t_c): candidats.append(pos + 1)

    meilleur_idx = None
    meilleur_delta = None
    for i in candidats:
        delta = float(t_image - t_c[i])
        if meilleur_delta is None or abs(delta) < abs(meilleur_delta):
            meilleur_idx = i
            meilleur_delta = delta

    if meilleur_idx is None:
        return None, None

    # filtrage par tolérance
    if abs(meilleur_delta) <= float(tol):
        return int(df_mots.iloc[meilleur_idx]["idx_global"]), float(meilleur_delta)
    return None, None

def _contexte_autour_mot(df_mots: pd.DataFrame, idx_global: int, k_avant: int = 6, k_apres: int = 8) -> str:
    """
    fabrique une courte fenêtre de texte autour d’un mot repéré par idx_global.
    Utilise des points de suspension en bord pour signaler que c’est un extrait local.
    """
    if df_mots is None or df_mots.empty:
        return ""
    # position de la ligne dans l’ordre actuel
    pos = int(np.where(df_mots["idx_global"].to_numpy() == idx_global)[0][0])
    i0 = max(0, pos - k_avant)
    i1 = min(len(df_mots), pos + k_apres + 1)
    tokens = df_mots.iloc[i0:i1]["mot"].astype(str).tolist()
    extrait = " ".join(t.strip() for t in tokens if t.strip())
    # Nettoyage simple des espaces
    extrait = " ".join(extrait.split())
    if i0 > 0:
        extrait = "… " + extrait
    if i1 < len(df_mots):
        extrait = extrait + " …"
    return extrait

def _legend_caption(image_name: str, t_image: float, statut: str, mot: str | None, delta: float | None, extrait: str | None) -> str:
    """
    compose une légende lisible et compacte selon le statut:
    - 'mot' : mot le plus proche trouvé
    - 'pause' : aucun mot à proximité
    """
    tete = f"{image_name} — {t_image:.2f}s"
    if statut == "mot":
        ligne2 = f"[{mot}] (Δ={delta:+.02f}s)"
        if extrait:
            return f"{tete}\n{ligne2}\n{extrait}"
        return f"{tete}\n{ligne2}"
    else:
        return f"{tete}\nPAUSE — aucun mot aligné dans la fenêtre."

# =========================
# composant principal
# =========================

def ui_images(
    df_images: pd.DataFrame,
    df_texte_aligne: pd.DataFrame | None = None,   # conservé pour compatibilité, non requis ici
    df_mots_aligne: pd.DataFrame | None = None,    # alignement mot-à-mot
    titre: str = "Galerie d’images (par lots)",
    tol_mot_s: float = 0.6,
    k_avant: int = 6,
    k_apres: int = 8,
    ncols: int = 5
) -> None:
    """
    affiche les images avec légendes synchronisées:
    - si un mot aligné est trouvé à ±tol_mot_s: affiche le mot + Δ + extrait local
    - sinon: affiche "PAUSE" (aucun mot dans la fenêtre)
    """
    st.markdown(f"### {titre}")

    if df_images is None or df_images.empty:
        st.caption("Aucune image à afficher.")
        return

    df_img = df_images.copy()
    if "t_image" not in df_img.columns:
        st.warning("df_images ne contient pas la colonne 't_image'.")
        return

    df_img = df_img.sort_values(by=["t_image", "fichier_image"]).reset_index(drop=True)
    df_mots = _normaliser_df_mots(df_mots_aligne)

    # bornes temporelles globales pour un filtre rapide
    t_min = float(np.nanmin(df_img["t_image"])) if df_img["t_image"].notna().any() else 0.0
    t_max = float(np.nanmax(df_img["t_image"])) if df_img["t_image"].notna().any() else 0.0
    col_a, col_b = st.columns(2)
    with col_a:
        f_t0 = st.number_input("Début fenêtre (s)", value=float(max(0.0, t_min)), step=0.1, format="%.2f")
    with col_b:
        f_t1 = st.number_input("Fin fenêtre (s)", value=float(t_max), step=0.1, format="%.2f")

    if f_t1 < f_t0:
        st.warning("La fin de fenêtre doit être ≥ au début.")
        return

    sel = df_img[df_img["t_image"].between(f_t0, f_t1)]
    st.caption(f"{len(sel)} image(s) entre {f_t0:.2f}s et {f_t1:.2f}s")

    if sel.empty:
        return

    lignes = [sel.iloc[i:i+ncols] for i in range(0, len(sel), ncols)]
    for bloc in lignes:
        cols = st.columns(len(bloc))
        for c, (_, row) in zip(cols, bloc.iterrows()):
            name = row["fichier_image"]
            timg = float(row["t_image"]) if np.isfinite(row["t_image"]) else np.nan
            b = _get_image_bytes_by_name(name)

            statut = "pause"
            mot = None
            delta = None
            extrait = None

            if np.isfinite(timg) and not df_mots.empty:
                idx, d = _trouver_mot_proche(df_mots, timg, tol=float(tol_mot_s))
                if idx is not None:
                    statut = "mot"
                    delta = d
                    ligne = df_mots.loc[df_mots["idx_global"] == idx].iloc[0]
                    mot = str(ligne.get("mot", "")).strip()
                    extrait = _contexte_autour_mot(df_mots, idx, k_avant=int(k_avant), k_apres=int(k_apres))

            caption = _legend_caption(name, timg if np.isfinite(timg) else float("nan"), statut, mot, delta, extrait)

            if b is not None:
                c.image(b, caption=caption, use_container_width=True)
            else:
                c.write(name)
                c.caption(caption)
