from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import time

import streamlit as st

from app_runtime import resolve_app_data_dir

APP_DATA_DIR = resolve_app_data_dir()
APP_TICKET_ID = os.environ.get("APP_TICKET_ID", "extraction-multimedia")


def _identifiant_sur() -> str:
    identifiant = (APP_TICKET_ID or "extraction-multimedia").strip()
    identifiant = re.sub(r"[^A-Za-z0-9_.-]+", "-", identifiant)
    return identifiant or "extraction-multimedia"


def chemin_cookies_session(repertoire_sortie: Path) -> Path:
    return repertoire_sortie / "cookies.txt"


def chemin_cookies_persistant() -> Path:
    dossier = os.environ.get("APP_COOKIES_DIR", "").strip()
    if dossier:
        return Path(dossier) / "cookies.txt"
    return APP_DATA_DIR / "cookies" / _identifiant_sur() / "cookies.txt"


def _chemins_cookies(repertoire_sortie: Path) -> list[tuple[str, Path]]:
    return [
        ("persistant", chemin_cookies_persistant()),
        ("session", chemin_cookies_session(repertoire_sortie)),
    ]


def _chemin_cookies_existant(repertoire_sortie: Path) -> Path | None:
    for _label, chemin in _chemins_cookies(repertoire_sortie):
        try:
            if chemin.exists() and chemin.stat().st_size > 0:
                return chemin
        except Exception:
            continue
    return None


def _copier_vers_session_si_possible(repertoire_sortie: Path, source: Path) -> None:
    destination = chemin_cookies_session(repertoire_sortie)
    if source == destination:
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    except Exception:
        pass


def cookies_disponibles(repertoire_sortie: Path) -> bool:
    return _chemin_cookies_existant(repertoire_sortie) is not None


def info_cookies(repertoire_sortie: Path) -> str:
    infos = []
    for label, chemin in _chemins_cookies(repertoire_sortie):
        try:
            if chemin.exists() and chemin.stat().st_size > 0:
                horodatage = datetime.fromtimestamp(chemin.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                infos.append(f"cookies.txt {label} présent ({chemin.stat().st_size} octets) - mis à jour le {horodatage}")
        except Exception:
            continue
    if not infos:
        return "Aucun cookies mémorisé."
    return " | ".join(infos)


def diagnostic_expiration_cookies(contenu: str) -> str:
    maintenant = int(time.time())
    expirations = []
    youtube_entries = 0
    for ligne in contenu.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") and not ligne.startswith("#HttpOnly_"):
            continue
        ligne_parse = ligne.replace("#HttpOnly_", "", 1)
        colonnes = ligne_parse.split("\t")
        if len(colonnes) < 7:
            continue
        domaine = colonnes[0].lower()
        if "youtube.com" not in domaine and "google.com" not in domaine:
            continue
        youtube_entries += 1
        try:
            expiration = int(colonnes[4])
        except ValueError:
            continue
        if expiration > 0:
            expirations.append(expiration)

    if youtube_entries == 0:
        return "Aucune entrée YouTube/Google exploitable détectée dans le cookies.txt."
    if not expirations:
        return "Cookies YouTube/Google détectés ; plusieurs entrées sont des cookies de session sans date d'expiration."

    expires_max = max(expirations)
    secondes_restantes = expires_max - maintenant
    if secondes_restantes <= 0:
        return "Cookies YouTube/Google détectés mais toutes les dates d'expiration utiles semblent dépassées."
    minutes = max(1, int(secondes_restantes / 60))
    if secondes_restantes < 3600:
        return f"Attention : le cookies.txt contient des cookies YouTube/Google qui expirent bientôt (~{minutes} min)."
    heures = int(secondes_restantes / 3600)
    return f"Cookies YouTube/Google détectés ; expiration utile la plus lointaine dans environ {heures} h."


def diagnostic_cookies(chemin: Path) -> str:
    if not chemin.exists():
        return "Aucun cookies présent."
    try:
        contenu = chemin.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Lecture cookies impossible : {e}"

    premiere_ligne = contenu.splitlines()[0].strip() if contenu.splitlines() else ""
    if "Netscape HTTP Cookie File" not in premiere_ligne:
        return "Format inattendu : le fichier ne ressemble pas à un export Netscape cookies.txt."
    if "youtube.com" not in contenu and ".youtube.com" not in contenu:
        return "Le cookies.txt ne contient aucune entrée YouTube détectée."
    if chemin.stat().st_size < 1024:
        return "Le cookies.txt semble très court ; export probablement incomplet."
    return "Format cookies.txt plausible pour yt-dlp. " + diagnostic_expiration_cookies(contenu)


def memoriser_cookies_depuis_upload(fichier_streamlit, repertoire_sortie: Path, forcer: bool):
    if fichier_streamlit is None:
        chemin_existant = _chemin_cookies_existant(repertoire_sortie)
        if chemin_existant is not None:
            _copier_vers_session_si_possible(repertoire_sortie, chemin_existant)
            return chemin_existant, "Réutilisation du cookies.txt mémorisé."
        return None, "Aucun cookies fourni et aucun cookies mémorisé."

    chemin_existant = _chemin_cookies_existant(repertoire_sortie)
    if chemin_existant is not None and not forcer:
        _copier_vers_session_si_possible(repertoire_sortie, chemin_existant)
        return chemin_existant, "Un cookies.txt est déjà mémorisé. Cochez 'Remplacer le cookies existant' pour le remplacer."

    try:
        contenu = fichier_streamlit.getbuffer() if hasattr(fichier_streamlit, "getbuffer") else fichier_streamlit.read()
        contenu_bytes = bytes(contenu)
        destination_session = chemin_cookies_session(repertoire_sortie)
        destination_persistante = chemin_cookies_persistant()
        for destination in (destination_session, destination_persistante):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(contenu_bytes)
        return destination_persistante, "cookies.txt mis à jour dans le stockage persistant de l'application."
    except Exception as e:
        return None, f"Échec de la mémorisation du cookies.txt : {e}"


def chemin_cookies_a_utiliser(repertoire_sortie: Path, fichier_streamlit, forcer: bool):
    if fichier_streamlit is not None:
        return memoriser_cookies_depuis_upload(fichier_streamlit, repertoire_sortie, forcer)
    chemin_existant = _chemin_cookies_existant(repertoire_sortie)
    if chemin_existant is not None:
        _copier_vers_session_si_possible(repertoire_sortie, chemin_existant)
        return chemin_existant, "Réutilisation du cookies.txt mémorisé."
    return None, "Aucun cookies disponible."


def afficher_section_cookies(repertoire_sortie: Path):
    st.markdown("#### Cookies YouTube (optionnel)")
    col1, col2 = st.columns([3, 2])
    with col1:
        cookies_file = st.file_uploader("Fichier cookies.txt", type=["txt"], key="cookies_file")
    with col2:
        forcer = st.checkbox("Remplacer le cookies existant", value=True, key="forcer_remplacement_cookies")

    st.caption(info_cookies(repertoire_sortie))

    cookies_path, message = chemin_cookies_a_utiliser(repertoire_sortie, cookies_file, forcer)
    if "aucun cookies" in message.lower():
        st.info(message)
    elif "réutilisation" in message.lower():
        st.info(message)
    elif "mémorisé" in message or "mis à jour" in message:
        st.success(message)
    else:
        st.warning(message)

    if cookies_path is not None:
        diagnostic = diagnostic_cookies(cookies_path)
        if diagnostic.startswith("Format cookies.txt plausible"):
            st.caption(diagnostic)
        else:
            st.warning(diagnostic)

    return cookies_path
