from datetime import datetime
from pathlib import Path

import streamlit as st


def chemin_cookies_session(repertoire_sortie: Path) -> Path:
    return repertoire_sortie / "cookies.txt"


def cookies_disponibles(repertoire_sortie: Path) -> bool:
    chemin = chemin_cookies_session(repertoire_sortie)
    return chemin.exists() and chemin.stat().st_size > 0


def info_cookies(repertoire_sortie: Path) -> str:
    chemin = chemin_cookies_session(repertoire_sortie)
    if not chemin.exists():
        return "Aucun cookies memorise pour cette session."
    horodatage = datetime.fromtimestamp(chemin.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return f"cookies.txt present ({chemin.stat().st_size} octets) - mis a jour le {horodatage}"


def diagnostic_cookies(chemin: Path) -> str:
    if not chemin.exists():
        return "Aucun cookies present."
    try:
        contenu = chemin.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Lecture cookies impossible : {e}"

    premiere_ligne = contenu.splitlines()[0].strip() if contenu.splitlines() else ""
    if "Netscape HTTP Cookie File" not in premiere_ligne:
        return "Format inattendu : le fichier ne ressemble pas a un export Netscape cookies.txt."
    if "youtube.com" not in contenu and ".youtube.com" not in contenu:
        return "Le cookies.txt ne contient aucune entree YouTube detectee."
    if chemin.stat().st_size < 1024:
        return "Le cookies.txt semble tres court ; export probablement incomplet."
    return "Format cookies.txt plausible pour yt-dlp."


def memoriser_cookies_depuis_upload(fichier_streamlit, repertoire_sortie: Path, forcer: bool):
    if fichier_streamlit is None:
        if cookies_disponibles(repertoire_sortie):
            return chemin_cookies_session(repertoire_sortie), "Reutilisation du cookies.txt memorise pour cette session."
        return None, "Aucun cookies fourni et aucun cookies memorise."

    destination = chemin_cookies_session(repertoire_sortie)
    if destination.exists() and not forcer:
        return destination, "Un cookies.txt est deja memorise. Cochez 'Forcer le remplacement' pour le remplacer."

    try:
        destination.write_bytes(fichier_streamlit.read())
        return destination, "cookies.txt memorise dans l'espace temporaire de cette session."
    except Exception as e:
        return None, f"Echec de la memorisation du cookies.txt : {e}"


def chemin_cookies_a_utiliser(repertoire_sortie: Path, fichier_streamlit, forcer: bool):
    if fichier_streamlit is not None:
        return memoriser_cookies_depuis_upload(fichier_streamlit, repertoire_sortie, forcer)
    if cookies_disponibles(repertoire_sortie):
        return chemin_cookies_session(repertoire_sortie), "Reutilisation du cookies.txt memorise pour cette session."
    return None, "Aucun cookies disponible."


def afficher_section_cookies(repertoire_sortie: Path):
    st.markdown("#### Cookies YouTube (optionnel)")
    col1, col2 = st.columns([3, 2])
    with col1:
        cookies_file = st.file_uploader("Fichier cookies.txt", type=["txt"], key="cookies_file")
    with col2:
        forcer = st.checkbox("Forcer le remplacement", value=False, key="forcer_remplacement_cookies")

    st.caption(info_cookies(repertoire_sortie))

    cookies_path, message = chemin_cookies_a_utiliser(repertoire_sortie, cookies_file, forcer)
    if "memorise" in message:
        st.success(message)
    elif "reutilisation" in message.lower():
        st.info(message)
    elif "aucun cookies" in message.lower():
        st.info(message)
    else:
        st.warning(message)

    if cookies_path is not None:
        diagnostic = diagnostic_cookies(cookies_path)
        if diagnostic.startswith("Format cookies.txt plausible"):
            st.caption(diagnostic)
        else:
            st.warning(diagnostic)

    return cookies_path
