"""Interface de reprise des hashtags Research dans le corpus PostgreSQL existant."""
import base64
import hashlib

import streamlit as st

from collecte.suivi_hashtags import (
    hashtags_a_reprendre, identifier_collecte_bilans_hashtags_csv,
    importer_bilans_hashtags_csv, regrouper_bilans_hashtags_csv,
)


def reprendre_depuis_bilans_csv(
        api, contenus, *, cle="", secret="", archive_zip=None):
    """Restaurer le corpus des CSV puis reprendre ses pages inachevées.

    Aucun nouveau travail n'est créé par /api/jobs : la seule opération de
    collecte autorisée ici est /reprendre-hashtags sur l'identifiant du bilan.
    La sélection reste bornée par l'état actuel du journal de l'archive.
    """
    identifiant = identifier_collecte_bilans_hashtags_csv(contenus)
    if bool(cle) != bool(secret):
        raise ValueError(
            "Renseignez ensemble Client key et Client secret Research, "
            "ou configurez les deux identifiants dans Coolify.")
    try:
        historique = api(f"/api/historique/{identifiant}/ouvrir", {})
    except RuntimeError as erreur:
        if archive_zip is None:
            raise ValueError(
                str(erreur) + " Si l'historique a disparu, importez également "
                "le ZIP original des résultats contenant publications.json "
                "et journal.json, puis relancez la reprise. "
                "Deux bilans CSV seuls ne permettent pas de restaurer "
                "le curseur de pagination.") from erreur
        if len(archive_zip) > 25_000_000:
            raise ValueError("Le ZIP original ne doit pas dépasser 25 Mo.")
        api(f"/api/historique/{identifiant}/restaurer-zip", {
            "archive_base64": base64.b64encode(archive_zip).decode("ascii")})
        historique = api(f"/api/historique/{identifiant}/ouvrir", {})
    if historique.get("id") != identifiant:
        raise ValueError("L'historique rouvert ne correspond pas au corpus des CSV.")
    if (historique.get("source_collecte") != "hashtags"
            or historique.get("hashtag_moteur") != "research"):
        raise ValueError(
            "Les bilans de hashtags exigent un historique de collecte Research.")
    if historique.get("busy") or historique.get("video_busy"):
        raise ValueError(
            "La collecte d'origine est déjà active ; aucune deuxième reprise lancée.")
    autorises = historique.get("hashtags_saisis") or historique.get("hashtags") or []
    selection_csv = importer_bilans_hashtags_csv(
        contenus, collecte_id=identifiant, hashtags_autorises=autorises)
    disponibles = set(hashtags_a_reprendre(
        historique.get("bilan_hashtags_sources") or []))
    selection = [hashtag for hashtag in selection_csv if hashtag in disponibles]
    if not selection:
        raise ValueError(
            "Aucun hashtag de ces bilans n'est encore inachevé dans le journal "
            "de la collecte d'origine. Aucun nouveau corpus n'a été créé.")
    donnees = {"hashtags": selection}
    if cle:
        donnees["research_client_key"] = cle
        donnees["research_client_secret"] = secret
    reprise = api(
        f"/api/historique/{identifiant}/reprendre-hashtags", donnees)
    if reprise.get("id") != identifiant:
        raise ValueError(
            "La reprise n'a pas confirmé l'identifiant du corpus d'origine.")
    return reprise, selection


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
    fichiers = st.file_uploader(
        "Importer plusieurs bilans de hashtags (CSV, facultatif)",
        type=["csv"], accept_multiple_files=True,
        key="bilan_reprise_hashtags_csv", disabled=occupe,
        help="Sélectionnez jusqu'à 20 bilans CSV. S'ils appartiennent "
             "à des collectes différentes, choisissez le corpus à reprendre : "
             "leurs publications et leurs curseurs ne seront pas mélangés. "
             "Aucun CSV n'est requis pour une reprise depuis l'historique.",
    )
    if not fichiers:
        st.session_state.pop("empreinte_bilan_hashtags", None)
    else:
        st.caption(
            "Si la reprise indique « Historique introuvable », importez "
            "également le ZIP des résultats de la collecte d'origine. "
            "Il contient le journal et les curseurs nécessaires. "
            "La restauration n'efface pas les publications PostgreSQL."
        )
        sauvegarde_zip = st.file_uploader(
            "ZIP original des résultats (si historique perdu)",
            type=["zip"], key="reprise_hashtags_zip_origine",
            disabled=occupe,
            help="ZIP téléchargé à l'issue de la collecte d'origine, "
                 "contenant publications.json et journal.json. "
                 "Les fichiers bilan_hashtags.csv seuls ne suffisent pas.",
        )
        contenus = [fichier.getvalue() for fichier in fichiers]
        try:
            groupes = regrouper_bilans_hashtags_csv(contenus)
        except ValueError as erreur:
            st.error(str(erreur))
        else:
            if len(groupes) > 1:
                st.warning(
                    f"Ces fichiers correspondent à {len(groupes)} collectes "
                    "distinctes. Leurs curseurs ne peuvent pas être fusionnés. "
                    "Choisissez la collecte historique à poursuivre ; "
                    "les autres corpus restent inchangés."
                )
                identifiant = st.selectbox(
                    "Collecte d'origine à reprendre",
                    options=list(groupes),
                    format_func=lambda cle: (
                        f"Corpus {cle[:8]} · {len(groupes[cle])} bilan(s) CSV"),
                    key="bilan_hashtags_collecte_cible",
                    disabled=occupe,
                )
            else:
                identifiant = next(iter(groupes))
            contenus_corpus = groupes[identifiant]
            if identifiant != collecte.get("id"):
                st.info(
                    "Les bilans sélectionnés concernent le corpus d'origine "
                    + identifiant[:8]
                    + ". Le bouton de reprise ci-dessous rouvre ce corpus "
                    "et conserve les publications et curseurs déjà enregistrés."
                )
            else:
                try:
                    selection_csv = importer_bilans_hashtags_csv(
                        contenus_corpus, collecte_id=collecte["id"],
                        hashtags_autorises=collecte.get("hashtags_saisis") or [])
                except ValueError as erreur:
                    st.error(str(erreur))
                else:
                    autorises = [
                        tag for tag in selection_csv if tag in disponibles]
                    if len(autorises) < len(selection_csv):
                        st.warning(
                            "Certains hashtags des CSV sont déjà terminés "
                            "dans le journal actuel : ils ne seront pas relancés."
                        )
                    cle_selection = (
                        "reprendre_hashtags_selection_" + collecte["id"])
                    empreintes = sorted(
                        hashlib.sha256(contenu).hexdigest()
                        for contenu in contenus_corpus)
                    empreinte = hashlib.sha256(
                        "|".join(empreintes).encode("ascii")).hexdigest()
                    if (not occupe and st.session_state.get(
                            "empreinte_bilan_hashtags") != empreinte):
                        st.session_state[cle_selection] = autorises
                        st.session_state["empreinte_bilan_hashtags"] = empreinte
                    st.success(
                        f"{len(contenus_corpus)} bilan(s) du corpus importé(s) ; "
                        f"{len(autorises)} hashtag(s) encore inachevé(s) "
                        "présélectionné(s), sans doublons."
                    )
            if st.button(
                    "Reprendre la collecte d'origine à partir des bilans CSV",
                    key="reprendre_direct_bilans_hashtags",
                    type="primary", disabled=occupe):
                cle = str(
                    st.session_state.get("research_client_key")
                    or st.session_state.get("cle_research_sequence")
                    or "").strip()
                secret = str(
                    st.session_state.get("research_client_secret")
                    or st.session_state.get("secret_research_sequence")
                    or "").strip()
                try:
                    reprise, selection = reprendre_depuis_bilans_csv(
                        api, contenus_corpus, cle=cle, secret=secret,
                        archive_zip=(
                            sauvegarde_zip.getvalue()
                            if sauvegarde_zip is not None else None))
                except (ValueError, RuntimeError) as erreur:
                    st.error(
                        "Reprise impossible : " + str(erreur)
                        + " Aucun nouveau corpus n'a été créé."
                    )
                else:
                    st.session_state["collecte"] = reprise
                    st.success(
                        f"Poursuite lancée sur le corpus {reprise['id'][:8]} "
                        f"pour {len(selection)} hashtag(s). "
                        "Les anciennes publications et les curseurs sont conservés."
                    )
                    st.rerun()
    if not (
        collecte.get("source_collecte") == "hashtags"
        and collecte.get("hashtag_moteur") == "research"
        and bilan and disponibles
        and not collecte.get("busy") and not collecte.get("video_busy")
    ):
        return
    with st.expander(
            "Poursuivre la collecte hashtags",
            expanded=bool(fichiers) or collecte.get("status") in (
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
