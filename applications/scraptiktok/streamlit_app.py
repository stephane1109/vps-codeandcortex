"""Interface Streamlit minimaliste ; la collecte et le navigateur restent dans FastAPI."""
from datetime import date
import re

import streamlit as st
from interface.client import appeler_api

st.set_page_config(page_title="ScrapTikTok", page_icon="📝", layout="centered")
st.title("ScrapTikTok")
st.caption("Collecter les textes des publications TikTok.")

session = st.context.cookies.get("scraptiktok_session", "")
autorisation = st.context.headers.get("Authorization", "")
if not re.fullmatch(r"[a-f0-9]{64}", session):
    st.info("Ouvrez l’application depuis sa page d’accueil pour initialiser votre session privée.")
    st.link_button("Ouvrir l’accueil", "/")
    st.stop()


def api(chemin, donnees=None):
    return appeler_api(chemin, session, autorisation, donnees)


def lancer(chemin, donnees):
    try:
        resultat = api(chemin, donnees)
    except RuntimeError as erreur:
        st.error(str(erreur)); return
    if "id" in resultat: st.session_state["collecte"] = resultat
    st.rerun()


def iso(valeur):
    return valeur.isoformat() if valeur else None


if "initialise" not in st.session_state:
    try:
        ancienne = api("/api/session")["job"]
    except RuntimeError as erreur:
        st.error(str(erreur)); st.stop()
    st.session_state["collecte"] = ancienne
    ancienne = ancienne or {}
    valeurs = {"source":ancienne.get("source_collecte","hashtags"), "hashtag":ancienne.get("hashtag",""),
        "second_hashtag":ancienne.get("second_hashtag",""), "operator":ancienne.get("operator","AND"),
        "comptes":", ".join(ancienne.get("comptes",[])), "medias":ancienne.get("medias",[]),
        "limit":ancienne.get("limit",50), "french_only":ancienne.get("french_only",True),
        "include_sources":ancienne.get("include_sources",True), "enrichir":ancienne.get("enrichir",True),
        "collecter_commentaires":ancienne.get("collecter_commentaires",False), "collecter_reponses":ancienne.get("collecter_reponses",False),
        "limite_commentaires":ancienne.get("limite_commentaires",50)}
    # Une recherche de médias ne reprend pas les hashtags d'une recherche précédente.
    for nom in ("hashtag", "second_hashtag"):
        valeurs[nom + "_comptes"] = ancienne.get(nom, "") if ancienne.get("source_collecte") in {"presse", "comptes"} else ""
        if ancienne.get("source_collecte") in {"presse", "comptes"}: valeurs[nom] = ""
    for nom in ("date_debut","date_fin"):
        valeurs[nom] = date.fromisoformat(ancienne[nom]) if ancienne.get(nom) else None
    for cle,valeur in valeurs.items(): st.session_state.setdefault(cle,valeur)
    st.session_state["initialise"] = True

# Conserver les filtres de chaque mode même quand leurs champs ne sont pas affichés.
for cle in ("hashtag", "second_hashtag", "hashtag_comptes", "second_hashtag_comptes"):
    st.session_state[cle] = st.session_state.get(cle, "")

collecte = st.session_state["collecte"] or {}
occupe = bool(collecte.get("busy") or collecte.get("video_busy"))
# Recharger le catalogue évite de conserver une ancienne liste dans une session ouverte.
try:
    medias = {m["id"]:m for m in api("/api/presse")["medias"]}
except RuntimeError as erreur:
    st.error(str(erreur)); st.stop()
onglet_collecte, onglet_aide = st.tabs(["Collecte", "Aide"])

