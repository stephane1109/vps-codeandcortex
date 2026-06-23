# main.py
# Analyse multimodale de la temporalité (texte + audio + images) – SHS/Politique
# Encodage images strict 1 fps : i_{N}s_1fps.jpg  => t_image = N (seconde entière)
# Texte sous image aligné au mot (à partir des timestamps Whisper et du texte corrigé)
# Attitudes : normalisation d’entrée pour éviter les erreurs de type
# Vidéo supprimée sous les images

import io
import re
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
import spacy
import librosa

from timestamp import (
    construire_df_timestamps_pour_fichier,
    construire_df_timestamps_mots,
    charger_timestamps_depuis_fichier,
)
from definitions import obtenir_definitions, obtenir_glossaire, afficher_legendes
from dictionnaire import (
    deictiques_proches,
    deictiques_eloignes,
    deictiques_passes,
    deictiques_plannificateur,
    marqueurs_planification,
    connecteurs_causaux,
)
from tests import ui_tests_auto, ui_tests_croises
from attitudes import calculer_attitudes_depuis_images, ui_attitudes_images
from emotions import ui_emotions_images
from vecteuremo import ui_vecteur_emotionnel
from images import ui_images
from anomalies import ui_anomalies

# whisper optionnel
try:
    from faster_whisper import WhisperModel
    _whisper_ok = True
except Exception:
    _whisper_ok = False


# =========================
# utilitaires texte
# =========================

