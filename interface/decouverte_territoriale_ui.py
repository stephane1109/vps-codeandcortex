"""Interface de découverte territoriale des @comptes TikTok.

Les hashtags et les descriptions servent à trouver
des comptes candidats ; leur résidence réelle n'est jamais déduite.
"""
from datetime import date, timedelta

import streamlit as st


def afficher_decouverte_territoriale(api, *, telecharger, occupe=False):
    """Créer, poursuivre et consulter un inventaire de comptes par territoire."""
    st.caption(
        "Recherche exclusivement avec la TikTok Research API. Le mode Place TikTok "
        "accepte l'URL ou l'identifiant du lieu pour documenter la référence, "
        "mais interroge les descriptions et hashtags par nom de ville : "
        "Research ne permet pas de filtrer directement par Place ID.")
    mode_territoire = st.radio(
        "Mode de recherche territoriale",
        ["place_reference", "region_code", "texte"],
        format_func=lambda mode: {
            "place_reference": "URL ou Place ID TikTok (recherche indirecte)",
            "region_code": "Pays d'enregistrement (Region Code)",
            "texte": "Ville mentionnée dans les vidéos",
        }[mode],
        key="territoire_mode_recherche", disabled=occupe)
    c1, c2 = st.columns(2)
    with c1:
        if mode_territoire == "region_code":
            code_region = st.text_input(
                "Region Code — pays (ISO à deux lettres)",
                value="FR", max_chars=2,
                key="territoire_recherche_region_code",
                help="FR = comptes enregistrés en France. "
                     "Ce code ne renseigne pas la ville.",
                disabled=occupe)
            ville = ""
        elif mode_territoire == "place_reference":
            reference_lieu = st.text_input(
                "URL TikTok du lieu ou Place ID",
                value="https://www.tiktok.com/place/Toulouse-22535796483363264",
                key="territoire_recherche_url_place",
                help="URL : le nom Toulouse et l'identifiant sont extraits automatiquement. "
                     "ID seul : renseignez également le nom de la ville.",
                disabled=occupe)
            ville = st.text_input(
                "Nom de la ville (facultatif si l'URL est complète)",
                value="", key="territoire_recherche_nom_place",
                disabled=occupe)
            code_region = None
            st.warning(
                "Recherche indirecte uniquement : le Place ID sera conservé "
                "comme référence, mais aucune vidéo ne pourra être confirmée "
                "comme associée à ce lieu à partir de la Research API.")
        else:
            ville = st.text_input(
                "Ville mentionnée", value="Toulouse",
                key="territoire_recherche_ville", disabled=occupe)
            code_region = None
        variantes = st.text_input(
            "Hashtags à croiser avec le territoire",
            value="manifestation, lyceen",
            key="territoire_recherche_hashtags_croises", disabled=occupe,
            help="Un ou plusieurs hashtags séparés par des virgules, "
                 "avec ou sans #. Ex. : manifestation, lyceen.")
        operateur = st.radio(
            "Croisement entre les hashtags",
            options=["OR", "AND"], horizontal=True,
            format_func=lambda valeur: (
                "OU (au moins un hashtag)" if valeur == "OR"
                else "ET (tous les hashtags)"),
            key="territoire_recherche_operateur", disabled=occupe)
    with c2:
        date_fin = st.date_input(
            "Fin des publications", value=date.today(),
            key="territoire_recherche_fin", disabled=occupe)
        date_debut = st.date_input(
            "Début des publications", value=date.today()-timedelta(days=29),
            key="territoire_recherche_debut", disabled=occupe)
    # Identifier une collecte existante avant de proposer une création.
    try:
        etat_serveur = api("/api/decouverte-territoriale")
    except RuntimeError as erreur:
        st.warning("État des collectes indisponible : " + str(erreur))
        return
    existantes = etat_serveur.get("inventaires", [])
    serveur_occupe = bool(etat_serveur.get("serveur_occupe"))
    actives = [
        entree for entree in existantes
        if entree.get("etat") == "en_cours"]
    if actives:
        st.info(
            "Une collecte de comptes est en cours : "
            + ", ".join(entree["ville"] for entree in actives)
            + ". Arrêtez-la avant de démarrer une autre collecte.")
    elif serveur_occupe:
        st.warning(
            "Une collecte de comptes est active dans une autre session. "
            "Elle ne peut pas être arrêtée depuis cet historique privé. "
            "Attendez sa fin ou revenez à la session qui l'a démarrée.")

    if st.button(
        "Collecte de compte",
        key="territoire_creer",
        disabled=occupe or serveur_occupe, type="primary"):
        cle = str(st.session_state.get("research_client_key") or "").strip()
        secret = str(st.session_state.get("research_client_secret") or "").strip()
        try:
            resultat = api("/api/decouverte-territoriale", {
                "demarrer": True,
                "research_client_key": cle or None,
                "research_client_secret": secret or None,
                "ville": ville.strip(),
                "variantes": [
                    v.strip() for v in variantes.split(",") if v.strip()],
                "operateur": operateur,
                "mode_territoire": mode_territoire,
                "region_code": code_region.strip().upper() if code_region else None,
                "reference_lieu": (
                    reference_lieu.strip()
                    if mode_territoire == "place_reference" else None),
                "date_debut": date_debut.isoformat(),
                "date_fin": date_fin.isoformat(),
            })
        except RuntimeError as erreur:
            st.error("Collecte impossible : " + str(erreur))
        else:
            st.session_state["territoire_inventaire_id"] = resultat["id"]
            st.session_state["territoire_inventaire_choix"] = resultat["id"]
            st.success(
                "Collecte de compte lancée : la recherche Research a démarré. "
                "Consultez ci-dessous son état et les résultats progressifs.")
    try:
        inventaires = api("/api/decouverte-territoriale").get("inventaires", [])
    except RuntimeError as erreur:
        st.warning("Inventaires indisponibles : " + str(erreur))
        return
    if not inventaires:
        st.info("Cliquez sur Collecte de compte pour créer et démarrer immédiatement la recherche.")
        return
    index = {ligne["id"]: ligne for ligne in inventaires}
    identifiant_precedent = st.session_state.get("territoire_inventaire_id")
    selection_id = st.selectbox(
        "Collectes de comptes enregistrées", options=list(index),
        index=list(index).index(identifiant_precedent)
              if identifiant_precedent in index else 0,
        format_func=lambda identifiant: (
            f"{index[identifiant]['ville']} — "
            f"{index[identifiant]['nombre_comptes']} compte(s)"
            + (" — arrêt demandé" if index[identifiant].get("arret_demande")
               else " — en cours" if index[identifiant].get("etat") == "en_cours"
               else " — terminé" if index[identifiant]["terminee"]
               else " — interrompue" if index[identifiant].get("etat") == "interrompue"
               else " — à démarrer")),
        key="territoire_inventaire_choix")
    st.session_state["territoire_inventaire_id"] = selection_id
    # Même si un autre inventaire est sélectionné, pouvoir arrêter
    # la collecte active sans créer de deuxième processus.
    active_non_selectionnee = next(
        (entree for entree in inventaires
         if entree.get("etat") == "en_cours" and entree["id"] != selection_id),
        None)
    if active_non_selectionnee:
        st.caption(
            "Collecte active : " + active_non_selectionnee["ville"]
            + ". Vous pouvez l'arrêter depuis cet écran.")
        if active_non_selectionnee.get("arret_demande"):
            st.info("Arrêt demandé : traitement de la page en cours.")
        elif st.button(
                "Arrêter la collecte active",
                key="territoire_arreter_autre", disabled=occupe):
            try:
                reponse = api(
                    f"/api/decouverte-territoriale/{active_non_selectionnee['id']}/arreter",
                    {})
                if reponse.get("arret_demande"):
                    st.session_state["territoire_inventaire_choix"] = (
                        active_non_selectionnee["id"])
                    st.rerun()
                else:
                    st.info(reponse.get("message", "Collecte déjà arrêtée."))
            except RuntimeError as erreur:
                st.error("Arrêt impossible : " + str(erreur))
    try:
        inventaire = api(f"/api/decouverte-territoriale/{selection_id}")
    except RuntimeError as erreur:
        st.error("Inventaire inaccessible : " + str(erreur))
        return
    tags = inventaire.get("hashtags_croises", [])
    if tags:
        liaison = " ET " if inventaire.get("operateur") == "AND" else " OU "
        mode = inventaire.get("mode_territoire", "texte")
        if mode == "region_code":
            territoire = f"region_code = {inventaire.get('region_code')}"
        elif mode == "place_reference":
            territoire = f"mention textuelle : {inventaire['ville']}"
        else:
            territoire = f"mention textuelle : {inventaire['ville']}"
        st.caption(
            f"Recherche : {territoire} ET "
            f"({liaison.join('#' + h for h in tags)}). "
            f"Période : {inventaire['date_debut']} au {inventaire['date_fin']}.")
        if mode == "place_reference":
            st.warning(
                f"Place ID fourni : {inventaire.get('place_id')}. "
                "Cet identifiant n'est pas transmis comme critère à Research : "
                "la correspondance exacte au lieu TikTok n'est pas vérifiée. "
                "L'inventaire contient seulement des comptes candidats.")
    else:
        st.caption(
            "Ancien inventaire sans croisement thématique. "
            "Pour une recherche ville + hashtags, créez un nouvel inventaire. "
            f"Période : {inventaire['date_debut']} au {inventaire['date_fin']}.")
    statistiques = st.columns(4)
    statistiques[0].metric("Comptes distincts", inventaire["nombre_comptes"])
    statistiques[1].metric("Vidéos examinées", inventaire["candidats"])
    statistiques[2].metric("Pages API", inventaire["pages"])
    statistiques[3].metric("Vidéos écartées par les critères", inventaire.get("videos_ecartees", 0))
    st.caption(
        f"Vidéos conformes retenues : {inventaire.get('videos_retenues', 0)} ; "
        f"vidéos hors territoire : {inventaire.get('videos_hors_territoire', 0)} ; "
        f"vidéos sans hashtag demandé : {inventaire.get('videos_sans_hashtag', 0)}. "
        "Une vidéo qui ne satisfait aucun des deux critères est comptée "
        "dans les deux motifs d'exclusion.")
    if inventaire.get("relances_serveur", 0):
        st.caption(
            "Incidents TikTok HTTP 5xx : "
            f"{inventaire.get('echecs_serveur', 0)} réponse(s) en erreur ; "
            f"{inventaire.get('relances_serveur', 0)} relance(s) effectuée(s).")
    if inventaire.get("erreur"):
        st.warning("Dernier diagnostic Research : " + inventaire["erreur"])
    en_cours = inventaire.get("etat") == "en_cours"
    if en_cours:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=5000, limit=None, key="territoire_actualisation")
        if inventaire.get("arret_demande"):
            st.info(
                "Arrêt demandé. La page Research en cours sera achevée "
                "avant l'enregistrement du curseur et l'activation "
                "du bouton Redémarrer la collecte.")
        else:
            st.info(
                "Collecte en cours : les résultats sont sauvegardés "
                "à chaque page. Vous pouvez demander l'arrêt sans "
                "effacer les comptes déjà trouvés.")
            if st.button(
                    "Arrêter la collecte", key="territoire_arreter",
                    type="secondary"):
                try:
                    reponse = api(
                        f"/api/decouverte-territoriale/{selection_id}/arreter",
                        {})
                    if reponse.get("arret_demande"):
                        st.rerun()
                    else:
                        st.info(reponse.get("message", "Collecte déjà arrêtée."))
                except RuntimeError as erreur:
                    st.error("Arrêt impossible : " + str(erreur))
    elif not inventaire["terminee"]:
        st.caption(
            "La collecte utilise vos clés Research de l'interface lorsqu'elles "
            "sont saisies, sinon celles de Coolify. Les clés ne sont pas "
            "enregistrées dans l'inventaire.")
        # La reprise reste réservée aux collectes déjà créées et inactives.
        etat_precedent = inventaire.get("etat", "en_attente")
        libelle_reprise = (
            "Redémarrer la collecte"
            if etat_precedent == "interrompue"
            else "Démarrer cette collecte enregistrée")
        if st.button(
            libelle_reprise, key="territoire_poursuivre",
            disabled=occupe or serveur_occupe, type="secondary"):
            cle = str(st.session_state.get("research_client_key") or "").strip()
            secret = str(st.session_state.get("research_client_secret") or "").strip()
            try:
                api(
                    f"/api/decouverte-territoriale/{selection_id}/poursuivre",
                    {"research_client_key": cle or None,
                     "research_client_secret": secret or None})
                st.rerun()
            except RuntimeError as erreur:
                st.error("Reprise impossible : " + str(erreur))
    else:
        st.success("Période parcourue : recherche terminée.")
    comptes = inventaire["comptes"]
    if not comptes:
        st.info(
            "Aucun compte découvert pour le moment. Lancez ou poursuivez la "
            "recherche et consultez le diagnostic éventuel ci-dessus.")
        return
    page = st.number_input(
        "Page de résultats (100 comptes par page)",
        min_value=1, max_value=max(1, (len(comptes)+99)//100),
        value=1, step=1, key="territoire_page_resultats")
    tranche = comptes[(page-1)*100:page*100]
    st.caption(
        "Un compte est retenu si au moins une vidéo mentionne le territoire "
        "ET contient le ou les hashtags demandés. La vidéo affichée en haut "
        "du profil peut être différente de la vidéo justificative. "
        "Les anciennes collectes sans trace détaillée sont signalées "
        "« preuve non enregistrée ».")
    st.dataframe(
        [{"Compte": v["username"],
          "Vidéos conformes": v["videos_trouvees"],
          "Hashtags de la vidéo justificative": ", ".join(
              (v.get("video_preuve") or {}).get(
                  "hashtags_correspondants", [])),
          "URL vidéo justificative": (
              (v.get("video_preuve") or {}).get("url_video", "")),
          "Justification": (
              "Vidéo conforme enregistrée" if v.get("video_preuve")
              else "Preuve non enregistrée dans cet historique")}
         for v in tranche],
        hide_index=True, use_container_width=True)
    selection = st.multiselect(
        "Comptes à transmettre à une collecte de profils",
        options=[c["username"] for c in comptes],
        key="territoire_comptes_selectionnes",
        help="Sélectionnez les comptes souhaités. Ils seront transférés "
             "par lots de 10, conformément au formulaire de collecte existant.")
    # Les liens directs ne transmettent pas les cookies privés de Streamlit.
    # Les fichiers sont obtenus côté serveur via le client API authentifié.
    try:
        fichier_txt = telecharger(
            f"/api/decouverte-territoriale/{selection_id}/comptes.txt")
        fichier_csv = telecharger(
            f"/api/decouverte-territoriale/{selection_id}/comptes.csv")
    except RuntimeError as erreur:
        st.error("Téléchargement impossible : " + str(erreur))
    else:
        colonne_txt, colonne_csv = st.columns(2)
        with colonne_txt:
            st.download_button(
                "Télécharger les @comptes en TXT",
                data=fichier_txt,
                file_name=f"comptes_{selection_id[:8]}.txt",
                mime="text/plain",
                use_container_width=True,
                key="territoire_telecharger_txt")
        with colonne_csv:
            st.download_button(
                "Télécharger les @comptes en CSV",
                data=fichier_csv,
                file_name=f"comptes_{selection_id[:8]}.csv",
                mime="text/csv",
                use_container_width=True,
                key="territoire_telecharger_csv")
    if selection:
        lots = [selection[i:i+10] for i in range(0, len(selection), 10)]
        lot = st.number_input(
            "Lot de profils à transférer", min_value=1,
            max_value=len(lots), value=1, step=1,
            key="territoire_lot_profils")
        courant = lots[lot-1]
        st.caption(
            f"Lot {lot}/{len(lots)} : " + ", ".join(courant))
        if st.button(
            "Envoyer ce lot vers la collecte Profils",
            key="territoire_envoyer_profils", disabled=occupe):
            st.session_state["comptes_territoire_en_attente"] = ", ".join(courant)
            st.session_state["territoire_transfert_confirme"] = True
            st.rerun()
    if st.session_state.pop("territoire_transfert_confirme", False):
        st.success(
            "Les comptes sélectionnés sont transmis au champ Profils. "
            "Vous pouvez préparer et lancer la collecte avec vos critères habituels.")
