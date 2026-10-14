"""Interface sobre de VisioTrack : imports, analyse séquentielle et exports."""

import os
import json
import tempfile
import threading
from pathlib import Path

import pandas as pd
import streamlit as st

from detection import CATEGORIES, inventorier_sources, traiter_lot


@st.cache_resource
def obtenir_verrou():
    """Limiter le processus Streamlit à un seul lot actif, toutes sessions confondues."""
    return threading.Lock()


def afficher_resultats():
    """Conserver le dernier résultat pendant les téléchargements et les réaffichages."""
    if "visiotrack_resultats" not in st.session_state:
        return
    tableau = pd.DataFrame(st.session_state.visiotrack_resultats)
    st.subheader("Résultats")
    succes = tableau[tableau.statut == "ok"].video_id.nunique()
    erreurs = tableau[tableau.statut == "erreur"].video_id.nunique()
    st.caption(f"{succes} vidéo(s) analysée(s) · {erreurs} erreur(s). Une ligne par vidéo et catégorie.")
    st.dataframe(tableau, hide_index=True, width="stretch", column_config={
        "video_id": "Identifiant", "source": "Vidéo", "statut": "Statut", "erreur": "Erreur",
        "duree_totale_s": st.column_config.NumberColumn("Durée totale (s)", format="%.3f"),
        "categorie": "Objet", "objet_detecte": "Détecté",
        "duree_visibilite_s": st.column_config.NumberColumn("Visibilité (s)", format="%.3f"),
        "pourcentage_visible": st.column_config.NumberColumn("Temps visible (%)", format="%.2f"),
        "maximum_simultane": "Maximum simultané",
        "frequence_demandee_ips": "Images/s demandées", "images_analysees": "Images analysées",
    })
    repertoire = Path(st.session_state.visiotrack_exports.name)
    afficher_apercu(tableau, repertoire)
    for colonne, (nom, libelle) in zip(st.columns(3), [
        ("resultats", "Résultats CSV"), ("intervalles", "Intervalles CSV"),
        ("detections", "Détections CSV"),
    ]):
        with colonne:
            # Streamlit lit les exports, mais aucune vidéo n'est conservée ici.
            with (repertoire / f"{nom}.csv").open("rb") as fichier:
                st.download_button(libelle, fichier, f"visiotrack_{nom}.csv",
                                   mime="text/csv", on_click="ignore", width="stretch")


def afficher_apercu(tableau, repertoire):
    """Ne charger dans le lecteur que la vidéo sélectionnée dans le lot."""
    videos = tableau[tableau.statut == "ok"].drop_duplicates("video_id").set_index("video_id")
    manifeste = repertoire / "apercus.json"
    if videos.empty or not manifeste.exists():
        return
    apercus = json.loads(manifeste.read_text(encoding="utf-8"))
    st.subheader("Vidéo avec détections")
    identifiant = st.selectbox("Vidéo à regarder", list(videos.index),
                              format_func=lambda cle: f"{cle} — {videos.loc[cle, 'source']}")
    apercu = apercus.get(identifiant, {})
    if "fichier" in apercu:
        # Le chemin pointe vers un MP4 H.264 de la session, compatible navigateur.
        # Largeur compacte : une vidéo TikTok 9:16 occupe environ 360 × 640 px,
        # sans recadrer ni déformer les vidéos ayant un autre rapport d'image.
        st.video(str(repertoire / apercu["fichier"]), width=360)
        frequence = videos.loc[identifiant, "frequence_demandee_ips"]
        st.caption(f"Cadres verts : objets détectés. Positions actualisées à {frequence:g} image(s)/s "
                   "; cadres effacés dès qu'un changement de plan est repéré, "
                   "jusqu'à une nouvelle détection. La visibilité ne prouve pas une utilisation.")
    else:
        st.warning(apercu.get("erreur", "Aperçu indisponible pour cette vidéo."))


def afficher_application():
    """Construire les seuls réglages nécessaires à l'analyse."""
    st.set_page_config(page_title="VisioTrack", page_icon="📱", layout="wide")
    st.title("VisioTrack")
    st.write("Mesurer la visibilité des smartphones et des objets dans vos vidéos.")
    st.caption("La présence à l'écran est mesurée ; elle ne prouve pas une utilisation effective.")

    with st.form("analyse"):
        urls = st.text_area("URL YouTube ou TikTok", placeholder="Une URL HTTPS par ligne", height=90)
        fichiers = st.file_uploader("Fichiers MP4 ou archives ZIP", type=["mp4", "zip"],
                                    accept_multiple_files=True)
        categories = st.multiselect("Objets à détecter", list(CATEGORIES), default=[67],
                                    format_func=lambda cle: CATEGORIES[cle].capitalize())
        frequence = st.number_input("Images analysées par seconde", min_value=0.1,
                                    max_value=30.0, value=1.0, step=0.5)
        dossier_serveur = os.getenv("VISIOTRACK_VIDEO_DIR")
        if dossier_serveur:
            st.caption("Les MP4 du dossier serveur configuré seront également analysés, sous-dossiers inclus.")
        lancer = st.form_submit_button("Lancer l'analyse", type="primary")

    st.caption("Les durées sont estimées par échantillonnage. À 1 image/s, une apparition brève peut être manquée.")
    if lancer:
        sources = inventorier_sources(fichiers, urls, dossier_serveur)
        if not categories or not sources:
            st.error("Ajoutez au moins une vidéo et sélectionnez un objet à détecter.")
        elif not obtenir_verrou().acquire(blocking=False):
            st.warning("Une analyse est déjà en cours sur ce serveur. Relancez après sa fin.")
        else:
            temporaire = None
            try:
                temporaire = tempfile.TemporaryDirectory(prefix="visiotrack-")
                barre_lot = st.progress(0.0, text=f"Préparation de {len(sources)} vidéo(s)…")
                barre_video = st.progress(0.0, text="Chargement du modèle CPU…")

                def actualiser_progression(numero, total, nom, valeur):
                    """Afficher une progression globale et celle de la vidéo courante."""
                    barre_lot.progress((numero - 1 + valeur) / total,
                                       text=f"Vidéo {numero}/{total}")
                    barre_video.progress(valeur, text=nom)

                with st.spinner("Analyse en cours…"):
                    resultats = traiter_lot(sources, categories, frequence, temporaire.name,
                                            actualiser_progression)
                ancien = st.session_state.get("visiotrack_exports")
                st.session_state.visiotrack_exports = temporaire
                st.session_state.visiotrack_resultats = resultats
                temporaire = None  # La session conserve les CSV et les aperçus annotés.
                if ancien:
                    ancien.cleanup()
            except Exception as erreur:
                st.error(f"L'analyse n'a pas pu aboutir : {erreur}")
            finally:
                if temporaire:
                    temporaire.cleanup()
                obtenir_verrou().release()
    afficher_resultats()


if __name__ == "__main__":
    afficher_application()
