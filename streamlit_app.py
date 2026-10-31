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
st.caption("Appli en cours de dév - modifiée 27-10-2026")

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
    if "id" in resultat:
        st.session_state["collecte"] = resultat
        if chemin == "/api/jobs" and donnees.get("cookies_tiktok"):
            st.session_state["_effacer_cookies_apres_requete"] = True
        if chemin == "/api/jobs" and donnees.get("presse_moteur") == "research":
            # Effacer les champs sensibles avant le prochain affichage,
            # sans écraser un widget déjà instancié pendant cette exécution.
            st.session_state["_effacer_research_apres_requete"] = True
        if chemin == "/api/jobs" and donnees.get("presse_moteur") == "tikhub":
            st.session_state["_effacer_tikhub_apres_requete"] = True
        if chemin == "/api/jobs" and donnees.get("presse_moteur") == "apify":
            st.session_state["_effacer_apify_apres_requete"] = True
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

    # Préserver les collectes enrichies terminées (notamment Presse et médias)
    # pour les exploiter dans Multimodale après rechargement de l'interface.
    if ancienne and not (
        ancienne.get("busy", False)
        or ancienne.get("video_busy", False)
        or ancienne.get("archive_prete", False)
    ):
        ancienne = None

    st.session_state["collecte"] = ancienne
    ancienne = ancienne or {}

    valeurs = {"source":ancienne.get("source_collecte","hashtags"), "hashtag":ancienne.get("hashtag",""),
        "second_hashtag":ancienne.get("second_hashtag",""), "operator":ancienne.get("operator","AND"),
        "croiser_hashtag_presse":ancienne.get("croiser_hashtag_presse",False),
        "hashtag_presse":ancienne.get("hashtag_presse",""),
        "rechercher_dans_texte": ancienne.get("rechercher_dans_texte", True),
        "variantes_accents": ancienne.get("variantes_accents", False),
        "comptes":", ".join(ancienne.get("comptes",[])), "medias":ancienne.get("medias",[]),
        "limit":ancienne.get("limit",50), "french_only":ancienne.get("french_only",True),
        "include_sources":ancienne.get("include_sources",True),
        "sauvegarde_progressive":ancienne.get("sauvegarde_progressive",False),
        "inclure_texte_genere_ia":ancienne.get("inclure_texte_genere_ia",False),
        "export_profil_sans_arobase":ancienne.get("supprimer_arobase_profil",True),
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
st.session_state.setdefault("croiser_hashtag_presse", False)
st.session_state.setdefault("hashtag_presse", "")
if st.session_state.pop("_effacer_cookies_apres_requete", False):
    st.session_state.pop("cookies_presse_fichier", None)
if st.session_state.pop("_effacer_research_apres_requete", False):
    st.session_state.pop("research_client_key", None)
    st.session_state.pop("research_client_secret", None)
if st.session_state.pop("_effacer_tikhub_apres_requete", False):
    st.session_state.pop("tikhub_api_key", None)
if st.session_state.pop("_effacer_apify_apres_requete", False):
    st.session_state.pop("apify_api_token", None)

# Conserver les filtres de chaque mode même quand leurs champs ne sont pas affichés.
for variable in VARIABLES_TXT:
    # Initialiser seulement si absent : préserver les choix manuels déjà faits.
    st.session_state.setdefault("txt_" + variable, variable != "hashtags")
    st.session_state["txt_" + variable] = st.session_state["txt_" + variable]
# Quand le mode Médias masque la radio ET/OU, Streamlit peut supprimer sa
# clé du session_state à la fin d'une exécution. Le formulaire médias doit
# rester lançable sans ce widget.
st.session_state.setdefault("operator", "AND")
st.session_state.setdefault("rechercher_dans_texte", True)
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
    st.subheader("Sauvegardes : collecte et analyse")
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
            st.caption(f"Deux sauvegardes distinctes conservées {duree_historique} jours : "
                       "données de collecte réimportables et résultats d'analyse, sans MP4.")
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
                    "Retrouver une collecte et son analyse",
                    list(index_analyses),
                    format_func=afficher_entree_historique,
                    key="choix_historique_scraptiktok",
                )
                entree = index_analyses[choix_historique]
                st.caption("Statut : " + entree.get("statut","indéterminé"))
                if st.button("Rouvrir la collecte et l’analyse",key="ouvrir_historique_scraptiktok",
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
                    "Sauvegarde 1 — Collecte (ZIP réimportable)",
                    f"/api/historique/{choix_historique}/sauvegarde/collecte",
                    use_container_width=True,
                )
                st.link_button(
                    "Sauvegarde 2 — Résultats de l'analyse (ZIP)",
                    f"/api/historique/{choix_historique}/sauvegarde/analyse",
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
onglet_collecte, onglet_multimodale, onglet_corpus, onglet_aide = st.tabs(
    ["Collecte", "Annotation/analyse", "Corpus fusionné", "Aide"]
)

with onglet_collecte:
    api_tiktok_suspendue = False
    source = st.radio("Rechercher par", ["hashtags","presse","comptes"], key="source", horizontal=True,
        format_func=lambda s:{"hashtags":"Hashtags","presse":"Presse et médias","comptes":"Autres comptes TikTok"}[s], disabled=occupe)
    if source == "presse":
        if st.session_state.get("presse_moteur") == "playwright":
            st.session_state["presse_moteur"] = "gallerydl"
        st.radio("Moteur de découverte Presse (une seule méthode par collecte)",
            ["api", "research", "navigateur", "gallerydl", "tikhub", "apify"],key="presse_moteur",horizontal=True,disabled=occupe,
            format_func=lambda v: {"api":"API web TikTok (secUid)", "research":"Research API officielle",
                                   "navigateur":"Méthode Selenium", "gallerydl":"Méthode gallery-dl",
                                   "tikhub":"Méthode TikHub (API) (payant)", "apify":"Méthode Apify (API) (payant)"}[v],
            help="L'API web TikTok n'est pas la Research API officielle. Elle peut renvoyer HTTP 429 "
                 "même lorsque la collecte par hashtags fonctionne. Le navigateur inspecte le profil "
                 "du média et son onglet Vidéos. Aucun basculement automatique n'est effectué après un refus.")
        if st.session_state.get("presse_moteur") == "research":
            st.text_input("TIKTOK_RESEARCH_CLIENT_KEY", key="research_client_key",
                          type="password", disabled=occupe,
                          help="Client key de l'application TikTok Research approuvée.")
            st.text_input("TIKTOK_RESEARCH_CLIENT_SECRET", key="research_client_secret",
                          type="password", disabled=occupe,
                          help="Client secret Research : masqué à l'écran et non enregistré dans les exports.")
        if st.session_state.get("presse_moteur") == "tikhub":
            st.text_input("Clé API TikHub", key="tikhub_api_key", type="password",
                          disabled=occupe,
                          help="Clé personnelle TikHub ; elle reste en mémoire uniquement pendant la collecte. "
                               "La variable Coolify TIKHUB_API_KEY peut également fournir la clé.")
            st.caption("Méthode payante : TikHub facture ses requêtes. "
                       "Profil + pages de publications (15 par page), puis une requête "
                       "supplémentaire par vidéo si « Texte généré par IA » est coché.")
        if st.session_state.get("presse_moteur") == "apify":
            st.text_input("Jeton API Apify", key="apify_api_token", type="password",
                          disabled=occupe,
                          help="Jeton personnel Apify. Peut aussi provenir de APIFY_API_TOKEN dans Coolify. "
                               "Il n'est jamais enregistré dans les exports.")
            st.caption("Méthode payante : l'Actor clockworks/tiktok-profile-scraper "
                       "s'exécute sur Apify. Nombre de résultats plafonné par la collecte. "
                       "Coût maximal par exécution : APIFY_MAX_CHARGE_USD (1 USD par défaut). "
                       "L'option Texte généré par IA nécessite Selenium et ne garantit pas de résumé.")
        if st.session_state.get("presse_moteur") == "navigateur":
            with st.expander("Session TikTok — cookies facultatifs"):
                st.file_uploader("Importer les cookies TikTok (.txt, format Netscape)",
                    type=["txt"], key="cookies_presse_fichier", disabled=occupe,
                    help="Utiliser un export de votre propre session TikTok. Les cookies restent "
                         "en mémoire pour cette collecte et ne figurent pas dans les résultats ou les archives.")
                st.caption("Sans fichier, la collecte utilise une session anonyme, sauf cookies configurés par l’administrateur. "
                           "Une session importée peut expirer ou nécessiter une vérification TikTok.")
        st.write("Choisir les médias à collecter")
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
        st.checkbox("Croisement avec un hashtag", key="croiser_hashtag_presse",
            disabled=occupe, help="Filtrer les publications des médias cochés avec un #hashtag exact. "
            "Le filtre s'applique après la découverte des vidéos, sans lancer une recherche générale.")
        if st.session_state.get("croiser_hashtag_presse"):
            st.text_input("Hashtag du croisement", key="hashtag_presse",
                placeholder="#manifestation", disabled=occupe,
                help="Un seul hashtag, avec ou sans #. Seules les publications portant ce hashtag "
                     "dans leur légende seront retenues pour les exports et les analyses.")
            st.caption("Croisement : comptes sélectionnés ET hashtag indiqué. "
                       "Le nombre de posts par média est une limite de lecture avant filtrage.")
        # Une seule ligne d'information Streamlit : plusieurs st.caption,
        # st.warning ou st.error consécutifs créent des espaces vides inutiles.
        # Les messages sont assemblés sans saut de paragraphe ; une alerte
        # utilise le même bloc, seulement avec une autre présentation.
        informations_presse = []
        alerte_presse = False
        if st.session_state.get("presse_moteur") == "api":
            informations_presse.append(
                "Moteur : API web Presse (distinct du navigateur Hashtags). "
                "Si HTTP 429, choisir manuellement « Méthode Selenium » "
                "pour une nouvelle collecte."
            )
        elif st.session_state.get("presse_moteur") == "research":
            informations_presse.append("Research API officielle : projet approuvé nécessaire. Les MP4 ne sont pas fournis par cette API.")
        elif st.session_state.get("presse_moteur") == "gallerydl":
            informations_presse.append("Moteur : gallery-dl (liste creator/item_list uniquement). La collecte n'ouvre pas les pages des vidéos ; les commentaires et résumés IA demandent Selenium.")
        elif st.session_state.get("presse_moteur") == "tikhub":
            informations_presse.append("Moteur : TikHub (API payante). Profils et publications via l'API ; résumés natifs TikTok itemCustomTDK lorsque l'option IA est cochée.")
        elif st.session_state.get("presse_moteur") == "apify":
            informations_presse.append("Moteur : Apify (API payante). La collecte se déroule sur Apify ; vidéos, légendes et compteurs sont réintégrés dans ScrapTikTok. Pas de téléchargement MP4 par l'Actor.")
        else:
            informations_presse.append("Moteur : Méthode Selenium.")
        if st.session_state.get("presse_moteur") != "research":
            budget_api = limites_admin.get("budget_api_presse", {})
            informations_presse.append(
                "Plafonds API Presse configurés (Coolify) : "
                + " ; ".join(
                    f"{budget_api.get(compteur, 0)}/{budget_api[maximum]} sur {periode}"
                    for compteur, maximum, periode in (
                        ("requete_minute", "maximum_minute", "1 min"),
                        ("requete_heure", "maximum_heure", "1 h"),
                        ("requete_24h", "maximum_24h", "24 h"),
                    )
                    if budget_api.get(maximum) is not None
                ) if any(budget_api.get(cle) is not None
                         for cle in ("maximum_minute", "maximum_heure", "maximum_24h"))
                else "API Presse : aucun plafond de requêtes configuré dans Coolify."
            )
            echeances = (
                ("minute", budget_api.get("reprise_locale_minute_utc")),
                ("heure", budget_api.get("reprise_locale_heure_utc")),
                ("jour UTC", budget_api.get("reprise_locale_jour_utc")),
                ("enregistrements UTC", budget_api.get("reprise_locale_enregistrements_utc")),
            )
            plafonds_epuises = [
                libelle + " : " +
                datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
                for libelle, epoch in echeances
                if isinstance(epoch, (int, float)) and epoch > 0
            ]
            if plafonds_epuises:
                alerte_presse = True
                informations_presse.append("Quotas locaux épuisés (réinitialisation) : "
                                            + " ; ".join(plafonds_epuises) + ".")
            else:
                if any(budget_api.get(cle) is not None
                       for cle in ("maximum_minute", "maximum_heure", "maximum_24h")):
                    informations_presse.append("Plafonds configurés non atteints.")
            try:
                limitation_presse = api("/api/presse/limitation")
                if limitation_presse.get("actif"):
                    api_tiktok_suspendue = st.session_state.get("presse_moteur", "api") == "api"
                    restant = limitation_presse.get("restant_secondes", 0)
                    alerte_presse = True
                    informations_presse.append(
                        f"TikTok : Retry-After actif, {restant//60} min {restant%60} s restantes."
                    )
                elif limitation_presse.get("ancien_429_sans_delai"):
                    dernier_429 = limitation_presse.get("dernier_429")
                    date_429 = (
                        datetime.fromtimestamp(dernier_429, tz=timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
                        if isinstance(dernier_429, (int, float)) and dernier_429 > 0
                        else "date inconnue"
                    )
                    informations_presse.append(
                        "Dernier HTTP 429 : " + date_429 +
                        " ; aucun Retry-After indiqué, reprise TikTok inconnue."
                    )
                else:
                    informations_presse.append("TikTok : aucun Retry-After actif.")
            except RuntimeError as erreur:
                alerte_presse = True
                informations_presse.append("État du Retry-After indisponible : " + str(erreur))
            try:
                version_presse = api("/healthz").get("version_presse")
                if version_presse:
                    informations_presse.append("Version : " + version_presse)
                else:
                    alerte_presse = True
                    informations_presse.append("Version serveur Presse absente : vérifier Coolify.")
            except RuntimeError as erreur:
                alerte_presse = True
                informations_presse.append("Version serveur indisponible : " + str(erreur))
        resume_presse = " · ".join(informations_presse)
        if alerte_presse:
            st.warning(resume_presse)
        else:
            st.caption(resume_presse)
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
                "L’option « Rechercher aussi dans le texte » est cochée par défaut : une vidéo dont la légende "
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
                         "Le nombre de vidéos demandé est global et les variantes partagent le quota du hashtag initial.")
            st.checkbox("Rechercher aussi dans le texte des légendes (en plus des hashtags)",
                key="rechercher_dans_texte", disabled=occupe,
                help="Décoché : seuls les #hashtags exacts de la légende comptent. "
                     "Coché (par défaut) : les mots entiers du texte comptent aussi, sans distinction de majuscules ou d’accents. "
                     "Par exemple, #lyceen peut correspondre à « lycéen » et #17octobre à « 17 octobre ». "
                     "Une vidéo dont la légende contient le mot correspondant est donc retenue "
                     "pour le TXT, même sans hashtag, si elle respecte la combinaison ET/OU "
                     "et les autres filtres (langue et période). "
                     "Ce choix agit après la découverte des vidéos TikTok.")
        st.number_input(
            "Nombre TOTAL de posts à lire (tous hashtags confondus)"
            if source == "hashtags" else "Nombre de posts TikTok à collecter par source",
            min_value=1, max_value=max_posts_admin, step=1, key="limit", disabled=occupe,
            help=(
                "Objectif maximal sur l'ensemble des hashtags saisis, en ET comme en OU. "
                "Le budget est partagé entre les hashtags, y compris leurs variantes. "
                "Les légendes, les langues et les dates sont filtrées après lecture."
                if source == "hashtags" else
                f"Borne technique du moteur : {max_posts_admin} posts par source. "
                "Il est vérifié aussi sur les requêtes API directes."
            ),
        )
        if source == "presse":
            nombre_medias=len(st.session_state.get("medias",[]))
            if nombre_medias:
                st.caption(
                    f"Objectif demandé : {st.session_state.get('limit',50)} vidéos "
                    f"PAR média, pour {nombre_medias} média(s) sélectionné(s) "
                    f"(jusqu'à {st.session_state.get('limit',50)*nombre_medias} vidéos au total, "
                    "si elles sont accessibles)."
                )
        if source == "comptes":
            st.caption("Les publications publiques des comptes sélectionnés sont parcourues en priorité. Les hashtags saisis sont appliqués aux légendes après découverte. La couverture du profil peut être incomplète.")
        st.checkbox("Filtre français", key="french_only", disabled=occupe,
            help="Retient uniquement les légendes reconnues en français. Les autres langues et les légendes indéterminées (trop courtes ou composées uniquement de hashtags) sont exclues du TXT. La voix et le texte incrusté dans la vidéo ne sont pas analysés.")
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
        with st.expander("Options des commentaires"):
            def respecter_choix_commentaires():
                if not st.session_state["collecter_commentaires"]: st.session_state["collecter_reponses"] = False
            st.checkbox("Inclure les réponses accessibles", key="collecter_reponses", disabled=occupe, help="Les réponses sont collectées uniquement si la collecte des commentaires est cochée.")
            st.number_input("Commentaires maximum par publication", min_value=1,
                max_value=max_commentaires_admin, step=1,
                key="limite_commentaires", disabled=occupe,
                help="Borne technique contrôlée également côté serveur.")
        st.subheader("Période")
        with st.expander("Dates (facultatif)", expanded=bool(st.session_state["date_debut"] or st.session_state["date_fin"])):
            d1,d2 = st.columns(2)
            d1.date_input("Du", value=None, key="date_debut", format="DD/MM/YYYY", disabled=occupe)
            d2.date_input("Au", value=None, key="date_fin", format="DD/MM/YYYY", disabled=occupe)
            st.caption("Jours inclus en UTC. Research API : 30 derniers jours par défaut, fenêtres successives de 30 jours pour une période plus longue." if source=="presse" and st.session_state.get("presse_moteur")=="research" else "Jours inclus en UTC, parmi les publications consultées. Les dates inconnues sont écartées si une période est choisie.")
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
        st.checkbox("Texte généré par IA", key="inclure_texte_genere_ia",
            value=False, disabled=occupe,
            help="Ajoute un second segment **** *source_ia uniquement si le résumé natif de TikTok est réellement récupéré. La légende originale reste *source_original. Avec TikHub, la récupération utilise l'API itemCustomTDK, qui peut être facturée par vidéo ; avec les autres moteurs, l'analyse du panneau TikTok nécessite un navigateur.")
        if st.form_submit_button("Lancer la collecte", type="primary",
                                 disabled=occupe or api_tiktok_suspendue
                                          or (source=="presse" and len(st.session_state.get("medias",[]))>max_sources_admin),
                                 on_click=respecter_choix_commentaires):
            debut,fin = iso(st.session_state["date_debut"]),iso(st.session_state["date_fin"])
            if source != "presse" and not st.session_state.get(cle_hashtag, "").strip():
                st.error("Le premier hashtag est obligatoire pour la collecte par hashtags ou profils.")
            elif source == "presse" and not st.session_state.get("medias"):
                st.error("Sélectionnez au moins un média.")
            elif (source == "presse" and st.session_state.get("croiser_hashtag_presse")
                  and not st.session_state.get("hashtag_presse", "").strip()):
                st.error("Saisissez le hashtag à croiser avec les médias.")
            elif debut and fin and debut>fin: st.error("La date de début doit précéder ou égaler la date de fin.")
            else:
                valeurs = {k:st.session_state[k] for k in ("limit","french_only","include_sources","collecter_commentaires","collecter_reponses","limite_commentaires","telecharger_mp4","sauvegarde_progressive","inclure_texte_genere_ia")}
                valeurs["supprimer_arobase_profil"] = st.session_state.get("export_profil_sans_arobase", True)
                valeurs["operator"] = "AND" if source == "presse" else st.session_state.get("operator", "AND")
                valeurs["presse_moteur"] = st.session_state.get("presse_moteur", "api")
                valeurs["croiser_hashtag_presse"] = (
                    bool(st.session_state.get("croiser_hashtag_presse", False)) if source == "presse" else False)
                valeurs["hashtag_presse"] = (
                    st.session_state.get("hashtag_presse", "").strip()
                    if valeurs["croiser_hashtag_presse"] else "")
                if source == "presse" and valeurs["presse_moteur"] == "navigateur":
                    fichier_cookies = st.session_state.get("cookies_presse_fichier")
                    if fichier_cookies is not None:
                        try:
                            if fichier_cookies.size > 1_048_576:
                                raise ValueError()
                            contenu_cookies = fichier_cookies.getvalue().decode("utf-8-sig")
                            from collecte.cookies_presse import charger_cookies_presse
                            charger_cookies_presse(contenu_cookies)
                            valeurs["cookies_tiktok"] = contenu_cookies
                        except (ValueError, RuntimeError):
                            st.error("Importez un fichier Netscape valide de moins de 1 Mo contenant des cookies TikTok non expirés.")
                            st.stop()
                if source == "presse" and valeurs["presse_moteur"] == "research":
                    valeurs["research_client_key"] = st.session_state.get("research_client_key", "")
                    valeurs["research_client_secret"] = st.session_state.get("research_client_secret", "")
                if source == "presse" and valeurs["presse_moteur"] == "tikhub":
                    valeurs["tikhub_api_key"] = st.session_state.get("tikhub_api_key", "")
                if source == "presse" and valeurs["presse_moteur"] == "apify":
                    valeurs["apify_api_token"] = st.session_state.get("apify_api_token", "")
                valeurs["rechercher_dans_texte"] = (
                    bool(st.session_state.get("rechercher_dans_texte", True)) if source != "presse" else False
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

    # Hors formulaire : changer le choix actualise les liens sans relancer la collecte.
    st.checkbox("Supprimer le @ devant les profils dans le TXT",
                key="export_profil_sans_arobase",
                help="Appliqué aux profils des blocs original et IA, dans l’aperçu, le TXT et le ZIP.")


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
                elif st.button("Arrêter la collecte", type="primary",
                               key="interrompre_collecte_active", use_container_width=True):
                    lancer(f"/api/jobs/{actuel['id']}/stop", {})
            elif "TikTok HTTP 429" in actuel.get("message", ""):
                st.info("Collecte terminée après HTTP 429 : aucun nouvel appel TikTok n'est lancé par ce traitement.")
            # Les changements d’étape recréent l’interface ; les images et gestes restent dans leur iframe stable.
            if any(precedent.get(k)!=actuel.get(k) for k in ("busy","video_busy")) or (precedent.get("status")=="attention") != (actuel.get("status")=="attention"):
                st.rerun()
            if actuel.get("comptes_filtres"):
                st.write("Filtre des profils : " + ", ".join("@" + compte for compte in actuel["comptes_filtres"]))
                if actuel.get("source_collecte") != "presse":
                    st.caption("Les hashtags sont vérifiés dans les légendes ; les autres auteurs sont exclus.")
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
                        "des hashtags dans les légendes et avant les autres filtres. La limite est GLOBALE : "
                        "avec 50 posts et deux hashtags, au plus 50 vidéos distinctes peuvent être retenues, "
                        "en mode OU comme en mode ET. La collecte répartit ce budget entre les hashtags. "
                        "Les variantes accentuées partagent le quota du hashtag initial ; les doublons "
                        "entre hashtags ne sont lus qu'une fois. Le choix ET/OU s'applique ensuite "
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
                        st.write(f"Filtre français : {actuel['non_french']} dans une autre langue écartés · {actuel['language_unknown']} de langue indéterminée écartés")
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
                    requetes_api_lot = 0
                    def ajouter_detail_source(message):
                        details_source.append(" ".join(str(message).split()))
                    for numero_source, bilan in enumerate(actuel["bilan_sources"], 1):
                        details_source = []
                        ajouter_detail_source(f"Source {numero_source} — {bilan['source']} : {bilan['liens']} lien(s) — {bilan['message']}")
                        informations_source = []
                        if actuel.get("source_collecte") == "presse":
                            version_source=bilan.get("version_collecteur")
                            if version_source:
                                informations_source.append(
                                    "Méthode enregistrée : "+str(bilan.get("presse_moteur") or "?")+
                                    " · version "+version_source
                                )
                            else:
                                ajouter_detail_source("Diagnostic issu d'une ancienne collecte, sans version enregistrée : "
                                           "relancez une collecte pour tester le nouveau moteur.")
                        if bilan.get("retenues_par_compte"):
                            informations_source.append("Liens retenus cumulés : " + " · ".join(
                                f"@{compte} : {nombre}" for compte, nombre in bilan["retenues_par_compte"].items()))
                        if informations_source:
                            ajouter_detail_source(" · ".join(informations_source))
                        navigation_videos = bilan.get("navigation_videos") or {}
                        navigation_observee = bilan.get("navigation_videos_observee") or {}
                        etat_page = bilan.get("etat_page") or {}
                        reseau_profil = bilan.get("reseau_profil") or {}
                        if etat_page or reseau_profil:
                            ajouter_detail_source(
                                "Chargement TikTok : HTTP " +
                                str(bilan.get("statut_http_profil") or "?") +
                                " · état " + str(etat_page.get("etat") or "?") +
                                " · erreur affichée : " + ("oui" if etat_page.get("erreur_tiktok") else "non") +
                                " · réponses vidéo : " + str(reseau_profil.get("reponses", 0)) +
                                (" · refus réseau HTTP " + str(reseau_profil["refus_http"])
                                 if reseau_profil.get("refus_http") else ""))
                        if navigation_videos.get("statut") == "selectionne_sans_publications":
                            ajouter_detail_source(
                                "L'onglet Vidéos est sélectionné mais aucune publication n'a été chargée. "
                                "Ce n'est pas une preuve que la liste des vidéos est accessible.")
                        if navigation_videos:
                            ajouter_detail_source(
                                "Accès Vidéos : " + str(navigation_videos.get("statut", "?")) +
                                (" · via " + str(navigation_videos.get("type"))
                                 if navigation_videos.get("type") else ""))
                        if navigation_observee:
                            ajouter_detail_source(
                                "Page visitée : " + str(navigation_observee.get("route", "?")) +
                                " · grilles : " + str(navigation_observee.get("grilles", 0)) +
                                " · liens vidéo du compte : " +
                                str(navigation_observee.get("liens_video_auteur", 0)))
                        for recherche in bilan.get("recherches", []):
                            ajouter_detail_source(f"{recherche['requete']} : {recherche['liens']} lien(s) retenu(s), {recherche['auteurs_ecartes']} d’autres auteurs écarté(s).")
                            auteurs = recherche.get("auteurs_dans_liens", {})
                            compte = recherche.get("compte")
                            if compte and not recherche.get("urls_embed_non_verifiees"):
                                ajouter_detail_source(f"@{compte} : {auteurs.get(compte, 0)} publication(s) dans les liens reçus de TikTok, sur {recherche.get('candidats_examines', 0)} publication(s) repérée(s).")
                                if recherche.get("candidats_examines") and not auteurs.get(compte, 0):
                                    ajouter_detail_source("Le compte ciblé est absent des liens reçus pour cette recherche. Le filtre l’a cherché ; cela ne prouve pas que ses vidéos n’existent pas.")
                            if auteurs:
                                frequents = sorted(auteurs.items(), key=lambda element: (-element[1], element[0]))[:10]
                                ajouter_detail_source("Auteurs indiqués dans les liens (10 premiers au maximum) : " + " · ".join(f"@{auteur} : {nombre}" for auteur, nombre in frequents))
                            navigation_detail = recherche.get("navigation_videos") or {}
                            navigation_observee = recherche.get("navigation_videos_observee") or {}
                            if navigation_detail:
                                ajouter_detail_source(
                                    "Accès Vidéos : " + str(navigation_detail.get("statut", "?")) +
                                    (" · via " + str(navigation_detail.get("type"))
                                     if navigation_detail.get("type") else ""))
                            if navigation_observee:
                                ajouter_detail_source(
                                    "Page visitée : " + str(navigation_observee.get("route", "?")) +
                                    " · grilles : " + str(navigation_observee.get("grilles", 0)) +
                                    " · liens vidéo du compte : " +
                                    str(navigation_observee.get("liens_video_auteur", 0)))
                            navigation=recherche.get("navigation_publications")
                            ligne_pagination = ""
                            if navigation=="research_officielle":
                                ajouter_detail_source(f"Research API : {recherche.get('pages_research',0)} page(s), {recherche.get('liens',0)} vidéo(s) retenue(s).")
                            elif navigation=="api_liste_createur":
                                provenance=recherche.get("source_secuid")
                                resolution=(
                                    "identifiant public vérifié lors d'une collecte précédente"
                                    if provenance=="cache_verifie" else
                                    "identifiant vérifié dans les vidéos du premier embed (sans embed vidéo supplémentaire)"
                                    if provenance=="embed_createur_videos" else
                                    "identifiant confirmé via l'embed d'une vidéo"
                                    if provenance=="embed_video" else
                                    "identifiant fourni par l'embed du créateur"
                                    if provenance=="embed_createur" else
                                    "identifiant non encore confirmé"
                                )
                                if recherche.get("urls_embed_non_verifiees"):
                                    ligne_pagination = (
                                        "Pagination : 0 page reçue. "
                                        f"{recherche['urls_embed_non_verifiees']} identifiant(s) repéré(s) "
                                        "dans l'embed, non vérifiés et non sauvegardés."
                                    )
                                else:
                                    ligne_pagination = (
                                        f"Liste vidéo TikTok par secUid : "
                                        f"{recherche.get('pages_api',0)} page(s) reçue(s), "
                                        f"{recherche.get('liens',0)} vidéo(s) retenue(s) "
                                        f"du média ; {resolution}."
                                    )
                            elif navigation=="onglet_videos_selectionne":
                                ajouter_detail_source("Onglet Vidéos du média confirmé : collecte sur sa grille et ses pages successives.")
                            elif navigation=="grille_videos_sans_onglet_distinct":
                                ajouter_detail_source("Grille de vidéos du média reconnue ; aucun onglet distinct n'était nécessaire.")
                            elif navigation=="onglet_videos_indisponible":
                                ajouter_detail_source("Onglet Vidéos introuvable sur ce profil : aucune recherche générale n'est substituée.")
                            elif navigation=="clic_onglet_videos_impossible":
                                ajouter_detail_source("Impossible d'ouvrir l'onglet Vidéos du média.")
                            elif navigation=="ouverture_onglet_videos_en_cours":
                                ajouter_detail_source("Ouverture de l'onglet Vidéos demandée, mais le chargement n'a pas été confirmé.")
                            elif navigation=="rubrique_selectionnee":
                                ajouter_detail_source("Rubrique Vidéos/Publications ouverte avant la pagination.")
                            elif navigation=="pas_de_rubrique_distincte_detectee":
                                ajouter_detail_source("Aucun accès distinct à « Toutes les vidéos » détecté : collecte sur la grille visible du profil.")
                            elif navigation=="clic_impossible":
                                ajouter_detail_source("TikTok a refusé l'ouverture de la rubrique Vidéos/Publications.")
                            details_pagination=recherche.get("pagination_bilan") or {}
                            if details_pagination:
                                ajouter_detail_source(
                                    f"Pagination du profil : {details_pagination.get('defilements',0)} "
                                    f"défilement(s), {details_pagination.get('sans_progres',0)} sans déplacement "
                                    f"de grille · {details_pagination.get('pages_reseau',0)} page(s) "
                                    "de publications reçue(s) par le navigateur."
                                )
                                if details_pagination.get("connexion_exigee"):
                                    ajouter_detail_source(
                                        "TikTok interrompt la pagination anonyme de ce média en demandant "
                                        "une connexion. Les premières vidéos restent conservées ; "
                                        "la recherche complémentaire tente d'en trouver d'autres."
                                    )
                                elif details_pagination.get("sans_progres",0):
                                    ajouter_detail_source(
                                        "La grille du profil n'a pas progressé à certains défilements. "
                                        "Cela peut provenir du conteneur TikTok ou d'une limite "
                                        "d'accès aux publications suivantes."
                                    )
                                if not details_pagination.get("reseau_disponible",True):
                                    ajouter_detail_source("Observation des pages réseau indisponible ; liens HTML uniquement.")
                            motifs = {"limit": "limite demandée atteinte", "no_new_links": "plus de nouveaux liens après plusieurs attentes",
                                      "max_scrolls": "budget de défilement atteint", "blocked": "vérification TikTok en attente",
                                      "tiktok_error": "erreur de chargement TikTok", "no_accessible_links": "aucun lien lisible",
                                      "connexion_apres_resultats": "invitation à se connecter et absence de nouveaux liens",
                                      "publications_non_accessibles": "invitation à se connecter et aucun lien lisible",
                                      "recherche_redirigee": "redirection vers une autre page"}
                            if recherche.get("arret"):
                                texte_arret = (f"{recherche.get('defilements', 0)} défilement(s) effectué(s). Arrêt : "
                                               + motifs.get(recherche["arret"], recherche["arret"]))
                                ligne_pagination = (ligne_pagination + " · " + texte_arret
                                                    if ligne_pagination else texte_arret)
                            if ligne_pagination:
                                ajouter_detail_source(ligne_pagination)
                            if recherche.get("diagnostic"):
                                diagnostic_recherche=recherche["diagnostic"]
                                code_recherche=diagnostic_recherche.get("code", "indéterminé")
                                ajouter_detail_source("Diagnostic : " + code_recherche)
                                if code_recherche in {"research_acces_refuse", "research_indisponible"}:
                                    ajouter_detail_source("Research API officielle : " + str(diagnostic_recherche.get("detail") or code_recherche))
                                elif code_recherche=="tiktok_limitation_429":
                                    ajouter_detail_source("TikTok a renvoyé HTTP 429 : le moteur API s'est arrêté sans "
                                             "essayer les autres vidéos ni les autres médias.")
                                    ajouter_detail_source(
                                        "Ce refus concerne l'API web Presse, et non nécessairement "
                                        "la collecte par hashtags. Pour une nouvelle collecte, "
                                        "vous pouvez choisir manuellement le moteur "
                                        "« Méthode Selenium ». "
                                        "ScrapTikTok n'enchaîne pas automatiquement un autre "
                                        "moteur après un HTTP 429."
                                    )
                                    etapes_429={
                                        "identification_media": "Identification du compte média",
                                        "identification_video": "Identification via une vidéo du média",
                                        "pagination_videos": "Pagination des publications",
                                        "non_commencee": "Avant le premier appel",
                                    }
                                    phase=diagnostic_recherche.get("etape_api")
                                    if phase:
                                        appels_media = int(recherche.get("requetes_tentees") or
                                                            diagnostic_recherche.get("requetes_tentees") or 0)
                                        ajouter_detail_source(
                                            "Média en échec : " + str(compte or bilan["source"])
                                            + f" · source {numero_source} de la sélection. "
                                            + "Étape du refus : " + etapes_429.get(phase,phase)
                                            + f" · {appels_media} requête(s) tentée(s) pour ce média "
                                            + f"· {requetes_api_lot + appels_media} "
                                              "requête(s) API Presse tentée(s) depuis le début de cette collecte (hors Selenium) "
                                            + f"· {diagnostic_recherche.get('pages_api',0)} "
                                              "page(s) reçue(s) pour ce média."
                                        )
                                elif code_recherche=="budget_interne_epuise":
                                    ajouter_detail_source("Budget administrateur des requêtes API Presse épuisé. "
                                               "La collecte a été arrêtée avant de solliciter TikTok.")
                                elif code_recherche=="tiktok_pause_429":
                                    ajouter_detail_source("Moteur API suspendu par la pause de protection après HTTP 429. "
                                               "Aucune requête TikTok n'a été envoyée pour cette nouvelle collecte.")
                                if diagnostic_recherche.get("retry_after_seconds"):
                                    ajouter_detail_source(f"Délai indicatif transmis par TikTok (Retry-After) : "
                                               f"{diagnostic_recherche['retry_after_seconds']} secondes.")
                                if diagnostic_recherche.get("detail"):
                                    ajouter_detail_source("Accès TikTok : " + diagnostic_recherche["detail"])
                            elif recherche.get("message_erreur"):
                                ajouter_detail_source("Accès TikTok : "+recherche["message_erreur"])
                            requetes_api_lot += int(recherche.get("requetes_tentees") or 0)
                        diagnostic = bilan.get("diagnostic", {})
                        if diagnostic:
                            indices = [str(diagnostic[cle]) for cle in ("code", "exception", "erreur_reseau", "url", "etat") if diagnostic.get(cle)]
                            ajouter_detail_source(" · ".join(indices))
                        st.caption(" · ".join(details_source))
            bilan_ia = actuel.get("bilan_textes_ia")
            if bilan_ia and bilan_ia["publications"]:
                st.caption(f"Textes IA TikTok récupérés : {bilan_ia['recuperes']} sur {bilan_ia['publications']} publications retenues dans le TXT.")
                if bilan_ia["recuperes"] < bilan_ia["publications"]:
                    st.warning("Certains résumés IA n’ont pas été récupérés. Ils peuvent être absents ou inaccessibles dans la page TikTok. Les textes originaux restent exportés.")
                with st.expander("Détail de la récupération des textes IA"):
                    st.dataframe(bilan_ia["details"], hide_index=True)
            with st.expander("Aperçu des textes"):
                st.caption("Les cinq premières publications, avec le codage des sources et les variables sélectionnées.")
                for publication in actuel.get("preview",[]):
                    cle_apercu = ("texte_export_sans_arobase" if st.session_state.get("export_profil_sans_arobase", True)
                                  else "texte_export_avec_arobase")
                    st.text(publication.get(cle_apercu, publication.get("texte_export", publication["description"])))
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
                        ),
                        "Langue": st.column_config.TextColumn("Langue de la légende",
                            help="Langue du texte écrit, sans les hashtags ni les mentions. La voix de la vidéo n’est pas analysée."),
                        "Retenue dans le TXT": st.column_config.TextColumn("Retenue dans le TXT",
                            help="Les publications exclues restent visibles dans ce tableau avec Non ; elles ne sont pas exportées dans le TXT.")
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
                sans_arobase = st.session_state.get("export_profil_sans_arobase", True)
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
            # Le WebSocket Streamlit et l'iframe peuvent arriver sur des
            # instances différentes lors d'un déploiement Coolify. Transmettre
            # seulement leurs empreintes pour diagnostiquer ce cas, sans
            # divulguer le cookie privé.
            try:
                contexte_controle = api("/api/session")
            except RuntimeError as erreur:
                st.warning("Impossible de vérifier la session du navigateur : " + str(erreur))
            else:
                instance_controle = contexte_controle.get("instance", "")
                empreinte_controle = contexte_controle.get("empreinte_session", "")
                identifiant_controle = st.session_state["collecte"]["id"]
                adresse_controle = (
                    f"/controle?collecte={identifiant_controle}"
                    f"&instance={instance_controle}&session={empreinte_controle}"
                )
                st.link_button(
                    "Ouvrir le navigateur TikTok dans un onglet séparé",
                    adresse_controle,
                    help="Alternative si le navigateur intégré n'affiche pas le CAPTCHA."
                )
                st.iframe(adresse_controle, height=850, alt="Navigateur TikTok du serveur")

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
    st.subheader("Protection contre les erreurs TikTok 429")
    st.write(
        "Les limites de l'API Presse viennent des variables d'environnement "
        "Coolify API_MAX_* ou SCRAPTIKTOK_API_MAX_*. Si une limite n'est pas "
        "configurée, le code n'en ajoute aucune. Deux alias renseignés pour "
        "un même plafond : la valeur la plus restrictive est retenue. "
        "Ces limites ne sont pas des quotas officiels du scraping TikTok "
        "et n'empêchent pas nécessairement les erreurs HTTP 429."
    )
    budget_aide = limites_admin.get("budget_api_presse", {})
    st.table([
        {"Limite locale (API Presse)": "Requêtes par minute",
         "Maximum actif": budget_aide.get("maximum_minute") or "Non configuré"},
        {"Limite locale (API Presse)": "Requêtes par heure",
         "Maximum actif": budget_aide.get("maximum_heure") or "Non configuré"},
        {"Limite locale (API Presse)": "Requêtes par jour UTC",
         "Maximum actif": budget_aide.get("maximum_24h") or "Non configuré"},
        {"Limite locale (API Presse)": "Enregistrements par jour UTC",
         "Maximum actif": budget_aide.get("maximum_enregistrements_24h") or "Non configuré"},
        {"Limite locale (API Presse)": "Intervalle minimal entre appels (s)",
         "Maximum actif": budget_aide.get("intervalle_min_s", "?")},
    ])
    st.caption(
        "Consommation : "
        f"{budget_aide.get('requete_24h', 0)} appels et "
        f"{budget_aide.get('enregistrements_24h', 0)} enregistrements aujourd'hui (UTC). "
        "Les limites sont communes à toutes les sessions. "
        "Le navigateur Selenium n'est pas comptabilisé ; son exécution reste limitée "
        "par la durée des collectes, les bornes techniques et les blocages TikTok. "
        "Chaque plafond configuré vient de Coolify ; une collecte s'arrête lorsqu'un plafond actif est atteint."
    )
    st.caption(
        "Les cinq anciennes variables de limitation par source sont ignorées. "
        "Références documentaires uniquement : "
        "[API officielle TikTok v2](https://developers.tiktok.com/docs/en/tiktok-api-v2-rate-limit) "
        "et [Research API](https://developers.tiktok.com/docs/en/research-api-faq)."
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
    st.subheader("Métrics, engagement et annotation")
    tache_desordre=st.session_state.get('collecte') or {}
    if tache_desordre.get('archive_prete'):
        nom_source={
            "presse": "Presse et médias", "comptes": "Profils",
            "hashtags": "Hashtags",
        }.get(tache_desordre.get("source_collecte"), "Collecte")
        st.caption(
            f"Source : {nom_source} · Les résultats et annotations peuvent être conservés "
            "dans votre historique privé pendant 30 jours, sans dupliquer les fichiers MP4."
        )
    if not tache_desordre.get('archive_prete'):
        if tache_desordre.get('source_collecte') == "presse" and tache_desordre.get('status') in {"failed", "partial", "stopped"}:
            st.warning("Aucune publication Presse exploitable n'a été enregistrée. La collecte a été interrompue avant de récupérer des métadonnées ; aucun fichier ni aucune vidéo non vérifiée ne sont proposés à l'analyse.")
        else:
            st.info("Effectuez une collecte dans l'onglet Collecte (Presse et médias, Profils ou Hashtags).")
    else:
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
                st.warning("Le serveur doit être redéployé avec les dépendances OpenCV de Désordre visuel.")
            elif not donnees.get('mp4_locaux') and not donnees.get('mp4_telechargeables'):
                st.warning("Aucun MP4 associé ni URL TikTok exploitable dans cette collecte. Consultez les publications collectées.")
            telecharger=st.checkbox("Télécharger les MP4 manquants avant l’analyse",value=True,key='desordre_telecharger',
                help="Les MP4 déjà présents sont réutilisés. Les échecs TikTok seront indiqués par publication.")
            activation=st.checkbox("Analyse du mouvement",key='activer_desordre',value=False)
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
            valeurs_ia = donnees.get('indicateurs_ia') or {}
            libelles_ia = {
                'declare_par_createur': 'Déclaré par le créateur',
                'etiquete_automatique': 'Étiquette automatique TikTok',
            }
            tableau['contenu_genere_ia'] = [
                libelles_ia.get(valeurs_ia.get(identifiant), 'Non renseigné')
                for identifiant in tableau['publication_id'].astype(str)
            ]
            tableau.insert(0,'numero_video',range(1,len(tableau)+1))
            st.markdown("**Qu’est-ce que l’indice de désordre visuel ?**",help=AIDE_INDICE)
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
            st.caption("Indice exploratoire de 0 à 100 — ce n’est pas un pourcentage. "
                       "Annotez « Mouvements dans l’image » et vos colonnes personnalisées : "
                       "1 = mouvements visibles, 0 = aucun mouvement visible, Non évaluée = manquant. "
                       "Les anciennes annotations de violence doivent être revérifiées avant de les interpréter comme des mouvements.")
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
                        'contenu_genere_ia':st.column_config.TextColumn('Généré par IA (TikTok)',
                            help='Étiquette signalée dans les métadonnées TikTok ; Non renseigné ne signifie pas absence d’IA.'),
                        'annotation_violence':st.column_config.SelectboxColumn(
                            'Mouvements dans l’image',options=list(options_violence),
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
                            raise RuntimeError("Le serveur n’a pas confirmé le codage des mouvements.")
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
                            raise RuntimeError("La relecture ne confirme pas les annotations des mouvements.")
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
                'violence_visible':'Mouvements dans l’image — codage manuel (0/1)'}
            engagements={'likes':'Nombre de likes','commentaires':'Nombre de commentaires','partages':'Nombre de partages','favoris':'Nombre de favoris','vues':'Nombre de vues',
                'likes_pour_1000_vues':'Likes pour 1 000 vues','commentaires_pour_1000_vues':'Commentaires pour 1 000 vues','partages_pour_1000_vues':'Partages pour 1 000 vues'}
            axe_x=st.selectbox("Indicateur visuel (axe horizontal)",list(indicateurs),format_func=indicateurs.get,key='desordre_x',help='Choisissez un indicateur automatique ou le codage manuel des mouvements dans l’image. Sa définition et son unité sont disponibles dans l’aide « Comprendre l’indicateur choisi » ci-dessous.')
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
                st.caption("Comparer les deux groupes (mouvements visibles : oui/non) sur les valeurs de l’indicateur visuel automatique.")
            afficher_droite=st.checkbox("Afficher la droite de régression linéaire",
                value=False, key="desordre_droite_regression",
                help="Ajoute une droite de tendance en pointillés au nuage de points, quand au moins "
                     "trois vidéos ont deux mesures valides et qu'aucune variable n'est constante. "
                     "Les points sont colorés selon leur position au-dessus, au-dessous ou sur la droite. "
                     "Il s’agit de moindres carrés sur les valeurs brutes, "
                     "pas du coefficient de Spearman (ρ), qui compare les rangs. "
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
                    st.info("Pour le codage des mouvements, évaluez plusieurs vidéos dans les deux catégories (0 et 1).")
            with st.expander("Toutes les corrélations"):
                st.dataframe([{cle:('Vitesse des sujets en mouvements' if cle=='indicateur' and valeur=='vitesse_residuelle' else valeur) for cle,valeur in ligne.items() if cle != 'permutations'}
                              for ligne in donnees.get('correlations',[])],hide_index=True,
                    column_config={nom:st.column_config.Column(help=aide) for nom,aide in AIDES_STATISTIQUES.items()})
            st.caption("Les valeurs manquantes restent absentes ; elles ne sont pas remplacées par zéro. "
                       "Les corrélations avec les mouvements annotés sont exploratoires et calculées uniquement "
                       "sur les annotations enregistrées, avec correction séparée pour les treize comparaisons possibles.")
            if etat.get('statut') in ('termine','partiel'):
                st.link_button("Corrélations avec mouvements (CSV)",
                    f"/api/jobs/{tache_desordre['id']}/desordre/correlations_violence.csv")
            st.link_button("Exporter le tableau complet (CSV réimportable)",
                f"/api/jobs/{tache_desordre['id']}/desordre/tableau-complet.csv",
                help="URL TikTok, indice de désordre, mouvements annotés, engagement, "
                     "variables personnalisées et provenance du lot.")
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