def nettoyer_texte(texte: str) -> str:
    """nettoyer espaces/retours à la ligne."""
    if not isinstance(texte, str):
        return ""
    t = texte.replace("\n", " ").replace("\r", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

import re as _re
def _pattern_un_mot(expr: str) -> _re.Pattern:
    """mot simple avec pluriels s|x."""
    base = _re.escape(expr)
    return _re.compile(rf"(?<!\w){base}(?:s|x)?(?!\w)")

def _pattern_multi_mots(expr: str) -> _re.Pattern:
    """expression multi-mots (espaces flexibles)."""
    parts = [_re.escape(p) for p in expr.split()]
    body = r"\s+".join(parts)
    return _re.compile(rf"(?<!\w){body}(?!\w)")

def lister_termes(texte: str, lexique: set) -> list:
    """appariement insensible à la casse, gère ponctuation/pluriels s|x."""
    if not isinstance(texte, str) or not texte:
        return []
    t = texte.lower()
    out = set()
    for expr in lexique:
        e = expr.lower().strip()
        pat = _pattern_multi_mots(e) if " " in e else _pattern_un_mot(e)
        if pat.search(t):
            out.add(expr)
    return sorted(out)

@st.cache_resource(show_spinner=False)
def charger_spacy_transformer():
    """charger spaCy transformer fr_dep_news_trf (CamemBERT)."""
    try:
        nlp = spacy.load("fr_dep_news_trf")
        return nlp, "Modèle spaCy Transformer (CamemBERT) chargé."
    except Exception as e:
        return None, f"Échec chargement fr_dep_news_trf : {e}. Installez : pip install 'spacy[transformers]' && python -m spacy download fr_dep_news_trf"


# =========================
# analyse textuelle
# =========================

def indicateurs_texte_doc(texte: str, nlp):
    """indicateurs document : temps verbaux + déictiques/planif/causaux + listes."""
    txt = nettoyer_texte(texte)
    if not txt or nlp is None:
        return None
    doc = nlp(txt)

    pres_terms, past_terms, fut_terms = [], [], []
    nb_verbes = 0
    for tok in doc:
        if tok.pos_ in {"VERB", "AUX"}:
            nb_verbes += 1
            m = tok.morph
            if "Tense=Pres" in m: pres_terms.append(tok.text)
            if "Tense=Imp" in m or "Tense=Past" in m: past_terms.append(tok.text)
            if "Tense=Fut" in m: fut_terms.append(tok.text)

    terms_deict_proches = lister_termes(txt, deictiques_proches)
    terms_deict_eloignes = lister_termes(txt, deictiques_eloignes)
    terms_deict_passes   = lister_termes(txt, deictiques_passes)
    terms_deict_planif   = lister_termes(txt, deictiques_plannificateur)
    terms_planifs        = lister_termes(txt, marqueurs_planification)
    terms_causaux        = lister_termes(txt, connecteurs_causaux)

    nb_mots = len(txt.split())
    def ratio(x, base): return float(x)/base if base else 0.0

    feats = {
        "mots": nb_mots, "verbes": nb_verbes,
        "present_brut": len(pres_terms), "passe_brut": len(past_terms), "futur_brut": len(fut_terms),
        "ratio_present_par_verbe": ratio(len(pres_terms), nb_verbes),
        "ratio_passe_par_verbe": ratio(len(past_terms), nb_verbes),
        "ratio_futur_par_verbe": ratio(len(fut_terms), nb_verbes),
        "deictiques_proches_brut": len(terms_deict_proches),
        "deictiques_eloignes_brut": len(terms_deict_eloignes),
        "deictiques_passes_brut": len(terms_deict_passes),
        "deictiques_plannificateur_brut": len(terms_deict_planif),
        "planification_brut": len(terms_planifs),
        "causaux_brut": len(terms_causaux),
        "termes_present": "; ".join(pres_terms),
        "termes_passe": "; ".join(past_terms),
        "termes_futur": "; ".join(fut_terms),
        "termes_deictiques_proches": "; ".join(terms_deict_proches),
        "termes_deictiques_eloignes": "; ".join(terms_deict_eloignes),
        "termes_deictiques_passes": "; ".join(terms_deict_passes),
        "termes_deictiques_plannificateur": "; ".join(terms_deict_planif),
        "termes_planification": "; ".join(terms_planifs),
        "termes_causaux": "; ".join(terms_causaux),
    }
    return feats, doc

def segments_texte(doc, fichier, locuteur):
    """lignes par phrase, sans timing (t_debut/t_fin NaN)."""
    lignes = []
    for sent in doc.sents:
        s = sent.text.strip()
        if not s:
            continue
        pres_terms, past_terms, fut_terms = [], [], []
        nb_verbes = 0
        for tok in sent:
            if tok.pos_ in {"VERB", "AUX"}:
                nb_verbes += 1
                m = tok.morph
                if "Tense=Pres" in m: pres_terms.append(tok.text)
                if "Tense=Imp" in m or "Tense=Past" in m: past_terms.append(tok.text)
                if "Tense=Fut" in m: fut_terms.append(tok.text)
        txt = nettoyer_texte(s)
        terms_deict_proches = lister_termes(txt, deictiques_proches)
        terms_deict_eloignes = lister_termes(txt, deictiques_eloignes)
        terms_deict_passes   = lister_termes(txt, deictiques_passes)
        terms_deict_planif   = lister_termes(txt, deictiques_plannificateur)
        terms_planifs        = lister_termes(txt, marqueurs_planification)
        nb_mots = len(txt.split())
        def ratio(x, base): return float(x)/base if base else 0.0
        lignes.append({
            "fichier": fichier, "locuteur": locuteur, "segment": s,
            "t_debut": np.nan, "t_fin": np.nan,
            "mots": nb_mots, "verbes": nb_verbes,
            "present_brut": len(pres_terms), "passe_brut": len(past_terms), "futur_brut": len(fut_terms),
            "ratio_present_par_verbe": ratio(len(pres_terms), nb_verbes),
            "ratio_passe_par_verbe": ratio(len(past_terms), nb_verbes),
            "ratio_futur_par_verbe": ratio(len(fut_terms), nb_verbes),
            "deictiques_proches_brut": len(terms_deict_proches),
            "deictiques_eloignes_brut": len(terms_deict_eloignes),
            "deictiques_passes_brut": len(terms_deict_passes),
            "deictiques_plannificateur_brut": len(terms_deict_planif),
            "planification_brut": len(terms_planifs),
            "termes_present": "; ".join(pres_terms),
            "termes_passe": "; ".join(past_terms),
            "termes_futur": "; ".join(fut_terms),
            "termes_deictiques_proches": "; ".join(terms_deict_proches),
            "termes_deictiques_eloignes": "; ".join(terms_deict_eloignes),
            "termes_deictiques_passes": "; ".join(terms_deict_passes),
            "termes_deictiques_plannificateur": "; ".join(terms_deict_planif),
            "termes_planification": "; ".join(terms_planifs),
        })
    return pd.DataFrame(lignes)


# =========================
# audio (pauses + débit)
# =========================

def charger_audio_bytes(file_bytes, sr_target=16000):
    """charger mono à sr_target."""
    try:
        y, sr = librosa.load(io.BytesIO(file_bytes), sr=sr_target, mono=True)
        return y, sr, None
    except Exception as e:
        return None, None, f"lecture audio impossible: {e}"

def timeline_pauses_et_debit(y, sr, seuil_quantile=25, seuil_pause_s=0.3, fenetre_activite_s=1.0):
    """intensité dB normalisée, pauses longues, activité vocale et débit par seconde."""
    hop = int(0.01 * sr)
    frame = int(0.03 * sr)
    e = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop).flatten()
    t = np.arange(len(e)) * (hop / sr)

    e_safe = np.maximum(e, 1e-12)
    e_max = float(np.max(e_safe))
    intensite_db = 20.0 * np.log10(e_safe / e_max)
    intensite_db = np.clip(intensite_db, -80.0, 0.0)

    q = np.percentile(e, seuil_quantile)
    silence = (e < q).astype(int)
    non_silence = 1 - silence

    frames_par_s = sr / hop

    pauses = []
    c = 0
    start_idx = None
    for i, v in enumerate(silence):
        if v == 1:
            if c == 0: start_idx = i
            c += 1
        if (v == 0 and c > 0) or (i == len(silence)-1 and c > 0):
            duree = c / frames_par_s
            if duree >= seuil_pause_s:
                end_idx = i if v == 0 else i
                pauses.append((start_idx, end_idx, duree))
            c = 0
            start_idx = None

    taille_fen = max(1, int(fenetre_activite_s * frames_par_s))
    activite = np.convolve(non_silence, np.ones(taille_fen)/taille_fen, mode="same")
    activite = np.clip(activite, 0.0, 1.0)

    nb_secs = int(np.ceil(len(e) / frames_par_s))
    debit_par_sec, parole_s, pause_s = [], [], []
    for s_i in range(nb_secs):
        i0 = int(s_i * frames_par_s)
        i1 = int(min((s_i + 1) * frames_par_s, len(e)))
        if i1 > i0:
            mean_non_sil = float(np.mean(non_silence[i0:i1]))
            parole_s.append(mean_non_sil * 1.0)
            pause_s.append((1.0 - mean_non_sil) * 1.0)
            debit_par_sec.append(mean_non_sil)
        else:
            parole_s.append(0.0)
            pause_s.append(0.0)
            debit_par_sec.append(0.0)

    t_secs = np.arange(nb_secs).astype(float)

    peaks = 0
    for i in range(1, len(e) - 1):
        if e[i] > e[i - 1] and e[i] > e[i + 1]:
            peaks += 1
    duree_totale = len(y) / sr if sr else 0.0
    debit_proxy_sps = float(peaks / duree_totale) if duree_totale > 0 else np.nan

    df_ts = pd.DataFrame({"t": t, "intensite_db": intensite_db, "activite_vocale_t": activite})
    df_pauses = pd.DataFrame([{"t_debut": p[0]*hop/sr, "t_fin": p[1]*hop/sr, "duree_s": p[2]} for p in pauses]) \
               if pauses else pd.DataFrame(columns=["t_debut","t_fin","duree_s"])
    df_debit_sec = pd.DataFrame({"t_seconde": t_secs, "debit_seconde": debit_par_sec})
    df_parole_pause_sec = pd.DataFrame({"t_seconde": t_secs, "parole_s": parole_s, "pause_s": pause_s})
    resume = {
        "nb_pauses": int(len(pauses)),
        "duree_pauses_totale_s": float(df_pauses["duree_s"].sum()) if not df_pauses.empty else 0.0,
        "duree_pause_moy_s": float(df_pauses["duree_s"].mean()) if not df_pauses.empty else 0.0,
        "duree_pause_med_s": float(df_pauses["duree_s"].median()) if not df_pauses.empty else 0.0,
        "parole_active_ratio": float(np.mean(debit_par_sec)) if len(debit_par_sec) else 0.0,
        "debit_proxy_sps": debit_proxy_sps,
        "duree_audio_s": float(duree_totale)
    }
    return df_ts, df_pauses, df_debit_sec, df_parole_pause_sec, resume


