"""Interface sobre de VisioTrack : imports, analyse séquentielle et exports."""

import os
import tempfile
import threading
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from detection import CATEGORIES, inventorier_sources, traiter_lot
from montage import creer_montage


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
    for colonne, (nom, libelle) in zip(st.columns(3), [
        ("resultats", "Résultats CSV"), ("intervalles", "Intervalles CSV"),
        ("detections", "Détections CSV"),
    ]):
        with colonne:
            # Streamlit lit les exports, mais aucune vidéo n'est conservée ici.
            with (repertoire / f"{nom}.csv").open("rb") as fichier:
                st.download_button(libelle, fichier, f"visiotrack_{nom}.csv",
                                   mime="text/csv", on_click="ignore", width="stretch")



def afficher_montage():
    """Proposer quatre URL et produire un quadriptyque vidéo indépendant des CSV."""
    st.subheader("Montage comparatif — quatre vidéos")
    st.caption(
        "Quatre fenêtres 2 × 2, rectangles de détection et compteurs des smartphones ; "
        "sans titres ni audio. Le montage s'arrête à la fin de la vidéo la plus longue, "
        "avec gel de la dernière image des vidéos plus courtes."
    )
    with st.form("montage_comparatif"):
        colonnes = st.columns(2)
        urls_montage = []
        for indice in range(4):
            with colonnes[indice % 2]:
                urls_montage.append(st.text_input(
                    f"URL {indice + 1}", key=f"visiotrack_url_montage_{indice}",
                    placeholder="https://www.youtube.com/watch?v=... ou https://www.tiktok.com/..."
                ))
        frequence_montage = st.number_input(
            "Images analysées par seconde (montage)", min_value=0.5,
            max_value=15.0, value=5.0, step=0.5,
            help="L'analyse de cinq images par seconde limite le temps de calcul. "
                 "Les rectangles sont conservés entre deux images analysées."
        )
        lancer_montage = st.form_submit_button(
            "Générer le montage MP4 (1920 × 1080)", type="primary"
        )

    if lancer_montage:
        if any(not url.strip() for url in urls_montage):
            st.error("Renseignez les quatre URL avant de générer le montage.")
        elif not obtenir_verrou().acquire(blocking=False):
            st.warning("Une analyse VisioTrack est déjà en cours sur ce serveur.")
        else:
            temporaire = None
            try:
                temporaire = tempfile.TemporaryDirectory(prefix="visiotrack-montage-")
                barre = st.progress(0.0, text="Préparation des quatre vidéos…")

                def actualiser_montage(numero, total, etape, avancement):
                    """Signaler le téléchargement, l'analyse et le rendu final."""
                    valeur = (numero - 1 + avancement) / total
                    barre.progress(min(1.0, max(0.0, valeur)),
                                   text=f"{etape} ({numero}/{total})")

                with st.spinner("Création du quadriptyque…"):
                    sortie, duree = creer_montage(
                        urls_montage, temporaire.name, frequence_montage, actualiser_montage
                    )
                ancien = st.session_state.get("visiotrack_montage_exports")
                st.session_state.visiotrack_montage_exports = temporaire
                st.session_state.visiotrack_montage_duree = duree
                temporaire = None
                if ancien:
                    ancien.cleanup()
            except Exception as erreur:
                st.error(f"Impossible de produire le quadriptyque : {erreur}")
            finally:
                if temporaire:
                    temporaire.cleanup()
                obtenir_verrou().release()

    if "visiotrack_montage_exports" in st.session_state:
        fichier = (Path(st.session_state.visiotrack_montage_exports.name)
                   / "visiotrack_montage_4_fenetres.mp4")
        if fichier.is_file():
            st.success(
                f"Montage créé — durée : {st.session_state.visiotrack_montage_duree:.1f} s "
                "— format : MP4 1920 × 1080, 15 images/s."
            )
            with fichier.open("rb") as entree:
                st.download_button(
                    "Télécharger le montage MP4", entree,
                    file_name="visiotrack_montage_4_fenetres.mp4",
                    mime="video/mp4", on_click="ignore", width="stretch"
                )


def afficher_application():
    """Construire les seuls réglages nécessaires à l'analyse."""
    st.set_page_config(page_title="VisioTrack", page_icon="📱", layout="wide")
    # Même propriété Analytics que la home ; une seule visite malgré les reruns.
    components.html(Path(__file__).with_name("analytics.html").read_text(encoding="utf-8"),
                    height=0, scrolling=False)
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
                temporaire = None  # La session conserve les CSV, pas les MP4 temporaires.
                if ancien:
                    ancien.cleanup()
            except Exception as erreur:
                st.error(f"L'analyse n'a pas pu aboutir : {erreur}")
            finally:
                if temporaire:
                    temporaire.cleanup()
                obtenir_verrou().release()
    afficher_resultats()
    afficher_montage()


if __name__ == "__main__":
    afficher_application()
