"""Interface Streamlit minimaliste ; la collecte et le navigateur restent dans FastAPI."""
import json
import os
from datetime import date, datetime, timezone
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
# Réduire la marge supérieure native sans masquer les commandes de la barre latérale.
st.html("""<style>
[data-testid="stMainBlockContainer"] { padding-top: 1rem; }
[data-testid="stHeader"] { background: transparent; height: 0; }
/* Le composant Analytics invisible ne doit pas occuper une ligne avant le titre. */
[data-testid="stElementContainer"]:has(iframe[height="0"]) { display: none; }
</style>""")
# Même propriété Analytics que la home ; une seule visite malgré les reruns.
components.html(Path(__file__).with_name("analytics.html").read_text(encoding="utf-8"),
                height=0, scrolling=False)
st.title("ScrapTikTok")
st.caption("Appli en cours de dév - modifiée 21-10-2026")
st.caption("Collecter les textes des publications TikTok.")

session = st.context.cookies.get("scraptiktok_session", "")
cookie_historique = st.context.cookies.get("scraptiktok_historique", "")
autorisation = st.context.headers.get("Authorization", "")
if not re.fullmatch(r"[a-f0-9]{64}", session):
    st.info("Ouvrez l’application depuis sa page d’accueil pour initialiser votre session privée.")
    st.link_button("Ouvrir l’accueil", "/")
    st.stop()


def api(chemin, donnees=None):
    return appeler_api(chemin, session, autorisation, donnees,
                      cookie_historique=cookie_historique)


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
        st.error(str(erreur))
        st.stop()

    # Restaurer uniquement une collecte ou une analyse en cours.
    # Ne pas réafficher automatiquement les résultats terminés.
    if ancienne and not (
        ancienne.get("busy", False)
        or ancienne.get("video_busy", False)
    ):
        ancienne = None

    st.session_state["collecte"] = ancienne
    ancienne = ancienne or {}

    valeurs = {"source":ancienne.get("source_collecte","hashtags"), "hashtag":ancienne.get("hashtag",""),
        "second_hashtag":ancienne.get("second_hashtag",""), "operator":ancienne.get("operator","AND"),
        "rechercher_dans_texte": ancienne.get("rechercher_dans_texte", False),
        "variantes_accents": ancienne.get("variantes_accents", False),
        "comptes":", ".join(ancienne.get("comptes",[])), "medias":ancienne.get("medias",[]),
        "limit":ancienne.get("limit",50), "french_only":ancienne.get("french_only",True),
        "include_sources":ancienne.get("include_sources",True),
        "sauvegarde_progressive":ancienne.get("sauvegarde_progressive",False),
        "collecter_commentaires":ancienne.get("collecter_commentaires",False),
        "collecter_reponses":ancienne.get("collecter_reponses",False),
        "limite_commentaires":ancienne.get("limite_commentaires",50)}

    variables = ancienne.get("variables_txt")
    if variables is None:
        # Nouveau formulaire : toutes les variables TXT sont cochées, sauf le
        # déplacement des hashtags. Une collecte active sans sélection explicite
        # conserve en revanche son ancien réglage de compatibilité.
        variables = (
            (["date", "profil", "id"] if ancienne.get("inclure_metadonnees_txt")
             else ["profil", "id"] if ancienne.get("include_sources", True) else [])
            if ancienne else [v for v in VARIABLES_TXT if v != "hashtags"]
        )
    variables = [{"republications": "partages", "url": "id"}.get(v, v) for v in variables]
    for variable in VARIABLES_TXT:
        valeurs["txt_" + variable] = variable in variables
    # Une recherche de médias ne reprend pas les hashtags d'une recherche précédente.
    for nom in ("hashtag", "second_hashtag"):
        valeurs[nom + "_comptes"] = ancienne.get(nom, "") if ancienne.get("source_collecte") == "comptes" else ""
        if ancienne.get("source_collecte") in {"presse", "comptes"}: valeurs[nom] = ""
    for nom in ("date_debut","date_fin"):
        valeurs[nom] = date.fromisoformat(ancienne[nom]) if ancienne.get(nom) else None
    for cle,valeur in valeurs.items(): st.session_state.setdefault(cle,valeur)
    st.session_state["initialise"] = True

st.session_state.setdefault("telecharger_mp4", False)
st.session_state.setdefault("sauvegarde_progressive", False)
st.session_state.setdefault("presse_moteur", "api")

# Conserver les filtres de chaque mode même quand leurs champs ne sont pas affichés.
for variable in VARIABLES_TXT:
    # Initialiser seulement si absent : préserver les choix manuels déjà faits.
    st.session_state.setdefault("txt_" + variable, variable != "hashtags")
    st.session_state["txt_" + variable] = st.session_state["txt_" + variable]
# Quand le mode Médias masque la radio ET/OU, Streamlit peut supprimer sa
# clé du session_state à la fin d'une exécution. Le formulaire médias doit
# rester lançable sans ce widget.
st.session_state.setdefault("operator", "AND")
st.session_state.setdefault("rechercher_dans_texte", False)
st.session_state.setdefault("variantes_accents", False)
for cle in ("hashtag", "second_hashtag", "hashtag_comptes", "second_hashtag_comptes",
            "operator", "limit", "french_only", "include_sources", "txt_date", "txt_profil", "txt_id",
            "collecter_commentaires", "collecter_reponses", "limite_commentaires", "telecharger_mp4",
            "date_debut", "date_fin", "comptes"):
    # Streamlit peut effacer les clés des widgets masqués au changement de mode.
    # Ne pas provoquer de KeyError avant même d'afficher le formulaire Médias.
    if cle in st.session_state:
        st.session_state[cle] = st.session_state[cle]

collecte = st.session_state["collecte"] or {}
occupe = bool(collecte.get("busy") or collecte.get("video_busy"))

# L'historique est identifié par un cookie privé distinct de la session de
# collecte ; la session peut expirer sans effacer les analyses des 30 jours.
with st.sidebar:
    st.subheader("Historique des analyses")
    if not cookie_historique:
        st.caption("Rechargez la page d'accueil pour activer l'historique privé.")
    else:
        try:
            historique_reponse = api("/api/historique")
        except RuntimeError as erreur:
            st.warning("Historique indisponible : " + str(erreur))
        else:
            analyses_passees = historique_reponse.get("analyses", [])
            duree_historique = historique_reponse.get("retention_jours", 30)
            st.caption(f"Collectes et analyses conservées {duree_historique} jours, "
                       "sans duplication des vidéos MP4.")
            if not analyses_passees:
                st.caption("Aucune analyse enregistrée.")
            else:
                index_analyses = {ligne["id"]:ligne for ligne in analyses_passees}
                def afficher_entree_historique(identifiant):
                    ligne = index_analyses[identifiant]
                    date_ = datetime.fromtimestamp(
                        ligne.get("actualise_le", 0), tz=timezone.utc
                    ).strftime("%d/%m/%Y")
                    return f"{date_} · {ligne.get('titre') or identifiant[:8]}"

                choix_historique = st.selectbox(
                    "Retrouver une analyse",
                    list(index_analyses),
                    format_func=afficher_entree_historique,
                    key="choix_historique_scraptiktok",
                )
                entree = index_analyses[choix_historique]
                st.caption("Statut : " + entree.get("statut","indéterminé"))
                if st.button("Rouvrir l'analyse",key="ouvrir_historique_scraptiktok",
                             disabled=occupe,use_container_width=True):
                    try:
                        analyse_reouverte=api(
                            f"/api/historique/{choix_historique}/ouvrir", {}
                        )
                        st.session_state["collecte"] = analyse_reouverte
                        st.rerun()
                    except RuntimeError as erreur:
                        st.error("Réouverture impossible : " + str(erreur))
                st.link_button(
                    "Télécharger les résultats (ZIP sans MP4)",
                    f"/api/historique/{choix_historique}/archive",
                    use_container_width=True,
                )

# Recharger les limites serveur, identiques pour tous les utilisateurs.
try:
    limites_admin = api("/api/collecte/limites")
except RuntimeError as erreur:
    st.error("Limites administrateur indisponibles : "+str(erreur))
    st.stop()
max_posts_admin = int(limites_admin["maximum_publications_par_source"])
max_sources_admin = int(limites_admin["maximum_sources_par_collecte"])
max_commentaires_admin = int(limites_admin["maximum_commentaires_par_video"])
st.session_state["limite_commentaires"] = min(
    max(1,int(st.session_state.get("limite_commentaires",50))),max_commentaires_admin)
st.session_state["limit"] = min(max(1,int(st.session_state.get("limit",50))),max_posts_admin)

# Recharger le catalogue évite de conserver une ancienne liste dans une session ouverte.
try:
    medias = {m["id"]:m for m in api("/api/presse")["medias"]}
except RuntimeError as erreur:
    st.error(str(erreur)); st.stop()
onglet_collecte, onglet_multimodale, onglet_desordre, onglet_corpus, onglet_aide = st.tabs(
    ["Collecte", "Multimodale", "Désordre visuel", "Corpus fusionné", "Aide"]
)