# =========================
# images 1 FPS : parsing + store
# =========================

_PAT_1FPS = re.compile(r"^i_(?P<s>\d+)s_1fps", re.IGNORECASE)

def _parse_ts_from_name_1fps(name: str) -> float | None:
    """extraire N depuis i_{N}s_1fps.jpg -> t=N (seconde entière)."""
    base = name.rsplit("/", 1)[-1].lower()
    m = _PAT_1FPS.match(base)
    if not m:
        return None
    return float(int(m.group("s")))

def preparer_images(files, decalage_global_s: float = 0.0):
    """inventaire images + stockage bytes en session (liste et mapping)."""
    if not files:
        return pd.DataFrame(columns=["fichier_image", "t_image", "caption"])
    store_list = []
    store_map = {}
    meta = []
    for f in files:
        name = f.name
        b = f.read()
        t = _parse_ts_from_name_1fps(name)
        if t is None:
            t = np.nan
        else:
            t = float(int(t))
        if not np.isnan(t):
            t = float(int(round(t + float(decalage_global_s or 0.0))))
        store_list.append({"name": name, "bytes": b})
        store_map[name] = b
        meta.append({"fichier_image": name, "t_image": t, "caption": ""})
    st.session_state["images_store"] = store_list
    st.session_state["images_store_map"] = store_map
    return pd.DataFrame(meta)

def get_image_bytes_by_name(name: str) -> bytes | None:
    """lecture depuis le mapping si dispo, sinon depuis la liste."""
    mp = st.session_state.get("images_store_map") or {}
    if name in mp:
        return mp[name]
    for it in st.session_state.get("images_store", []) or []:
        if isinstance(it, dict) and it.get("name") == name:
            return it.get("bytes")
    return None


