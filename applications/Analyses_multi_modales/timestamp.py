# timestamp.py
# Alignement mot-à-mot entre texte corrigé et timestamps issus de segments Whisper.
# Hypothèse : on ne dispose que de (t_debut, t_fin, texte_segment) pour Whisper.
# On distribue linéairement la durée du segment sur les tokens du segment,
# puis on aligne ces tokens "horodatés" aux tokens du texte corrigé.

from __future__ import annotations
import io
import json
import re
import math
from difflib import SequenceMatcher
from typing import List, Tuple, Dict
import pandas as pd
import numpy as np

# =========================
# utilitaires de normalisation
# =========================

def _nettoyer_espace(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _tokeniser(s: str) -> List[str]:
    """
    Tokenisation simple insensible à la casse, en gardant les apostrophes internes.
    Exemples: "l’État", "aujourd’hui" -> "l", "état", "aujourd’hui".
    """
    if not isinstance(s, str):
        return []
    s = s.lower()
    # remplace ponctuation forte par espace
    s = re.sub(r"[\.!?;,:\(\)\[\]\{\}«»\"“”„…–—\-_/\\]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return []
    # on autorise l’apostrophe comme caractère de mot
    tokens = re.findall(r"[a-zàâäçéèêëîïôöùûüÿœæ0-9']+", s, flags=re.IGNORECASE)
    return tokens

# =========================
# projection linéaire des temps sur tokens Whisper
# =========================

def _horodater_tokens_segment(tokens_seg: List[str], t0: float, t1: float) -> List[Tuple[str, float, float]]:
    """
    Répartir linéairement [t0, t1] sur les tokens_seg.
    Renvoie liste de (token, t_deb, t_fin).
    """
    if not tokens_seg:
        return []
    dur = max(0.0, float(t1) - float(t0))
    n = len(tokens_seg)
    if dur == 0.0:
        # cas pathologique : même timecode pour début/fin
        return [(tok, float(t0), float(t0)) for tok in tokens_seg]
    out = []
    for i, tok in enumerate(tokens_seg):
        a = i / n
        b = (i + 1) / n
        ti0 = t0 + a * dur
        ti1 = t0 + b * dur
        out.append((tok, float(ti0), float(ti1)))
    return out

def _build_tokens_whisper(segs_whisper: List[Tuple[float, float, str]]) -> List[Tuple[str, float, float]]:
    """
    A partir des segments Whisper [(t0,t1,texte)], produit une séquence de tokens horodatés.
    """
    seq = []
    for t0, t1, txt in segs_whisper:
        toks = _tokeniser(_nettoyer_espace(txt))
        seq.extend(_horodater_tokens_segment(toks, float(t0), float(t1)))
    return seq

# =========================
# alignement tokens corrigés <-> tokens horodatés Whisper
# =========================

def _align_tokens(ref: List[str], hyp: List[str]) -> List[Tuple[int, int]]:
    """
    Aligne ref (texte corrigé) sur hyp (tokens Whisper horodatés, sans temps ici)
    en renvoyant des paires (i_ref, j_hyp) pour les correspondances.
    Utilise SequenceMatcher sur tokens. Ignore les 'equal' trop courts si nécessaire.
    """
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    mapping = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping.append((i1 + k, j1 + k))
        # on laisse tomber les insert/delete/replace : pas de temps fiable pour ces positions
    return mapping

# =========================
# construction du DataFrame mot-à-mot
# =========================

def construire_df_timestamps_mots(texte_corrige: str, segs_whisper: List[Tuple[float, float, str]]) -> pd.DataFrame:
    """
    Produit un DataFrame mot-à-mot pour le texte corrigé, avec colonnes :
      idx, mot, t_debut, t_fin
    Les mots non alignés reçoivent t_debut/t_fin = NaN.
    """
    txt = _nettoyer_espace(texte_corrige or "")
    tokens_ref = _tokeniser(txt)
    hyp_with_time = _build_tokens_whisper(segs_whisper)  # [(tok, t0, t1), ...]
    tokens_hyp = [w for (w, _, _) in hyp_with_time]

    pairs = _align_tokens(tokens_ref, tokens_hyp)
    # index -> temps
    j2time: Dict[int, Tuple[float, float]] = {j: (t0, t1) for j, (w, t0, t1) in enumerate(hyp_with_time)}
    i2time: Dict[int, Tuple[float, float]] = {}

    for i, j in pairs:
        if j in j2time:
            i2time[i] = j2time[j]

    lignes = []
    for i, tok in enumerate(tokens_ref):
        if i in i2time:
            t0, t1 = i2time[i]
        else:
            t0 = np.nan
            t1 = np.nan
        lignes.append({"idx": int(i), "mot": tok, "t_debut": t0, "t_fin": t1})

    df = pd.DataFrame(lignes)
    return df

# =========================
# récupération de contexte textuel autour d’un temps t
# =========================

def texte_autour_t(df_mots: pd.DataFrame, t: float, rayon: int = 7) -> str:
    """
    Retourne une fenêtre textuelle centrée sur le mot actif à l’instant t.
    Le mot central est entouré de ** pour mise en évidence en Markdown.
    Si aucun mot ne couvre t, choisit le mot au temps le plus proche (distance minimale au centre [t_debut,t_fin]).
    """
    if df_mots is None or df_mots.empty or not np.isfinite(t):
        return ""

    # priorité : mot qui couvre t
    couvre = df_mots[(df_mots["t_debut"].astype(float) <= t) & (df_mots["t_fin"].astype(float) >= t)]
    if not couvre.empty:
        idx0 = int(couvre.iloc[0]["idx"])
    else:
        # à défaut, mot dont le centre est le plus proche
        tmp = df_mots.dropna(subset=["t_debut", "t_fin"]).copy()
        if tmp.empty:
            return ""
        centres = (tmp["t_debut"].astype(float) + tmp["t_fin"].astype(float)) / 2.0
        j = int((centres - float(t)).abs().idxmin())
        idx0 = int(tmp.loc[j, "idx"])

    i0 = max(0, idx0 - rayon)
    i1 = min(len(df_mots), idx0 + rayon + 1)

    mots = df_mots.loc[i0:i1 - 1, "mot"].tolist()
    centre_pos = idx0 - i0
    if 0 <= centre_pos < len(mots):
        mots[centre_pos] = f"**{mots[centre_pos]}**"

    return " ".join(mots)

# =========================
# compat : séquences de segments pour affichage par phrase (optionnel)
# =========================

def construire_df_timestamps_pour_fichier(texte_corrige: str, segs_whisper: List[Tuple[float, float, str]], nlp=None) -> pd.DataFrame:
    """
    Version précédente conservée pour compatibilité : renvoie un DataFrame par segment (pas mot-à-mot).
    Colonnes : t_debut, t_fin, segment
    Ici, on ne refait pas d’alignement exact phrase à phrase ; on concatène les segments Whisper nettoyés.
    """
    lignes = []
    for t0, t1, s in segs_whisper:
        s = _nettoyer_espace(s)
        if not s:
            continue
        lignes.append({"t_debut": float(t0), "t_fin": float(t1), "segment": s})
    return pd.DataFrame(lignes)


# =========================
# import manuel de timestamps externes (1 Hz)
# =========================

_TIME_COL_CANDIDATES = [
    "t_sec", "sec", "second", "seconde", "seconds", "time", "temps", "timestamp", "t", "start",
]
_TEXT_COL_CANDIDATES = [
    "texte", "texte_sec", "text", "segment", "contenu", "transcription", "caption", "phrase",
]


def _to_seconds_generic(val) -> float | None:
    """convertit divers formats (float, hh:mm:ss, mm:ss) en secondes."""
    if val is None:
        return None
    if isinstance(val, (int, float, np.integer, np.floating)):
        if isinstance(val, float) and math.isnan(val):
            return None
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[\.,](\d+))?", s)
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2))
    s_ = int(m.group(3))
    frac = 0.0
    if m.group(4):
        frac = float(f"0.{m.group(4)}")
    return h * 3600.0 + m_ * 60.0 + s_ + frac