with onglet_collecte:
    api_tiktok_suspendue = False
    source = st.radio("Rechercher par", ["hashtags","presse","comptes"], key="source", horizontal=True,
        format_func=lambda s:{"hashtags":"Hashtags","presse":"Presse et médias","comptes":"Autres comptes TikTok"}[s], disabled=occupe)
    if source == "presse":
        st.write("Choisir les médias à collecter")
        st.caption("Cochez les médias dont vous souhaitez collecter les publications publiques. Aucun hashtag nécessaire.")
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
        st.caption(f"{len(selection)} média(s) sélectionné(s) sur {len(medias)}. "
                   f"Borne technique : {max_sources_admin} source(s) par collecte. "
                   "Seules les publications des comptes cochés sont retenues.")
        if len(selection)>max_sources_admin:
            st.warning("Trop de médias sélectionnés pour une même collecte : "
                       f"maximum {max_sources_admin}.")
        st.radio("Moteur de découverte Presse (une seule méthode par collecte)",
            ["api", "navigateur"],key="presse_moteur",horizontal=True,disabled=occupe,
            format_func=lambda v: "API du créateur (secUid)" if v=="api" else "Grille du profil (Selenium)",
            help="L'API utilise les pages de publications du média. Le navigateur inspecte l'onglet Vidéos. "
                 "Les deux moteurs ne sont jamais enchaînés pendant une même collecte.")
        budget_api=limites_admin.get("budget_api_presse",{})
        st.caption(
            f"Budget API Presse partagé : {budget_api.get('requete_minute',0)}/"
            f"{budget_api.get('maximum_minute','?')} requêtes sur 1 min ; "
            f"{budget_api.get('requete_heure',0)}/"
            f"{budget_api.get('maximum_heure','?')} sur 1 h ; "
            f"{budget_api.get('requete_24h',0)}/"
            f"{budget_api.get('maximum_24h','?')} sur 24 h. "
            "Ces plafonds locaux ne sont pas des limites officielles applicables au scraping."
        )
        try:
            limitation_presse=api("/api/presse/limitation")
            if limitation_presse.get("actif"):
                api_tiktok_suspendue = st.session_state.get("presse_moteur","api") == "api"
                restant=limitation_presse.get("restant_secondes",0)
                st.error(
                    f"TikTok a demandé une attente explicite (Retry-After) : "
                    f"encore {restant//60} min {restant%60} s. "
                    "Seul le moteur API Presse est temporairement désactivé."
                )
            elif limitation_presse.get("ancien_429_sans_delai"):
                st.warning(
                    "TikTok a renvoyé HTTP 429 sans préciser de délai. "
                    "L'ancienne pause locale d'une heure est annulée. "
                    "Un nouvel essai reste susceptible d'être refusé ; "
                    "ScrapTikTok ne déclenche aucun nouvel essai automatiquement."
                )
            else:
                st.caption("API TikTok : aucune attente Retry-After active.")
            st.caption("Limite chiffrée officielle : non publiée pour cette API web interne. "
                       "La limite de 600 requêtes/minute de l'API officielle v2 ne s'y applique pas.")
        except RuntimeError as erreur:
            st.warning("État de limitation TikTok indisponible : "+str(erreur))
        try:
            version_presse=api("/healthz").get("version_presse")
            if version_presse:
                st.caption("Version active du serveur Presse : "+version_presse)
            else:
                st.error("Ancienne version du serveur : numéro de version Presse absent. Vérifier le déploiement Coolify.")
        except RuntimeError as erreur:
            st.warning("Version du serveur non vérifiable : "+str(erreur))
    elif source == "comptes":
        st.text_input("Comptes TikTok", key="comptes", placeholder="@lemondefr, @franceinfo", help="Jusqu’à 10 comptes séparés par des virgules ou espaces.", disabled=occupe)
        st.caption("Avec ou sans @ : @lemondefr et lemondefr sont acceptés.")
        st.caption("Jusqu’à 10 profils, séparés par des virgules ou des espaces. Renseignez au moins un hashtag ci-dessous pour lancer la collecte.")
    cle_hashtag = "hashtag" if source == "hashtags" else "hashtag_comptes"
    cle_second = "second_hashtag" if source == "hashtags" else "second_hashtag_comptes"
    # Envoyer les filtres ensemble évite les pertes de saisie entre deux réexécutions.
    with st.form("filtres_collecte", border=False, enter_to_submit=False):
        if source != "presse":
            c1,c2 = st.columns(2)
            aide_hashtag = (
                "Saisissez un hashtag sans espace, avec ou sans #. Exemple : #17octobre ou 17octobre. "
                "Par défaut, la sélection finale porte uniquement sur les hashtags précédés de #. "
                "Si vous cochez « Rechercher aussi dans le texte », une vidéo dont la légende "
                "contient le mot recherché est retenue pour le TXT, même sans # (par exemple "
                "#lyceen et « lycéen », ou #17octobre et « 17 octobre »). "
                "La règle ET/OU et les filtres de langue/période restent applicables. "
                "Seules les vidéos effectivement découvertes et lues sur TikTok peuvent être retenues."
            )
            c1.text_input("Hashtag (obligatoire)", key=cle_hashtag, placeholder="#actualité",
                          help=aide_hashtag, disabled=occupe)
            c1.caption("Avec ou sans # : #actualité ou actualité. Un seul hashtag, sans espace.")
            c2.text_input("Deuxième hashtag (facultatif)", key=cle_second, placeholder="#politique",
                          help=aide_hashtag, disabled=occupe)
            c2.caption("Avec ou sans # : #politique ou politique. Un seul hashtag, sans espace.")
            st.radio("Combiner les hashtags", ["AND","OR"], format_func=lambda v:"ET — les deux" if v=="AND" else "OU — au moins un", key="operator", horizontal=True, disabled=occupe)
            if source == "hashtags":
                st.checkbox("Inclure les variantes accentuées des hashtags",
                    key="variantes_accents", disabled=occupe,
                    help="Décoché : seul le hashtag exact est accepté (#lyceen différent de #lycéen). "
                         "Coché : les variantes avec ou sans accents sont prises en compte ; "
                         "ScrapTikTok explore également un nombre limité de pages de variantes (#lyceen, #lycéen…). "
                         "Les variantes proposées sont heuristiques (huit graphies au maximum par hashtag) : "
                         "la recherche peut être plus longue sans garantir un résultat exhaustif. "
                         "Le nombre de vidéos demandé reste commun à toutes les variantes du même hashtag.")
            st.checkbox("Rechercher aussi dans le texte des légendes (en plus des hashtags)",
                key="rechercher_dans_texte", disabled=occupe,
                help="Décoché (par défaut) : seuls les #hashtags exacts de la légende comptent. "
                     "Coché : les mots entiers du texte comptent aussi, sans distinction de majuscules ou d’accents. "
                     "Par exemple, #lyceen peut correspondre à « lycéen » et #17octobre à « 17 octobre ». "
                     "Une vidéo dont la légende contient le mot correspondant est donc retenue "
                     "pour le TXT, même sans hashtag, si elle respecte la combinaison ET/OU "
                     "et les autres filtres (langue et période). "
                     "Ce choix agit après la découverte des vidéos TikTok.")
        st.number_input("Nombre de posts TikTok à collecter par source",
            min_value=1, max_value=max_posts_admin, step=1, key="limit", disabled=occupe,
            help=f"Borne technique du moteur : {max_posts_admin} posts par source. "
                 "Il est vérifié aussi sur les requêtes API directes.")
        st.caption("Le nombre de textes exportés peut être inférieur selon les filtres et les publications accessibles.")
        if source == "presse":
            st.caption("Parcours des profils publics des médias sélectionnés. Seuls leurs auteurs sont admis ; les filtres de langue et de période restent disponibles. Couverture potentiellement incomplète.")
        elif source == "comptes":
            st.caption("Les publications publiques des comptes sélectionnés sont parcourues en priorité. Les hashtags saisis sont appliqués aux légendes après découverte. La couverture du profil peut être incomplète.")
        st.checkbox("Filtre français", key="french_only", disabled=occupe,
            help="Exclut les légendes identifiées dans une autre langue. Les légendes courtes ou de langue indéterminée sont conservées et signalées.")
        st.checkbox("Télécharger les vidéos (MP4)", key="telecharger_mp4", disabled=occupe,
            help="Télécharge les vidéos accessibles des publications retenues dans l’archive ZIP. La variable ID reste dans le TXT pour retrouver chaque fichier.")
        st.checkbox("Sauvegarde progressive des collectes (toutes les 10 publications)",
            key="sauvegarde_progressive", disabled=occupe,
            help="Facultatif, désactivé par défaut. Conserve sur le VPS un ZIP de récupération "
                 "avec les légendes, publications, commentaires et données de sélection. "
                 "Le ZIP est remplacé toutes les 10 publications traitées et à la fin de la collecte, "
                 "même partielle. Il reste disponible après redémarrage pendant 7 jours par défaut, "
                 "si /app/data est un volume persistant. Les MP4 ne sont pas copiés. "
                 "Cela ne permet pas de reprendre automatiquement Selenium.")
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
            def respecter_choix_commentaires():
                if not st.session_state["collecter_commentaires"]: st.session_state["collecter_reponses"] = False
            st.checkbox("Inclure les réponses accessibles", key="collecter_reponses", disabled=occupe, help="Les réponses sont collectées uniquement si la collecte des commentaires est cochée.")
            st.number_input("Commentaires maximum par publication", min_value=1,
                max_value=max_commentaires_admin, step=1,
                key="limite_commentaires", disabled=occupe,
                help="Borne technique contrôlée également côté serveur.")
        if st.form_submit_button("Lancer la collecte", type="primary",
                                 disabled=occupe or api_tiktok_suspendue
                                          or (source=="presse" and len(st.session_state.get("medias",[]))>max_sources_admin),
                                 on_click=respecter_choix_commentaires):
            debut,fin = iso(st.session_state["date_debut"]),iso(st.session_state["date_fin"])
            if source != "presse" and not st.session_state.get(cle_hashtag, "").strip():
                st.error("Le premier hashtag est obligatoire pour la collecte par hashtags ou profils.")
            elif source == "presse" and not st.session_state.get("medias"):
                st.error("Sélectionnez au moins un média.")
            elif debut and fin and debut>fin: st.error("La date de début doit précéder ou égaler la date de fin.")
            else:
                valeurs = {k:st.session_state[k] for k in ("limit","french_only","include_sources","collecter_commentaires","collecter_reponses","limite_commentaires","telecharger_mp4","sauvegarde_progressive")}
                valeurs["operator"] = "AND" if source == "presse" else st.session_state.get("operator", "AND")
                valeurs["presse_moteur"] = st.session_state.get("presse_moteur", "api")
                valeurs["rechercher_dans_texte"] = (
                    bool(st.session_state.get("rechercher_dans_texte", False)) if source != "presse" else False
                )
                valeurs["variantes_accents"] = (
                    bool(st.session_state.get("variantes_accents", False)) if source == "hashtags" else False
                )
                # Toujours préparer l'archive, même si une ancienne session l'avait désactivée.
                valeurs["enrichir"] = True
                valeurs["variables_txt"] = [v for v in VARIABLES_TXT if st.session_state["txt_" + v]]
                valeurs.update(hashtag="" if source == "presse" else st.session_state.get(cle_hashtag,""),
                    second_hashtag="" if source == "presse" else st.session_state.get(cle_second,""),
                    source_collecte=source, date_debut=debut, date_fin=fin,
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
            if actuel.get("busy"):
                if (actuel.get("debug_collecte") or {}).get("arret_demande"):
                    st.warning("Arrêt demandé : le moteur termine l'opération en cours et sauvegarde les résultats déjà obtenus.")
                elif st.button("Arrêter immédiatement la collecte", type="primary",
                               key="interrompre_collecte_active", use_container_width=True):
                    lancer(f"/api/jobs/{actuel['id']}/stop", {})
            # Les changements d’étape recréent l’interface ; les images et gestes restent dans leur iframe stable.
            if any(precedent.get(k)!=actuel.get(k) for k in ("busy","video_busy")) or (precedent.get("status")=="attention") != (actuel.get("status")=="attention"):
                st.rerun()
            if actuel.get("comptes_filtres"):
                st.write("Filtre des profils : " + ", ".join("@" + compte for compte in actuel["comptes_filtres"]))
                st.caption("Les comptes sont parcourus directement, avec recherche par identifiant en secours. "
                           + ("Aucun hashtag n'est imposé aux médias ; les autres auteurs sont exclus."
                              if actuel.get("source_collecte") == "presse" else
                              "Les hashtags sont vérifiés dans les légendes ; les autres auteurs sont exclus."))
            if actuel.get("sauvegarde_progressive") and actuel.get("erreur_sauvegarde"):
                st.warning(actuel["erreur_sauvegarde"])
            if actuel.get("sauvegarde_progressive"):
                point=actuel.get("dernier_point_sauvegarde") or {}
                if point:
                    st.caption(f"Sauvegarde progressive : {point.get('traitees',0)} publication(s) traitée(s) sauvegardée(s) · {point.get('sauvegarde_le','')}.")
                else:
                    st.caption("Sauvegarde progressive activée : premier point après 10 publications traitées.")
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
            if st.checkbox("Mode debug — diagnostic de la collecte",key="debug_collecte_active",
                    help="Affiche les causes d’arrêt, les limites et les 100 derniers événements. Le diagnostic technique est enregistré automatiquement pour cette session, même si cette case était décochée."):
                diagnostic=actuel.get('debug_collecte')
                if diagnostic:
                    cause=diagnostic.get('cause_arret')
                    if cause: st.warning(cause['explication'])
                    elif actuel.get('status')=='stopped': st.warning('Cause non enregistrée pour cette ancienne collecte.')
                    st.json(diagnostic,expanded=True)
                    st.download_button('Télécharger le diagnostic debug (JSON)',
                        json.dumps(diagnostic,ensure_ascii=False,indent=2),
                        file_name='diagnostic_collecte.json',mime='application/json',
                        key='telecharger_debug_collecte')
                else: st.info('Diagnostic indisponible pour cette ancienne session. Relancez une collecte après le déploiement.')
            compteurs = actuel.get("compteurs_collecte")
            if compteurs:
                aides_retenues = {
                    "hashtags": (
                        "Nombre de publications TikTok distinctes retenues pour lecture, avant vérification "
                        "des hashtags dans les légendes et avant les autres filtres. La limite est PAR HASHTAG "
                        "saisi : avec 20 posts et deux hashtags, jusqu’à 40 vidéos différentes peuvent être "
                        "retenues, en mode OU comme en mode ET. Les doublons sont dédupliqués ; les variantes "
                        "accentuées partagent le quota du hashtag initial. Le choix ET/OU s’applique ensuite "
                        "aux légendes pour déterminer les textes exportés."
                    ),
                    "comptes": (
                        "Nombre de publications distinctes trouvées sur les profils choisis, avant filtrage "
                        "des hashtags dans les légendes. La limite s’applique à chaque compte ; les doublons "
                        "ne sont comptés qu’une fois."
                    ),
                    "presse": (
                        "Nombre de publications distinctes trouvées pour les médias sélectionnés, avant "
                        "filtrage de langue et de période. La limite s’applique à chaque média ; les doublons "
                        "ne sont comptés qu’une fois."
                    ),
                }
                colonnes = st.columns(4)
                for colonne, cle, titre in zip(colonnes,
                        ("decouvertes", "retenues", "traitees", "exportees"),
                        ("Découvertes", "Retenues pour lecture", "Traitées", "Exportées dans le TXT")):
                    colonne.metric(titre, compteurs[cle],
                        help=aides_retenues.get(actuel.get("source_collecte")) if cle == "retenues" else None)
                st.caption(("Découvertes : publications des médias sélectionnés ; retenues : auteur vérifié. Aucun filtre par hashtag. "
                            if actuel.get("source_collecte") == "presse" else
                            "Découvertes : vidéos repérées sur les profils ou par recherche du compte. Retenues : auteur conforme ; filtrage hashtags/texte effectué après lecture. "
                            if actuel.get("source_collecte") == "comptes" else "")
                           + "Les autres filtres peuvent réduire le nombre de publications exportées.")
            else:
                st.caption(f"{actuel['captions']} textes · {actuel['processed']}/{actuel['discovered']} publications lues")
            if actuel.get("hashtags"):
                combinaison = (" ET " if actuel["operator"] == "AND" else " OU ").join("#" + h for h in actuel["hashtags"])
                st.caption("Filtre appliqué : " + combinaison
                           + (" (hashtags et texte)" if actuel.get("rechercher_dans_texte")
                              else " (hashtags uniquement)")
                           + (" · variantes accentuées incluses" if actuel.get("variantes_accents") else ""))
                if "bilan_hashtags" in actuel and actuel.get("processed", 0):
                    with st.expander("Bilan des filtres", expanded=not actuel["busy"] and not actuel["captions"]):
                        st.caption("Comptages sur les légendes lisibles dans la période choisie, avant le filtre français. "
                                   + ("Hashtags ou mots entiers du texte, sans distinction d’accents."
                                      if actuel.get("rechercher_dans_texte") else
                                      "Seuls les hashtags précédés de # sont pris en compte.")
                                   + (" Comparaison des hashtags avec et sans accents."
                                      if actuel.get("variantes_accents") else ""))
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
                        if actuel.get("source_collecte") == "presse":
                            version_source=bilan.get("version_collecteur")
                            if version_source:
                                st.caption("Méthode enregistrée : "+str(bilan.get("presse_moteur") or "?")+
                                           " · version "+version_source)
                            else:
                                st.warning("Diagnostic issu d'une ancienne collecte, sans version enregistrée : "
                                           "relancez une collecte pour tester le nouveau moteur.")
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
                            navigation=recherche.get("navigation_publications")
                            if navigation=="api_liste_createur":
                                provenance=recherche.get("source_secuid")
                                resolution=(
                                    "identifiant confirmé via l'embed d'une vidéo"
                                    if provenance=="embed_video" else
                                    "identifiant fourni par l'embed du créateur"
                                    if provenance=="embed_createur" else
                                    "identifiant non encore confirmé"
                                )
                                st.caption(
                                    f"Liste vidéo TikTok par secUid : "
                                    f"{recherche.get('pages_api',0)} page(s) reçue(s), "
                                    f"{recherche.get('liens',0)} vidéo(s) retenue(s) "
                                    f"du média ; {resolution}."
                                )
                            elif navigation=="onglet_videos_selectionne":
                                st.caption("Onglet Vidéos du média confirmé : collecte sur sa grille et ses pages successives.")
                            elif navigation=="grille_videos_sans_onglet_distinct":
                                st.caption("Grille de vidéos du média reconnue ; aucun onglet distinct n'était nécessaire.")
                            elif navigation=="onglet_videos_indisponible":
                                st.warning("Onglet Vidéos introuvable sur ce profil : aucune recherche générale n'est substituée.")
                            elif navigation=="clic_onglet_videos_impossible":
                                st.warning("Impossible d'ouvrir l'onglet Vidéos du média.")
                            elif navigation=="ouverture_onglet_videos_en_cours":
                                st.caption("Ouverture de l'onglet Vidéos demandée, mais le chargement n'a pas été confirmé.")
                            elif navigation=="rubrique_selectionnee":
                                st.caption("Rubrique Vidéos/Publications ouverte avant la pagination.")
                            elif navigation=="pas_de_rubrique_distincte_detectee":
                                st.caption("Aucun accès distinct à « Toutes les vidéos » détecté : collecte sur la grille visible du profil.")
                            elif navigation=="clic_impossible":
                                st.warning("TikTok a refusé l'ouverture de la rubrique Vidéos/Publications.")
                            details_pagination=recherche.get("pagination_bilan") or {}
                            if details_pagination:
                                st.caption(
                                    f"Pagination du profil : {details_pagination.get('defilements',0)} "
                                    f"défilement(s), {details_pagination.get('sans_progres',0)} sans déplacement "
                                    f"de grille · {details_pagination.get('pages_reseau',0)} page(s) "
                                    "de publications reçue(s) par le navigateur."
                                )
                                if details_pagination.get("connexion_exigee"):
                                    st.warning(
                                        "TikTok interrompt la pagination anonyme de ce média en demandant "
                                        "une connexion. Les premières vidéos restent conservées ; "
                                        "la recherche complémentaire tente d'en trouver d'autres."
                                    )
                                elif details_pagination.get("sans_progres",0):
                                    st.info(
                                        "La grille du profil n'a pas progressé à certains défilements. "
                                        "Cela peut provenir du conteneur TikTok ou d'une limite "
                                        "d'accès aux publications suivantes."
                                    )
                                if not details_pagination.get("reseau_disponible",True):
                                    st.caption("Observation des pages réseau indisponible ; liens HTML uniquement.")
                            motifs = {"limit": "limite demandée atteinte", "no_new_links": "plus de nouveaux liens après plusieurs attentes",
                                      "max_scrolls": "budget de défilement atteint", "blocked": "vérification TikTok en attente",
                                      "tiktok_error": "erreur de chargement TikTok", "no_accessible_links": "aucun lien lisible",
                                      "connexion_apres_resultats": "invitation à se connecter et absence de nouveaux liens",
                                      "publications_non_accessibles": "invitation à se connecter et aucun lien lisible",
                                      "recherche_redirigee": "redirection vers une autre page"}
                            if recherche.get("arret"):
                                st.caption(f"{recherche.get('defilements', 0)} défilement(s) effectué(s). Arrêt : " + motifs.get(recherche["arret"], recherche["arret"]))
                            if recherche.get("diagnostic"):
                                diagnostic_recherche=recherche["diagnostic"]
                                code_recherche=diagnostic_recherche.get("code", "indéterminé")
                                st.caption("Diagnostic : " + code_recherche)
                                if code_recherche=="tiktok_limitation_429":
                                    st.error("TikTok a renvoyé HTTP 429 : le moteur API s'est arrêté sans "
                                             "essayer les autres vidéos ni les autres médias.")
                                elif code_recherche=="budget_interne_epuise":
                                    st.warning("Budget administrateur des requêtes API Presse épuisé. "
                                               "La collecte a été arrêtée avant de solliciter TikTok.")
                                elif code_recherche=="tiktok_pause_429":
                                    st.warning("Moteur API suspendu par la pause de protection après HTTP 429. "
                                               "Aucune requête TikTok n'a été envoyée pour cette nouvelle collecte.")
                                if diagnostic_recherche.get("retry_after_seconds"):
                                    st.caption(f"Délai indicatif transmis par TikTok (Retry-After) : "
                                               f"{diagnostic_recherche['retry_after_seconds']} secondes.")
                                if diagnostic_recherche.get("detail"):
                                    st.warning("Accès TikTok : " + diagnostic_recherche["detail"])
                            elif recherche.get("message_erreur"):
                                st.warning("Accès TikTok : "+recherche["message_erreur"])
                        diagnostic = bilan.get("diagnostic", {})
                        if diagnostic:
                            indices = [str(diagnostic[cle]) for cle in ("code", "exception", "erreur_reseau", "url", "etat") if diagnostic.get(cle)]
                            st.caption(" · ".join(indices))
            if actuel.get("apercu_engagement"):
                st.caption(f"{len(actuel['apercu_engagement'])} publications enregistrées · {actuel.get('captions',0)} textes retenus après les filtres.")

                def compteur(mesure):
                    if mesure.get("valeur") is None:
                        return "Indisponible"
                    return ("≈ " if mesure.get("estime") else "") + str(mesure["valeur"])

                lignes = []
                for publication in actuel["apercu_engagement"]:
                    ligne = {
                        "Auteur": "@" + publication["author"],
                        "Publication": publication["url"],
                        "URL TikTok": publication["url"]
                    }

                    for cle, titre in (
                        ("likes", "Likes"),
                        ("vues", "Vues"),
                        ("partages", "Partages"),
                        ("commentaires", "Nombre de commentaires"),
                        ("favoris", "Nombre de favoris")
                    ):
                        ligne[titre] = compteur(
                            publication.get("engagement", {}).get(cle, {})
                        )

                    ligne["Retenue dans le TXT"] = (
                        "Oui" if publication.get("retenue_txt", True) else "Non"
                    )

                    ligne["Langue"] = {
                        "fr": "Français",
                        "other": "Autre langue",
                        "unknown": "Indéterminée",
                        None: "Non évaluée"
                    }.get(publication.get("langue_detection"), "Non évaluée")

                    lignes.append(ligne)

                st.dataframe(
                    lignes,
                    hide_index=True,
                    column_config={
                        "Publication": st.column_config.LinkColumn(
                            "Publication", display_text="Ouvrir"
                        )
                    }
                )

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

with onglet_collecte:
    with st.expander("Sauvegardes progressives — récupérer un corpus", expanded=False):
        st.caption("Les ZIP sont conservés sur le volume VPS pendant 7 jours par défaut, "
                   "mais leur téléchargement depuis cette interface nécessite le cookie privé "
                   "d’origine (valable 24 h). Ils contiennent TXT et JSON, sans MP4 ni "
                   "reprise automatique de la collecte.")
        if st.button("Actualiser la liste des sauvegardes",key="actualiser_sauvegardes"):
            st.session_state.pop("sauvegardes_collectes",None)
        if "sauvegardes_collectes" not in st.session_state:
            try:
                st.session_state["sauvegardes_collectes"]=api("/api/sauvegardes")["sauvegardes"]
            except RuntimeError as erreur:
                st.warning("Liste indisponible : "+str(erreur))
                st.session_state["sauvegardes_collectes"]=[]
        for point in st.session_state["sauvegardes_collectes"]:
            st.write(f"{point.get('source','Collecte')} — {point.get('traitees',0)} traitée(s) · "
                     f"{point.get('retenues',0)} retenue(s) · {point.get('statut','')} · "
                     f"{point.get('sauvegarde_le','')}")
            st.link_button("Télécharger le ZIP — "+point['id'][:8],
                f"/api/sauvegardes/{point['id']}/telecharger")
        if not st.session_state["sauvegardes_collectes"]:
            st.info("Aucune sauvegarde disponible pour cette session.")


with onglet_aide:
    st.subheader("Comment utiliser l’application")
    st.markdown("1. Choisissez **Presse et médias**, cochez les comptes ou utilisez **Tout cocher**.\n"
                "2. Pour Presse et médias, aucun hashtag n'est nécessaire : cochez les comptes, choisissez les filtres facultatifs et lancez la collecte. Pour Hashtags et Profils, indiquez un hashtag (deuxième facultatif, ET/OU).\n"
                "3. Les médias sont parcourus par compte public, avec recherche ciblée en secours. Seules les publications des auteurs sélectionnés sont conservées.\n"
                "4. La fenêtre TikTok s’ouvre automatiquement si une vérification est nécessaire ou si une recherche ne fournit plus de publications lisibles. Intervenez dans cette fenêtre, puis cliquez sur **Continuer**.\n"
                "5. Téléchargez le TXT ou l’archive ZIP lorsque les résultats sont disponibles.")
    st.caption("En cas de résultat vide, consultez le détail des sources et les compteurs de filtres. Une page inaccessible n’indique pas qu’un compte n’a aucune publication. Le TXT contient les légendes ; le ZIP enrichi ajoute les données et les commentaires demandés.")
    st.subheader("Limites officielles TikTok et marge de 20 %")
    st.table([
        {"Interface officielle": "API v2 : /v2/user/info/, /v2/video/list/, /v2/video/query/",
         "Limite TikTok": "600 requêtes/min par endpoint", "Référence -20 %": "480 requêtes/min"},
        {"Interface officielle": "Research API : vidéos/commentaires",
         "Limite TikTok": "1 000 requêtes/jour", "Référence -20 %": "800 requêtes/jour"},
        {"Interface officielle": "Research API : enregistrements",
         "Limite TikTok": "100 000 enregistrements/jour", "Référence -20 %": "80 000 enregistrements/jour"},
    ])
    st.caption(
        "Sources officielles TikTok : "
        "[API v2 - limites de requêtes](https://developers.tiktok.com/docs/en/tiktok-api-v2-rate-limit) ; "
        "[Research API - FAQ sur les quotas](https://developers.tiktok.com/docs/en/research-api-faq). "
        "La Research API réinitialise son quota quotidien à minuit UTC ; "
        "ScrapTikTok suit ce calendrier pour ses budgets quotidiens, "
        "tout en conservant les fenêtres glissantes d'une minute et d'une heure."
    )
    st.warning(
        "Ces quotas officiels concernent des API distinctes : ils ne s'appliquent "
        "ni à l'API web interne /api/creator/item_list/, ni à Selenium. "
        "Les valeurs -20 % sont des références de comparaison et non des "
        "seuils officiellement autorisés pour le scraping. "
        "Le plafond de 80 000 enregistrements est désormais appliqué localement "
        "aux objets des pages API Presse ; il ne comptabilise pas Selenium."
    )
    st.subheader("Bornes techniques et quotas globaux de ScrapTikTok")
    st.caption("Les cinq anciennes variables de limitation par source sont ignorées. Le moteur conserve ses bornes techniques et le délai maximal des collectes.")
    budget_aide = limites_admin.get("budget_api_presse", {})
    st.table([
        {"Paramètre": "Publications par source (borne technique)",
         "Valeur active": limites_admin.get("maximum_publications_par_source", "?"),
         "Effet": "Publications maximum par source et par collecte"},
        {"Paramètre": "Sources par collecte (borne technique)",
         "Valeur active": limites_admin.get("maximum_sources_par_collecte", "?"),
         "Effet": "Sources maximum dans une collecte"},
        {"Paramètre": "Commentaires par vidéo (borne technique)",
         "Valeur active": limites_admin.get("maximum_commentaires_par_video", "?"),
         "Effet": "Commentaires maximum par vidéo"},
        {"Paramètre": "Défilements Selenium (borne technique)",
         "Valeur active": limites_admin.get("maximum_defilements", "?"),
         "Effet": "Défilements automatiques maximum du navigateur"},
        {"Paramètre": "Pages de l'API Presse (borne technique)",
         "Valeur active": limites_admin.get("maximum_pages_api_par_source", "?"),
         "Effet": "Pages maximum de l'API Presse par source"},
        {"Paramètre": "SCRAPTIKTOK_API_MIN_INTERVAL_SECONDS",
         "Valeur active": budget_aide.get("intervalle_min_s", "?"),
         "Effet": "Secondes minimum entre deux appels API Presse"},
        {"Paramètre": "SCRAPTIKTOK_API_MAX_REQUESTS_PER_MINUTE",
         "Valeur active": budget_aide.get("maximum_minute", "?"),
         "Effet": "Requêtes API Presse sur une minute glissante (toutes sessions)"},
        {"Paramètre": "SCRAPTIKTOK_API_MAX_REQUESTS_PER_HOUR",
         "Valeur active": budget_aide.get("maximum_heure", "?"),
         "Effet": "Requêtes API Presse sur une heure glissante (toutes sessions)"},
        {"Paramètre": "SCRAPTIKTOK_API_MAX_REQUESTS_PER_DAY",
         "Valeur active": budget_aide.get("maximum_24h", "?"),
         "Effet": "Requêtes API Presse depuis minuit UTC (toutes sessions)"},
        {"Paramètre": "SCRAPTIKTOK_API_MAX_RECORDS_PER_DAY",
         "Valeur active": budget_aide.get("maximum_enregistrements_24h", "?"),
         "Effet": "Objets de pages API Presse depuis minuit UTC (toutes sessions)"},
    ])
    st.caption(
        f"Consommation actuelle du moteur API Presse : "
        f"{budget_aide.get('requete_minute', 0)} sur 1 minute, "
        f"{budget_aide.get('requete_heure', 0)} sur 1 heure et "
        f"{budget_aide.get('requete_24h', 0)} requêtes depuis minuit UTC ; "
        f"{budget_aide.get('enregistrements_24h', 0)} enregistrements depuis minuit UTC. "
        "Le plafond le plus contraignant s'applique. "
        "Ces compteurs ne mesurent pas les requêtes de Selenium. "
        "Les quotas globaux proviennent de l'environnement réellement chargé dans Coolify. "
        "Les cinq plafonds par source ne sont plus lus depuis les variables d'environnement."
    )
    st.subheader("Limites de durée, de concurrence et de tickets Redis")
    st.table([
        {"Variable": "APP_TICKET_MAX_ACTIVE",
         "Valeur active": os.getenv("APP_TICKET_MAX_ACTIVE", "1"),
         "Effet": "Tickets actifs simultanés pour ScrapTikTok"},
        {"Variable": "APP_TICKET_MAX_WAITING",
         "Valeur active": os.getenv("APP_TICKET_MAX_WAITING", "20"),
         "Effet": "Places maximum dans la file d'attente"},
        {"Variable": "APP_TICKET_COST",
         "Valeur active": os.getenv("APP_TICKET_COST", "4"),
         "Effet": "Unités de capacité serveur prises par un ticket"},
        {"Variable": "CAPACITE_SERVEUR",
         "Valeur active": os.getenv("CAPACITE_SERVEUR", "6"),
         "Effet": "Capacité globale partagée du VPS"},
        {"Variable": "APP_TICKET_TTL_SECONDS",
         "Valeur active": os.getenv("APP_TICKET_TTL_SECONDS", "1800"),
         "Effet": "Secondes avant expiration d'un ticket non renouvelé"},
        {"Variable": "APP_TICKET_HEARTBEAT_MS",
         "Valeur active": os.getenv("APP_TICKET_HEARTBEAT_MS", "300000"),
         "Effet": "Intervalle de renouvellement du ticket (millisecondes)"},
        {"Variable": "APP_TICKET_HIDDEN_RELEASE_SECONDS",
         "Valeur active": os.getenv("APP_TICKET_HIDDEN_RELEASE_SECONDS", "300"),
         "Effet": "Délai de libération après masquage de l'onglet (0 : désactivé)"},
        {"Variable": "APP_TICKET_WAIT_REFRESH_MS",
         "Valeur active": os.getenv("APP_TICKET_WAIT_REFRESH_MS", "10000"),
         "Effet": "Rafraîchissement de la file d'attente (millisecondes)"},
        {"Variable": "MAX_CONCURRENT_JOBS",
         "Valeur active": os.getenv("MAX_CONCURRENT_JOBS", "1"),
         "Effet": "Collectes simultanées maximum sur le serveur"},
        {"Variable": "JOB_TIMEOUT_SECONDS",
         "Valeur active": os.getenv("JOB_TIMEOUT_SECONDS", "1800"),
         "Effet": "Durée maximale d'une collecte (secondes)"},
        {"Variable": "IDLE_TIMEOUT_SECONDS",
         "Valeur active": os.getenv("IDLE_TIMEOUT_SECONDS", "300"),
         "Effet": "Inactivité maximale pendant une collecte (secondes)"},
        {"Variable": "RESULT_TTL_SECONDS",
         "Valeur active": os.getenv("RESULT_TTL_SECONDS", "3600"),
         "Effet": "Rétention des résultats temporaires (secondes)"},
        {"Variable": "CHECKPOINT_TTL_SECONDS",
         "Valeur active": os.getenv("CHECKPOINT_TTL_SECONDS", "604800"),
         "Effet": "Rétention des sauvegardes progressives (secondes)"},
    ])
    st.caption(
        "Le ticket Redis peut être renouvelé à chaque heartbeat : son TTL n'est "
        "pas une limite absolue de présence. Le délai maximal d'une collecte "
        "est gouverné par JOB_TIMEOUT_SECONDS. Les valeurs affichées proviennent "
        "de l'environnement du conteneur ; aucun secret Redis n'est exposé."
    )
    st.subheader("Comprendre l’analyse du désordre visuel")
    from analyse_desordre.presentation import (
        AIDE_PREPARATION_DESORDRE, PROCESSUS_DESORDRE, AIDE_AGREGATION_DESORDRE
    )
    st.markdown(AIDE_PREPARATION_DESORDRE)
    for titre, explication in PROCESSUS_DESORDRE:
        with st.expander(titre):
            st.markdown(explication)
    st.markdown("**Comment est calculé l’indice de désordre visuel ?**")
    st.markdown(AIDE_AGREGATION_DESORDRE)




with onglet_multimodale:
    st.subheader("Vidéos similaires")
    st.caption("Recherche de séquences visuelles communes, y compris entre lots et collectes du même utilisateur. Le son seul ne constitue pas une preuve visuelle.")
    tache = st.session_state.get("collecte") or {}
    if not tache.get("archive_prete"):
        st.info("Effectuez une collecte enrichie avant de lancer l’analyse multimodale.")
    elif not tache.get("video_disponible"):
        st.info("Le serveur doit utiliser INSTALL_VIDEO=semantique ou 1 pour DINOv2 (base pour les copies seules) pour activer l’analyse vidéo.")
    else:
        pas = st.number_input("Intervalle entre les images (secondes)", min_value=0.25, max_value=30.0, value=3.0, step=0.25)
        dinov2 = st.checkbox("Rechercher les vidéos similaires avec DINOv2", value=True)
        groupes_dino = st.checkbox("Créer des groupes de similarité DINOv2", value=False)
        seuil_dino = st.number_input("Seuil de regroupement DINOv2 (−1 à 1)", min_value=-1.0, max_value=1.0,
            value=None, step=0.01, disabled=not groupes_dino,
            help="Choisissez ce seuil après examen des scores. Aucun seuil ne filtre les dix voisins affichés.")
        with st.expander("Options multimodales"):
            sha = st.checkbox("Comparer les fichiers identiques", value=True)
            sequences = st.checkbox("Vérifier aussi les séquences avec pHash/ORB", value=True)
            audio = st.checkbox("Mesurer les indicateurs audio")
            ocr = st.checkbox("Lire les textes incrustés (OCR)")
            embeddings = st.checkbox("Comparer aussi le contenu global avec CLIP",
                help="Compare le contenu visuel même sans images identiques : décors, objets, types de scènes. Ne prouve pas un même événement et ne compare pas les paroles.")
            seuil_semantique = st.slider("Similarité de contenu minimale", min_value=0.5, max_value=0.99,
                value=0.75, step=0.01, disabled=not embeddings,
                help="Un seuil bas propose davantage de rapprochements à vérifier. Le score n'est pas une probabilité.")
            modeles = st.checkbox("Autoriser le téléchargement des modèles facultatifs", value=True)
            if dinov2:
                st.caption("DINOv2 nécessite ses poids : téléchargement au premier usage si autorisé, sinon utilisation du cache local uniquement.")
            if embeddings and not modeles:
                st.info("La similarité de contenu utilise CLIP. Autorisez le téléchargement des modèles, sauf si des poids locaux ont été configurés sur le serveur.")
            nettoyer = st.checkbox("Supprimer les MP4 après indexation", value=False,
                help="Les empreintes et vignettes sont conservées pour les comparaisons futures. Les MP4 supprimés ne figureront plus dans le ZIP.")
        st.caption("Traitement séquentiel par lots de 20, reprise automatique. Relancer reprend les éléments en attente après une interruption.")
        if st.button("Lancer / reprendre l’analyse", disabled=occupe or (groupes_dino and seuil_dino is None)):
            lancer(f"/api/jobs/{tache['id']}/video", {"dinov2":dinov2,"seuil_groupes_dino":seuil_dino if groupes_dino else None,"pas_images_s":pas,"comparer_sha256":sha,
                "comparer_sequences":sequences,"audio":audio,
                "ocr":ocr,"embeddings":embeddings,"seuil_semantique":seuil_semantique,"telecharger_modeles":modeles,"nettoyer_videos":nettoyer})
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
            if etat.get('erreurs'):
                st.warning(f"Analyse partielle : {len(etat['erreurs'])} erreur(s). Consultez les causes ci-dessous ; les résultats des vidéos analysées restent disponibles.")
                with st.expander("Détail des erreurs par vidéo", expanded=True):
                    st.dataframe([{"Vidéo":e.get('id','Lot'),"Cause":e.get('statut',e.get('type','Erreur')),
                                   "Détail":e.get('raison','Erreur')} for e in etat['erreurs']],hide_index=True)
            st.caption("Un groupe relie des publications par des correspondances directes ; toutes les vidéos du groupe ne sont pas nécessairement identiques. Le score est heuristique, pas une probabilité calibrée.")
            st.subheader("Vidéos similaires")
            st.caption("Chaque vidéo est interrogée. Jusqu'à 50 vidéos : toutes les paires du lot sont calculées. Au-delà : dix voisins indexés par vidéo. Le score DINOv2 porte sur les images ; CLIP compare le contenu global.")
            couverture=donnees.get('diagnostic',{}).get('dinov2',{})
            if 'paires_uniques_du_lot' in couverture:
                st.caption(f"Lot courant : {couverture['paires_uniques_du_lot']} paires avec résultat sur {couverture['paires_possibles_du_lot']} combinaisons possibles. Les voisins inter-lots peuvent s'ajouter au tableau.")
            paires=donnees.get('paires_dino',[])
            cible=None
            if paires:
                st.write(f"{len(donnees['videos_dino'])} vidéos avec résultats · {len(paires)} paires distinctes, sans doubler A/B et B/A")
                st.dataframe([{"Vidéo A":r['a'],"Vidéo B":r['b'],"URL A":r.get('url_a'),"URL B":r.get('url_b'),
                    "DINOv2":round(r['score'],3),"CLIP (contenu global)":round(r['score_clip'],3) if r.get('score_clip') is not None else None,
                    "Moment A (s)":r.get('temps_a'),"Moment B (s)":r.get('temps_b'),"Temporalité":r.get('nature')} for r in paires],hide_index=True)
                source,cible=st.selectbox("Paire à examiner",[(r['a'],r['b']) for r in paires],
                    format_func=lambda paire:paire[0]+" ↔ "+paire[1],key='paire_dino_'+tache['id'])
            elif donnees.get('videos_dino'):
                source=st.selectbox("Vidéo à comparer",donnees['videos_dino'],key='source_dino_'+tache['id'])
            if donnees.get('videos_dino'):
                selection=api(f"/api/jobs/{tache['id']}/videos-similaires?video={source}")
                for rang,r in enumerate(selection['dinov2'],1):
                    if cible is not None and r['b']!=cible:continue
                    with st.expander(f"{r['a']} ↔ {r['b']} — DINOv2 {r['score']:.3f} — {r['nature']}",expanded=cible is not None):
                        if r.get('score_clip') is not None: st.write(f"CLIP — contenu global : {r['score_clip']:.3f}")
                        st.caption("Les régions de même couleur et de même numéro indiquent des rapprochements locaux. Elles ne disent pas s’il s’agit du même objet, d’une texture ou d’une couleur proche, et n’expliquent pas à elles seules le score global. Même des images sans rapport peuvent avoir des régions proches.")
                        exemples=r.get('correspondances') or [r['meilleure']]
                        for m in exemples[:3]:
                            st.write(f"Images à {m['temps_a']:.1f} s et {m['temps_b']:.1f} s — score {m.get('score',r['score']):.3f}")
                            colonnes=st.columns(2)
                            for colonne,cote in zip(colonnes,('a','b')):
                                with colonne:
                                    st.markdown(f"![Image à {m['temps_'+cote]:.1f} s](/api/jobs/{tache['id']}/miniatures-dino/{m['image_'+cote]})")
                            chemin_regions = f"/api/jobs/{tache['id']}/regions-dino/{m['image_a']}/{m['image_b']}"
                            cle_regions = chemin_regions
                            if st.button("Localiser les régions proches", key=cle_regions, disabled=actuel.get('video_busy',False)):
                                try:
                                    api(chemin_regions, {})
                                except RuntimeError as erreur:
                                    st.error(str(erreur))
                            try:
                                localisation = api(chemin_regions)
                            except RuntimeError:
                                localisation = {'statut':'non_calcule'}
                            if localisation.get('statut') == 'en_cours':
                                st.info("Comparaison des régions en cours sur CPU…")
                            elif localisation.get('statut') == 'erreur':
                                st.warning(localisation.get('raison'))
                            elif localisation.get('statut') == 'termine':
                                if not localisation.get('regions'):
                                    st.info("Aucune région informative à rapprocher après exclusion des bandes noires et des zones uniformes.")
                                    continue
                                for colonne,cote in zip(st.columns(2),('a','b')):
                                    with colonne:
                                        st.markdown(f"![Régions correspondantes — {cote.upper()}]({chemin_regions}/{cote})")
                                st.caption("Bandes noires et zones uniformes exclues. Localisation approximative sur miniatures ; meilleurs voisins réciproques, sans seuil de validation. Le score cosinus local n’est pas une probabilité.")
                                st.dataframe([{"Région":z['numero'], "Score local":round(z['score'],3)}
                                              for z in localisation['regions']],hide_index=True)
                        for cote in ('a','b'):
                            if r.get('url_'+cote): st.link_button("Ouvrir la vidéo "+cote.upper()+" sur TikTok",r['url_'+cote])
                        if r['segments']:
                            st.dataframe([{"Début A (s)":seg['debut_a_s'],"Fin A (s)":seg['fin_a_s'],
                                "Début B (s)":seg['debut_b_s'],"Fin B (s)":seg['fin_b_s'],"Images concordantes":seg['images']} for seg in r['segments']],hide_index=True)
                if selection.get('groupes_dino'):
                    with st.expander("Groupes DINOv2 — liens directs, pas identité de tous les membres"):
                        st.json(selection['groupes_dino'])
            else:
                st.info("Analyse DINOv2 en cours ; les résultats apparaîtront à la fin du lot." if actuel.get("video_busy") else "Aucun voisin DINOv2 disponible. Consultez ci-dessous les statuts du modèle et le nombre d'images analysées.")
            st.subheader("Copies et séquences — vérification complémentaire")
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
                dino=diagnostic.get('dinov2',{})
                st.write({"MP4 présents":diagnostic.get('videos_mp4_disponibles'),"Vidéos décodées":diagnostic.get('videos_decodees'),
                          "Images décodées":diagnostic.get('images_decodees'),"DINOv2":dino})
                st.caption(f"{diagnostic['paires_candidates']} paire(s) candidate(s) · {diagnostic['paires_orb_testees']} vérification(s) ORB · {diagnostic['images_confirmees']} image(s) confirmée(s)")
                with st.expander('Diagnostic de la recherche'):
                    st.json(diagnostic)
            if donnees['etat'] and not donnees['groupes'] and not actuel.get('video_busy'):
                if not etat.get('videos_analysees'):
                    st.warning('Aucune vidéo analysée : vérifiez les erreurs de téléchargement ci-dessus.')
                elif diagnostic and not diagnostic['paires_candidates']:
                    st.info('Aucun candidat visuel trouvé dans les images échantillonnées. Cela ne prouve pas que les vidéos sont différentes.')
                else:
                    st.info('Des candidats ont été examinés, sans séquence commune confirmée. Le diagnostic indique les étapes de rejet.')
            st.subheader("Scènes et contenus similaires")
            st.caption("Proximité visuelle calculée par CLIP, même sans séquence commune. Le score cosinus n'est pas une probabilité ; il ne confirme ni un même événement, ni un même lieu. Les paroles ne sont pas comparées.")
            similaires=donnees.get('similarites_semantiques',[])
            if similaires:
                st.dataframe([{"TikTok A":c['a'],"URL A":c.get('url_a'),"Média A":c.get('media_a'),
                               "TikTok B":c['b'],"URL B":c.get('url_b'),"Média B":c.get('media_b'),
                               "Similarité visuelle (cosinus)":round(c['score_cosinus'],3)} for c in similaires],
                             hide_index=True)
            semantique=diagnostic.get('semantique',{})
            statuts=semantique.get('statuts',{})
            if not semantique.get('activee'):
                st.info("Cochez « Comparer aussi le contenu global avec CLIP » puis lancez l'analyse.")
            elif sum(n for statut,n in statuts.items() if statut!='mesure'):
                st.warning("Comparaison de contenu incomplète : certains modèles ou dépendances sont indisponibles. Vérifiez le diagnostic et l'autorisation de téléchargement des modèles.")
            elif not similaires:
                st.info("Aucune proximité de contenu au-dessus du seuil parmi les candidats examinés. Cela ne prouve pas que les sujets sont différents.")
            if not actuel.get('video_busy'):
                st.link_button("Exporter les résultats (CSV, JSON, IRaMuTeQ dans le ZIP)",f"/api/jobs/{tache['id']}/archive")
        afficher_similarites()


with onglet_desordre:
    st.subheader("Désordre visuel et engagement")
    st.caption("Mesurer l’agitation visuelle des vidéos (mouvements, instabilité et irrégularité) et explorer ses liens avec l’engagement sur TikTok.")
    tache_desordre=st.session_state.get('collecte') or {}
    if not tache_desordre.get('archive_prete'):
        st.info("Effectuez une collecte enrichie pour utiliser cette analyse.")
    else:
        st.caption("Les résultats et annotations peuvent être conservés dans votre historique privé "
                   "pendant 30 jours, sans dupliquer les fichiers MP4.")
        if st.button("Enregistrer cette analyse (30 jours)",
                     key=f"sauvegarder_desordre_{tache_desordre['id']}",
                     disabled=bool(tache_desordre.get('busy') or tache_desordre.get('video_busy'))):
            try:
                confirmation_analyse=api(
                    f"/api/jobs/{tache_desordre['id']}/desordre/sauvegarder",{}
                )
                if confirmation_analyse.get("ok"):
                    st.success("Analyse et codages enregistrés dans l'historique privé.")
                else:
                    st.error("L'archive n'a pas été confirmée par le serveur.")
            except RuntimeError as erreur:
                st.error("Enregistrement de l'analyse impossible : " + str(erreur))
        # Ne pas rafraîchir automatiquement le formulaire d'annotation une fois
        # l'analyse terminée : l'édition des cellules doit rester stable.
        @st.fragment(run_every='3s' if tache_desordre.get('video_busy') or tache_desordre.get('busy') else None)
        def afficher_desordre():
            try:
                actuel=api(f"/api/jobs/{tache_desordre['id']}")
                donnees=api(f"/api/jobs/{tache_desordre['id']}/desordre")
            except RuntimeError as erreur:
                st.error(str(erreur));return
            if (bool(actuel.get('video_busy')) != bool(tache_desordre.get('video_busy')) or
                    bool(actuel.get('busy')) != bool(tache_desordre.get('busy'))):
                st.session_state['collecte'] = actuel
                st.rerun()
            etat=donnees.get('etat',{})
            en_cours=etat.get('statut')=='en_cours' and actuel.get('video_busy',False)
            st.write(f"{donnees.get('publications_collectees',0)} publication(s) collectée(s) · {donnees.get('mp4_locaux',0)} MP4 présent(s) · {donnees.get('mp4_manquants',0)} MP4 manquant(s).")
            if not donnees.get('disponible'):
                st.warning("Le serveur doit être redéployé avec les dépendances de cette analyse (INSTALL_VIDEO=base, semantique ou 1).")
            elif not donnees.get('mp4_locaux') and not donnees.get('mp4_telechargeables'):
                st.warning("Aucun MP4 associé ni URL TikTok exploitable dans cette collecte. Consultez les publications collectées.")
            telecharger=st.checkbox("Télécharger les MP4 manquants avant l’analyse",value=True,key='desordre_telecharger',
                help="Les MP4 déjà présents sont réutilisés. Les échecs TikTok seront indiqués par publication.")
            activation=st.checkbox("Activer l’analyse du désordre visuel",key='activer_desordre',value=False)
            with st.expander("Paramètres de cette analyse"):
                frequence=st.number_input("Images analysées par seconde",min_value=1.,max_value=60.,value=10.,step=1.,key='frequence_desordre')
                duree=st.number_input("Durée maximale par vidéo (secondes)",min_value=1.,max_value=3600.,value=10.,step=5.,key='duree_desordre',
                    help="Cette valeur limite la portion analysée, et non la durée totale autorisée d’une vidéo TikTok. "
                         "Avec 10 s : une vidéo de 6 s est analysée entièrement ; pour une vidéo de 2 min, "
                         "seules les 10 premières secondes sont étudiées. À 10 images/s, cela représente environ "
                         "100 images pour une vidéo d’au moins 10 s. Les boutons +/− ajustent la durée par pas de 5 secondes "
                         "(par exemple 10, 15 ou 20 s). Conséquence méthodologique : les indicateurs "
                         "d’une vidéo longue décrivent uniquement son début, tandis que les vidéos courtes sont "
                         "analysées entièrement. Pour étudier une portion plus longue, augmentez cette limite "
                         "(jusqu’à 3 600 s).")
            indisponible=not activation or not donnees.get('disponible') or not (donnees.get('mp4_locaux') or (telecharger and donnees.get('mp4_telechargeables'))) or actuel.get('busy') or actuel.get('video_busy')
            if st.button("Lancer l’analyse du désordre",disabled=bool(indisponible),key='lancer_desordre'):
                lancer(f"/api/jobs/{tache_desordre['id']}/desordre",{'frequence':frequence,'duree_max':duree,'telecharger_manquants':telecharger})
            if en_cours:
                st.progress(min(1.,etat.get('terminees',0)/max(1,etat.get('total',0))))
                st.write(etat.get('etape','Calcul en cours'))
                if st.button("Arrêter l’analyse du désordre",key='arreter_desordre'):
                    lancer(f"/api/jobs/{tache_desordre['id']}/video/stop",{})
            elif etat.get('statut') in ('echec','interrompu'):
                st.warning(etat.get('erreur') or etat.get('etape','Analyse interrompue'))
            elif etat.get('statut')=='partiel':
                st.warning("Résultats partiels : consultez les statuts et la couverture de chaque vidéo.")
            if etat.get('erreurs_telechargement'):
                st.warning("MP4 exclus du lot : détail des échecs de téléchargement ci-dessous.")
                st.dataframe(etat['erreurs_telechargement'],hide_index=True)
            resultats=donnees.get('indicateurs',[])
            absentes=donnees.get('sans_resultat',[])
            lignes=resultats+absentes
            if absentes and etat.get('statut') in ('termine','partiel','echec','interrompu'):
                st.warning(f"Analyse incomplète : {len(absentes)} publication(s) du corpus n’ont aucun résultat enregistré. Consultez les lignes sans résultat et relancez l’analyse pour les traiter.")
            personnalises=donnees.get("codages_personnalises") or {"variables":[],"valeurs":{}}
            variables_personnalisees=personnalises.get("variables") or []
            valeurs_personnalisees=personnalises.get("valeurs") or {}
            traitement_termine=not actuel.get("busy") and not actuel.get("video_busy")
            with st.expander("Variables de codage personnalisées",expanded=not variables_personnalisees):
                st.caption("Créez jusqu'à 20 variables binaires (ex. Symbole de l'État, Présence policière). "
                           "Le nom reste modifiable ; les valeurs enregistrées restent associées aux mêmes vidéos.")
                with st.form(f"desordre_creer_variable_{tache_desordre['id']}"):
                    nom_creation=st.text_input(
                        "Nom de la nouvelle variable",
                        placeholder="Ex. Symbole de l'État",
                        max_chars=70,
                    )
                    creer=st.form_submit_button(
                        "Ajouter une colonne au tableau",
                        disabled=not traitement_termine or len(variables_personnalisees)>=20,
                    )
                if creer:
                    try:
                        reponse=api(f"/api/jobs/{tache_desordre['id']}/desordre/variables",
                                    {"nom":nom_creation})
                        if not reponse.get("ok"):
                            raise RuntimeError("La variable n'a pas été créée.")
                        st.session_state['desordre_confirmation_variable']="Variable créée."
                        st.rerun()
                    except RuntimeError as erreur:
                        st.error("Création impossible : "+str(erreur))
                if variables_personnalisees:
                    with st.form(f"desordre_renommer_variable_{tache_desordre['id']}"):
                        choix_variable=st.selectbox(
                            "Variable à renommer",
                            [v["id"] for v in variables_personnalisees],
                            format_func=lambda identifiant:next(
                                (v["nom"] for v in variables_personnalisees if v["id"]==identifiant),
                                identifiant),
                        )
                        nom_courant=next(
                            v["nom"] for v in variables_personnalisees if v["id"]==choix_variable
                        )
                        nouveau_nom=st.text_input(
                            "Nouveau nom",value=nom_courant,max_chars=70,
                            key=f"desordre_renommer_nom_{tache_desordre['id']}_{choix_variable}",
                        )
                        renommer=st.form_submit_button("Renommer la variable",disabled=not traitement_termine)
                    if renommer:
                        try:
                            reponse=api(
                                f"/api/jobs/{tache_desordre['id']}/desordre/variables/{choix_variable}/renommer",
                                {"nom":nouveau_nom},
                            )
                            if not reponse.get("ok"):
                                raise RuntimeError("Le nom de la variable n'a pas été enregistré.")
                            st.session_state['desordre_confirmation_variable']="Variable renommée ; codages conservés."
                            st.rerun()
                        except RuntimeError as erreur:
                            st.error("Renommage impossible : "+str(erreur))
                confirmation_variable=st.session_state.pop('desordre_confirmation_variable',None)
                if confirmation_variable: st.success(confirmation_variable)
                st.link_button(
                    "Exporter les variables et leurs annotations (CSV)",
                    f"/api/jobs/{tache_desordre['id']}/desordre/codages.csv",
                )
            if not lignes:
                st.info("Les colonnes créées seront éditables dès que le tableau d'analyse sera disponible.")
                return
            total_collecte=max(donnees.get('publications_collectees',0),len(lignes))
            st.caption(f"{len(resultats)} publication(s) avec un résultat enregistré sur {total_collecte} · {max(0,total_collecte-len(resultats))} sans résultat enregistré. Un résultat peut lui-même signaler une erreur.")
            if etat.get('statut') not in ('termine','partiel'):
                st.info('Résultats intermédiaires sauvegardés : les vidéos déjà traitées restent consultables, même si le lot est encore en cours ou a été interrompu.')
            import pandas as pd
            from analyse_desordre.presentation import AIDE_INDICE, AIDES_INDICATEURS, AIDE_SPEARMAN, AIDES_STATISTIQUES, AIDES_COLONNES, preparer_graphique, superposer_droite_regression, formater_nombre
            tableau=pd.DataFrame(lignes)
            # Les identifiants restent des chaînes, même au-delà de 15 chiffres.
            tableau['publication_id']=tableau['publication_id'].astype(str)
            tableau.insert(0,'numero_video',range(1,len(tableau)+1))
            st.markdown("**Qu’est-ce que l’indice de désordre visuel ?**",help=AIDE_INDICE)
            st.caption("Indice exploratoire de 0 à 100 — ce n’est pas un pourcentage.")
            # Une seule grille : menus déroulants directement dans la colonne
            # de chaque vidéo ; toutes les mesures automatiques restent protégées.
            from analyse_desordre.annotation import modifications_depuis_tableau
            from analyse_desordre.codages_personnalises import modifications_depuis_tableau as modifications_personnalisees
            options_violence=('Non évaluée','Non (0)','Oui (1)')
            etiquette_violence={None:'Non évaluée',0:'Non (0)',1:'Oui (1)'}
            tableau_editable=tableau.copy()
            tableau_editable.insert(1,'annotation_violence',[
                etiquette_violence.get(
                    None if pd.isna(valeur) else int(valeur),'Non évaluée')
                for valeur in tableau['violence_visible']
            ])
            for position, variable in enumerate(variables_personnalisees,2):
                valeurs=valeurs_personnalisees.get(variable["id"]) or {}
                tableau_editable.insert(position,variable["id"],[
                    etiquette_violence.get(valeurs.get(identifiant),"Non évaluée")
                    for identifiant in tableau_editable['publication_id']
                ])
            colonnes_visibles=[nom for nom in tableau_editable.columns
                              if nom!='violence_visible']
            colonnes_annotations={"annotation_violence",*[v["id"] for v in variables_personnalisees]}
            etat_finalise=etat.get('statut') in ('termine','partiel')
            st.caption("Annotez directement les colonnes « Violence physique visible » et vos variables personnalisées. "
                       "Choisissez Non évaluée, Non (0) ou Oui (1), puis enregistrez. "
                       "Non évaluée reste une valeur manquante, jamais un zéro.")
            # Un formulaire empêche chaque sélection de provoquer un rerun
            # de Streamlit et de remettre la colonne à « Non évaluée ».
            # Les cellules et la ligne restent affichées jusqu'à la sauvegarde.
            with st.form(f"desordre_annotations_{tache_desordre['id']}",clear_on_submit=False):
                tableau_modifie=st.data_editor(
                    tableau_editable,hide_index=True,use_container_width=True,num_rows='fixed',
                    disabled=[nom for nom in tableau_editable.columns if nom not in colonnes_annotations]
                             if etat_finalise else True,
                    column_order=colonnes_visibles,
                    column_config={
                        **{v["id"]:st.column_config.SelectboxColumn(
                            v["nom"],options=list(options_violence),required=True,width="medium",
                            help="Codage manuel : Non évaluée (manquant), Non (0), Oui (1).")
                           for v in variables_personnalisees},
                        **{nom:st.column_config.Column(help=aide)
                           for nom,aide in AIDES_COLONNES.items() if nom in tableau_editable},
                        'numero_video':st.column_config.NumberColumn('N° vidéo',format='%d',
                            help='Numéro de repérage dans cette analyse, repris dans les infobulles du graphique.'),
                        'publication_id':st.column_config.TextColumn('ID TikTok'),
                        'annotation_violence':st.column_config.SelectboxColumn(
                            'Violence physique visible',options=list(options_violence),
                            required=True,help=AIDES_INDICATEURS['violence_visible'],width='medium'),
                        'indice_desordre':st.column_config.NumberColumn('Indice de désordre (0–100)',help=AIDE_INDICE),
                        'vitesse_residuelle':st.column_config.NumberColumn('Vitesse des sujets en mouvements',
                            help=AIDES_INDICATEURS['vitesse_residuelle']),
                        'url':st.column_config.LinkColumn('URL TikTok',help=AIDES_COLONNES['url'])
                    },
                    key=f"desordre_editeur_principal_{tache_desordre['id']}_{donnees.get('annotation_version','0')}"
                )
                bouton_enregistrement=st.form_submit_button(
                    "Enregistrer les annotations",disabled=not etat_finalise)
            if bouton_enregistrement:
                try:
                    changements_violence=modifications_depuis_tableau(
                        tableau_editable,tableau_modifie,colonne='annotation_violence')
                    changements_personnalises=modifications_personnalisees(
                        tableau_editable,tableau_modifie,variables_personnalisees)
                    if changements_violence:
                        retour=api(f"/api/jobs/{tache_desordre['id']}/desordre/annotations",
                                   {'annotations':changements_violence})
                        if not retour.get("ok"):
                            raise RuntimeError("Le serveur n'a pas confirmé le codage de violence.")
                    if changements_personnalises:
                        retour=api(f"/api/jobs/{tache_desordre['id']}/desordre/codages",
                                   {'annotations':changements_personnalises})
                        if not retour.get("ok"):
                            raise RuntimeError("Le serveur n'a pas confirmé les codages personnalisés.")
                    if changements_violence or changements_personnalises:
                        nouvelles_donnees=api(f"/api/jobs/{tache_desordre['id']}/desordre")
                        confirmees={
                            str(ligne['publication_id']):ligne.get('violence_visible')
                            for ligne in nouvelles_donnees.get('indicateurs',[])+
                                         nouvelles_donnees.get('sans_resultat',[])
                        }
                        if any(confirmees.get(ch['publication_id'],'absent') !=
                               ch['violence_visible'] for ch in changements_violence):
                            raise RuntimeError("La relecture ne confirme pas les annotations de violence.")
                        nouveaux_codages=(nouvelles_donnees.get("codages_personnalises") or {}).get("valeurs",{})
                        if any(nouveaux_codages.get(ch["variable_id"],{}).get(ch["publication_id"]) != ch["valeur"]
                               for ch in changements_personnalises):
                            raise RuntimeError("La relecture ne confirme pas les codages personnalisés.")
                        st.session_state['desordre_dernier_enregistrement']=(
                            tache_desordre['id'],len(changements_violence)+len(changements_personnalises))
                        st.rerun()
                    else:
                        st.info("Aucune annotation modifiée.")
                except (RuntimeError,ValueError) as erreur:
                    st.error("Enregistrement impossible : "+str(erreur))
            confirmation=st.session_state.pop('desordre_dernier_enregistrement',None)
            if confirmation and confirmation[0]==tache_desordre['id']:
                st.success(f"{confirmation[1]} annotation(s) enregistrée(s).")
            effectif_ann=donnees.get('annotations_violence',{})
            st.caption(f"Annotations sauvegardées : {effectif_ann.get('oui',0)} oui · "
                       f"{effectif_ann.get('non',0)} non · "
                       f"{effectif_ann.get('non_evaluees',len(tableau))} non évaluées.")
            st.link_button("Exporter les annotations (CSV)",
                f"/api/jobs/{tache_desordre['id']}/desordre/annotations.csv")
            st.subheader("Croiser les variables")
            indicateurs={'indice_desordre':'Indice de désordre visuel (0–100)','instabilite_camera':'Instabilité de la caméra (diagonales/s²)',
                'entropie_directionnelle':'Entropie directionnelle (0–1)','irregularite_temporelle':'Irrégularité temporelle (0–1)',
                'vitesse_residuelle':'Vitesse des sujets en mouvements (diagonales/s)',
                'violence_visible':'Violence physique visible — codage manuel (0/1)'}
            engagements={'likes':'Nombre de likes','commentaires':'Nombre de commentaires','partages':'Nombre de partages','favoris':'Nombre de favoris','vues':'Nombre de vues',
                'likes_pour_1000_vues':'Likes pour 1 000 vues','commentaires_pour_1000_vues':'Commentaires pour 1 000 vues','partages_pour_1000_vues':'Partages pour 1 000 vues'}
            axe_x=st.selectbox("Indicateur visuel (axe horizontal)",list(indicateurs),format_func=indicateurs.get,key='desordre_x',help='Choisissez un indicateur automatique ou le codage manuel de violence. Sa définition et son unité sont disponibles dans l’aide « Comprendre l’indicateur choisi » ci-dessous.')
            autres_mesures={cle:nom for cle,nom in indicateurs.items() if cle!='violence_visible'} if axe_x=='violence_visible' else {}
            variables_verticales={**engagements, **autres_mesures}
            # Une nouvelle option ne doit pas rendre invalide une ancienne sélection Streamlit.
            if st.session_state.get('desordre_y') not in variables_verticales:
                st.session_state['desordre_y']='likes'
            axe_y=st.selectbox("Variable à croiser (axe vertical)",list(variables_verticales),format_func=variables_verticales.get,key='desordre_y',help='Choisissez un compteur, un taux pour 1 000 vues, ou, avec le codage manuel, un indicateur automatique.')
            st.markdown('**Comprendre la variable choisie**',
                help=AIDES_COLONNES[axe_y] if axe_y in AIDES_COLONNES else AIDES_INDICATEURS[axe_y])
            if axe_y in engagements:
                st.caption("Les nombres bruts dépendent notamment de l’audience. Les taux pour 1 000 vues permettent aussi une comparaison rapportée à l’exposition.")
            else:
                st.caption("Comparer les deux groupes (violence oui/non) sur les valeurs de l’indicateur visuel automatique.")
            afficher_droite=st.checkbox("Afficher la droite de régression linéaire",
                value=False, key="desordre_droite_regression",
                help="Ajoute une droite de tendance en pointillés au nuage de points, quand au moins "
                     "trois vidéos ont deux mesures valides et qu'aucune variable n'est constante. "
                     "Elle représente une régression linéaire (moindres carrés) sur les valeurs brutes, "
                     "pas le coefficient de Spearman (ρ), qui compare les rangs. "
                     "Une droite ne prouve pas une causalité et peut être sensible aux valeurs extrêmes.")
            if axe_x not in tableau or axe_y not in tableau:
                st.info("Variable absente de ces anciens résultats : relancez l’analyse.")
            else:
                st.markdown("**Comprendre l’indicateur choisi**",help=AIDES_INDICATEURS[axe_x])
                points,specification,effectifs=preparer_graphique(tableau,axe_x,axe_y,indicateurs[axe_x],variables_verticales[axe_y])
                st.caption(f"{effectifs['videos']} vidéo(s) représentée(s) sur {total_collecte} publications collectées · {max(0,total_collecte-len(resultats))} sans résultat · {max(0,effectifs['exclues']-len(absentes))} résultat(s) sans les deux mesures valides · {effectifs['positions']} position(s) distincte(s). Un point = une vidéo ; des points très proches peuvent aussi se masquer visuellement.")
                if effectifs['superposees']:
                    st.info(f"{effectifs['superposees']} vidéos partagent exactement des coordonnées avec d’autres : leurs points se superposent. Survolez pour retrouver leurs numéros dans le tableau.")
                if afficher_droite:
                    if axe_x=='violence_visible':
                        st.info("Droite non affichée pour le codage binaire 0/1 : comparez directement les deux groupes de vidéos.")
                    else:
                        specification, raison_droite = superposer_droite_regression(points, specification)
                        if raison_droite:
                            st.info("Droite non disponible : " + raison_droite)
                        else:
                            st.caption("Droite en pointillés : régression linéaire descriptive sur les valeurs brutes, distincte de la corrélation de Spearman. Elle ne démontre pas de causalité.")
                if points.empty: st.info("Aucune publication ne possède les deux mesures nécessaires.")
                else:
                    st.vega_lite_chart(points,specification,use_container_width=True)
                    st.caption(f"Axe vertical : {variables_verticales[axe_y]}. Les espaces séparent les milliers : 1 600 000 = un million six cent mille. Survolez un point pour voir son numéro, son identifiant et ses valeurs.")
                correlation=next((r for r in donnees.get('correlations',[]) if r['indicateur']==axe_x and r['engagement']==axe_y),None)
                if correlation and correlation.get('rho') is not None:
                    st.markdown("**Corrélation de Spearman**",help=AIDE_SPEARMAN)
                    for colonne,cle,libelle,decimales in zip(st.columns(4),('rho','n','p','p_ajustee_bh'),
                            ('ρ — Spearman','Vidéos comparées','p-value','p-value ajustée'),(3,0,6,6)):
                        colonne.metric(libelle,formater_nombre(correlation.get(cle),decimales),help=AIDES_STATISTIQUES[cle])
                elif axe_x=='violence_visible':
                    st.info("Pour le codage de violence, évaluez plusieurs vidéos dans les deux catégories (0 et 1).")
            with st.expander("Toutes les corrélations"):
                st.dataframe([{cle:('Vitesse des sujets en mouvements' if cle=='indicateur' and valeur=='vitesse_residuelle' else valeur) for cle,valeur in ligne.items() if cle != 'permutations'}
                              for ligne in donnees.get('correlations',[])],hide_index=True,
                    column_config={nom:st.column_config.Column(help=aide) for nom,aide in AIDES_STATISTIQUES.items()})
            st.caption("Les valeurs manquantes restent absentes ; elles ne sont pas remplacées par zéro. "
                       "Les corrélations avec la violence sont exploratoires et calculées uniquement "
                       "sur les annotations enregistrées, avec correction séparée pour les treize comparaisons possibles.")
            if etat.get('statut') in ('termine','partiel'):
                st.link_button("Corrélations avec violence (CSV)",
                    f"/api/jobs/{tache_desordre['id']}/desordre/correlations_violence.csv")
            st.link_button("Exporter le tableau complet (CSV réimportable)",
                f"/api/jobs/{tache_desordre['id']}/desordre/tableau-complet.csv",
                help="URL TikTok, indice de désordre, mouvements, engagement, "
                     "violence, variables personnalisées et provenance du lot.")
            for nom,libelle in [('indicateurs_engagement.csv','Indicateurs et engagements CSV'),('mesures_temporelles.csv','Mesures temporelles CSV'),('correlations_spearman.csv','Corrélations CSV')]:
                if etat.get('statut') in ('termine','partiel') or nom=='indicateurs_engagement.csv':
                    st.link_button(libelle,f"/api/jobs/{tache_desordre['id']}/desordre/export/{nom}")
        afficher_desordre()


with onglet_corpus:
    st.subheader("Fusionner plusieurs analyses de Désordre visuel")
    st.caption("Importez les CSV « Tableau complet » des collectes ou des archives "
               "de l'historique. Toutes les URLs, mesures, annotations et provenances "
               "sont conservées. Aucune vidéo n'est téléchargée.")
    st.info("La fusion permet de recalculer les comparaisons statistiques. "
            "L'indice de désordre et les mesures de mouvement ne sont pas recalculés : "
            "ils proviennent des MP4 examinés dans chaque analyse d'origine.")
    fichiers_corpus = st.file_uploader(
        "Importer les tableaux complets CSV (20 fichiers maximum, 10 Mo chacun)",
        type=["csv"], accept_multiple_files=True, key="fichiers_corpus_fusion",
    )
    choix_doublons = st.radio(
        "Si le même ID TikTok apparaît dans plusieurs tableaux",
        ("premier", "dernier"), horizontal=True,
        format_func=lambda v: {"premier":"Conserver le premier",
                                "dernier":"Conserver le dernier"}[v],
        key="choix_doublons_corpus",
        help="Une même vidéo compte une seule fois dans les effectifs et corrélations.")
    if fichiers_corpus:
        from analyse_desordre.corpus_fusion import fusionner_tableaux
        try:
            fusion = fusionner_tableaux([
                (fichier.name, fichier.getvalue()) for fichier in fichiers_corpus
            ], priorite=choix_doublons)
        except ValueError as erreur:
            st.error("Import impossible : " + str(erreur))
        else:
            c1,c2,c3 = st.columns(3)
            c1.metric("Publications uniques",fusion["nombre_unique"])
            c2.metric("Lignes importées",fusion["total_initial"])
            c3.metric("Doublons écartés",fusion["doublons"])
            if fusion["doublons_divergents"]:
                st.warning(
                    f"{fusion['doublons_divergents']} doublon(s) présentent des "
                    "valeurs différentes entre les lots. Le choix de priorité "
                    "ci-dessus détermine quelles valeurs sont conservées."
                )
            st.download_button(
                "Télécharger le corpus fusionné (CSV)",
                fusion["csv"].encode("utf-8"),
                file_name="scraptiktok_corpus_fusionne.csv", mime="text/csv",
            )
            import pandas as pd
            tableau_fusionne = pd.DataFrame(fusion["lignes"])
            st.dataframe(
                tableau_fusionne, hide_index=True, use_container_width=True,
                column_config={
                    "publication_id":st.column_config.TextColumn("ID TikTok"),
                    "url":st.column_config.LinkColumn("URL TikTok"),
                }
            )
            exclues = {
                "publication_id","url","analyse_source","statut","erreur",
                "metadonnees_presentes","parametres_frequence",
                "parametres_dimension","parametres_duree_max",
            }
            numeriques = {}
            for nom in tableau_fusionne.columns:
                if nom in exclues:
                    continue
                valeurs = pd.to_numeric(
                    tableau_fusionne[nom].replace("",None),errors="coerce")
                if valeurs.notna().sum() >= 3:
                    numeriques[nom] = valeurs
            if len(numeriques) >= 2:
                st.subheader("Nouvelles comparaisons statistiques")
                choix_x = st.selectbox("Variable horizontale",list(numeriques),
                    index=list(numeriques).index("indice_desordre")
                    if "indice_desordre" in numeriques else 0,
                    key="comparaison_corpus_x")
                variables_y = [cle for cle in numeriques if cle != choix_x]
                choix_y = st.selectbox("Variable verticale",variables_y,
                    index=variables_y.index("likes") if "likes" in variables_y else 0,
                    key="comparaison_corpus_y")
                observations = pd.DataFrame({
                    "publication_id":tableau_fusionne["publication_id"].astype(str),
                    choix_x:numeriques[choix_x],
                    choix_y:numeriques[choix_y],
                }).dropna(subset=[choix_x,choix_y])
                st.caption(f"{len(observations)} vidéo(s) avec deux mesures valides "
                           f"sur {len(tableau_fusionne)} publications uniques. "
                           "Les valeurs manquantes ne sont jamais remplacées par zéro.")
                if not observations.empty:
                    st.scatter_chart(observations.head(3000),x=choix_x,y=choix_y)
                    if len(observations)>3000:
                        st.caption("Le graphique affiche 3 000 observations au maximum ; "
                                   "les statistiques utilisent les données complètes.")
                if st.button("Calculer Spearman sur le corpus fusionné",
                             key="calcul_spearman_corpus"):
                    if len(observations)<3:
                        st.warning("Au moins trois vidéos sont nécessaires.")
                    else:
                        try:
                            if len(observations)<=2000:
                                from analyse_desordre.statistiques import correlation_spearman
                                statistique = correlation_spearman(
                                    observations[choix_x],observations[choix_y],
                                    permutations=999,graine=42)
                            else:
                                from scipy.stats import spearmanr
                                import math
                                mesure = spearmanr(observations[choix_x],
                                                  observations[choix_y])
                                rho,p = float(mesure.statistic),float(mesure.pvalue)
                                statistique = {"n":len(observations),
                                    "rho":rho if math.isfinite(rho) else None,
                                    "p":p if math.isfinite(p) else None,
                                    "methode":"approximation_asymptotique"}
                            st.write({
                                "n":statistique["n"],
                                "ρ Spearman":statistique["rho"],
                                "p-value":statistique["p"],
                                "Méthode":statistique["methode"],
                            })
                            st.caption("Analyse exploratoire : p-value bilatérale "
                                       "non corrigée pour les comparaisons multiples. "
                                       "Vérifiez l'homogénéité des lots et des paramètres d'analyse.")
                        except ImportError:
                            st.warning("SciPy est requis pour le calcul de la corrélation.")
            elif len(tableau_fusionne):
                st.info("Choisissez des tableaux possédant au moins deux variables "
                        "avec trois mesures numériques valides.")