# =========================
# graphiques (Altair)
# =========================

def chart_intensite(df_ts, df_pauses, df_images=None):
    base = alt.Chart(df_ts).encode(x=alt.X('t:Q', title='Temps (s)', scale=alt.Scale(domainMin=0)))
    courbe = base.mark_line().encode(
        y=alt.Y('intensite_db:Q', title='Intensité (dB, normalisée)', scale=alt.Scale(domain=[-80, 0])),
        tooltip=[alt.Tooltip('t:Q', format='.2f'), alt.Tooltip('intensite_db:Q', format='.1f')]
    )
    cal = courbe
    if df_pauses is not None and not df_pauses.empty:
        bandes = alt.Chart(df_pauses).mark_rect(opacity=0.25).encode(
            x='t_debut:Q', x2='t_fin:Q', color=alt.value('#888')
        )
        etiquettes = alt.Chart(df_pauses).mark_text(dy=-8).encode(
            x='t_debut:Q', text=alt.Text('duree_s:Q', format='.2f')
        )
        cal = cal + bandes + etiquettes
    if df_images is not None and not df_images.empty:
        pts = alt.Chart(df_images.dropna(subset=["t_image"])).mark_point(filled=True, size=60).encode(
            x='t_image:Q', y=alt.value(-5),
            shape=alt.value('triangle-up'),
            tooltip=['fichier_image:N', alt.Tooltip('t_image:Q', format='.0f')]
        )
        cal = cal + pts
    return cal.properties(height=260)

def chart_debit(df_ts, df_debit_sec):
    c_act = alt.Chart(df_ts).mark_line().encode(
        x=alt.X('t:Q', title='Temps (s)', scale=alt.Scale(domainMin=0)),
        y=alt.Y('activite_vocale_t:Q', title='Activité vocale (0–1)')
    )
    bars = alt.Chart(df_debit_sec).mark_bar(opacity=0.45).encode(
        x=alt.X('t_seconde:Q', title='Temps (s)', scale=alt.Scale(domainMin=0)),
        y=alt.Y('debit_seconde:Q', title='Débit par seconde (0–1)')
    )
    return alt.layer(bars, c_act).resolve_scale(x='shared', y='independent').properties(height=240)

def chart_parole_pause(df_parole_pause_sec):
    df_long = df_parole_pause_sec.melt(
        id_vars=['t_seconde'], value_vars=['parole_s','pause_s'],
        var_name='type', value_name='duree_s'
    )
    df_long['type'] = df_long['type'].replace({'parole_s':'parole','pause_s':'pause'})
    return alt.Chart(df_long).mark_bar().encode(
        x=alt.X('t_seconde:Q', title='Temps (s)', scale=alt.Scale(domainMin=0)),
        y=alt.Y('duree_s:Q', title='Durée (s) dans la seconde'),
        color=alt.Color('type:N', title='Type')
    ).properties(height=240)


# =========================
# whisper (timestamps seulement)
# =========================

@st.cache_resource(show_spinner=False)
def _load_whisper_model():
    """Charge Whisper une seule fois pour limiter le coût mémoire/CPU sur le VPS."""
    if not _whisper_ok:
        return None, "faster-whisper indisponible."
    try:
        model = WhisperModel("small", device="cpu", compute_type="int8")
        return model, "Modèle Whisper prêt."
    except Exception as exc:
        return None, f"Échec chargement Whisper : {exc}"

def transcrire_whisper_en_segments(file_bytes: bytes, langue: str = "fr") -> list[tuple[float, float, str]]:
    """renvoie [(t_debut,t_fin,texte)] ; utilisé uniquement pour construire df_align."""
    if not _whisper_ok:
        return []
    try:
        model, _ = _load_whisper_model()
        if model is None:
            return []
        import tempfile
        segs = []
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            tmp.write(file_bytes); tmp.flush()
            segments, info = model.transcribe(
                tmp.name, language=langue, beam_size=5, temperature=0.0,
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
                word_timestamps=False
            )
            for s in segments:
                if s.start is None or s.end is None:
                    continue
                segs.append((float(s.start), float(s.end), (s.text or "").strip()))
        return segs
    except Exception:
        return []


# =========================
# interface streamlit (+ persistance)
# =========================

st.set_page_config(page_title="Temporalité multimodale – SHS/Politique", layout="wide")
st.title("Analyse multimodale de la temporalité (texte + audio + images)")

for k in [
    "df_docs",
    "df_segt",
    "df_audio",
    "df_sega",
    "plots_audio",
    "df_images",
    "images_store",
    "images_store_map",
    "df_align",
    "df_align_sec",
    "df_align_mots",
    "df_attitudes",
    "df_emotions",
    "texts_map",
    "texte_corrige_global",
]:
    if k not in st.session_state:
        st.session_state[k] = (
            None
            if k
            in [
                "df_docs",
                "df_segt",
                "df_audio",
                "df_sega",
                "df_images",
                "df_align",
                "df_align_sec",
                "df_align_mots",
                "df_attitudes",
                "texte_corrige_global",
            ]
            else ({} if k in ["images_store_map", "texts_map"] else [])
        )

