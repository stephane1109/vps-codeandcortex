"""Interface sobre de VisioTrack : imports, analyse séquentielle et exports."""

import os
import json
import base64
import tempfile
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from detection import CATEGORIES, colonnes_resultats, inventorier_sources, traiter_lot
from montage import assembler_videos, creer_montage
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
    identifiant = afficher_graphiques(tableau, choix, repertoire)
    afficher_apercu(tableau, repertoire, identifiant)
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


def lire_chronologie_video(chemin, identifiant):
    """Lire les CSV par blocs et ne conserver que la vidéo sélectionnée."""
    blocs = []
    for bloc in pd.read_csv(chemin, chunksize=10000, dtype={"video_id": str}):
        selection = bloc[bloc.video_id == identifiant]
        if not selection.empty:
            blocs.append(selection)
    return pd.concat(blocs, ignore_index=True) if blocs else pd.DataFrame()


def afficher_graphiques(tableau, choix, repertoire):
    """Situer les plages de présence sur toute la durée de la vidéo."""
    videos = tableau[tableau.statut == "ok"].drop_duplicates("video_id").set_index("video_id")
    if videos.empty:
        return None
    fichiers = {"quantifier_temps": repertoire / "intervalles.csv",
                "compter_distincts": repertoire / "chronologie.csv"}
    if any(choix.get(option) and not chemin.exists() for option, chemin in fichiers.items()):
        st.info("Relancez l'analyse pour obtenir les chronologies de ce lot.")
        return None
    st.subheader("Chronologie des détections")
    if len(videos) > 1:
        identifiant = st.selectbox("Vidéo des graphiques et de l'aperçu", list(videos.index),
                                  format_func=lambda cle: f"{cle} — {videos.loc[cle, 'source']}")
    else:
        identifiant = videos.index[0]
        st.caption(f"{identifiant} — {videos.loc[identifiant, 'source']}")
    duree = float(videos.loc[identifiant, "duree_totale_s"])
    axe_temps = {"type": "quantitative", "title": "Temps dans la vidéo (s)",
                 "scale": {"domain": [0, duree], "nice": False}}
    if choix.get("quantifier_temps"):
        st.markdown("**Présence dans la vidéo**")
        plages = lire_chronologie_video(fichiers["quantifier_temps"], identifiant)
        categories = tableau.loc[(tableau.video_id == identifiant) & (tableau.statut == "ok"),
                                 "categorie"].dropna().unique().tolist()
        # Une seule bande par catégorie, même lorsque plusieurs appareils sont
        # visibles ensemble. Les intervalles de catégorie évitent les doublons.
        fond = [{"categorie": categorie, "debut_s": 0, "fin_s": duree}
                for categorie in categories]
        if plages.empty:
            plages = pd.DataFrame(columns=["categorie", "debut_s", "fin_s", "duree_s"])
        specification = {
            "encoding": {
                "x": {**axe_temps, "field": "debut_s"},
                "x2": {"field": "fin_s"},
                "y": {"field": "categorie", "type": "nominal", "sort": categories,
                      "title": None, "axis": {"ticks": False, "domain": False}},
            },
            "layer": [
                # La bande grise couvre toujours la vidéo entière, y compris
                # avant la première apparition et après la dernière détection.
                {"data": {"values": fond}, "mark": {"type": "bar", "size": 24, "color": "#e5e7eb"}},
                {"mark": {"type": "bar", "size": 24, "color": "#22c55e"},
                 "encoding": {"tooltip": [
                     {"field": "categorie", "type": "nominal", "title": "Objet"},
                     {"field": "debut_s", "type": "quantitative", "title": "Début (s)", "format": ".2f"},
                     {"field": "fin_s", "type": "quantitative", "title": "Fin (s)", "format": ".2f"},
                     {"field": "duree_s", "type": "quantitative", "title": "Durée visible (s)", "format": ".2f"},
                 ]}},
            ],
        }
        st.vega_lite_chart(plages, specification, width="stretch", height=max(80, 44 * len(categories)))
        st.caption("Gris : durée totale de la vidéo. Vert : au moins un objet de cette catégorie est visible. "
                   "L'axe horizontal indique le temps en secondes.")
        if plages.empty:
            st.info("Aucun objet détecté dans cette vidéo.")
        st.caption("Les plages sont estimées entre deux images analysées et arrêtées aux changements de plan repérés.")
    if choix.get("compter_distincts"):
        st.markdown("**Nombre d'objets distincts aperçus au fil du temps**")
        evolution = lire_chronologie_video(fichiers["compter_distincts"], identifiant)
        if not evolution.empty:
            specification = {
                "mark": {"type": "line", "interpolate": "step-after", "point": True},
                "encoding": {
                    "x": {**axe_temps, "field": "horodatage_s"},
                    "y": {"field": "nombre_distincts_cumule", "type": "quantitative",
                          "title": "Objets distincts depuis le début (estim.)",
                          "scale": {"zero": True}, "axis": {"format": "d", "tickMinStep": 1}},
                    "color": {"field": "categorie", "type": "nominal", "title": "Catégorie"},
                    "tooltip": [
                        {"field": "horodatage_s", "type": "quantitative", "title": "Temps (s)", "format": ".2f"},
                        {"field": "categorie", "type": "nominal", "title": "Objet"},
                        {"field": "nombre_distincts_cumule", "type": "quantitative", "title": "Distincts cumulés", "format": "d"},
                        {"field": "nombre_visible", "type": "quantitative", "title": "Visibles à cet instant", "format": "d"},
                    ],
                },
            }
            st.vega_lite_chart(evolution, specification, width="stretch", height=260)
            st.caption("Le cumul augmente à chaque nouvel identifiant aperçu ; il ne diminue pas quand un objet disparaît. "
                       "Le survol indique aussi combien d'objets sont visibles à cet instant.")
        st.download_button("Évolution des détections CSV", fichiers["compter_distincts"].read_bytes(),
                           "visiotrack_chronologie.csv", mime="text/csv", on_click="ignore")
    return identifiant


