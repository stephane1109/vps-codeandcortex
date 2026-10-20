"""Interface Streamlit minimaliste ; la collecte et le navigateur restent dans FastAPI."""
from datetime import date
import re

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from interface.client import appeler_api

VARIABLES_TXT = {"date": "Date", "profil": "Profil", "id": "ID vidéo", "vues": "Nombre de vues",
                 "likes": "Nombre de likes", "partages": "Nombre de partages",
                 "commentaires": "Nombre de commentaires", "favoris": "Nombre de favoris",
                 "hashtags": "Hashtags sous le texte"}

# Une icône transparente évite aussi le favicon Streamlit affiché par défaut.
st.set_page_config(page_title="ScrapTikTok", page_icon='<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>', layout="wide", initial_sidebar_state="expanded")
# Même propriété Analytics que la home ; une seule visite malgré les reruns.
components.html(Path(__file__).with_name("analytics.html").read_text(encoding="utf-8"),
                height=0, scrolling=False)
st.title("ScrapTikTok")
st.caption("Appli en cours de dév - modifiée 11-10-2026")
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


def arreter_avant_liberation():
    """Arrêter uniquement les traitements appartenant à cette session."""
    try:
        tache = api("/api/session")["job"] or {}
        if tache.get("busy"):
            api(f"/api/jobs/{tache['id']}/stop", {})
        if tache.get("video_busy"):
            api(f"/api/jobs/{tache['id']}/video/stop", {})
    except RuntimeError as erreur:
        st.error(str(erreur))
        return False
    return True


from ticket_gate import enforce_streamlit_access, SESSION_STATE_KEY, identifiant_ticket_session
# L’interface et l’API utilisent la même identité privée pour vérifier le ticket.
st.session_state[SESSION_STATE_KEY] = identifiant_ticket_session(session)
enforce_streamlit_access("scraptiktok", "ScrapTikTok", avant_liberation=arreter_avant_liberation)


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
        "include_sources":ancienne.get("include_sources",True),
        "telecharger_mp4":ancienne.get("telecharger_mp4",False),
        "collecter_commentaires":ancienne.get("collecter_commentaires",True), "collecter_reponses":ancienne.get("collecter_reponses",False),
        "limite_commentaires":ancienne.get("limite_commentaires",50)}
    variables = ancienne.get("variables_txt")
    if variables is None:
        variables = ["date", "profil", "id"] if ancienne.get("inclure_metadonnees_txt") else ["profil", "id"] if ancienne.get("include_sources", True) else []
    variables = [{"republications": "partages", "url": "id"}.get(v, v) for v in variables]
    for variable in VARIABLES_TXT:
        valeurs["txt_" + variable] = variable in variables
    # Une recherche de médias ne reprend pas les hashtags d'une recherche précédente.
    for nom in ("hashtag", "second_hashtag"):
        valeurs[nom + "_comptes"] = ancienne.get(nom, "") if ancienne.get("source_collecte") in {"presse", "comptes"} else ""
        if ancienne.get("source_collecte") in {"presse", "comptes"}: valeurs[nom] = ""
    for nom in ("date_debut","date_fin"):
        valeurs[nom] = date.fromisoformat(ancienne[nom]) if ancienne.get(nom) else None
    for cle,valeur in valeurs.items(): st.session_state.setdefault(cle,valeur)
    st.session_state["initialise"] = True

st.session_state.setdefault("telecharger_mp4", False)

# Conserver les filtres de chaque mode même quand leurs champs ne sont pas affichés.
for variable in VARIABLES_TXT:
    valeur_initiale = (variable in ("date", "profil", "id") and
        (st.session_state.get("inclure_metadonnees_txt", False) or
         (variable in ("profil", "id") and st.session_state.get("include_sources", True))))
    if variable == "id":
        valeur_initiale = st.session_state.get("txt_url", valeur_initiale)
    if variable == "partages":
        valeur_initiale = st.session_state.get("txt_republications", valeur_initiale)
    st.session_state.setdefault("txt_" + variable, valeur_initiale)
    st.session_state["txt_" + variable] = st.session_state["txt_" + variable]
