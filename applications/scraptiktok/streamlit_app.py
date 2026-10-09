"""Interface Streamlit minimaliste ; la collecte et le navigateur restent dans FastAPI."""
from datetime import date
import re

import streamlit as st
from interface.client import appeler_api

st.set_page_config(page_title="ScrapTikTok", page_icon="📝", layout="centered")
st.title("ScrapTikTok")
st.caption("Collecter les textes TikTok et comparer les vidéos.")

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
        st.session_state["configuration"] = api("/api/configuration")
        st.session_state["inventaire"] = api("/api/presse")["medias"]
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
    for nom in ("date_debut","date_fin"):
        valeurs[nom] = date.fromisoformat(ancienne[nom]) if ancienne.get(nom) else None
    for cle,valeur in valeurs.items(): st.session_state.setdefault(cle,valeur)
    st.session_state["initialise"] = True

collecte = st.session_state["collecte"] or {}
occupe = bool(collecte.get("busy") or collecte.get("video_busy"))
video_disponible = st.session_state["configuration"]["video_disponible"]
medias = {m["id"]:m for m in st.session_state["inventaire"]}
onglet_collecte, onglet_aide = st.tabs(["Collecte", "Aide"])

with onglet_collecte:
    source = st.radio("Rechercher par", ["hashtags","presse","comptes"], key="source", horizontal=True,
        format_func=lambda s:{"hashtags":"Hashtags","presse":"Presse et médias","comptes":"Autres comptes TikTok"}[s], disabled=occupe)
    if source == "presse":
        st.write("Choisir les médias à collecter")
        st.caption("Cochez un ou plusieurs comptes. Les hashtags ci-dessous permettent de filtrer leurs publications.")
        def memoriser_medias():
            st.session_state["medias"] = [m for m in medias if st.session_state.get("media_" + m, False)]
        colonnes_medias = st.columns(2)
        for indice,(identifiant,media) in enumerate(medias.items()):
            cle = "media_" + identifiant
            st.session_state.setdefault(cle, identifiant in st.session_state.get("medias", []))
            colonnes_medias[indice % 2].checkbox(media["nom"] + " (@" + media["compte"] + ")",
                key=cle, disabled=occupe, on_change=memoriser_medias)
        st.caption("Inventaire de départ ; utilisez « Autres comptes TikTok » pour ajouter un compte à votre recherche.")
    elif source == "comptes":
        st.text_input("Comptes TikTok", key="comptes", placeholder="@lemondefr, @franceinfo", help="Jusqu’à 10 comptes séparés par des virgules ou espaces.", disabled=occupe)
    c1,c2 = st.columns(2)
    c1.text_input("Hashtag" if source == "hashtags" else "Hashtag facultatif", key="hashtag", placeholder="#actualité", disabled=occupe)
    c2.text_input("Deuxième hashtag (facultatif)", key="second_hashtag", placeholder="#politique", disabled=occupe)
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
        st.checkbox("Créer l’archive enrichie et préparer l’analyse vidéo", key="enrichir", disabled=occupe)
        st.checkbox("Collecter les commentaires accessibles", key="collecter_commentaires", disabled=occupe)
        def activer_commentaires():
            if st.session_state["collecter_reponses"]: st.session_state["collecter_commentaires"] = True
        st.checkbox("Inclure les réponses accessibles", key="collecter_reponses", disabled=occupe, on_change=activer_commentaires)
        st.number_input("Commentaires maximum par publication", min_value=1, max_value=500, step=1, key="limite_commentaires", disabled=occupe)
        st.caption("La collecte par comptes crée automatiquement l’archive enrichie. Les commentaires restent dans un corpus séparé.")
    with st.expander("Options vidéo (facultatif)"):
        # Le formulaire transmet les choix avec le clic, sans course entre réexécutions.
        with st.form("comparaison_video", border=False):
            st.checkbox("Repérer les fichiers identiques (SHA-256)", value=True, key="comparer_sha256", disabled=occupe)
            st.checkbox("Repérer les séquences communes (pHash + ORB)", value=True, key="comparer_sequences", disabled=occupe)
            if not video_disponible:
                st.info("La comparaison vidéo est momentanément indisponible.")
            elif not collecte.get("archive_prete"):
                st.caption("Disponible après une collecte avec l’archive enrichie.")
            if st.form_submit_button("Comparer les vidéos", disabled=occupe or not video_disponible or not collecte.get("archive_prete")):
                options = {k:st.session_state[k] for k in ("comparer_sha256","comparer_sequences")}
                lancer(f"/api/jobs/{collecte['id']}/video",options)
    if st.button("Lancer la collecte", type="primary", disabled=occupe):
        debut,fin = iso(st.session_state["date_debut"]),iso(st.session_state["date_fin"])
        if debut and fin and debut>fin: st.error("La date de début doit précéder ou égaler la date de fin.")
        else:
            valeurs = {k:st.session_state[k] for k in ("hashtag","second_hashtag","operator","limit","french_only","include_sources","enrichir","collecter_commentaires","collecter_reponses","limite_commentaires")}
            valeurs.update(source_collecte=source, date_debut=debut, date_fin=fin,
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
            st.write(actuel["message"])
            st.caption(f"{actuel['captions']} textes · {actuel['processed']}/{actuel['discovered']} publications lues")
            if actuel["date_debut"] or actuel["date_fin"]:
                st.caption(f"Période : {actuel['hors_periode']} hors période · {actuel['dates_indeterminees']} sans date connue")
            if actuel["busy"]:
                st.progress(min(1.0,actuel["processed"]/max(1,actuel["discovered"])))
                if st.button("Arrêter la collecte"): lancer(f"/api/jobs/{actuel['id']}/stop",{})
            if actuel["video_statut"] != "non_lance":
                libelles={"en_cours":"Analyse vidéo en cours…","termine":"Analyse vidéo terminée.","partiel":"Analyse vidéo partielle : voir le journal de l’archive.","interrompu":"Analyse interrompue ; dernière archive conservée.","echec":"Analyse vidéo en échec ; collecte conservée."}
                st.write(libelles.get(actuel["video_statut"],actuel["video_statut"]))
                if actuel.get("video_progression"):
                    st.caption(actuel["video_progression"].get("etape", ""))
            if actuel["video_busy"] and st.button("Arrêter l’analyse vidéo"): lancer(f"/api/jobs/{actuel['id']}/video/stop",{})
            liens = st.columns(2)
            if actuel["can_download"]: liens[0].link_button("Télécharger le TXT", f"/api/jobs/{actuel['id']}/download")
            if actuel["archive_prete"] and not (actuel["busy"] or actuel["video_busy"]): liens[1].link_button("Télécharger l’archive ZIP", f"/api/jobs/{actuel['id']}/archive")
        afficher_resultats()
        if st.session_state["collecte"].get("status") == "attention":
            st.info("Vérifiez TikTok dans le navigateur ci-dessous, puis cliquez sur Continuer dans cette fenêtre.")
            st.iframe("/classique?controle=1", height=850, alt="Navigateur TikTok du serveur")
        with st.expander("Aperçu des textes"):
            for publication in st.session_state["collecte"].get("preview",[]):
                st.text("@" + publication["author"])
                st.text(publication["description"])

with onglet_aide:
    st.subheader("Comment utiliser l’application")
    st.markdown("1. Choisissez vos hashtags ou vos médias et vos filtres.\n"
                "2. Lancez la collecte ; validez TikTok dans la fenêtre intégrée si demandé.\n"
                "3. Téléchargez le TXT. Pour comparer les vidéos, ouvrez **Options vidéo**, choisissez les méthodes et cliquez sur **Comparer les vidéos** après la collecte enrichie.")
    st.subheader("Les méthodes, simplement")
    st.markdown("- **SHA-256** : une empreinte du fichier complet. Elle repère les copies strictement identiques ; un réencodage change l’empreinte.\n"
                "- **pHash** : une empreinte de l’apparence des images. Elle présélectionne les images ressemblantes.\n"
                "- **ORB** : compare des points visuels caractéristiques et leur disposition pour vérifier les images communes, y compris certains recadrages.\n"
                "- **Comparaison temporelle** : vérifie que plusieurs images communes se suivent dans le même ordre. pHash, ORB et le temps travaillent ensemble pour détecter un réemploi de séquence.")
    st.caption("Le TXT contient les légendes. Le ZIP enrichi rassemble les données, les mesures et les résultats vidéo. Les valeurs indéterminées et les scores de confiance sont conservés ; aucun résultat ne garantit une collecte exhaustive.")