with onglet_collecte:
    source = st.radio("Rechercher par", ["hashtags","presse","comptes"], key="source", horizontal=True,
        format_func=lambda s:{"hashtags":"Hashtags","presse":"Presse et médias","comptes":"Autres comptes TikTok"}[s], disabled=occupe)
    if source == "presse":
        st.write("Choisir les médias à collecter")
        st.caption("Cochez un ou plusieurs comptes. Les hashtags ci-dessous permettent de filtrer leurs publications.")
        def memoriser_medias():
            st.session_state["medias"] = [m for m in medias if st.session_state.get("media_" + m, False)]
        def cocher_tous_les_medias():
            st.session_state["medias"] = list(medias)
            for identifiant in medias:
                st.session_state["media_" + identifiant] = True
        st.button("Tout cocher", key="tous_medias", on_click=cocher_tous_les_medias, disabled=occupe)
        colonnes_medias = st.columns(2)
        for indice,(identifiant,media) in enumerate(medias.items()):
            cle = "media_" + identifiant
            st.session_state.setdefault(cle, identifiant in st.session_state.get("medias", []))
            colonnes_medias[indice % 2].checkbox(media["nom"] + " (@" + media["compte"] + ")",
                key=cle, disabled=occupe, on_change=memoriser_medias)
        selection = [m for m in medias if st.session_state.get("media_" + m, False)]
        st.session_state["medias"] = selection
        st.caption(f"{len(selection)} média(s) sélectionné(s) sur {len(medias)}. Les comptes seront visités l’un après l’autre.")
    elif source == "comptes":
        st.text_input("Comptes TikTok", key="comptes", placeholder="@lemondefr, @franceinfo", help="Jusqu’à 10 comptes séparés par des virgules ou espaces.", disabled=occupe)
    cle_hashtag = "hashtag" if source == "hashtags" else "hashtag_comptes"
    cle_second = "second_hashtag" if source == "hashtags" else "second_hashtag_comptes"
    c1,c2 = st.columns(2)
    c1.text_input("Hashtag" if source == "hashtags" else "Hashtag facultatif", key=cle_hashtag, placeholder="#actualité", disabled=occupe)
    c2.text_input("Deuxième hashtag (facultatif)", key=cle_second, placeholder="#politique", disabled=occupe)
    st.radio("Combiner les hashtags", ["AND","OR"], format_func=lambda v:"ET — les deux" if v=="AND" else "OU — au moins un", key="operator", horizontal=True, disabled=occupe)
    st.number_input("Publications par source", min_value=1, max_value=300, step=1, key="limit", disabled=occupe)
    st.checkbox("Français uniquement", key="french_only", disabled=occupe,
        help="Détection sur la légende ; textes trop courts ou de langue incertaine écartés.")
    with st.expander("Période facultative", expanded=bool(st.session_state["date_debut"] or st.session_state["date_fin"])):
        d1,d2 = st.columns(2)
        d1.date_input("Du", value=None, key="date_debut", format="DD/MM/YYYY", disabled=occupe)
        d2.date_input("Au", value=None, key="date_fin", format="DD/MM/YYYY", disabled=occupe)
        st.caption("Jours inclus en UTC, parmi les publications consultées. Les dates inconnues sont écartées si une période est choisie.")
        def effacer_dates():
            st.session_state["date_debut"] = None; st.session_state["date_fin"] = None
        st.button("Effacer la période", on_click=effacer_dates, disabled=occupe)
    with st.expander("Exports et commentaires"):
        st.checkbox("Inclure les auteurs et liens dans le TXT", key="include_sources", disabled=occupe)
        st.checkbox("Créer l’archive enrichie", key="enrichir", disabled=occupe)
        st.checkbox("Collecter les commentaires accessibles", key="collecter_commentaires", disabled=occupe)
        def activer_commentaires():
            if st.session_state["collecter_reponses"]: st.session_state["collecter_commentaires"] = True
        st.checkbox("Inclure les réponses accessibles", key="collecter_reponses", disabled=occupe, on_change=activer_commentaires)
        st.number_input("Commentaires maximum par publication", min_value=1, max_value=500, step=1, key="limite_commentaires", disabled=occupe)
        st.caption("La collecte par comptes crée automatiquement l’archive enrichie. Les commentaires restent dans un corpus séparé.")
    if st.button("Lancer la collecte", type="primary", disabled=occupe):
        debut,fin = iso(st.session_state["date_debut"]),iso(st.session_state["date_fin"])
        if debut and fin and debut>fin: st.error("La date de début doit précéder ou égaler la date de fin.")
        else:
            valeurs = {k:st.session_state[k] for k in ("operator","limit","french_only","include_sources","enrichir","collecter_commentaires","collecter_reponses","limite_commentaires")}
            valeurs.update(hashtag=st.session_state.get(cle_hashtag,""), second_hashtag=st.session_state.get(cle_second,""), source_collecte=source, date_debut=debut, date_fin=fin,
                comptes=re.split(r"[\s,;]+",st.session_state.get("comptes", "").strip()) if source == "comptes" and st.session_state.get("comptes", "").strip() else [],
                medias=st.session_state.get("medias",[]) if source == "presse" else [])
            lancer("/api/jobs",valeurs)