for cle in ("hashtag", "second_hashtag", "hashtag_comptes", "second_hashtag_comptes",
            "operator", "limit", "french_only", "include_sources", "txt_date", "txt_profil", "txt_id",
            "collecter_commentaires", "collecter_reponses", "limite_commentaires", "telecharger_mp4",
            "date_debut", "date_fin", "comptes"):
    st.session_state[cle] = st.session_state[cle]

collecte = st.session_state["collecte"] or {}
occupe = bool(collecte.get("busy") or collecte.get("video_busy"))

# Recharger le catalogue évite de conserver une ancienne liste dans une session ouverte.
try:
    medias = {m["id"]:m for m in api("/api/presse")["medias"]}
except RuntimeError as erreur:
    st.error(str(erreur)); st.stop()
onglet_collecte, onglet_multimodale, onglet_aide = st.tabs(["Collecte", "Multimodale", "Aide"])

with onglet_collecte:
    source = st.radio("Rechercher par", ["hashtags","presse","comptes"], key="source", horizontal=True,
        format_func=lambda s:{"hashtags":"Hashtags","presse":"Presse et médias","comptes":"Autres comptes TikTok"}[s], disabled=occupe)
    if source == "presse":
        st.write("Choisir les médias à collecter")
        st.caption("Cochez un ou plusieurs comptes. Renseignez au moins un hashtag ci-dessous pour filtrer leurs publications.")
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
        st.caption(f"{len(selection)} média(s) sélectionné(s) sur {len(medias)}. Chaque média coché est recherché. Au moins un hashtag est obligatoire.")
    elif source == "comptes":
        st.text_input("Comptes TikTok", key="comptes", placeholder="@lemondefr, @franceinfo", help="Jusqu’à 10 comptes séparés par des virgules ou espaces.", disabled=occupe)
        st.caption("Avec ou sans @ : @lemondefr et lemondefr sont acceptés.")
        st.caption("Jusqu’à 10 profils, séparés par des virgules ou des espaces. Renseignez au moins un hashtag ci-dessous pour lancer la collecte.")
    cle_hashtag = "hashtag" if source == "hashtags" else "hashtag_comptes"
    cle_second = "second_hashtag" if source == "hashtags" else "second_hashtag_comptes"
    # Envoyer les filtres ensemble évite les pertes de saisie entre deux réexécutions.
    with st.form("filtres_collecte", border=False, enter_to_submit=False):
        c1,c2 = st.columns(2)
        c1.text_input("Hashtag (obligatoire)", key=cle_hashtag, placeholder="#actualité", disabled=occupe)
        c1.caption("Avec ou sans # : #actualité ou actualité. Un seul hashtag, sans espace.")
        c2.text_input("Deuxième hashtag (facultatif)", key=cle_second, placeholder="#politique", disabled=occupe)
        c2.caption("Avec ou sans # : #politique ou politique. Un seul hashtag, sans espace.")
        st.radio("Combiner les hashtags", ["AND","OR"], format_func=lambda v:"ET — les deux" if v=="AND" else "OU — au moins un", key="operator", horizontal=True, disabled=occupe)
        st.number_input("Nombre de posts TikTok à collecter par source", min_value=1, max_value=1000, step=1, key="limit", disabled=occupe,
            help="Saisissez un nombre entre 1 et 1 000. En mode Hashtags : limite par hashtag. En mode Presse/médias ou Profils : limite par compte, tous hashtags confondus, avant les autres filtres.")
        st.caption("Le nombre de textes exportés peut être inférieur selon les filtres et les publications accessibles.")
        if source != "hashtags":
            st.caption("Chaque compte sélectionné est recherché avec chaque hashtag. Seules ses publications sont conservées, dans la limite demandée par compte. Résultats non exhaustifs.")
        st.checkbox("Filtre français", key="french_only", disabled=occupe,
            help="Exclut les légendes identifiées dans une autre langue. Les légendes courtes ou de langue indéterminée sont conservées et signalées.")
        st.checkbox("Télécharger les vidéos (MP4)", key="telecharger_mp4", disabled=occupe,
            help="Télécharge les vidéos accessibles des publications retenues dans l’archive ZIP. La variable ID reste dans le TXT pour retrouver chaque fichier.")
        st.checkbox("Collecter les textes des commentaires", key="collecter_commentaires", disabled=occupe,
            help="Sur les publications retenues, dans la limite indiquée sous Options des commentaires. Le nombre de commentaires est recherché même si cette option est décochée.")
        with st.expander("Période facultative", expanded=bool(st.session_state["date_debut"] or st.session_state["date_fin"])):
            d1,d2 = st.columns(2)
            d1.date_input("Du", value=None, key="date_debut", format="DD/MM/YYYY", disabled=occupe)
            d2.date_input("Au", value=None, key="date_fin", format="DD/MM/YYYY", disabled=occupe)
            st.caption("Jours inclus en UTC, parmi les publications consultées. Les dates inconnues sont écartées si une période est choisie.")
            def effacer_dates():
                st.session_state["date_debut"] = None; st.session_state["date_fin"] = None
            st.form_submit_button("Effacer la période", on_click=effacer_dates, disabled=occupe)
        st.write("Variables à inclure avant chaque post dans le TXT")
        choix_variables = [(variable, titre) for variable, titre in VARIABLES_TXT.items() if variable != "hashtags"]
        for debut_ligne in range(0, len(choix_variables), 3):
            for colonne, (variable, titre) in zip(st.columns(3), choix_variables[debut_ligne:debut_ligne + 3]):
                colonne.checkbox(titre, key="txt_" + variable, disabled=occupe)
        st.checkbox(VARIABLES_TXT["hashtags"], key="txt_hashtags", disabled=occupe,
            help="Déplace les hashtags sur une ligne sous le texte. Décoché, la légende reste inchangée.")
        with st.expander("Options des commentaires"):
            def activer_commentaires():
                if st.session_state["collecter_reponses"]: st.session_state["collecter_commentaires"] = True
            st.checkbox("Inclure les réponses accessibles", key="collecter_reponses", disabled=occupe, help="Inclure les réponses active aussi la collecte des commentaires.")
            st.number_input("Commentaires maximum par publication", min_value=1, max_value=500, step=1, key="limite_commentaires", disabled=occupe)
        if st.form_submit_button("Lancer la collecte", type="primary", disabled=occupe, on_click=activer_commentaires):
            debut,fin = iso(st.session_state["date_debut"]),iso(st.session_state["date_fin"])
            if not st.session_state.get(cle_hashtag, "").strip():
                st.error("Renseignez au moins un hashtag pour une collecte par profil ou média." if source != "hashtags" else "Le premier hashtag est obligatoire.")
            elif debut and fin and debut>fin: st.error("La date de début doit précéder ou égaler la date de fin.")
            else:
                valeurs = {k:st.session_state[k] for k in ("operator","limit","french_only","include_sources","collecter_commentaires","collecter_reponses","limite_commentaires","telecharger_mp4")}
                # Toujours préparer l'archive, même si une ancienne session l'avait désactivée.
                valeurs["enrichir"] = True
                valeurs["variables_txt"] = [v for v in VARIABLES_TXT if st.session_state["txt_" + v]]
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
            if actuel.get("comptes_filtres"):
                st.write("Filtre des profils : " + ", ".join("@" + compte for compte in actuel["comptes_filtres"]))
                st.caption("La recherche cible successivement chaque profil ci-dessus avec les hashtags saisis. Les résultats d’autres auteurs sont exclus.")
            if actuel.get("source_collecte") == "presse":
                selection_moteur = actuel.get("medias", [])
                with st.expander(f"Médias pris en compte par la collecte : {len(selection_moteur)}"):
                    for identifiant in selection_moteur:
                        media = medias.get(identifiant)
                        st.write(f"{media['nom']} (@{media['compte']})" if media else identifiant)
            if actuel.get("status") == "attention" and actuel.get("type_intervention") == "connexion":
                st.info("Une invitation à se connecter est visible. Si un CAPTCHA apparaît, résolvez-le dans la fenêtre ci-dessous. Sinon, fermez l’invitation si possible, puis cliquez sur Continuer. Les publications déjà obtenues sont conservées.")
            elif actuel.get("status") == "attention" and actuel.get("type_intervention") == "captcha":
                st.warning("TikTok demande un CAPTCHA. Terminez la vérification dans la fenêtre ci-dessous.")
            else:
                st.write(actuel["message"])
            compteurs = actuel.get("compteurs_collecte")
            if compteurs:
                colonnes = st.columns(4)
                for colonne, cle, titre in zip(colonnes,
                        ("decouvertes", "retenues", "traitees", "exportees"),
                        ("Découvertes", "Retenues pour lecture", "Traitées", "Exportées dans le TXT")):
                    colonne.metric(titre, compteurs[cle])
                st.caption(("Découvertes : résultats des recherches compte + hashtag. Retenues pour lecture : auteur conforme au compte ciblé. L’auteur est à nouveau contrôlé avant les exports. " if actuel.get("source_collecte") != "hashtags" else "")
                           + "Les filtres peuvent réduire le nombre de publications exportées.")
            else:
                st.caption(f"{actuel['captions']} textes · {actuel['processed']}/{actuel['discovered']} publications lues")
            if actuel.get("hashtags") and (actuel["source_collecte"] != "hashtags" or actuel["second_hashtag"]):
                combinaison = (" ET " if actuel["operator"] == "AND" else " OU ").join("#" + h for h in actuel["hashtags"])
                st.caption("Filtre appliqué : " + combinaison)
                if "bilan_hashtags" in actuel and actuel.get("processed", 0):
                    with st.expander("Bilan des filtres", expanded=not actuel["busy"] and not actuel["captions"]):
                        st.caption("Comptages sur les légendes lisibles dans la période choisie, avant le filtre français. Un hashtag doit être précédé de # dans la légende.")
                        for hashtag, nombre in actuel["bilan_hashtags"].items():
                            st.write(f"#{hashtag} : {nombre} légende(s)")
                        st.write(f"{combinaison} : {actuel['correspondances_hashtags']} légende(s) correspondante(s)")
                        st.write(f"Filtre français : {actuel['non_french']} dans une autre langue écartés · {actuel['language_unknown']} de langue indéterminée conservés")
                        st.write(f"{actuel['legendes_vides']} publication(s) sans légende lisible · {actuel['errors']} erreur(s) de lecture")
            if actuel["date_debut"] or actuel["date_fin"]:
                st.caption(f"Période : {actuel['hors_periode']} hors période · {actuel['dates_indeterminees']} sans date connue")
            if actuel["busy"]:
                st.progress(min(1.0,actuel["processed"]/max(1,actuel["discovered"])))
                if actuel.get("status") != "attention":
                    st.caption("La fenêtre TikTok s’ouvre automatiquement en cas de vérification. Pour les profils et médias, elle s’ouvre aussi si aucune publication n’est lisible ou si la pagination se bloque.")
                if st.button("Arrêter la collecte"): lancer(f"/api/jobs/{actuel['id']}/stop",{})
            if actuel.get("diagnostics"):
                with st.expander("Diagnostics de collecte"):
                    libelles = {"erreur_session": "Session Selenium perdue", "erreur_extraction_video": "Erreur d’extraction d’une publication",
                                "erreur_navigateur": "Erreur du navigateur"}
                    for diagnostic in actuel["diagnostics"]:
                        st.write(libelles.get(diagnostic["code"], diagnostic["code"]) +
                                 (" · publication " + diagnostic["publication_id"] if diagnostic.get("publication_id") else ""))
            if actuel.get("bilan_sources"):
                with st.expander("Détail des sources", expanded=not actuel["busy"] and not actuel["captions"]):
                    for bilan in actuel["bilan_sources"]:
                        st.write(f"{bilan['source']} : {bilan['liens']} lien(s) — {bilan['message']}")
                        if bilan.get("retenues_par_compte"):
                            st.caption("Liens retenus cumulés : " + " · ".join(
                                f"@{compte} : {nombre}" for compte, nombre in bilan["retenues_par_compte"].items()))
                        for recherche in bilan.get("recherches", []):
                            st.write(f"{recherche['requete']} : {recherche['liens']} lien(s) retenu(s), {recherche['auteurs_ecartes']} d’autres auteurs écarté(s).")
                            auteurs = recherche.get("auteurs_dans_liens", {})
                            compte = recherche.get("compte")
                            if compte:
                                st.caption(f"@{compte} : {auteurs.get(compte, 0)} publication(s) dans les liens reçus de TikTok, sur {recherche.get('candidats_examines', 0)} publication(s) repérée(s).")
                                if recherche.get("candidats_examines") and not auteurs.get(compte, 0):
                                    st.info("Le compte ciblé est absent des liens reçus pour cette recherche. Le filtre l’a cherché ; cela ne prouve pas que ses vidéos n’existent pas.")
                            if auteurs:
                                frequents = sorted(auteurs.items(), key=lambda element: (-element[1], element[0]))[:10]
                                st.caption("Auteurs indiqués dans les liens (10 premiers au maximum) : " + " · ".join(f"@{auteur} : {nombre}" for auteur, nombre in frequents))
                            motifs = {"limit": "limite demandée atteinte", "no_new_links": "plus de nouveaux liens après plusieurs attentes",
                                      "max_scrolls": "budget de défilement atteint", "blocked": "vérification TikTok en attente",
                                      "tiktok_error": "erreur de chargement TikTok", "no_accessible_links": "aucun lien lisible",
                                      "connexion_apres_resultats": "invitation à se connecter et absence de nouveaux liens",
                                      "publications_non_accessibles": "invitation à se connecter et aucun lien lisible",
                                      "recherche_redirigee": "redirection vers une autre page"}
                            if recherche.get("arret"):
                                st.caption(f"{recherche.get('defilements', 0)} défilement(s) effectué(s). Arrêt : " + motifs.get(recherche["arret"], recherche["arret"]))
                            if recherche.get("diagnostic"):
                                st.caption("Diagnostic : " + recherche["diagnostic"].get("code", "indéterminé"))
                        diagnostic = bilan.get("diagnostic", {})
                        if diagnostic:
                            indices = [str(diagnostic[cle]) for cle in ("code", "exception", "erreur_reseau", "url", "etat") if diagnostic.get(cle)]
                            st.caption(" · ".join(indices))
            if actuel.get("apercu_engagement"):
                def compteur(mesure):
                    if mesure.get("valeur") is None: return "Indisponible"
                    return ("≈ " if mesure.get("estime") else "") + str(mesure["valeur"])
                lignes = []
                for publication in actuel["apercu_engagement"]:
                    ligne = {"Auteur": "@" + publication["author"], "Publication": publication["url"], "URL TikTok": publication["url"]}
                    for cle, titre in (("likes", "Likes"), ("vues", "Vues"), ("partages", "Partages"), ("commentaires", "Nombre de commentaires")):
                        ligne[titre] = compteur(publication.get("engagement", {}).get(cle, {}))
                    ligne["Langue"] = {"fr": "Français", "unknown": "Indéterminée"}.get(publication.get("langue_detection"), "Non évaluée")
                    lignes.append(ligne)
                st.dataframe(lignes, hide_index=True, column_config={"Publication": st.column_config.LinkColumn("Publication", display_text="Ouvrir")})
            if actuel.get("collecter_commentaires"):
                st.write(f"{actuel.get('commentaires_collectes', 0)} texte(s) de commentaires récupéré(s).")
                if actuel.get("commentaires_indisponibles"):
                    st.warning(f"Commentaires non récupérés ou collecte interrompue pour {actuel['commentaires_indisponibles']} publication(s). Voir le détail ci-dessous.")
                if actuel.get("bilan_commentaires"):
                    with st.expander("Détail de la collecte des commentaires"):
                        st.dataframe([{"ID vidéo": e["publication_id"], "Nombre annoncé": e.get("annonces"),
                            "Textes récupérés": e.get("recuperes", 0), "Diagnostic": e.get("message") or e.get("statut")}
                            for e in actuel["bilan_commentaires"]], hide_index=True)
            else:
                st.caption("La collecte des textes des commentaires n’était pas activée pour cette recherche. Le nombre de commentaires reste inclus dans les compteurs.")
            if actuel.get("telecharger_mp4") and actuel.get("bilan_mp4"):
                disponibles = sum(bool(v.get("video_fichier")) for v in actuel["bilan_mp4"])
                st.write(f"MP4 : {disponibles}/{len(actuel['bilan_mp4'])} fichier(s) disponible(s).")
                with st.expander("Bilan des téléchargements MP4"):
                    st.dataframe([{"ID vidéo": v["video_id"], "Fichier": v.get("video_fichier"),
                                   "État": v.get("video_message")} for v in actuel["bilan_mp4"]], hide_index=True)
            choix_export = ""
            if actuel["can_download"] or actuel["archive_prete"]:
                sans_arobase = st.checkbox("Supprimer le @ devant les profils dans le TXT", value=True,
                    key="export_profil_sans_arobase_" + actuel["id"])
                choix_export = "?supprimer_arobase_profil=" + ("true" if sans_arobase else "false")
            liens = st.columns(2)
            if actuel["can_download"]:
                liens[0].link_button("Télécharger le TXT", f"/api/jobs/{actuel['id']}/download{choix_export}")
                liens[1].link_button("Télécharger les compteurs CSV", f"/api/jobs/{actuel['id']}/engagement.csv")
            if actuel["archive_prete"] and not (actuel["busy"] or actuel["video_busy"]): liens[0].link_button("Télécharger l’archive ZIP", f"/api/jobs/{actuel['id']}/archive{choix_export}")
            if actuel.get("commentaires_collectes"):
                liens[1].link_button("Télécharger les commentaires TXT", f"/api/jobs/{actuel['id']}/commentaires.txt")
        afficher_resultats()
        if st.session_state["collecte"].get("status") == "attention":
            st.info("Vérifiez TikTok dans le navigateur ci-dessous, puis cliquez sur Continuer dans cette fenêtre. La sélection des médias reste celle de la collecte lancée.")
            adresse_controle = f"/controle?collecte={st.session_state['collecte']['id']}"
            st.iframe(adresse_controle, height=850, alt="Navigateur TikTok du serveur")
        with st.expander("Aperçu des textes"):
            for publication in st.session_state["collecte"].get("preview",[]):
                st.text("@" + publication["author"])
                st.text(publication["description"])

