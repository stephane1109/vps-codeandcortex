# pages/transcription_cooccurrences.py
# Transcription horodatée (Whisper) + recherche de cooccurrences par fenêtre de mots ou par phrase,
# avec reconstruction du segment de texte et timeline des occurrences.
# Prérequis recommandés (requirements.txt) :
#   faster-whisper==1.*     # pour des timestamps par mot fiables et rapides
#   torch                   # CPU ok, GPU si dispo
#   opencv-python-headless  # déjà utilisé ailleurs
#   pandas, numpy, altair, streamlit
#
# Remarques :
# - Si faster-whisper n’est pas disponible, le script tente openai-whisper et se rabat sur des timestamps de segment.
# - L’upload fonctionne pour .mp3 .wav .m4a .mp4 ; on peut aussi utiliser la "vidéo préparée" présente en session.
# - Les cooccurrences sont détectées si TOUS les termes saisis apparaissent dans la même fenêtre (mots ou phrase).
# - La normalisation retire la casse et (optionnel) les accents.
# - Une timeline Altair place chaque occurrence, avec accès au texte et aux bornes temporelles.

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from app_runtime import enforce_access, heartbeat
from core_media import initialiser_repertoires, info_ffmpeg

# ======================= Structures de données =======================

@dataclass
class MotHorodate:
    texte: str
    t0: float
    t1: float

@dataclass
class SegmentHorodate:
    texte: str
    t0: float
    t1: float
    mots: List[MotHorodate]

# ======================= Utilitaires texte =======================

def normaliser_texte(s: str, enlever_accents: bool, to_lower: bool = True) -> str:
    """Normalise le texte pour la recherche (casse/accents)."""
    if s is None:
        return ""
    t = s
    if to_lower:
        t = t.lower()
    if enlever_accents:
        t = ''.join(
            c for c in unicodedata.normalize("NFD", t)
            if unicodedata.category(c) != "Mn"
        )
    return t

def tokenizer_mots(s: str) -> List[str]:
    """Tokenisation simple par mots (alphanum) avec conservation d’ordre."""
    return re.findall(r"\b[\w’']+\b", s, flags=re.UNICODE)

# ======================= Chargement Whisper =======================

