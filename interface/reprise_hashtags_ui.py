"""Interface de reprise des hashtags Research dans le corpus PostgreSQL existant."""
import hashlib

import streamlit as st

from collecte.suivi_hashtags import (
    hashtags_a_reprendre, identifier_collecte_bilan_hashtags_csv,
    importer_bilan_hashtags_csv,
)


def afficher_reprise_hashtags(api, lancer, occupe):
    """Permettre une reprise sans CSV ; importation du bilan facultative."""
    collecte = st.session_state.get("collecte") or {}
    bilan = collecte.get("bilan_hashtags_sources") or []
    disponibles = (hashtags_a_reprendre(bilan)
                   if collecte.get("source_collecte") == "hashtags" else [])
    st.caption(
        "Aucun fichier CSV n'est nécessaire pour reprendre une collecte déjà "
        "affichée. Si vous l'avez fermée, sélectionnez-la dans "
        "« Historique temporaire — collectes et analyses » à gauche, "
        "puis cliquez sur « Rouvrir la collecte et l’analyse ». "
        "Le bilan_hashtags.csv est également présent dans le ZIP des résultats."
    )
    fichier = st.file_uploader(
        "Importation facultative d'un bilan de hashtags (CSV)",
        type=["csv"], key="bilan_reprise_hashtags_csv", disabled=occupe,
        help="Utilisez uniquement cette option pour sélectionner des hashtags "
             "à partir d'un ancien bilan. Le CSV n'est pas requis pour "
             "poursuivre la collecte affichée ou rouverte depuis l'historique.",
    )
    if fichier is None:
        st.session_state.pop("empreinte_bilan_hashtags", None)
    else:
        contenu = fichier.getvalue()
        try:
            identifiant = identifier_collecte_bilan_hashtags_csv(contenu)
        except ValueError as erreur:
            st.error(str(erreur))
        else:
            if identifiant != collecte.get("id"):
                st.info(
                    "Ce fichier appartient à une autre collecte. "
                    "Rouvrez le corpus correspondant avant la reprise."
                )
                if st.button(
                        "Rouvrir la collecte du bilan hashtags",
                        key="ouvrir_collecte_bilan_hashtags", disabled=occupe):
                    try:
                        archive = api(
                            f"/api/historique/{identifiant}/ouvrir", {})
                    except RuntimeError as erreur:
                        st.error("Réouverture impossible : " + str(erreur))
                    else:
                        st.session_state["collecte"] = archive
                        st.rerun()
            else:
                try:
                    selection_csv = importer_bilan_hashtags_csv(
                        contenu, collecte_id=collecte["id"],
                        hashtags_autorises=collecte.get("hashtags_saisis") or [])
                except ValueError as erreur:
                    st.error(str(erreur))
                else:
                    autorises = [
                        tag for tag in selection_csv if tag in disponibles
                    ]
                    if len(autorises) < len(selection_csv):
                        st.warning(
                            "Des hashtags du CSV sont déjà terminés "
                            "dans le journal actuel : ils ne sont pas relancés."
                        )
                    cle = "reprendre_hashtags_selection_" + collecte["id"]
                    empreinte = hashlib.sha256(contenu).hexdigest()
                    if (not occupe and st.session_state.get(
                            "empreinte_bilan_hashtags") != empreinte):
                        # Modifier les valeurs avant la construction du widget.
                        st.session_state[cle] = autorises
                        st.session_state["empreinte_bilan_hashtags"] = empreinte
                    st.success(
                        f"{len(autorises)} hashtag(s) encore inachevé(s) "
                        "présélectionné(s) pour la reprise."
                    )
    if not (
        collecte.get("source_collecte") == "hashtags"
        and collecte.get("hashtag_moteur") == "research"
        and bilan and disponibles
        and not collecte.get("busy") and not collecte.get("video_busy")
    ):
        return
    with st.expander(
            "Poursuivre la collecte hashtags",
            expanded=fichier is not None or collecte.get("status") in (
                "partial", "stopped")):
        st.caption(
            "La séquence précédente est terminée et sauvegardée. "
            "La reprise conserve le même identifiant, les publications et "
            "les critères initiaux. Si un curseur Research a été enregistré, "
            "la collecte repart de la page suivante. TikTok peut toutefois "
            "refuser un curseur devenu invalide, notamment après une longue "
            "interruption."
        )
        selection = st.multiselect(
            "Hashtags à reprendre",
            options=disponibles,
            default=disponibles,
            key="reprendre_hashtags_selection_" + collecte["id"],
            format_func=lambda tag: "#" + tag,
            disabled=occupe,
        )
        st.caption(
            "Pour poursuivre les hashtags sélectionnés, utilisez le bouton "
            "\"Poursuivre la collecte\" affiché dans les résultats. "
            "Une seule commande de reprise est proposée pour éviter les "
            "relancements concurrents et les pertes d'affichage."
        )