with onglet_collecte:
    if collecte:
        st.divider()
        st.subheader("Résultats")
        @st.fragment(run_every="1s")
        def afficher_resultats():
            precedent = st.session_state["collecte"]
            try: actuel = api("/api/jobs/" + precedent["id"])
            except RuntimeError as erreur:
                st.warning(str(erreur)); return
            st.session_state["collecte"] = actuel
            # Les changements d’étape recréent l’interface ; les images et gestes restent dans leur iframe stable.
            if any(precedent.get(k)!=actuel.get(k) for k in ("busy","video_busy")) or (precedent.get("status")=="attention") != (actuel.get("status")=="attention"):
                st.rerun()
            if actuel.get("source_collecte") == "presse":
                selection_moteur = actuel.get("medias", [])
                with st.expander(f"Médias pris en compte par la collecte : {len(selection_moteur)}"):
                    for identifiant in selection_moteur:
                        media = medias.get(identifiant)
                        st.write(f"{media['nom']} (@{media['compte']})" if media else identifiant)
            st.write(actuel["message"])
            st.caption(f"{actuel['captions']} textes · {actuel['processed']}/{actuel['discovered']} publications lues")
            if actuel["date_debut"] or actuel["date_fin"]:
                st.caption(f"Période : {actuel['hors_periode']} hors période · {actuel['dates_indeterminees']} sans date connue")
            if actuel["busy"]:
                st.progress(min(1.0,actuel["processed"]/max(1,actuel["discovered"])))
                if st.button("Arrêter la collecte"): lancer(f"/api/jobs/{actuel['id']}/stop",{})
            if actuel.get("bilan_sources"):
                with st.expander("Détail des sources", expanded=not actuel["busy"] and not actuel["captions"]):
                    for bilan in actuel["bilan_sources"]:
                        st.write(f"{bilan['source']} : {bilan['liens']} lien(s) — {bilan['message']}")
                        diagnostic = bilan.get("diagnostic", {})
                        if diagnostic:
                            indices = [str(diagnostic[cle]) for cle in ("code", "exception", "erreur_reseau", "url", "etat") if diagnostic.get(cle)]
                            st.caption(" · ".join(indices))
            liens = st.columns(2)
            if actuel["can_download"]: liens[0].link_button("Télécharger le TXT", f"/api/jobs/{actuel['id']}/download")
            if actuel["archive_prete"] and not (actuel["busy"] or actuel["video_busy"]): liens[1].link_button("Télécharger l’archive ZIP", f"/api/jobs/{actuel['id']}/archive")
        afficher_resultats()
        if st.session_state["collecte"].get("status") == "attention":
            st.info("Vérifiez TikTok dans le navigateur ci-dessous, puis cliquez sur Continuer dans cette fenêtre. La sélection des médias reste celle de la collecte lancée.")
            st.iframe("/classique?controle=1", height=850, alt="Navigateur TikTok du serveur")
        with st.expander("Aperçu des textes"):
            for publication in st.session_state["collecte"].get("preview",[]):
                st.text("@" + publication["author"])
                st.text(publication["description"])

with onglet_aide:
    st.subheader("Comment utiliser l’application")
    st.markdown("1. Choisissez **Presse et médias**, cochez les comptes ou utilisez **Tout cocher**.\n"
                "2. Les hashtags sont facultatifs pour les médias. Ajoutez les filtres souhaités, puis lancez la collecte.\n"
                "3. Tous les médias cochés sont transmis au moteur. Les profils accessibles sont collectés automatiquement.\n"
                "4. Validez TikTok dans la fenêtre intégrée si demandé, puis cliquez sur **Continuer**.\n"
                "5. Téléchargez le TXT ou l’archive ZIP lorsque les résultats sont disponibles.")
    st.caption("En cas de résultat vide, consultez le détail des sources et les compteurs de filtres. Une page inaccessible n’indique pas qu’un compte n’a aucune publication. Le TXT contient les légendes ; le ZIP enrichi ajoute les données et les commentaires demandés.")