with onglet_aide:
    st.subheader("Comment utiliser l’application")
    st.markdown("1. Choisissez **Presse et médias**, cochez les comptes ou utilisez **Tout cocher**.\n"
                "2. Renseignez au moins un hashtag, y compris pour les profils et médias. Le deuxième est facultatif (ET/OU). Ajoutez les autres filtres, puis lancez la collecte.\n"
                "3. Tous les médias cochés sont transmis au moteur. Chaque compte coché est recherché avec chacun des hashtags ; seuls les auteurs sélectionnés sont retenus.\n"
                "4. La fenêtre TikTok s’ouvre automatiquement si une vérification est nécessaire ou si une recherche ne fournit plus de publications lisibles. Intervenez dans cette fenêtre, puis cliquez sur **Continuer**.\n"
                "5. Téléchargez le TXT ou l’archive ZIP lorsque les résultats sont disponibles.")
    st.caption("En cas de résultat vide, consultez le détail des sources et les compteurs de filtres. Une page inaccessible n’indique pas qu’un compte n’a aucune publication. Le TXT contient les légendes ; le ZIP enrichi ajoute les données et les commentaires demandés.")




with onglet_multimodale:
    st.subheader("Vidéos similaires")
    st.caption("Recherche de séquences visuelles communes, y compris entre lots et collectes du même utilisateur. Le son seul ne constitue pas une preuve visuelle.")
    tache = st.session_state.get("collecte") or {}
    if not tache.get("archive_prete"):
        st.info("Effectuez une collecte enrichie avant de lancer l’analyse multimodale.")
    elif not tache.get("video_disponible"):
        st.info("Le serveur doit utiliser INSTALL_VIDEO=base ou 1 pour activer l’analyse vidéo.")
    else:
        pas = st.number_input("Intervalle entre les images (secondes)", min_value=0.25, max_value=30.0, value=1.0, step=0.25)
        with st.expander("Options multimodales"):
            sha = st.checkbox("Comparer les fichiers identiques", value=True)
            sequences = st.checkbox("Rechercher les séquences visuelles communes", value=True)
            audio = st.checkbox("Mesurer les indicateurs audio")
            transcription = st.checkbox("Transcrire la parole")
            ocr = st.checkbox("Lire les textes incrustés (OCR)")
            embeddings = st.checkbox("Calculer les ressemblances sémantiques")
            modeles = st.checkbox("Autoriser le téléchargement des modèles facultatifs")
            nettoyer = st.checkbox("Supprimer les MP4 après indexation", value=False,
                help="Les empreintes et vignettes sont conservées pour les comparaisons futures. Les MP4 supprimés ne figureront plus dans le ZIP.")
        st.caption("Traitement séquentiel par lots de 20, reprise automatique. Relancer reprend les éléments en attente après une interruption.")
        if st.button("Lancer / reprendre l’analyse", disabled=occupe):
            lancer(f"/api/jobs/{tache['id']}/video", {"pas_images_s":pas,"comparer_sha256":sha,
                "comparer_sequences":sequences,"audio":audio,"transcription":transcription,
                "ocr":ocr,"embeddings":embeddings,"telecharger_modeles":modeles,"nettoyer_videos":nettoyer})
        @st.fragment(run_every="3s")
        def afficher_similarites():
            try:
                actuel=api(f"/api/jobs/{tache['id']}")
                donnees=api(f"/api/jobs/{tache['id']}/videos-similaires")
            except RuntimeError as erreur:
                st.error(str(erreur)); return
            etat=donnees['etat']
            st.write(etat.get('etape','Analyse non lancée'))
            st.progress(min(1.0,etat.get('videos_analysees',0)/max(1,etat.get('videos_total',1))))
            st.caption(f"{etat.get('videos_analysees',0)} vidéo(s) analysée(s) — {actuel.get('video_statut','non_lance')}")
            if etat.get('erreurs'): st.warning("Analyse partielle : "+" ; ".join(e.get('raison','Erreur') for e in etat['erreurs']))
            st.caption("Un groupe relie des publications par des correspondances directes ; toutes les vidéos du groupe ne sont pas nécessairement identiques. Le score est heuristique, pas une probabilité calibrée.")
            for groupe in donnees['groupes']:
                with st.expander(groupe['id']+" — "+str(len(groupe['publications']))+" publications",expanded=True):
                    lignes=[]
                    for c in donnees['correspondances']:
                        if c['a'] not in groupe['publications'] or c['b'] not in groupe['publications']: continue
                        for segment in c['segments']:
                            lignes.append({"TikTok A":c['a'],"URL A":c.get('url_a'),"Média A":c.get('media_a'),
                                "TikTok B":c['b'],"URL B":c.get('url_b'),"Média B":c.get('media_b'),
                                "Début A (s)":segment['debut_a_s'],"Fin A (s)":segment['fin_a_s'],
                                "Début B (s)":segment['debut_b_s'],"Fin B (s)":segment['fin_b_s'],
                                "Type":c['type'],"Confiance":c['confiance']})
                    st.dataframe(lignes,hide_index=True,column_config={"URL A":st.column_config.LinkColumn(),"URL B":st.column_config.LinkColumn()})
            diagnostic=donnees.get('diagnostic',{})
            if diagnostic:
                st.caption(f"{diagnostic['paires_candidates']} paire(s) candidate(s) · {diagnostic['paires_orb_testees']} vérification(s) ORB · {diagnostic['images_confirmees']} image(s) confirmée(s)")
                with st.expander('Diagnostic de la recherche'):
                    st.json(diagnostic)
            if donnees['etat'] and not donnees['groupes']:
                if not etat.get('videos_analysees'):
                    st.warning('Aucune vidéo analysée : vérifiez les erreurs de téléchargement ci-dessus.')
                elif diagnostic and not diagnostic['paires_candidates']:
                    st.info('Aucun candidat visuel trouvé dans les images échantillonnées. Cela ne prouve pas que les vidéos sont différentes.')
                else:
                    st.info('Des candidats ont été examinés, sans séquence commune confirmée. Le diagnostic indique les étapes de rejet.')
            if not actuel.get('video_busy'):
                st.link_button("Exporter les résultats (CSV, JSON, IRaMuTeQ dans le ZIP)",f"/api/jobs/{tache['id']}/archive")
        afficher_similarites()