def _select_column(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    for cand in candidates:
        for c in columns:
            if cand in c.lower():
                return c
    return None


def _df_from_json_payload(payload) -> pd.DataFrame:
    rows = []
    if isinstance(payload, dict):
        payload = payload.get("timestamps") or payload.get("data") or payload
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                t_val = None
                txt_val = None
                for key, value in item.items():
                    key_l = str(key).lower()
                    if t_val is None and any(cand in key_l for cand in _TIME_COL_CANDIDATES):
                        t_val = value
                    if txt_val is None and any(cand in key_l for cand in _TEXT_COL_CANDIDATES):
                        txt_val = value
                if t_val is not None or txt_val is not None:
                    rows.append({"t_raw": t_val, "texte_raw": txt_val})
    if not rows:
        return pd.DataFrame(columns=["t_raw", "texte_raw"])
    return pd.DataFrame(rows)


def charger_timestamps_depuis_fichier(file_bytes: bytes, filename: str | None = None) -> pd.DataFrame:
    """
    Interprète un fichier de timestamps (CSV/TSV/JSON/texte) et renvoie un DataFrame [t_sec, texte_sec].
    La seconde est arrondie à l'entier inférieur (1 Hz) et les textes vides sont filtrés.
    """
    if not file_bytes:
        return pd.DataFrame(columns=["t_sec", "texte_sec"])

    try:
        raw = file_bytes.decode("utf-8")
    except Exception:
        raw = file_bytes.decode("latin-1", errors="ignore")
    if not raw.strip():
        return pd.DataFrame(columns=["t_sec", "texte_sec"])

    # tentative JSON
    df_candidates: list[pd.DataFrame] = []
    try:
        payload = json.loads(raw)
        df_json = _df_from_json_payload(payload)
        if not df_json.empty:
            df_candidates.append(df_json)
    except Exception:
        pass

    # tentative CSV/TSV (détection auto du séparateur)
    buf = io.StringIO(raw)
    try:
        df_csv = pd.read_csv(buf, sep=None, engine="python")
        if not df_csv.empty:
            df_candidates.append(df_csv)
    except Exception:
        for sep in [";", "\t", "|", ","]:
            buf.seek(0)
            try:
                df_sep = pd.read_csv(buf, sep=sep)
                if not df_sep.empty:
                    df_candidates.append(df_sep)
                    break
            except Exception:
                continue

    if not df_candidates:
        return pd.DataFrame(columns=["t_sec", "texte_sec"])

    for df in df_candidates:
        if df is None or df.empty:
            continue
        cols = list(df.columns)
        time_col = _select_column(cols, _TIME_COL_CANDIDATES)
        text_col = _select_column(cols, _TEXT_COL_CANDIDATES)
        if time_col is None or text_col is None:
            continue
        tmp = df[[time_col, text_col]].rename(columns={time_col: "t_raw", text_col: "texte_raw"}).copy()
        tmp["t_sec"] = tmp["t_raw"].apply(_to_seconds_generic)
        tmp["texte_sec"] = tmp["texte_raw"].astype(str).str.strip()
        tmp = tmp.dropna(subset=["t_sec"])
        if tmp.empty:
            continue
        tmp["t_sec"] = tmp["t_sec"].apply(lambda x: int(math.floor(float(x))))
        tmp = tmp[tmp["texte_sec"].astype(str).str.strip() != ""]
        if tmp.empty:
            continue
        agg = (
            tmp.groupby("t_sec")["texte_sec"]
            .apply(lambda s: " ".join([str(v).strip() for v in s if str(v).strip()]))
            .reset_index()
        )
        agg["t_sec"] = agg["t_sec"].astype("Int64")
        return agg.sort_values("t_sec").reset_index(drop=True)

    return pd.DataFrame(columns=["t_sec", "texte_sec"])