def afficher_apercu(tableau, repertoire, identifiant=None):
    """Ne charger dans le lecteur que la vidéo sélectionnée dans le lot."""
    videos = tableau[tableau.statut == "ok"].drop_duplicates("video_id").set_index("video_id")
    manifeste = repertoire / "apercus.json"
    if videos.empty or not manifeste.exists():
        return
    apercus = json.loads(manifeste.read_text(encoding="utf-8"))
    st.subheader("Vidéo avec détections")
    if identifiant is None:
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



def afficher_montage(acces_initial):
    """Analyser jusqu'à quatre URL puis générer un split seulement si demandé."""
    st.subheader("Analyse comparative — 1 à 4 URL")
    with st.form("montage_comparatif"):
        colonnes_urls = st.columns(2)
        urls_montage = []
        for indice in range(4):
            with colonnes_urls[indice % 2]:
                urls_montage.append(st.text_input(
                    f"URL {indice + 1}", key=f"visiotrack_url_montage_{indice}",
                    placeholder="https://www.youtube.com/watch?v=... ou https://www.tiktok.com/..."
                ))
        categorie_montage = st.selectbox(
            "Objet à détecter avec YOLO",
            list(CATEGORIES),
            index=67,
            format_func=lambda categorie: CATEGORIES[categorie].capitalize(),
            help="Le smartphone est sélectionné par défaut. Toutes les URL renseignées "
                 "sont analysées avec cette catégorie."
        )
        frequence_montage = st.number_input(
            "Images analysées par seconde (comparaison)", min_value=0.5,
            max_value=15.0, value=5.0, step=0.5,
            help="Cette fréquence d'analyse YOLO s'applique aux vidéos non encore analysées."
        )
        generer_split = st.checkbox(
            "Générer une vidéo split (2, 3 ou 4 fenêtres)", value=False,
            help="Option facultative. Deux URL : deux écrans côte à côte ; "
                 "trois URL : trois écrans côte à côte ; "
                 "quatre URL : quatre écrans en grille 2 × 2. "
                 "Sans cette option, chaque vidéo reste consultable séparément."
        )
        lancer_montage = st.form_submit_button("Analyser les URL", type="primary")

    if lancer_montage:
        urls_retenues = [adresse.strip() for adresse in urls_montage if adresse.strip()]
        if not urls_retenues:
            st.error("Renseignez au moins une URL avant de lancer l'analyse.")
        elif generer_split and len(urls_retenues) < 2:
            st.error("La vidéo split nécessite au moins deux URL. "
                     "Pour analyser une seule vidéo, décochez cette option.")
        elif not obtenir_verrou().acquire(blocking=False):
            st.warning("Une analyse VisioTrack est déjà en cours sur ce serveur.")
        else:
            temporaire = None
            try:
                temporaire = tempfile.TemporaryDirectory(prefix="visiotrack-montage-")
                barre = st.progress(0.0, text=f"Préparation de {len(urls_retenues)} vidéo(s)…")
                dernier_renouvellement = 0.0

                def actualiser_montage(numero, total, etape, avancement):
                    """Conserver l'accès pendant les traitements et afficher leur progression."""
                    nonlocal dernier_renouvellement
                    maintenant = time.monotonic()
                    if maintenant - dernier_renouvellement >= 30:
                        if not renouveler_acces_analyse(acces_initial["ticket_id"]):
                            st.error("L'accès n'est plus actif. Reprenez l'accès avant de relancer le montage.")
                            st.stop()
                        dernier_renouvellement = maintenant
                    valeur = (numero - 1 + avancement) / total
                    barre.progress(min(1.0, max(0.0, valeur)),
                                   text=f"{etape} ({numero}/{total})")

                # Réutiliser les analyses de cette session pour les mêmes URL.
                # Le lecteur du module principal conserve déjà les MP4 annotés
                # et la chronologie des effectifs, sans conserver les sources brutes.
                reutilisations = {}
                session_precedente = st.session_state.get("visiotrack_exports")
                resultats_precedents = st.session_state.get("visiotrack_resultats", [])
                if session_precedente is not None:
                    repertoire_precedent = Path(session_precedente.name)
                    manifeste_precedent = repertoire_precedent / "apercus.json"
                    chronologie_precedente = repertoire_precedent / "chronologie.csv"
                    if manifeste_precedent.is_file() and chronologie_precedente.is_file():
                        apercus_precedents = json.loads(
                            manifeste_precedent.read_text(encoding="utf-8")
                        )
                        urls_demandees = set(urls_retenues)
                        for ligne in resultats_precedents:
                            if (ligne.get("statut") != "ok"
                                    or ligne.get("categorie") != CATEGORIES[categorie_montage]
                                    or ligne.get("source") not in urls_demandees):
                                continue
                            identifiant = ligne["video_id"]
                            chemin_rel = apercus_precedents.get(identifiant, {}).get("fichier")
                            if not chemin_rel:
                                continue
                            chemin_apercu = repertoire_precedent / chemin_rel
                            if chemin_apercu.is_file():
                                reutilisations[ligne["source"]] = {
                                    "apercu": str(chemin_apercu),
                                    "chronologie": str(chronologie_precedente),
                                    "video_id": identifiant,
                                    "resultat": ligne,
                                }
                if reutilisations:
                    st.info(
                        f"{len(reutilisations)} vidéo(s) déjà analysée(s) dans cette session "
                        "seront réutilisées sans nouveau téléchargement."
                    )
                with st.spinner("Analyse des URL et création des vidéos annotées…"):
                    sortie, duree = creer_montage(
                        urls_retenues, temporaire.name, frequence_montage,
                        actualiser_montage, categorie=categorie_montage,
                        reutilisations=reutilisations,
                        generer_split=generer_split,
                    )
                ancien = st.session_state.get("visiotrack_montage_exports")
                st.session_state.visiotrack_montage_exports = temporaire
                st.session_state.visiotrack_montage_duree = duree
                st.session_state.visiotrack_montage_nombre = len(urls_retenues)
                st.session_state.visiotrack_montage_split = generer_split
                temporaire = None
                if ancien:
                    ancien.cleanup()
            except Exception as erreur:
                st.error(f"Impossible de terminer l’analyse comparative : {erreur}")
            finally:
                if temporaire:
                    temporaire.cleanup()
                obtenir_verrou().release()

    if "visiotrack_montage_exports" in st.session_state:
        repertoire = Path(st.session_state.visiotrack_montage_exports.name)
        nombre_videos = st.session_state.get("visiotrack_montage_nombre", 4)
        avec_split = st.session_state.get("visiotrack_montage_split", True)

        # Une vidéo split peut aussi être produite après l'analyse,
        # sans relancer YOLO ni télécharger une seconde fois les URL.
        if nombre_videos >= 2 and not avec_split:
            if st.button(
                f"Générer une vidéo split des {nombre_videos} analyses existantes",
                type="primary", key="visiotrack_split_depuis_analyses"
            ):
                if not obtenir_verrou().acquire(blocking=False):
                    st.warning("Une analyse VisioTrack est déjà en cours.")
                else:
                    try:
                        pistes = [
                            repertoire / f"case_{indice}.mp4"
                            for indice in range(1, nombre_videos + 1)
                        ]
                        sortie_split = (
                            repertoire / f"visiotrack_montage_{nombre_videos}_fenetres.mp4"
                        )
                        with st.spinner("Assemblage des vidéos YOLO déjà analysées…"):
                            duree_split = assembler_videos(pistes, sortie_split)
                        st.session_state.visiotrack_montage_duree = duree_split
                        st.session_state.visiotrack_montage_split = True
                        avec_split = True
                    except Exception as erreur:
                        st.error(f"Impossible de produire la vidéo split : {erreur}")
                    finally:
                        obtenir_verrou().release()

        if avec_split:
            fichier_split = repertoire / f"visiotrack_montage_{nombre_videos}_fenetres.mp4"
            if fichier_split.is_file():
                st.subheader(f"Vidéo split — {nombre_videos} fenêtres")
                st.video(str(fichier_split))
                st.caption(
                    f"Détections YOLO simultanées — durée : "
                    f"{st.session_state.visiotrack_montage_duree:.1f} s. "
                    "MP4 1920 × 1080, sans audio, dernière image figée."
                )
                with fichier_split.open("rb") as entree:
                    st.download_button(
                        "Télécharger la vidéo split MP4", entree,
                        file_name=fichier_split.name, mime="video/mp4",
                        on_click="ignore", width="stretch"
                    )

        st.subheader(f"Vidéos annotées — {nombre_videos} analyse(s) YOLO")
        colonnes_apercus = st.columns(2)
        for indice in range(1, nombre_videos + 1):
            fichier_individuel = repertoire / f"case_{indice}.mp4"
            if fichier_individuel.is_file():
                with colonnes_apercus[(indice - 1) % 2]:
                    st.caption(f"URL {indice}")
                    st.video(str(fichier_individuel))
                    with fichier_individuel.open("rb") as entree:
                        st.download_button(
                            f"Télécharger la vidéo annotée {indice}",
                            entree, file_name=f"visiotrack_analyse_{indice}.mp4",
                            mime="video/mp4", on_click="ignore",
                            width="stretch", key=f"visiotrack_telecharger_analyse_{indice}"
                        )

        chemin_csv = repertoire / "visiotrack_montage_resultats.csv"
        if chemin_csv.is_file():
            st.subheader("Résultats des analyses YOLO")
            st.dataframe(pd.read_csv(chemin_csv), hide_index=True, width="stretch")
            with chemin_csv.open("rb") as entree:
                st.download_button(
                    "Télécharger les résultats des vidéos (CSV)",
                    entree, file_name="visiotrack_montage_resultats.csv",
                    mime="text/csv", on_click="ignore", width="stretch"
                )


