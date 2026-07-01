# main.py
# Page d’accueil : choix de la source (URL + cookies, ou fichier local),
# préparation de la vidéo de base (HD ou compressée), intervalle optionnel,
# et aperçu. Aucune extraction ici : tout se fait dans les onglets.

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

import streamlit as st
from pathlib import Path
import subprocess

from app_runtime import enforce_access, heartbeat
from core_media import (
    initialiser_repertoires, info_ffmpeg, afficher_message_cookies,
    preparer_depuis_url, preparer_depuis_fichier, SEUIL_APERCU_OCTETS
)

# ----------------- Initialisation -----------------
BASE_DIR, REP_SORTIE, REP_TMP = initialiser_repertoires()

st.set_page_config(page_title="Source & Préparation", layout="wide")
enforce_access()
st.title("Source & Préparation de la vidéo")
st.markdown("**www.codeandcortex.fr**")

# Etat partagé
st.session_state.setdefault("video_base", None)
st.session_state.setdefault("base_court", None)
st.session_state.setdefault("url", "")
st.session_state.setdefault("cookies_path", None)
st.session_state.setdefault("local_temp_path", None)
st.session_state.setdefault("local_name_base", None)
st.session_state.setdefault("debut_secs", 0)
st.session_state.setdefault("fin_secs", 10)

# ----------------- Diagnostic -----------------
with st.expander("Diagnostic système"):
    chemin_ffmpeg, version_l1 = info_ffmpeg()
    if chemin_ffmpeg:
        st.write(f"ffmpeg : {chemin_ffmpeg}")
        if version_l1:
            st.code(version_l1)
    else:
        st.write("ffmpeg : introuvable")

# ----------------- Source -----------------
st.subheader("Choix de la source")

colL, colR = st.columns([2, 1])

with colL:
    url = st.text_input("URL YouTube", value=st.session_state["url"])
    st.session_state["url"] = url

cookies_path = afficher_message_cookies(REP_SORTIE)

with colR:
    qualite = st.radio("Qualité vidéo de base", ["Compressée (1280p, CRF 28)", "HD (max qualité dispo)"], index=0)
    verbose = st.checkbox("Mode diagnostic yt-dl", value=False)

st.markdown(
    "Par défaut, l’extraction porte sur **toute la vidéo**. "
    "Active un intervalle personnalisé si besoin. "
    "Si la vidéo est restreinte (403), exporte tes cookies avec l’extension Firefox : "
    "[cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)."
)

etendue = st.radio("Étendue à préparer", ["Toute la vidéo", "Intervalle personnalisé"], index=0, horizontal=True)
utiliser_intervalle = (etendue == "Intervalle personnalisé")
if utiliser_intervalle:
    st.info(f"Intervalle personnalisé activé : de {st.session_state['debut_secs']}s à {st.session_state['fin_secs']}s. La préparation traitera uniquement cet intervalle.")
    c1, c2 = st.columns(2)
    st.session_state["debut_secs"] = c1.number_input("Début (s)", min_value=0, value=st.session_state["debut_secs"])
    st.session_state["fin_secs"] = c2.number_input("Fin (s)", min_value=1, value=st.session_state["fin_secs"])
    if st.session_state["fin_secs"] <= st.session_state["debut_secs"]:
        st.warning("La fin doit être strictement supérieure au début.")

st.subheader("Ou importer un fichier local")
f_local = st.file_uploader("Importer une vidéo (.mp4)", type=["mp4"])
if f_local is not None:
    tmp = REP_TMP / f"local_{f_local.name}"
    with open(tmp, "wb") as g:
        g.write(f_local.read())
    st.session_state["local_temp_path"] = str(tmp)
    st.session_state["local_name_base"] = Path(f_local.name).stem
    st.success(f"Fichier local chargé : {f_local.name}")

if st.button("Préparer la vidéo"):
    heartbeat()
    with st.spinner("Préparation en cours..."):
        if st.session_state.get("local_temp_path"):
            ok, msg = preparer_depuis_fichier(
                Path(st.session_state["local_temp_path"]),
                st.session_state["local_name_base"],
                qualite,
                utiliser_intervalle,
                st.session_state["debut_secs"],
                st.session_state["fin_secs"]
            )
        elif st.session_state["url"]:
            ok, msg = preparer_depuis_url(
                st.session_state["url"],
                cookies_path,
                qualite,
                verbose,
                utiliser_intervalle,
                st.session_state["debut_secs"],
                st.session_state["fin_secs"]
            )
        else:
            st.warning("Veuillez fournir une URL ou un fichier local.")
            ok, msg = False, None

        if ok:
            st.session_state["video_base"], st.session_state["base_court"] = msg
            heartbeat()
            st.success(f"Vidéo prête : {Path(st.session_state['video_base']).name}")
        elif msg:
            st.error(msg)

st.subheader("Aperçu")
apercu_ok = False
if st.session_state.get("video_base") and Path(st.session_state["video_base"]).exists():
    p = Path(st.session_state["video_base"])
    if p.stat().st_size <= SEUIL_APERCU_OCTETS:
        with open(p, "rb") as fh:
            st.video(fh.read(), format="video/mp4")
            apercu_ok = True

if not apercu_ok:
    st.info("Aperçu indisponible ou fichier volumineux. Utilisez les onglets pour l’extraction et les analyses.")
