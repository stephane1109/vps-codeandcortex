"""Interface sobre de VisioTrack : imports, analyse séquentielle et exports."""

import os
import json
import tempfile
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from detection import CATEGORIES, colonnes_resultats, inventorier_sources, traiter_lot
from ticket_gate import enforce_streamlit_access, renouveler_acces_analyse


@st.cache_resource
def obtenir_verrou():
    """Limiter le processus Streamlit à un seul lot actif, toutes sessions confondues."""
    return threading.Lock()


def afficher_resultats():
    """Conserver le dernier résultat pendant les téléchargements et les réaffichages."""
    if "visiotrack_resultats" not in st.session_state:
        return
    # Conserver les choix du lot terminé, même si le formulaire est modifié ensuite.
    choix = st.session_state.get("visiotrack_mesures", {"quantifier_temps": True, "compter_distincts": False})
    tableau = pd.DataFrame(st.session_state.visiotrack_resultats).reindex(columns=colonnes_resultats(**choix))
    st.subheader("Résultats")
    succes = tableau[tableau.statut == "ok"].video_id.nunique()
    erreurs = tableau[tableau.statut == "erreur"].video_id.nunique()
    st.caption(f"{succes} vidéo(s) analysée(s) · {erreurs} erreur(s). Une ligne par vidéo et catégorie.")
    # Les mêmes explications alimentent les info-bulles et la légende dépliable.
    colonnes = {
        "video_id": st.column_config.Column("Identifiant", help=(
            "Identifiant attribué à la vidéo dans ce lot, par exemple v000001. "
            "Il permet de retrouver la même vidéo dans les trois exports CSV.")),
        "source": st.column_config.Column("Vidéo", help=(
            "Nom du fichier, emplacement dans une archive ZIP ou URL de la vidéo analysée.")),
        "statut": st.column_config.Column("Statut", help=(
            "« ok » : analyse terminée. « erreur » : la vidéo n'a pas pu être analysée ; "
            "ses mesures ne sont pas renseignées.")),
        "erreur": st.column_config.Column("Erreur", help=(
            "Explication du problème rencontré lors de l'import ou de l'analyse. "
            "Cette cellule reste vide si l'analyse a réussi.")),
        "duree_totale_s": st.column_config.NumberColumn("Durée totale (s)", format="%.3f", help=(
            "Durée complète de la piste vidéo, en secondes. Ce n'est pas le temps de calcul de l'analyse.")),
        "categorie": st.column_config.Column("Objet", help=(
            "Catégorie recherchée sur cette ligne, par exemple smartphone. "
            "Une vidéo peut avoir plusieurs lignes si plusieurs catégories ont été sélectionnées.")),
        "objet_detecte": st.column_config.CheckboxColumn("Détecté", help=(
            "Case cochée si au moins un objet de cette catégorie a été détecté sur une image analysée. "
            "Une case non cochée signifie qu'aucun n'a été détecté, sans garantir son absence dans la vidéo.")),
        "duree_visibilite_s": st.column_config.NumberColumn("Visibilité (s)", format="%.3f", help=(
            "Durée cumulée estimée pendant laquelle au moins un objet de cette catégorie est visible. "
            "Deux smartphones visibles ensemble pendant 10 secondes comptent pour 10 secondes, pas 20.")),
        "pourcentage_visible": st.column_config.NumberColumn("Temps visible (%)", format="%.2f", help=(
            "Part de la durée vidéo pendant laquelle la catégorie est visible : visibilité ÷ durée totale × 100. "
            "Par exemple, 10 secondes sur une vidéo de 40 secondes donnent 25 %.")),
        "maximum_simultane": st.column_config.NumberColumn("Maximum simultané", format="%d", help=(
            "Plus grand nombre d'objets de cette catégorie détectés sur une même image analysée. "
            "Deux smartphones visibles ensemble donnent 2 ; montrés l'un après l'autre, ils peuvent donner 1. "
            "Ce n'est pas le nombre total d'objets différents dans la vidéo.")),
        "nombre_objets_distincts_estime": st.column_config.NumberColumn("Objets distincts (estim.)", format="%d", help=(
            "Nombre estimé d'objets différents de cette catégorie dans cette vidéo. "
            "Un objet suivi sur plusieurs images compte une seule fois. Une coupe, une occultation "
            "ou un suivi perdu peut faire recompter le même téléphone ; deux appareils qui se remplacent "
            "au même endroit peuvent aussi être confondus. Ce n'est pas un inventaire certain des appareils physiques.")),
        "frequence_demandee_ips": st.column_config.NumberColumn("Images/s demandées", help=(
            "Nombre d'images à analyser par seconde demandé au lancement : 1 signifie une image par seconde, "
            "5 signifie cinq images par seconde. Le nombre effectivement analysé reste limité par la cadence du fichier.")),
        "images_analysees": st.column_config.NumberColumn("Images analysées", format="%d", help=(
            "Nombre total d'images de cette vidéo effectivement analysées, y compris celles sans détection. "
            "Ce n'est ni le nombre d'objets détectés ni le nombre total d'images du fichier.")),
    }
    colonnes = {nom: configuration for nom, configuration in colonnes.items() if nom in tableau.columns}
    st.dataframe(tableau, hide_index=True, width="stretch", column_config=colonnes)
    if choix["compter_distincts"]:
        st.caption("Le nombre distinct est une estimation par suivi : le même téléphone peut être recompté "
                   "après une coupe ou une disparition. Il n'est pas reconnu avec certitude d'un plan à l'autre.")
    with st.expander("Légende des colonnes (?)"):
        st.caption("Ces explications sont aussi disponibles en survolant les en-têtes du tableau.")
        st.table([{"Colonne": configuration["label"], "Signification": configuration["help"]}
                  for configuration in colonnes.values()])
    repertoire = Path(st.session_state.visiotrack_exports.name)
    afficher_apercu(tableau, repertoire)
    exports = [("resultats", "Résultats CSV")]
    if choix["quantifier_temps"]:
        exports.append(("intervalles", "Intervalles CSV"))
    exports.append(("detections", "Détections CSV"))
    for colonne, (nom, libelle) in zip(st.columns(len(exports)), exports):
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
    st.set_page_config(page_title="VisioTrack", page_icon="📱", layout="wide",
                       initial_sidebar_state="expanded")
    # Réserver un accès avant de permettre les imports ou l'analyse.
    acces_initial = enforce_streamlit_access("visiotrack", "VisioTrack")
    st.title("VisioTrack")
    st.caption("La présence à l'écran est mesurée ; elle ne prouve pas une utilisation effective.")

    with st.form("analyse"):
        urls = st.text_area("URL YouTube ou TikTok", placeholder="Une URL HTTPS par ligne", height=90)
        fichiers = st.file_uploader("Fichiers MP4 ou archives ZIP", type=["mp4", "zip"],
                                    accept_multiple_files=True)
        categories = st.multiselect("Objets à détecter", list(CATEGORIES), default=[67],
                                    format_func=lambda cle: CATEGORIES[cle].capitalize())
        quantifier_temps = st.checkbox("Quantifier le temps à l'image", value=True,
                                      help="Calculer la durée de visibilité et le pourcentage de la vidéo.")
        compter_distincts = st.checkbox("Quantifier le nombre d'objets distincts aperçus", value=True,
                                        help="Smartphones par défaut. Estimation par suivi pour chaque catégorie "
                                             "sélectionnée ; un même téléphone peut être recompté après une coupe "
                                             "ou une disparition. Les deux mesures peuvent être cochées ensemble.")
        frequence = st.number_input("Images analysées par seconde", min_value=0.1,
                                    max_value=30.0, value=1.0, step=0.5)
        dossier_serveur = os.getenv("VISIOTRACK_VIDEO_DIR")
        if dossier_serveur:
            st.caption("Les MP4 du dossier serveur configuré seront également analysés, sous-dossiers inclus.")
        lancer = st.form_submit_button("Lancer l'analyse", type="primary")

    st.caption("À 1 image/s, une apparition brève peut être manquée et le suivi d'un téléphone peut être perdu. "
               "Les durées et le nombre d'objets distincts sont des estimations.")
    if lancer:
        sources = inventorier_sources(fichiers, urls, dossier_serveur)
        if not quantifier_temps and not compter_distincts:
            st.error("Cochez au moins une mesure à quantifier.")
        elif not categories or not sources:
            st.error("Ajoutez au moins une vidéo et sélectionnez un objet à détecter.")
        elif not obtenir_verrou().acquire(blocking=False):
            st.warning("Une analyse est déjà en cours sur ce serveur. Relancez après sa fin.")
        else:
            temporaire = None
            try:
                temporaire = tempfile.TemporaryDirectory(prefix="visiotrack-")
                barre_lot = st.progress(0.0, text=f"Préparation de {len(sources)} vidéo(s)…")
                barre_video = st.progress(0.0, text="Chargement du modèle CPU…")
                dernier_renouvellement = 0.0

                def actualiser_progression(numero, total, nom, valeur):
                    """Afficher une progression globale et celle de la vidéo courante."""
                    nonlocal dernier_renouvellement
                    maintenant = time.monotonic()
                    # Un long lot doit conserver son accès pendant les calculs.
                    if maintenant - dernier_renouvellement >= 30:
                        if not renouveler_acces_analyse(acces_initial["ticket_id"]):
                            st.error("L'accès n'est plus actif. Reprenez l'accès avant de relancer l'analyse.")
                            st.stop()
                        dernier_renouvellement = maintenant
                    barre_lot.progress((numero - 1 + valeur) / total,
                                       text=f"Vidéo {numero}/{total}")
                    barre_video.progress(valeur, text=nom)

                with st.spinner("Analyse en cours…"):
                    resultats = traiter_lot(sources, categories, frequence, temporaire.name,
                                            actualiser_progression, quantifier_temps=quantifier_temps,
                                            compter_distincts=compter_distincts)
                ancien = st.session_state.get("visiotrack_exports")
                st.session_state.visiotrack_exports = temporaire
                st.session_state.visiotrack_resultats = resultats
                st.session_state.visiotrack_mesures = {"quantifier_temps": quantifier_temps,
                                                      "compter_distincts": compter_distincts}
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