def afficher_application():
    """Construire les seuls réglages nécessaires à l'analyse."""
    # Utiliser une image transparente pour éviter le favicon Streamlit par défaut.
    # Retirer simplement page_icon ferait apparaître le logo Streamlit.
    favicon_transparent = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
    )
    st.set_page_config(page_title="VisioTrack", page_icon=favicon_transparent, layout="wide",
                       initial_sidebar_state="expanded")
    # Supprimer l'espacement supérieur de Streamlit sans toucher aux autres marges.
    st.html("""
        <style>
        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer,
        .main .block-container {
            padding-top: 1.25rem !important;
        }
        </style>
    """)
    st.title("VisioTrack")
    st.caption("version 19-11-2026")
    # Réserver un accès avant de permettre les imports ou l'analyse.
    acces_initial = enforce_streamlit_access("visiotrack", "VisioTrack")

    with st.form("analyse"):
        urls = st.text_area("URL YouTube ou TikTok", placeholder=(
            "https://www.tiktok.com/@ladepechedumidi/video/7691631006369058081"
            "?q=manifestation%20toulouse&t=1791983293656"), height=90,
            help="Une URL HTTPS par ligne.")
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
    afficher_montage(acces_initial)
    # L'iframe Analytics ne doit pas créer d'espacement avant le titre.
    components.html(Path(__file__).with_name("analytics.html").read_text(encoding="utf-8"),
                    height=0, scrolling=False)


if __name__ == "__main__":
    afficher_application()
