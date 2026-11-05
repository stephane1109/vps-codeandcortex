"""Interface de découverte territoriale des @comptes TikTok.

Seules les vidéos associées à des hashtags territoriaux servent à trouver
des comptes candidats ; leur résidence réelle n'est jamais déduite.
"""
import csv
from datetime import date, timedelta

import streamlit as st


def afficher_decouverte_territoriale(api, *, occupe=False):
    """Créer, poursuivre et consulter un inventaire de comptes par territoire."""
    st.caption(
        "Découvrez des @comptes à partir de vidéos portant des hashtags "
        "territoriaux. Une mention de Toulouse, par exemple, ne prouve "
        "pas que l'auteur réside à Toulouse. Les résultats sont dédupliqués "
        "et sauvegardés dans votre historique privé.")
    c1, c2 = st.columns(2)
    with c1:
        ville = st.text_input(
            "Territoire (ville)", value="Toulouse",
            key="territoire_recherche_ville", disabled=occupe)
        variantes = st.text_input(
            "Autres hashtags à rechercher (facultatifs)",
            value="toulousain, toulousaine",
            key="territoire_recherche_variantes", disabled=occupe,
            help="Séparez les variantes par une virgule. Exemple : "
                 "toulousain, toulousaine, hautegaronne.")
    with c2:
        date_fin = st.date_input(
            "Fin des publications", value=date.today(),
            key="territoire_recherche_fin", disabled=occupe)
        date_debut = st.date_input(
            "Début des publications", value=date.today()-timedelta(days=29),
            key="territoire_recherche_debut", disabled=occupe)
    if st.button(
        "Créer un inventaire territorial",
        key="territoire_creer", disabled=occupe, type="primary"):
        try:
            resultat = api("/api/decouverte-territoriale", {
                "ville": ville.strip(),
                "variantes": [
                    v.strip() for v in variantes.split(",") if v.strip()],
                "date_debut": date_debut.isoformat(),
                "date_fin": date_fin.isoformat(),
            })
        except RuntimeError as erreur:
            st.error("Création impossible : " + str(erreur))
        else:
            st.session_state["territoire_inventaire_id"] = resultat["id"]
            st.rerun()
    try:
        inventaires = api("/api/decouverte-territoriale").get("inventaires", [])
    except RuntimeError as erreur:
        st.warning("Inventaires indisponibles : " + str(erreur))
        return
    if not inventaires:
        st.info("Créez un inventaire territorial pour commencer la recherche.")
        return
    index = {ligne["id"]: ligne for ligne in inventaires}
    identifiant_precedent = st.session_state.get("territoire_inventaire_id")
    selection_id = st.selectbox(
        "Inventaires territoriaux enregistrés", options=list(index),
        index=list(index).index(identifiant_precedent)
              if identifiant_precedent in index else 0,
        format_func=lambda identifiant: (
            f"{index[identifiant]['ville']} — "
            f"{index[identifiant]['nombre_comptes']} compte(s)"
            + (" — terminé" if index[identifiant]["terminee"] else " — à poursuivre")),
        key="territoire_inventaire_choix")
    st.session_state["territoire_inventaire_id"] = selection_id
    try:
        inventaire = api(f"/api/decouverte-territoriale/{selection_id}")
    except RuntimeError as erreur:
        st.error("Inventaire inaccessible : " + str(erreur))
        return
    st.caption(
        f"Hashtags : {', '.join('#'+h for h in inventaire['hashtags'])}. "
        f"Période : {inventaire['date_debut']} au {inventaire['date_fin']}.")
    statistiques = st.columns(3)
    statistiques[0].metric("Comptes distincts", inventaire["nombre_comptes"])
    statistiques[1].metric("Vidéos examinées", inventaire["candidats"])
    statistiques[2].metric("Pages API", inventaire["pages"])
    if inventaire.get("erreur"):
        st.warning("Dernier diagnostic Research : " + inventaire["erreur"])
    if not inventaire["terminee"]:
        if st.button(
            "Rechercher / poursuivre la découverte (3 pages maximum)",
            key="territoire_poursuivre", disabled=occupe):
            try:
                resultat = api(
                    f"/api/decouverte-territoriale/{selection_id}/poursuivre",
                    {})
            except RuntimeError as erreur:
                st.error("Découverte interrompue : " + str(erreur))
            else:
                st.session_state["territoire_dernier_bilan"] = (
                    resultat["nombre_comptes"], resultat["pages"])
                st.rerun()
    else:
        st.success("Période parcourue : recherche terminée.")
    comptes = inventaire["comptes"]
    if not comptes:
        st.info(
            "Aucun compte découvert pour le moment. Poursuivez la recherche "
            "ou essayez d'autres hashtags territoriaux.")
        return
    page = st.number_input(
        "Page de résultats (100 comptes par page)",
        min_value=1, max_value=max(1, (len(comptes)+99)//100),
        value=1, step=1, key="territoire_page_resultats")
    tranche = comptes[(page-1)*100:page*100]
    st.dataframe(
        [{"Compte": v["username"],
          "Vidéos territoriales trouvées": v["videos_trouvees"]}
         for v in tranche],
        hide_index=True, use_container_width=True)
    selection = st.multiselect(
        "Comptes à transmettre à une collecte de profils",
        options=[c["username"] for c in comptes],
        key="territoire_comptes_selectionnes",
        help="Sélectionnez les comptes souhaités. Ils seront transférés "
             "par lots de 10, conformément au formulaire de collecte existant.")
    st.link_button(
        "Télécharger tous les comptes en CSV",
        f"/api/decouverte-territoriale/{selection_id}/comptes.csv")
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
