# pages/3_Analyse_audio.py
# Analyse audio : pauses, intensité (pics), débit approximatif.
# Entrée : WAV ou MP3. On affiche l’enveloppe RMS, on détecte les pauses (> dur_min_pause),
# on trouve des pics d’intensité, et on estime un débit de parole via segments "voisés" naïfs.

import streamlit as st
from pathlib import Path
import numpy as np
import soundfile as sf
import io

from app_runtime import enforce_access, heartbeat

st.set_page_config(page_title="Analyse audio", layout="wide")
enforce_access()
st.title("Analyse audio : pauses, intensité, débit")

f = st.file_uploader("Importer un fichier audio (.wav, .mp3 via ffmpeg non nécessaire ici si déjà wav)", type=["wav"])
win_ms = st.slider("Fenêtre RMS (ms)", 10, 200, 50, 10)
seuil_silence = st.slider("Seuil silence (RMS relatif)", 0.01, 0.20, 0.05, 0.01)
dur_min_pause = st.slider("Durée minimale d’une pause (ms)", 100, 1500, 300, 50)
k_pic = st.slider("k pour détection de pics (μ + kσ)", 1.0, 6.0, 3.0, 0.1)

def lire_audio(path_or_buf):
    data, sr = sf.read(path_or_buf)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), sr

def enveloppe_rms(x, sr, win_ms):
    n = int(sr * win_ms / 1000)
    n = max(4, n)
    pad = n // 2
    x2 = np.pad(x, (pad, pad), mode='reflect')
    rms = np.sqrt(np.convolve(x2**2, np.ones(n)/n, mode="valid"))
    t = np.arange(len(rms)) / sr
    return t, rms

def detecter_pauses(t, rms, seuil, dur_min_s):
    low = rms < seuil
    pauses = []
    start = None
    for i, v in enumerate(low):
        if v and start is None:
            start = i
        if (not v or i == len(low)-1) and start is not None:
            end = i if not v else i
            if (t[end] - t[start]) >= dur_min_s:
                pauses.append((t[start], t[end]))
            start = None
    return pauses

def pics_intensite(t, rms, k):
    mu, si = float(rms.mean()), float(rms.std())
    thr = mu + k * si
    idx = np.where(rms >= thr)[0]
    # Regrouper en pics séparés
    pics = []
    if idx.size:
        start = idx[0]; last = idx[0]
        for i in idx[1:]:
            if i == last + 1:
                last = i
            else:
                mid = (start + last)//2
                pics.append((t[mid], rms[mid]))
                start = i; last = i
        mid = (start + last)//2
        pics.append((t[mid], rms[mid]))
    return thr, pics

def debit_parole_estime(t, rms, seuil_voix):
    # Débit approximatif basé sur “segments voix” vs silence, puis pics locaux comme proxy syllabes.
    voix = rms >= seuil_voix
    segs = []
    s = None
    for i, v in enumerate(voix):
        if v and s is None: s = i
        if (not v or i == len(voix)-1) and s is not None:
            e = i if not v else i
            segs.append((t[s], t[e] if e < len(t) else t[-1]))
            s = None
    duree = t[-1] if len(t) else 0
    nb_segs = len(segs)
    # Proxy débit : nb_segs / minute
    wpm = (nb_segs / (duree/60.0)) if duree > 0 else 0.0
    return wpm, segs

if f and st.button("Analyser"):
    heartbeat()
    data = f.read()
    try:
        x, sr = lire_audio(io.BytesIO(data))
    except Exception as e:
        st.error(f"Lecture audio échouée : {e}")
        st.stop()
    t, rms = enveloppe_rms(x, sr, win_ms)
    seuil_abs = float(rms.max()) * seuil_silence
    pauses = detecter_pauses(t, rms, seuil_abs, dur_min_pause/1000.0)
    thr, pics = pics_intensite(t, rms, k_pic)
    wpm, segs_voix = debit_parole_estime(t, rms, seuil_abs*2.0)

    st.write(f"Durée : {t[-1]:.1f}s — SR : {sr} Hz")
    st.write(f"Pauses détectées : {len(pauses)} — Débit estimé : {wpm:.1f} segments/min")

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=rms, mode="lines", name="RMS"))
    fig.add_hline(y=thr, line=dict(dash="dot"), annotation_text="Seuil pics")
    for a, b in pauses:
        fig.add_vrect(x0=a, x1=b, fillcolor="red", opacity=0.15, line_width=0)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    st.subheader("Pauses")
    for i, (a, b) in enumerate(pauses, 1):
        st.write(f"{i:02d}. {a:.2f}s → {b:.2f}s ({b-a:.2f}s)")

    st.subheader("Pics d’intensité")
    for i, (tt, vv) in enumerate(pics, 1):
        st.write(f"{i:02d}. {tt:.2f}s (RMS={vv:.3f})")

    st.subheader("Segments “voix”")
    for i, (a, b) in enumerate(segs_voix, 1):
        st.write(f"{i:02d}. {a:.2f}s → {b:.2f}s ({b-a:.2f}s)")
    heartbeat()