@st.cache_resource(show_spinner=False)
def charger_faster_whisper(modele: str, compute_type: str = "int8") -> Optional[object]:
    """Charge faster-whisper si disponible, sinon None."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
        m = WhisperModel(model_size_or_path=modele, compute_type=compute_type)
        return m
    except Exception:
        return None

@st.cache_resource(show_spinner=False)
def charger_openai_whisper(modele: str) -> Optional[object]:
    """Charge openai-whisper (fallback, moins précis pour les timestamps mot-à-mot)."""
    try:
        import whisper  # type: ignore
        return whisper.load_model(modele)
    except Exception:
        return None

# ======================= Transcription =======================

def transcrire_faster_whisper(
    modele, chemin: str, langue: Optional[str], beam_size: int = 5
) -> Tuple[List[SegmentHorodate], str]:
    """Transcrit avec faster-whisper en récupérant segments + mots (timestamps)."""
    segments: List[SegmentHorodate] = []
    log = ""
    try:
        # word_timestamps = True donne des mots horodatés
        it, info = modele.transcribe(
            chemin,
            language=langue if langue else None,
            beam_size=beam_size,
            vad_filter=True,
            word_timestamps=True
        )
        for seg in it:
            mots = []
            if seg.words:
                for w in seg.words:
                    if w.start is not None and w.end is not None:
                        mots.append(MotHorodate(texte=w.word or "", t0=float(w.start), t1=float(w.end)))
            segments.append(SegmentHorodate(texte=seg.text or "", t0=float(seg.start), t1=float(seg.end), mots=mots))
        log = f"Langue détectée: {getattr(info, 'language', '?')} • Prob: {getattr(info, 'language_probability', '?')}"
    except Exception as e:
        log = f"Erreur faster-whisper: {e}"
    return segments, log

def transcrire_openai_whisper(
    modele, chemin: str, langue: Optional[str]
) -> Tuple[List[SegmentHorodate], str]:
    """Transcrit avec openai-whisper. Pas de mots horodatés natifs -> fallback segments."""
    segments: List[SegmentHorodate] = []
    log = ""
    try:
        # openai-whisper accepte des options similaires ; force timestamps par segments
        res = modele.transcribe(chemin, language=langue if langue else None, verbose=False)
        for s in res.get("segments", []):
            t0 = float(s.get("start", 0.0))
            t1 = float(s.get("end", t0))
            txt = s.get("text", "")
            segments.append(SegmentHorodate(texte=txt, t0=t0, t1=t1, mots=[]))
        log = "Transcription réalisée avec openai-whisper (mots horodatés indisponibles)."
    except Exception as e:
        log = f"Erreur openai-whisper: {e}"
    return segments, log

# ======================= Recherche de cooccurrences =======================

def contient_tous_termes(tokens_norm: List[str], termes_norm: List[str]) -> bool:
    """Vérifie que tous les termes recherchés sont présents dans une liste de tokens normalisés."""
    ens = set(tokens_norm)
    return all(t in ens for t in termes_norm)

def fenetres_glissantes_mots(
    segments: List[SegmentHorodate],
    taille_fenetre: int,
    enlever_accents: bool,
) -> List[Tuple[float, float, str]]:
    """
    Balaye l'ensemble des mots (toutes phrases concaténées) avec une fenêtre glissante
    de taille N, en conservant les timestamps du premier et dernier mot de la fenêtre.
    Retourne une liste de tuples (t0, t1, texte_fenetre).
    """
    # Construit la séquence globale mots + temps
    tous_mots: List[MotHorodate] = []
    for seg in segments:
        if seg.mots:
            tous_mots.extend(seg.mots)
        else:
            # fallback : pas de timestamps mot-à-mot -> approx en 5 sous-mots
            tokens = tokenizer_mots(seg.texte)
            if len(tokens) == 0:
                continue
            t_step = (seg.t1 - seg.t0) / max(1, len(tokens))
            for i, tok in enumerate(tokens):
                t0 = seg.t0 + i * t_step
                t1 = min(seg.t1, t0 + t_step)
                tous_mots.append(MotHorodate(tok, t0, t1))

    fenetres: List[Tuple[float, float, str]] = []
    if len(tous_mots) == 0:
        return fenetres

    # Tokens normalisés + mapping indices -> texte et temps
    tokens_norm = [normaliser_texte(m.texte, enlever_accents) for m in tous_mots]
    for i in range(0, len(tous_mots) - max(1, taille_fenetre) + 1):
        j = i + taille_fenetre
        sous_tokens = tokens_norm[i:j]
        t0 = float(tous_mots[i].t0)
        t1 = float(tous_mots[j - 1].t1)
        # reconstruit le texte brut de cette fenêtre
        texte = " ".join(m.texte for m in tous_mots[i:j])
        fenetres.append((t0, t1, texte))
    return fenetres

def occurrences_par_fenetre_mots(
    segments: List[SegmentHorodate],
    termes: List[str],
    taille_fenetre: int,
    enlever_accents: bool,
) -> List[Dict]:
    """
    Détecte les fenêtres glissantes de N mots contenant tous les termes.
    Retourne une liste de dicts {t0, t1, texte, type="fenetre_mots"}.
    """
    termes_norm = [normaliser_texte(t, enlever_accents) for t in termes if t.strip()]
    res: List[Dict] = []
    if len(termes_norm) == 0:
        return res

    # Préparer la séquence globale de mots et fenêtres
    # Pour éviter un coût énorme, on vérifie la condition avec un set dans chaque fenêtre
    fens = fenetres_glissantes_mots(segments, taille_fenetre=taille_fenetre, enlever_accents=enlever_accents)
    for (t0, t1, texte) in fens:
        tokens_norm = [normaliser_texte(tok, enlever_accents) for tok in tokenizer_mots(texte)]
        if contient_tous_termes(tokens_norm, termes_norm):
            res.append({"t0": t0, "t1": t1, "texte": texte, "type": "fenetre_mots"})
    return res

def occurrences_par_phrase(
    segments: List[SegmentHorodate],
    termes: List[str],
    enlever_accents: bool,
) -> List[Dict]:
    """
    Cherche les cooccurrences au niveau de la phrase (segment).
    Un segment est retenu si tous les termes y apparaissent.
    """
    termes_norm = [normaliser_texte(t, enlever_accents) for t in termes if t.strip()]
    res: List[Dict] = []
    if len(termes_norm) == 0:
        return res

    for seg in segments:
        txt_norm = normaliser_texte(seg.texte, enlever_accents)
        tokens = tokenizer_mots(txt_norm)
        if contient_tous_termes(tokens, termes_norm):
            res.append({"t0": seg.t0, "t1": seg.t1, "texte": seg.texte, "type": "phrase"})
    return res

# ======================= Altair helpers =======================

def timeline_occurrences_chart(df: pd.DataFrame, titre: str) -> alt.Chart:
    """Crée un graphique de type barres horizontales positionnées sur le temps."""
    if df.empty:
        return alt.Chart(pd.DataFrame({"t": [], "dur": []})).mark_bar()
    dfd = df.copy()
    dfd["t"] = dfd["t0"].astype(float)
    dfd["dur"] = (dfd["t1"] - dfd["t0"]).astype(float)
    base = alt.Chart(dfd).mark_bar().encode(
        x=alt.X("t:Q", title="Temps (s)"),
        x2="t1:Q",
        y=alt.Y("type:N", title="Type"),
        color=alt.Color("type:N", legend=None),
        tooltip=[alt.Tooltip("t0:Q", title="Début (s)", format=".2f"),
                 alt.Tooltip("t1:Q", title="Fin (s)", format=".2f"),
                 alt.Tooltip("texte:N", title="Extrait")]
    ).properties(title=titre, width=1000, height=70 + 10 * max(1, dfd["type"].nunique()))
    return base

# ======================= Application Streamlit =======================

BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()
st.set_page_config(page_title="Transcription & Cooccurrences", layout="wide")
enforce_access()
st.title("Transcription horodatée & cooccurrences")
st.markdown("www.codeandcortex.fr")

# Rappel ffmpeg dispo
ffmpeg_path, _ = info_ffmpeg()

# État partagé
st.session_state.setdefault("transc_segments", None)
st.session_state.setdefault("fichier_transc", None)

st.subheader("Source")
c1, c2 = st.columns([1, 1])
with c1:
    up = st.file_uploader("Importer un fichier audio/vidéo (.mp3 .wav .m4a .mp4)", type=["mp3", "wav", "m4a", "mp4"], key="up_cooc")
    if up is not None:
        p = REP_TMP / f"cooc_{up.name}"
        with open(p, "wb") as g:
            g.write(up.read())
        st.session_state["fichier_transc"] = str(p)
        st.success(f"Fichier chargé : {p.name}")
with c2:
    if st.session_state.get("video_base"):
        st.info(f"Vidéo préparée détectée : {Path(st.session_state['video_base']).name}")
        use_prepared = st.checkbox("Utiliser la vidéo préparée", value=False)
        if use_prepared:
            st.session_state["fichier_transc"] = st.session_state["video_base"]

if st.session_state.get("fichier_transc") is None:
    st.stop()

st.subheader("Paramètres de transcription")
c3, c4, c5, c6 = st.columns(4)
with c3:
    backend = st.selectbox("Moteur", ["faster-whisper (recommandé)", "openai-whisper (fallback)"], index=0)
with c4:
    modele = st.selectbox("Modèle", ["base", "small", "medium", "large-v3"], index=1)
with c5:
    langue = st.text_input("Langue (code ISO, vide = détection)", value="")
with c6:
    compute_type = st.selectbox("Compute type (faster-whisper)", ["int8", "int8_float16", "float16", "float32"], index=0)

lancer = st.button("Lancer / Refaire la transcription", type="primary")

if lancer:
    heartbeat()
    chemin = st.session_state["fichier_transc"]
    segments: List[SegmentHorodate] = []
    journal = ""

    if backend.startswith("faster"):
        modele_fw = charger_faster_whisper(modele, compute_type=compute_type)
        if modele_fw is None:
            st.warning("faster-whisper indisponible. Basculement sur openai-whisper.")
            modele_ow = charger_openai_whisper(modele)
            if modele_ow is None:
                st.error("Aucun moteur Whisper n’est disponible. Ajoute 'faster-whisper' ou 'openai-whisper' dans requirements.txt.")
                st.stop()
            segments, journal = transcrire_openai_whisper(modele_ow, chemin, langue or None)
        else:
            segments, journal = transcrire_faster_whisper(modele_fw, chemin, langue or None)
    else:
        modele_ow = charger_openai_whisper(modele)
        if modele_ow is None:
            st.error("openai-whisper indisponible. Ajoute 'openai-whisper' ou choisis faster-whisper.")
            st.stop()
        segments, journal = transcrire_openai_whisper(modele_ow, chemin, langue or None)

    if len(segments) == 0:
        st.error("Transcription vide.")
        if journal:
            st.code(journal)
        st.stop()

    st.session_state["transc_segments"] = segments
    heartbeat()
    st.success("Transcription terminée.")
    if journal:
        st.caption(journal)

# Si pas de transcription, on s’arrête ici
if not st.session_state.get("transc_segments"):
    st.info("Clique sur « Lancer / Refaire la transcription » pour continuer.")
    st.stop()

segments: List[SegmentHorodate] = st.session_state["transc_segments"]

# Tableau segments
st.subheader("Aperçu des segments")
df_seg = pd.DataFrame([
    {"t0": s.t0, "t1": s.t1, "dur": s.t1 - s.t0, "texte": s.texte, "nb_mots": len(s.mots)}
    for s in segments
])
st.dataframe(df_seg, use_container_width=True)

st.download_button(
    "Télécharger la transcription (CSV segments)",
    data=df_seg.to_csv(index=False).encode("utf-8"),
    file_name="transcription_segments.csv",
    mime="text/csv"
)

# ======================= Zone de recherche cooccurrences =======================

st.subheader("Recherche de cooccurrences")
c7, c8, c9 = st.columns([2, 1, 1])
with c7:
    termes_brut = st.text_input("Termes (séparés par des virgules)", value="apprentissage, attention")
with c8:
    enlever_accents = st.checkbox("Ignorer les accents", value=True)
with c9:
    mode_fenetre = st.radio("Mode", ["Fenêtre de mots", "Phrase (segment)"], index=0, horizontal=True)

taille_fenetre = st.slider("Taille de la fenêtre (en nombre de mots)", min_value=3, max_value=50, value=10, step=1)

termes = [t.strip() for t in termes_brut.split(",") if t.strip()]
if len(termes) == 0:
    st.warning("Saisis au moins un terme, idéalement deux ou plus pour une cooccurrence.")
    st.stop()

lancer_recherche = st.button("Chercher les cooccurrences", type="primary")

if lancer_recherche:
    heartbeat()
    res_fen: List[Dict] = []
    res_seg: List[Dict] = []
    if mode_fenetre == "Fenêtre de mots":
        res_fen = occurrences_par_fenetre_mots(segments, termes=termes, taille_fenetre=taille_fenetre, enlever_accents=enlever_accents)
    else:
        res_seg = occurrences_par_phrase(segments, termes=termes, enlever_accents=enlever_accents)

    resultats = res_fen if mode_fenetre == "Fenêtre de mots" else res_seg
    if len(resultats) == 0:
        st.info("Aucune cooccurrence trouvée avec ces paramètres.")
    else:
        # DataFrame résultats
        df_occ = pd.DataFrame(resultats).sort_values(["t0", "t1"]).reset_index(drop=True)
        df_occ["dur"] = df_occ["t1"] - df_occ["t0"]
        st.subheader("Occurrences détectées")
        st.dataframe(df_occ, use_container_width=True)

        st.download_button(
            "Télécharger les occurrences (CSV)",
            data=df_occ.to_csv(index=False).encode("utf-8"),
            file_name="cooccurrences.csv",
            mime="text/csv"
        )

        # Timeline des occurrences
        st.subheader("Timeline des cooccurrences")
        chart = timeline_occurrences_chart(df_occ, "Cooccurrences")
        st.altair_chart(chart.interactive(), use_container_width=True)
        heartbeat()

        # Scrubber pour naviguer d’une occurrence à l’autre
        st.subheader("Navigation et reconstruction du segment")
        if len(df_occ) > 0:
            tmin = float(df_occ["t0"].min())
            tmax = float(df_occ["t1"].max())
            st.session_state.setdefault("t_nav", tmin)
            t_nav = st.slider(
                "Curseur temps (s)",
                min_value=tmin, max_value=tmax,
                value=float(st.session_state["t_nav"]),
                step=max(0.01, (tmax - tmin) / max(1000, len(df_occ)))
            )
            st.session_state["t_nav"] = float(t_nav)

            # Occurrence la plus proche
            arr_centres = ((df_occ["t0"].to_numpy() + df_occ["t1"].to_numpy()) / 2.0).astype(float)
            idx = int(np.argmin(np.abs(arr_centres - st.session_state["t_nav"])))
            occ = df_occ.iloc[idx]

            # Reconstruction du texte du passage : on concatène les segments qui recouvrent [t0, t1]
            t0_sel = float(occ["t0"])
            t1_sel = float(occ["t1"])
            extraits: List[str] = []
            for s in segments:
                if s.t1 < t0_sel or s.t0 > t1_sel:
                    continue
                extraits.append(s.texte.strip())
            passage = " ".join(extraits).strip()

            st.write(f"Occurrence #{idx+1}/{len(df_occ)}")
            st.write(f"Début: {t0_sel:.2f}s • Fin: {t1_sel:.2f}s • Durée: {t1_sel - t0_sel:.2f}s")
            st.text_area("Passage reconstruit", value=passage, height=180)

            # Indication des termes trouvés
            termes_norm = [normaliser_texte(t, enlever_accents) for t in termes]
            passage_norm = normaliser_texte(passage, enlever_accents)
            presentes = [t for t in termes if normaliser_texte(t, enlever_accents) in tokenizer_mots(passage_norm)]
            manquantes = [t for t in termes if normaliser_texte(t, enlever_accents) not in tokenizer_mots(passage_norm)]

            st.write(f"Termes présents: {', '.join(presentes) if presentes else '(aucun)'}")
            if len(manquantes) > 0:
                st.caption(f"Termes non retrouvés dans la reconstruction textuelle affichée: {', '.join(manquantes)}")

else:
    st.info("Régle les paramètres et clique « Chercher les cooccurrences » pour afficher les occurrences et la timeline.")