tab_data, tab_analyse, tab_anomalies, tab_tests, tab_attitudes, tab_emotions, tab_vecteuremo, tab_legend = st.tabs(
    [
        "1. Données",
        "2. Analyse",
        "3. Anomalies",
        "4. Tests croisés",
        "5. Attitudes",
        "6. Émotions",
        "7. Vecteur émotionnel",
        "Légendes",
    ]
)

with st.sidebar:
    st.header("Paramètres")
    nlp, msg_nlp = charger_spacy_transformer()
    st.caption(msg_nlp)
    locuteur_global = st.text_input("Identifiant locuteur", value="locuteur_1")
    use_whisper = st.checkbox("Transcrire l'audio avec Whisper (si installé)", value=False)
    fichiers_txt = st.file_uploader("Fichiers texte (.txt)", type=["txt"], accept_multiple_files=True)
    fichiers_audio = st.file_uploader("Fichiers audio (.wav, .mp3)", type=["wav", "mp3"], accept_multiple_files=True)
    fichier_timestamps = st.file_uploader(
        "Fichier timestamps (texte aligné)",
        type=["csv", "tsv", "txt", "json"],
        accept_multiple_files=False,
        help="Colonnes attendues : temps (s, mm:ss ou hh:mm:ss) et texte."
    )
    st.divider()
    st.caption("Images synchronisées (1 fps strict) : i_12s_1fps.jpg")
    format_image = st.radio(
        "Format des images (pour optimiser la détection de visage)",
        options=["16/9 (Paysage)", "9/16 (Portrait)"],
        index=0,
        horizontal=True
    )
    decalage_global_s = st.number_input("Décalage global images (s)", value=0.0, step=0.1, format="%.2f")
    fichiers_images = st.file_uploader("Images (.png, .jpg, .jpeg)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    lancer = st.button("Lancer l’analyse")

if lancer:
    with tab_data:
        st.subheader("Texte – Documents et segments (phrases)")
        docs_rows, segments_txt_rows = [], []
        df_align_sec_uploaded = None
        st.session_state["df_align_mots"] = pd.DataFrame(columns=["idx", "mot", "t_debut", "t_fin"])
        if fichiers_txt:
            if nlp is None:
                st.error("Aucun modèle spaCy utilisable. Installez fr_dep_news_trf.")
            else:
                texts_map = st.session_state.get("texts_map", {}) or {}
                for f in fichiers_txt:
                    contenu = f.read().decode("utf-8", errors="ignore")
                    texts_map[f.name] = contenu
                    out = indicateurs_texte_doc(contenu, nlp)
                    if out is None:
                        continue
                    feats, doc = out
                    feats.update({"modalite":"texte","fichier":f.name,"locuteur":locuteur_global})
                    docs_rows.append(feats)
                    segments_txt_rows.append(segments_texte(doc, f.name, locuteur_global))
                st.session_state["texts_map"] = texts_map
                st.session_state["texte_corrige_global"] = "\n\n".join(texts_map.values())

                if docs_rows:
                    df_docs = pd.DataFrame(docs_rows)
                    st.session_state["df_docs"] = df_docs.copy()
                    cols_docs = [
                        "modalite","fichier","locuteur",
                        "present_brut","passe_brut","futur_brut",
                        "ratio_present_par_verbe","ratio_passe_par_verbe","ratio_futur_par_verbe",
                        "deictiques_proches_brut","deictiques_eloignes_brut","deictiques_passes_brut","deictiques_plannificateur_brut",
                        "planification_brut",
                        "termes_present","termes_passe","termes_futur",
                        "termes_deictiques_proches","termes_deictiques_eloignes","termes_deictiques_passes","termes_deictiques_plannificateur",
                        "termes_planification","termes_causaux"
                    ]
                    st.dataframe(df_docs[[c for c in cols_docs if c in df_docs.columns]])

                if segments_txt_rows:
                    df_segt = pd.concat(segments_txt_rows, ignore_index=True)
                    st.session_state["df_segt"] = df_segt.copy()
                    cols_seg = [
                        "fichier","locuteur","segment","t_debut","t_fin",
                        "present_brut","passe_brut","futur_brut",
                        "ratio_present_par_verbe","ratio_passe_par_verbe","ratio_futur_par_verbe",
                        "deictiques_proches_brut","deictiques_eloignes_brut","deictiques_passes_brut","deictiques_plannificateur_brut",
                        "planification_brut",
                        "termes_present","termes_passe","termes_futur",
                        "termes_deictiques_proches","termes_deictiques_eloignes","termes_deictiques_passes","termes_deictiques_plannificateur",
                        "termes_planification"
                    ]
                    st.markdown("Segments (phrases) sans timing")
                    st.dataframe(df_segt[[c for c in cols_seg if c in df_segt.columns]])

        st.subheader("Audio – Récapitulatif et alignement (timestamps Whisper)")
        audio_rows, plots_audio = [], []
        segs_all = []
        segs_rows = []
        if fichiers_audio:
            for f in fichiers_audio:
                fbytes = f.read()
                y, sr, err = charger_audio_bytes(fbytes, sr_target=16000)
                if err:
                    st.error(f"{f.name} : {err}")
                    continue
                df_ts, df_pauses, df_debit_sec, df_parole_pause_sec, res = timeline_pauses_et_debit(y, sr)
                segs = transcrire_whisper_en_segments(fbytes, langue="fr") if use_whisper else []
                if segs:
                    segs_all.extend(segs)
                    segs_rows.extend(
                        {
                            "modalite": "audio_segment",
                            "fichier": f.name,
                            "locuteur": locuteur_global,
                            "t_debut": float(t0),
                            "t_fin": float(t1),
                            "segment": texte,
                        }
                        for t0, t1, texte in segs
                    )
                audio_rows.append({
                    "modalite":"audio","fichier":f.name,"locuteur":locuteur_global,
                    "nb_pauses":res["nb_pauses"],
                    "duree_pauses_totale_s":res["duree_pauses_totale_s"],
                    "duree_pause_moy_s":res["duree_pause_moy_s"],
                    "duree_pause_med_s":res["duree_pause_med_s"],
                    "parole_active_ratio":res["parole_active_ratio"],
                    "debit_proxy_sps":res["debit_proxy_sps"],
                    "duree_audio_s":res["duree_audio_s"]
                })
                plots_audio.append((f.name, df_ts, df_pauses, df_debit_sec, df_parole_pause_sec))

        if segs_rows:
            df_sega = pd.DataFrame(list(segs_rows))
            st.session_state["df_sega"] = df_sega.copy()
        else:
            st.session_state["df_sega"] = pd.DataFrame(columns=["modalite", "fichier", "locuteur", "t_debut", "t_fin", "segment"])

        texte_corrige = st.session_state.get("texte_corrige_global", "")
        if fichier_timestamps is not None:
            try:
                df_align_sec_uploaded = charger_timestamps_depuis_fichier(
                    fichier_timestamps.getvalue(), filename=fichier_timestamps.name
                )
            except Exception as e:
                st.warning(f"{fichier_timestamps.name} : lecture timestamps impossible ({e})")
                df_align_sec_uploaded = pd.DataFrame(columns=["t_sec", "texte_sec"])
            else:
                if df_align_sec_uploaded is not None and not df_align_sec_uploaded.empty:
                    st.success(f"{fichier_timestamps.name} : {len(df_align_sec_uploaded)} seconde(s) de texte importées.")
                    st.session_state["df_align_sec"] = df_align_sec_uploaded.copy()
                else:
                    st.warning(f"{fichier_timestamps.name} : aucun timestamp exploitable trouvé.")
        if use_whisper and segs_all and texte_corrige and nlp is not None:
            df_align = construire_df_timestamps_pour_fichier(
                texte_corrige=texte_corrige,
                segs_whisper=segs_all,
                nlp=nlp
            )
            st.session_state["df_align"] = df_align.copy()

            df_align_mots = construire_df_timestamps_mots(
                texte_corrige=texte_corrige,
                segs_whisper=segs_all,
            )
            st.session_state["df_align_mots"] = df_align_mots.copy()

            # construction robuste df_align_sec
            df_align_sec = None
            if isinstance(df_align, pd.DataFrame) and not df_align.empty:
                cols = set(df_align.columns.str.lower())
                if {"t_token","mot"}.issubset(cols):
                    tmp = df_align.rename(columns=str.lower).dropna(subset=["t_token"]).copy()
                    tmp["t_sec"] = tmp["t_token"].apply(lambda x: int(x) if pd.notna(x) else pd.NA)
                    df_align_sec = (tmp.groupby("t_sec")["mot"]
                                       .apply(lambda s: " ".join([w for w in s if isinstance(w, str) and w.strip()]))
                                       .reset_index()
                                       .rename(columns={"mot":"texte_sec"}))
                elif {"t_debut","t_fin"}.issubset(cols):
                    tmp = df_align.rename(columns=str.lower).copy()
                    txt_col = "texte" if "texte" in tmp.columns else ("segment" if "segment" in tmp.columns else None)
                    if txt_col is not None:
                        rows = []
                        for _, r in tmp.dropna(subset=["t_debut","t_fin"]).iterrows():
                            t0 = float(r["t_debut"]); t1 = float(r["t_fin"])
                            if not np.isfinite(t0) or not np.isfinite(t1):
                                continue
                            s0 = int(np.floor(t0)); s1 = int(np.floor(t1))
                            for s in range(s0, s1+1):
                                rows.append({"t_sec": s, "texte_piece": str(r[txt_col])})
                        if rows:
                            exp = pd.DataFrame(rows)
                            df_align_sec = (exp.groupby("t_sec")["texte_piece"]
                                              .apply(lambda s: " ".join([w for w in s if isinstance(w, str) and w.strip()]))
                                              .reset_index()
                                              .rename(columns={"texte_piece":"texte_sec"}))
            if df_align_sec is None:
                df_align_sec = pd.DataFrame(columns=["t_sec","texte_sec"])
            if df_align_sec_uploaded is not None and not df_align_sec_uploaded.empty:
                st.info("Timestamps Whisper calculés mais remplacés par le fichier importé.")
            else:
                st.session_state["df_align_sec"] = df_align_sec.copy()

        if st.session_state.get("df_align_sec") is None:
            st.session_state["df_align_sec"] = pd.DataFrame(columns=["t_sec", "texte_sec"])

        if audio_rows:
            df_audio = pd.DataFrame(audio_rows)
            st.session_state["df_audio"] = df_audio.copy()
            st.session_state["plots_audio"] = plots_audio
            cols_audio = [
                "modalite","fichier","locuteur",
                "nb_pauses","duree_pauses_totale_s","duree_pause_moy_s","duree_pause_med_s",
                "parole_active_ratio","debit_proxy_sps","duree_audio_s"
            ]
            st.dataframe(df_audio[cols_audio])

        st.subheader("Images – Inventaire (1 fps strict)")
        if fichiers_images:
            df_images = preparer_images(fichiers_images, decalage_global_s=decalage_global_s)
            st.session_state["df_images"] = df_images.copy()
        df_images = st.session_state.get("df_images")
        if df_images is not None:
            st.dataframe(df_images)

with tab_analyse:
    st.subheader("Graphiques audio")
    pa = st.session_state.get("plots_audio", [])
    df_images = st.session_state.get("df_images")
    if pa:
        for nom, df_ts, df_pauses, df_debit_sec, df_parole_pause_sec in pa:
            st.markdown(f"Intensité (dB) et pauses – {nom}")
            st.altair_chart(chart_intensite(df_ts, df_pauses, df_images=df_images), use_container_width=True)
            st.markdown(f"Débit de parole – {nom}")
            st.altair_chart(chart_debit(df_ts, df_debit_sec), use_container_width=True)
            st.markdown(f"Parole vs Pause (barres empilées) – {nom}")
            st.altair_chart(chart_parole_pause(df_parole_pause_sec), use_container_width=True)
    else:
        st.info("Chargez des fichiers audio pour afficher les graphiques.")

    st.subheader("Galerie d’images synchronisée (1 image = 1 seconde)")
    df_images = st.session_state.get("df_images")
    df_align_mots = st.session_state.get("df_align_mots")
    df_align_sec = st.session_state.get("df_align_sec")
    if df_images is None or df_images.empty:
        st.caption("Aucune image importée.")
    elif df_align_mots is not None and not df_align_mots.empty:
        col_opts = st.columns(3)
        with col_opts[0]:
            tol_mot_s = st.number_input("Tolérance alignement mot (s)", value=0.40, min_value=0.05, max_value=2.0, step=0.05, format="%.2f")
        with col_opts[1]:
            k_avant = st.number_input("Mots avant", value=4, min_value=0, max_value=20, step=1)
        with col_opts[2]:
            k_apres = st.number_input("Mots après", value=6, min_value=0, max_value=20, step=1)

        ui_images(
            df_images,
            df_mots_aligne=df_align_mots,
            titre="Galerie d’images synchronisée (mot à mot)",
            tol_mot_s=float(tol_mot_s),
            k_avant=int(k_avant),
            k_apres=int(k_apres),
        )
    else:
        st.info("Aucun alignement mot-à-mot disponible. Affichage par seconde (texte agrégé).")

        vals = df_images["t_image"].dropna().values if "t_image" in df_images.columns else []
        tmin = int(np.nanmin(vals)) if len(vals) else 0
        tmax = int(np.nanmax(vals)) if len(vals) else 0
        c1, c2 = st.columns(2)
        with c1:
            t0 = st.number_input("Début (s)", value=float(tmin), step=1.0, format="%.0f")
        with c2:
            t1 = st.number_input("Fin (s)", value=float(tmax), step=1.0, format="%.0f")
        if t1 < t0:
            st.warning("La fin doit être ≥ au début.")
        else:
            sel = df_images[df_images["t_image"].between(t0, t1)]
            st.caption(f"{len(sel)} image(s) entre {int(t0)}s et {int(t1)}s")

            texte_map = {}
            if df_align_sec is not None and not df_align_sec.empty:
                for _, r in df_align_sec.iterrows():
                    t_val = r.get("t_sec")
                    if pd.isna(t_val):
                        continue
                    try:
                        t_key = int(t_val)
                    except Exception:
                        continue
                    texte_map[t_key] = r.get("texte_sec", "")

            if not sel.empty:
                ncols = 5
                rows = [sel.iloc[i:i+ncols] for i in range(0, len(sel), ncols)]
                for r in rows:
                    cols = st.columns(len(r))
                    for c, (_, row) in zip(cols, r.iterrows()):
                        nm = row["fichier_image"]
                        b = get_image_bytes_by_name(nm)
                        tsec = int(row["t_image"]) if pd.notna(row["t_image"]) else None
                        caption_txt = texte_map.get(tsec, "")
                        if b is not None:
                            leg = f"{nm} — {tsec if tsec is not None else 'NA'}s"
                            if isinstance(caption_txt, str) and caption_txt.strip():
                                leg = leg + "\n" + caption_txt
                            c.image(b, caption=leg, use_container_width=True)
                        else:
                            c.write(nm)

with tab_anomalies:
    df_txt_segments = st.session_state.get("df_segt")
    df_audio_resumes = st.session_state.get("df_sega")
    if df_audio_resumes is None or getattr(df_audio_resumes, "empty", True):
        df_audio_resumes = st.session_state.get("df_audio")
    df_sync_nv = st.session_state.get("df_attitudes")
    try:
        ui_anomalies(
            df_texte=df_txt_segments,
            df_audio=df_audio_resumes,
            df_sync=df_sync_nv,
            temps_texte="t_debut",
            temps_audio="t_debut",
            temps_sync="t_image",
        )
    except Exception as e:
        st.error(f"Erreur interface anomalies : {e}")

with tab_tests:
    dfs = {}
    if st.session_state.get("df_docs") is not None: dfs["Texte – Documents"] = st.session_state["df_docs"]
    if st.session_state.get("df_segt") is not None: dfs["Texte – Segments"] = st.session_state["df_segt"]
    if st.session_state.get("df_audio") is not None: dfs["Audio – Récapitulatif"] = st.session_state["df_audio"]
    if st.session_state.get("df_sega") is not None: dfs["Audio – Segments (Whisper)"] = st.session_state["df_sega"]
    ui_tests_auto(dfs)
    st.divider()
    ui_tests_croises(dfs)

with tab_attitudes:
    st.subheader("Attitudes (images -> AUs / postures)")
    df_images = st.session_state.get("df_images")
    images_store_list = st.session_state.get("images_store", []) or []
    images_store_map = st.session_state.get("images_store_map", {}) or {}

    if df_images is None or df_images.empty:
        st.info("Importez d’abord des images (i_{N}s_1fps.jpg).")
    else:
        store_norm = []
        if isinstance(images_store_list, list) and images_store_list:
            for it in images_store_list:
                if isinstance(it, dict):
                    nom = it.get("name")
                    bts = it.get("bytes")
                    if nom is None or bts is None:
                        continue
                    try:
                        store_norm.append({"name": str(nom), "bytes": bytes(bts)})
                    except Exception:
                        continue
                elif isinstance(it, (list, tuple)) and len(it) == 2:
                    nom, bts = it
                    try:
                        store_norm.append({"name": str(nom), "bytes": bytes(bts)})
                    except Exception:
                        continue
        if not store_norm and isinstance(images_store_map, dict) and images_store_map:
            for nom, bts in images_store_map.items():
                try:
                    store_norm.append({"name": str(nom), "bytes": bytes(bts)})
                except Exception:
                    continue

        try:
            df_att_images, df_att_agrege = calculer_attitudes_depuis_images(store_norm)
        except Exception as e:
            st.error(f"Erreur attitudes: {e}")
            df_att_images = pd.DataFrame(columns=["fichier_image", "t_image"])
            df_att_agrege = pd.DataFrame()

        if isinstance(df_att_images, pd.DataFrame) and not df_att_images.empty:
            st.session_state["df_attitudes"] = df_att_images.copy()
            try:
                ui_attitudes_images(df_att_images, df_att_agrege)
            except Exception as e:
                st.warning(f"Affichage attitudes: {e}")
        else:
            st.caption("Aucune mesure d’attitudes calculée.")

with tab_emotions:
    df_images = st.session_state.get("df_images")
    try:
        ui_emotions_images(df_images)
    except Exception as e:
        st.error(f"Erreur interface émotions : {e}")

with tab_vecteuremo:
    try:
        ui_vecteur_emotionnel()
    except Exception as e:
        st.error(f"Erreur interface vecteur émotionnel : {e}")

with tab_legend:
    afficher_legendes()
