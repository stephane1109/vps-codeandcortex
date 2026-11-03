"""Interface de reprise des hashtags Research dans le corpus PostgreSQL existant."""
import hashlib

import streamlit as st

from collecte.suivi_hashtags import (
    hashtags_a_reprendre, identifier_collecte_bilan_hashtags_csv,
    importer_bilan_hashtags_csv,
)


def afficher_reprise_hashtags(api, lancer, occupe):
    """Importer un bilan et sélectionner uniquement les hashtags inachevés."""
    collecte = st.session_state.get("collecte") or {}
    bilan = collecte.get("bilan_hashtags_sources") or []
    disponibles = (hashtags_a_reprendre(bilan)
                   if collecte.get("source_collecte") == "hashtags" else [])
    fichier = st.file_uploader(
        "Importer un bilan de hashtags CSV d'une collecte précédente",
        type=["csv"], key="bilan_reprise_hashtags_csv", disabled=occupe,
        help="Le bilan permet de retrouver la collecte d'origine et de "
             "reprendre ses hashtags sans créer un deuxième corpus PostgreSQL.",
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
            "Reprendre cette collecte hashtags dans PostgreSQL",
            expanded=fichier is not None):
        st.caption(
            "La reprise conserve le même identifiant de collecte, les publications "
            "enregistrées et les critères initiaux. Seules les recherches inachevées "
            "sont interrogées. TikTok peut exiger une nouvelle pagination lorsque "
            "les anciens curseurs ne sont plus valides."
        )
        selection = st.multiselect(
            "Hashtags à reprendre",
            options=disponibles,
            default=disponibles,
            key="reprendre_hashtags_selection_" + collecte["id"],
            format_func=lambda tag: "#" + tag,
            disabled=occupe,
        )
        if st.button(
                "Reprendre les hashtags (même corpus PostgreSQL)",
                key="reprendre_hashtags_" + collecte["id"],
                disabled=occupe or not selection,
                type="primary"):
            requete = {
                "hashtags": selection,
                "source_collecte": "hashtags",
                "hashtag_moteur": "research",
            }
            cle = st.session_state.get("research_client_key", "").strip()
            secret = st.session_state.get("research_client_secret", "").strip()
            if cle or secret:
                requete["research_client_key"] = cle
                requete["research_client_secret"] = secret
            lancer(
                "/api/historique/" + collecte["id"] + "/reprendre-hashtags",
                requete,
            )
