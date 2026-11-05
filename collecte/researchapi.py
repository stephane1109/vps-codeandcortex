"""Moteur de la TikTok Research API : authentification, vidéos, commentaires et réponses.

Accès conditionné à une autorisation research.data.basic. Pas de navigateur,
pas de secUid, pas de téléchargement vidéo, jamais de tentative sur l'API web.
Documentation : https://developers.tiktok.com/docs/en/research-api-specs-query-videos
"""
from datetime import datetime, timedelta, timezone, date
import hashlib
import json
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .verification_comptes import normaliser_compte

VERSION_RESEARCH = "research-api-officielle-v2"
URL_TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
URL_VIDEOS = "https://open.tiktokapis.com/v2/research/video/query/"
URL_COMMENTAIRES = "https://open.tiktokapis.com/v2/research/video/comment/list/"
URL_PROFIL = "https://open.tiktokapis.com/v2/research/user/info/"
CHAMPS = ("id,username,video_description,create_time,region_code,like_count,"
          "comment_count,share_count,view_count,favorites_count,video_duration,hashtag_names,video_tag")
CHAMPS_COMMENTAIRES = "id,video_id,text,like_count,reply_count,parent_comment_id,create_time"
CHAMPS_PROFIL = "follower_count"
CHAMPS_PROFIL_AUTORISES = (
    "is_verified", "follower_count", "following_count",
    "likes_count", "video_count",
)
MAX_PAGES = 60
TAILLE_MAX = 4_000_000
_cache_token = {"valeur": None, "expire": 0.0, "identite": None}
_verrou_token = threading.Lock()


class ResearchErreur(RuntimeError):
    """Erreur de l'API officielle, sans confusion avec l'API web secUid."""


class ResearchAccesRefuse(ResearchErreur):
    """Clés absentes, droits insuffisants ou quota officiel atteint."""


class ResearchJetonInvalide(ResearchAccesRefuse):
    """Jeton OAuth Research invalide ; renouvellement ponctuel autorisé."""


class ResearchErreurServeur(ResearchErreur):
    """Réponse transitoire HTTP 5xx du serveur officiel TikTok."""

    def __init__(self, statut_http):
        self.statut_http = int(statut_http)
        super().__init__(f"Research API HTTP {self.statut_http}.")


def poursuivre_apres_erreur_serveur(
        erreur, *, source_collecte, moteur_actif, echecs_consecutifs, seuil=3):
    """Poursuivre une collecte Presse sauf en cas de pannes 5xx répétées."""
    return (
        isinstance(erreur, ResearchErreurServeur)
        and source_collecte == "presse"
        and moteur_actif == "research"
        and echecs_consecutifs < seuil
    )


def identifiants_disponibles():
    return bool(os.getenv("TIKTOK_RESEARCH_CLIENT_KEY", "").strip()
                and os.getenv("TIKTOK_RESEARCH_CLIENT_SECRET", "").strip())


def _requete(url, *, data, headers):
    """POST vers deux URL officielles fixes, sans redirection vers un tiers."""
    from .republications_research import url_republications
    # Les champs de profil peuvent varier selon les cases activées, mais
    # ils restent strictement limités à ceux reconnus par la Research API.
    profil_autorise = False
    if url.startswith(URL_PROFIL + "?fields="):
        champs = url.split("?fields=", 1)[1].split(",")
        profil_autorise = bool(champs) and all(
            champ in CHAMPS_PROFIL_AUTORISES for champ in champs
        ) and len(champs) == len(set(champs))
    if url not in (URL_TOKEN, _url_videos(), _url_commentaires(),
                   url_republications()) and not profil_autorise:
        raise ResearchErreur("Endpoint Research non autorisé.")
    # Budget quotidien partagé par les collectes Research de cette instance.
    # Les jetons OAuth ne comptent pas parmi les recherches de données.
    if url != URL_TOKEN:
        from stockage.collectes_research import reserver_requete
        from pathlib import Path
        dossier = Path(os.getenv("DATA_DIR", "data"))
        if not reserver_requete(dossier):
            raise ResearchAccesRefuse(
                "Quota local quotidien Research atteint : reprise après 00 h UTC.")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=25) as resultat:
            if resultat.geturl() != url:
                raise ResearchErreur("Redirection Research inattendue.")
            contenu = resultat.read(TAILLE_MAX + 1)
            if len(contenu) > TAILLE_MAX:
                raise ResearchErreur("Réponse Research trop volumineuse.")
    except HTTPError as erreur:
        if erreur.code == 401:
            # Seul le code officiel autorise à distinguer un jeton expiré
            # d'une permission Research réellement absente. Ne jamais
            # conserver ni afficher la réponse complète du serveur.
            try:
                detail = json.loads(erreur.read(4096))
                information = detail.get("error") or {}
                code_erreur = (
                    information.get("code") if isinstance(information, dict)
                    else information if isinstance(information, str)
                    else detail.get("code"))
            except (ValueError, UnicodeError, AttributeError, OSError):
                code_erreur = None
            if code_erreur == "access_token_invalid":
                raise ResearchJetonInvalide(
                    "Research API HTTP 401 : jeton d'accès invalide ou expiré."
                ) from erreur
            if code_erreur in ("scope_not_authorized", "scope_not_authorised"):
                raise ResearchAccesRefuse(
                    "Research API HTTP 401 : autorisation Research insuffisante "
                    "(scope_not_authorized)."
                ) from erreur
            raise ResearchAccesRefuse(
                "Research API HTTP 401 : authentification ou autorisation refusée. "
                "Vérifier le jeton et les droits du projet Research."
            ) from erreur
        if erreur.code == 403:
            raise ResearchAccesRefuse(
                "Research API HTTP 403 : accès refusé au projet Research."
            ) from erreur
        if erreur.code == 429:
            raise ResearchAccesRefuse(
                "Research API HTTP 429 : limite de requêtes TikTok atteinte."
            ) from erreur
        if erreur.code in (500, 502, 503, 504):
            # Une panne du serveur TikTok n'est pas un refus de droits ou de quota.
            # Le pilote de collecte décide de poursuivre ou d'interrompre le lot.
            raise ResearchErreurServeur(erreur.code) from erreur
        raise ResearchErreur(f"Research API HTTP {erreur.code}.") from erreur
    except (URLError, OSError, TimeoutError) as erreur:
        raise ResearchErreur("Research API : erreur réseau ou expiration du délai.") from erreur
    try:
        objet = json.loads(contenu)
    except (UnicodeError, TypeError, ValueError) as erreur:
        raise ResearchErreur("Research API : réponse JSON invalide.") from erreur
    if not isinstance(objet, dict):
        raise ResearchErreur("Research API : objet JSON attendu.")
    code = (objet.get("error") or {}).get("code", "ok") if isinstance(objet.get("error"), dict) else "ok"
    if code not in ("ok", 0, "0", None):
        # Les détails du serveur pourraient contenir des informations de session.
        if code == "access_token_invalid":
            raise ResearchJetonInvalide(
                "Research API : jeton d'accès invalide ou expiré (access_token_invalid).")
        if code == "rate_limit_exceeded":
            raise ResearchAccesRefuse(
                "Research API : limite de requêtes atteinte (rate_limit_exceeded).")
        if str(code) in ("scope_not_authorized", "scope_not_authorised",
                         "unauthorized", "invalid_client"):
            raise ResearchAccesRefuse(
                "Research API : autorisation ou identifiants refusés ("
                + str(code) + ").")
        raise ResearchErreur("Research API : réponse en erreur (" + str(code)[:60] + ").")
    return objet


def _url_videos():
    return URL_VIDEOS + "?fields=" + CHAMPS


def _url_commentaires():
    return URL_COMMENTAIRES + "?fields=" + CHAMPS_COMMENTAIRES


def _url_profil():
    return URL_PROFIL + "?fields=" + CHAMPS_PROFIL


def _jeton(requete=_requete, maintenant=time.monotonic, *,
           credentiels=None, renouveler=False):
    if credentiels is None:
        cle = os.getenv("TIKTOK_RESEARCH_CLIENT_KEY", "").strip()
        secret = os.getenv("TIKTOK_RESEARCH_CLIENT_SECRET", "").strip()
    else:
        cle, secret = (valeur.strip() for valeur in credentiels)
    if not cle or not secret:
        raise ResearchAccesRefuse(
            "Research API non configurée : renseigner TIKTOK_RESEARCH_CLIENT_KEY et "
            "TIKTOK_RESEARCH_CLIENT_SECRET après validation du projet."
        )
    with _verrou_token:
        # Empreinte seulement : ne jamais conserver le Client secret brut dans
        # le cache partagé entre les sessions.
        identité = hashlib.sha256((cle + "\0" + secret).encode("utf-8")).hexdigest()
        horloge = maintenant()
        if (not renouveler and _cache_token["identite"] == identité
                and _cache_token["valeur"]
                and horloge + 90 < _cache_token["expire"]):
            return _cache_token["valeur"]
        corps = urlencode({"client_key": cle, "client_secret": secret,
                           "grant_type": "client_credentials"}).encode()
        reponse = requete(URL_TOKEN, data=corps,
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
        token = reponse.get("access_token")
        if not isinstance(token, str) or not token:
            raise ResearchAccesRefuse("Research API : aucun jeton reçu (projet approuvé ?).")
        try:
            validite = int(reponse.get("expires_in", 0))
        except (TypeError, ValueError):
            validite = 0
        _cache_token.update(valeur=token, expire=horloge + max(0, validite),
                            identite=identité)
        return token


def _dates(debut, fin, *, aujourd_hui=None):
    """Fenêtres UTC récentes en premier, de 30 jours calendaires au maximum."""
    aujourd_hui = aujourd_hui or datetime.now(timezone.utc).date()
    try:
        derniere = date.fromisoformat(fin) if fin else aujourd_hui
        premiere = date.fromisoformat(debut) if debut else derniere - timedelta(days=29)
    except ValueError as erreur:
        raise ResearchErreur("Research API : période invalide (AAAA-MM-JJ).") from erreur
    if derniere > aujourd_hui:
        derniere = aujourd_hui
    if premiere > derniere:
        raise ResearchErreur("Research API : période de début postérieure à la fin.")
    while derniere >= premiere:
        borne = max(premiere, derniere - timedelta(days=29))
        yield borne.strftime("%Y%m%d"), derniere.strftime("%Y%m%d")
        derniere = borne - timedelta(days=1)


def _entier_non_negatif(valeur):
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, int) and valeur >= 0:
        return valeur
    if isinstance(valeur, str) and valeur.isdecimal():
        return int(valeur)
    return None


def _fiche(video, compte):
    if not isinstance(video, dict):
        return None
    try:
        auteur = normaliser_compte(video.get("username") or "")
    except (ValueError, TypeError, AttributeError):
        return None
    if compte is not None and auteur != compte:
        return None
    identifiant = str(video.get("id") or video.get("video_id") or "")
    if not re.fullmatch(r"\d{5,30}", identifiant):
        return None
    description = video.get("video_description")
    description = description.strip() if isinstance(description, str) else ""
    cree = _entier_non_negatif(video.get("create_time"))
    try:
        date_creation = datetime.fromtimestamp(cree, timezone.utc).isoformat() if cree else ""
    except (OverflowError, OSError, ValueError):
        date_creation = ""
    engagement = {}
    for nom, champ in (("vues", "view_count"), ("likes", "like_count"),
                       ("commentaires", "comment_count"), ("partages", "share_count"),
                       ("favoris", "favorites_count")):
        valeur = _entier_non_negatif(video.get(champ))
        if valeur is not None:
            engagement[nom] = {"valeur": valeur, "brut": str(valeur)}
    hashtags = video.get("hashtag_names")
    hashtags = ([str(v).lstrip("#") for v in hashtags if isinstance(v, str)]
                if isinstance(hashtags, list) else re.findall(r"#(\w+)", description))
    from .metadonnees import indicateur_ia
    from .variables_profil import normaliser_region
    return {"contenu_genere_ia": indicateur_ia(video), "id": identifiant,
            "url": f"https://www.tiktok.com/@{auteur}/video/{identifiant}",
            "author": auteur, "description": description,
            "created_at": date_creation,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "hashtags": list(dict.fromkeys(hashtags)),
            "engagement": engagement, "source": "research_api_officielle",
            "status": "ok" if description else "empty_caption", "error": "",
            "region_code": normaliser_region(video.get("region_code")),
            "video_duration": _entier_non_negatif(video.get("video_duration"))}


def collecter_videos_presse_research(compte, limite, rapport, *, debut=None, fin=None,
                                    check=None, progress=None, requete=_requete,
                                    jeton=None, pause=time.sleep, aujourd_hui=None,
                                    credentiels=None, hashtag=None, exclusions=(),
                                    hashtags=None, operateur="OR",
                                    filtre_region=None, maximum_candidats=None,
                                    maximum_requetes=None, position_reprise=None,
                                    enchainement_automatique=False):
    """Recherche paginée, segmentée et reprenable sans perdre sa position."""
    compte = normaliser_compte(compte) if compte is not None else None
    from .selection_hashtags import normaliser_liste_hashtags
    liste_hashtags = normaliser_liste_hashtags(
        list(hashtags) if hashtags else [hashtag] if hashtag else [])
    if operateur not in ("AND", "OR"):
        raise ResearchErreur("Research API : opérateur de hashtags inconnu.")
    if filtre_region not in (None, "FR"):
        raise ResearchErreur("Research API : code de région non autorisé.")
    if compte is None and not liste_hashtags:
        raise ResearchErreur("Research API : renseigner un compte ou un hashtag.")
    from .exclusion_hashtags import hashtags_a_exclure
    hashtags_exclus = normaliser_liste_hashtags(exclusions)
    if {nom.casefold() for nom in liste_hashtags}.intersection(
            nom.casefold() for nom in hashtags_exclus):
        raise ResearchErreur("Un hashtag recherché ne peut pas être exclu.")
    verifier = check or (lambda: None)
    # Un segment concerne les candidats reçus, et non les seules vidéos
    # conservées : un hashtag peu productif ne peut plus consommer le quota
    # quotidien sans atteindre la fin d'un lot.
    if maximum_candidats is not None:
        if (not isinstance(maximum_candidats, int)
                or isinstance(maximum_candidats, bool)
                or maximum_candidats < 1):
            raise ResearchErreur("Un segment Research doit examiner au moins un candidat.")
    if maximum_requetes is not None:
        if (not isinstance(maximum_requetes, int)
                or isinstance(maximum_requetes, bool)
                or maximum_requetes < 1):
            raise ResearchErreur("Une séquence Research exige au moins une requête.")
    if position_reprise is not None:
        if not isinstance(position_reprise, dict):
            raise ResearchErreur("Position de reprise Research invalide.")
        indice_reprise = position_reprise.get("indice_periode")
        curseur_reprise = position_reprise.get("cursor")
        recherche_reprise = position_reprise.get("search_id")
        if (not isinstance(indice_reprise, int) or indice_reprise < 0
                or (curseur_reprise is not None and (
                    not isinstance(curseur_reprise, int) or curseur_reprise < 0
                    or not isinstance(recherche_reprise, str)
                    or not recherche_reprise))):
            raise ResearchErreur("Position de pagination Research non exploitable.")
    # La collecte automatique n’impose aucun plafond de publications local.
    automatique = limite is None
    if not automatique:
        limite = max(1, min(int(limite), 1000))
    libelle_tags = (" OU " if operateur == "OR" else " ET ").join(
        "#" + nom for nom in liste_hashtags)
    libelle = (f"@{compte} ET ({libelle_tags})" if compte and len(liste_hashtags) > 1 else
               f"@{compte} ET {libelle_tags}" if compte and liste_hashtags else
               libelle_tags if liste_hashtags else f"@{compte}")
    rapport.update(compte_attendu=compte, navigation_publications="research_officielle",
                   requete_recherche=libelle + " : Research API officielle",
                   hashtags_recherches=list(liste_hashtags),
                   operateur_hashtags=operateur,
                   discovered_urls=[], metadonnees_api={}, pages_research=0,
                   requetes_tentees=0, candidats_examines=0, auteurs_ecartes=0,
                   collecte_partielle=True, exhaustif=False,
                   fournisseur_donnees="TikTok Research API",
                   hashtags_exclus=list(hashtags_exclus), exclus_hashtags_api=0,
                   ecartes_hashtags_api=0, ecartes_region_api=0,
                   filtre_region=filtre_region,
                   liens_page_research=[], apercu_ecartes_research=[])
    verifier()
    # Vérifier d'abord les dates ; aucune requête sur une période invalide.
    periodes = list(_dates(debut, fin, aujourd_hui=aujourd_hui))
    # Conserver les dates UTC effectives dès la première requête.
    # Le bilan CSV doit pouvoir restaurer la même période même si
    # l'utilisateur n'avait pas renseigné de dates explicites.
    rapport["plage_research"] = {
        "debut": periodes[-1][0], "fin": periodes[0][1]}
    if position_reprise is not None:
        if position_reprise["indice_periode"] >= len(periodes):
            raise ResearchErreur("Période de reprise Research hors du corpus initial.")
        attendues = periodes[position_reprise["indice_periode"]]
        if (position_reprise.get("debut_periode") != attendues[0]
                or position_reprise.get("fin_periode") != attendues[1]):
            raise ResearchErreur("La période de la recherche a changé depuis l'arrêt.")
    acces = jeton if jeton is not None else _jeton(requete=requete, credentiels=credentiels)
    if not isinstance(acces, str) or not acces:
        raise ResearchAccesRefuse("Research API : jeton absent.")
    contenus = {}
    vus = set()
    # Ces bornes délimitent les séquences internes sans interrompre le job.
    debut_sequence_candidats = 0
    debut_sequence_requetes = 0
    rapport["sequences_terminees"] = 0
    # Conserver les références vivantes des données : les réécritures
    # intégrales à chaque page ralentissaient les collectes importantes.
    rapport["metadonnees_api"] = contenus
    for indice_periode, (borne_debut, borne_fin) in enumerate(periodes):
        if (position_reprise is not None
                and indice_periode < position_reprise["indice_periode"]):
            continue
        reprendre_ici = (position_reprise is not None
                        and indice_periode == position_reprise["indice_periode"])
        curseur = position_reprise.get("cursor") if reprendre_ici else None
        search_id = position_reprise.get("search_id") if reprendre_ici else None
        curseurs_vus = set()
        while (automatique or (rapport["pages_research"] < MAX_PAGES
                                and len(contenus) < limite)):
            # Mémoriser la page à lire AVANT tout appel ou vérification.
            # Un arrêt entre deux pages conserve le prochain curseur.
            rapport["reprise_pagination_research"] = {
                "indice_periode": indice_periode,
                "debut_periode": borne_debut,
                "fin_periode": borne_fin,
                "cursor": curseur,
                "search_id": search_id,
            }
            verifier()
            conditions = []
            if compte is not None:
                conditions.append({"field_name": "username", "operation": "EQ",
                                   "field_values": [compte]})
            if filtre_region == "FR":
                conditions.append({
                    "field_name": "region_code", "operation": "EQ",
                    "field_values": ["FR"]})
            if liste_hashtags:
                if operateur == "OR" and len(liste_hashtags) > 1:
                    # IN produit le groupe (hashtag A OU hashtag B) conjoint
                    # à username, sans ambiguïté entre les opérateurs de l'API.
                    conditions.append({"field_name": "hashtag_name",
                                       "operation": "IN",
                                       "field_values": list(liste_hashtags)})
                else:
                    conditions.extend(
                        {"field_name": "hashtag_name", "operation": "EQ",
                         "field_values": [nom]} for nom in liste_hashtags)
            requete_corps = {
                "query": {"and": conditions},
                "start_date": borne_debut, "end_date": borne_fin,
                "max_count": (
                    min(100, maximum_candidats - (
                        rapport["candidats_examines"] - debut_sequence_candidats))
                    if maximum_candidats is not None
                    else 100 if automatique
                    else min(100, limite - len(contenus))),
                "is_random": False,
            }
            if hashtags_exclus:
                # Le serveur TikTok applique NOT IN sur le champ hashtag_name.
                requete_corps["query"]["not"] = [{
                    "field_name": "hashtag_name", "operation": "IN",
                    "field_values": list(hashtags_exclus),
                }]
            if curseur is not None:
                requete_corps["cursor"] = curseur
                requete_corps["search_id"] = search_id
            # Un hashtag peut parcourir l'API pendant plusieurs heures.
            # Le jeton OAuth Research expire normalement après deux heures :
            # vérifier le cache avant chaque page plutôt qu'une seule fois
            # au lancement de la source.
            try:
                if jeton is None:
                    acces = _jeton(requete=requete, credentiels=credentiels)
                corps_pagination = json.dumps(requete_corps).encode("utf-8")
                rapport["requetes_tentees"] += 1
                try:
                    reponse = requete(
                        _url_videos(), data=corps_pagination,
                        headers={"Authorization": "Bearer " + acces,
                                 "Content-Type": "application/json"})
                except ResearchJetonInvalide:
                    # Ne réessayer que si TikTok confirme access_token_invalid.
                    # Même page, même cursor/search_id, une seule relance.
                    # Un échec d'autorisation ou un 429 ne déclenche rien.
                    if jeton is not None:
                        raise
                    acces = _jeton(
                        requete=requete, credentiels=credentiels,
                        renouveler=True)
                    rapport["requetes_tentees"] += 1
                    rapport["renouvellements_jeton_401"] = (
                        int(rapport.get("renouvellements_jeton_401") or 0) + 1)
                    reponse = requete(
                        _url_videos(), data=corps_pagination,
                        headers={"Authorization": "Bearer " + acces,
                                 "Content-Type": "application/json"})
            except ResearchErreur:
                rapport["discovery_stop"] = "research_refus_ou_erreur"
                raise
            donnees = reponse.get("data")
            if not isinstance(donnees, dict) or not isinstance(donnees.get("videos"), list):
                raise ResearchErreur("Research API : liste videos absente de la réponse.")
            rapport["pages_research"] += 1
            videos = donnees["videos"]
            rapport["candidats_examines"] += len(videos)
            liens_page = []
            for video in videos:
                identifiant = str(video.get("id") or video.get("video_id") or "") if isinstance(video, dict) else ""
                if identifiant in vus:
                    continue
                vus.add(identifiant)
                fiche = _fiche(video, compte)
                if fiche and hashtags_a_exclure(fiche, hashtags_exclus):
                    # Défense locale si l'API renvoie malgré tout un hashtag exclu.
                    rapport["exclus_hashtags_api"] += 1
                    continue
                if (filtre_region == "FR" and fiche
                        and fiche.get("region_code") != "FR"):
                    # Research peut utiliser une recherche approximative.
                    # Une vidéo hors France n'entre pas dans le corpus FR.
                    rapport["ecartes_region_api"] += 1
                    if len(rapport["apercu_ecartes_research"]) < 20:
                        rapport["apercu_ecartes_research"].append({
                            "url": fiche["url"],
                            "auteur": fiche["author"],
                            "legende": fiche["description"][:350],
                            "hashtags": fiche.get("hashtags") or [],
                            "region": fiche.get("region_code") or "inconnue",
                            "motif": "Compte non enregistré en France"})
                    continue
                hashtags_observes = (
                    {str(tag).lstrip("#").casefold() for tag in fiche.get("hashtags", [])}
                    if fiche else set())
                if fiche:
                    # Les hashtags explicitement présents dans la légende
                    # complètent le tableau officiel si celui-ci est incomplet.
                    # Ne pas confondre un mot ordinaire avec un hashtag.
                    hashtags_observes.update(
                        tag.casefold() for tag in re.findall(
                            r"#(\w+)", fiche.get("description") or ""))
                concordances = [
                    nom.casefold() in hashtags_observes for nom in liste_hashtags
                ]
                valide = (all(concordances) if operateur == "AND"
                          else any(concordances)) if concordances else True
                if fiche and valide:
                    contenus[identifiant] = fiche
                    liens_page.append(fiche["url"])
                else:
                    rapport["auteurs_ecartes"] += 1
                    if fiche and not valide:
                        rapport["ecartes_hashtags_api"] += 1
                        if len(rapport["apercu_ecartes_research"]) < 20:
                            rapport["apercu_ecartes_research"].append({
                                "url": fiche["url"],
                                "auteur": fiche["author"],
                                "legende": fiche["description"][:350],
                                "hashtags": fiche.get("hashtags") or [],
                                "region": fiche.get("region_code") or "inconnue",
                                "motif": "Hashtags recherchés non satisfaits"})
                if not automatique and len(contenus) >= limite:
                    break
            # Publier immédiatement les nouveaux liens et leurs métadonnées,
            # afin que le pilote puisse lire/exporter chaque page reçue.
            rapport["liens_page_research"] = liens_page
            rapport["discovered_urls"].extend(liens_page)
            rapport["retenues_par_compte"] = {compte: len(contenus)}
            # Tant que le traitement de cette page n'est pas achevé,
            # garder son CURSEUR D'ENTRÉE comme point de reprise. Une
            # interruption pendant la lecture ne doit perdre aucune vidéo.
            rapport["reprise_pagination_research"] = {
                "indice_periode": indice_periode,
                "debut_periode": borne_debut,
                "fin_periode": borne_fin,
                "cursor": curseur,
                "search_id": search_id}
            page_suivante = None
            if donnees.get("has_more"):
                suivant = donnees.get("cursor")
                identifiant_recherche = donnees.get("search_id")
                if (isinstance(suivant, int) and suivant >= 0
                        and suivant not in curseurs_vus
                        and identifiant_recherche):
                    page_suivante = {
                        "indice_periode": indice_periode,
                        "debut_periode": borne_debut,
                        "fin_periode": borne_fin,
                        "cursor": suivant,
                        "search_id": str(identifiant_recherche)}
            elif indice_periode + 1 < len(periodes):
                prochaine = periodes[indice_periode + 1]
                page_suivante = {
                    "indice_periode": indice_periode + 1,
                    "debut_periode": prochaine[0],
                    "fin_periode": prochaine[1],
                    "cursor": None, "search_id": None}
            if progress:
                progress(len(contenus))
            # Le traitement de la page s'est terminé normalement : seulement
            # maintenant enregistrer le curseur suivant. Si le traitement
            # lève Stopped ou une erreur, l'entrée de la page reste mémorisée.
            rapport["reprise_pagination_research"] = page_suivante
            if donnees.get("has_more") and page_suivante is None:
                # TikTok annonce une suite mais n’indique pas comment y accéder.
                # Ne jamais repartir implicitement au début de la recherche,
                # ni avancer vers une autre période en laissant celle-ci incomplète.
                rapport["reprise_pagination_research"] = {
                    "indice_periode": indice_periode,
                    "debut_periode": borne_debut,
                    "fin_periode": borne_fin,
                    "cursor": curseur,
                    "search_id": search_id,
                    "pagination_invalide": True,
                }
                rapport["discovery_stop"] = "pagination_research_invalide"
                rapport["collecte_partielle"] = True
                rapport["plage_research"] = {
                    "debut": periodes[-1][0], "fin": periodes[0][1]}
                return list(rapport["discovered_urls"])
            # Une séquence comporte au plus 1 000 candidats ou 10 appels.
            # En mode automatique, poursuivre avec le curseur validé.
            # Le quota quotidien est contrôlé avant chaque appel Research.
            if (page_suivante is not None
                    and ((maximum_candidats is not None
                          and rapport["candidats_examines"] - debut_sequence_candidats
                          >= maximum_candidats)
                         or (maximum_requetes is not None
                             and rapport["requetes_tentees"] - debut_sequence_requetes
                             >= maximum_requetes))):
                rapport["sequences_terminees"] += 1
                if enchainement_automatique:
                    debut_sequence_candidats = rapport["candidats_examines"]
                    debut_sequence_requetes = rapport["requetes_tentees"]
                else:
                    rapport["discovery_stop"] = "lot_termine"
                    rapport["collecte_partielle"] = True
                    rapport["plage_research"] = {
                        "debut": periodes[-1][0], "fin": periodes[0][1]}
                    return list(rapport["discovered_urls"])
            if not automatique and len(contenus) >= limite:
                rapport["discovery_stop"] = "limit"
                break
            if not donnees.get("has_more"):
                break
            suivant = donnees.get("cursor")
            identifiant_recherche = donnees.get("search_id")
            if (not isinstance(suivant, int) or suivant < 0
                    or suivant in curseurs_vus or not identifiant_recherche):
                rapport["discovery_stop"] = "pagination_research_invalide"
                break
            curseurs_vus.add(suivant)
            curseur, search_id = suivant, str(identifiant_recherche)
            pause(1.0)
        if not automatique and (len(contenus) >= limite or rapport["pages_research"] >= MAX_PAGES):
            break
    if not automatique and rapport["pages_research"] >= MAX_PAGES and len(contenus) < limite:
        rapport["discovery_stop"] = "plafond_pages_research"
    else:
        rapport.setdefault("discovery_stop", "fin_des_periodes")
    rapport["collecte_partielle"] = (rapport.get("discovery_stop") != "fin_des_periodes"
                                   if automatique else len(contenus) < limite)
    rapport["plage_research"] = {"debut": periodes[-1][0], "fin": periodes[0][1]}
    return list(rapport["discovered_urls"])



def collecter_profil_research(compte, *, inclure_abonnes=True,
                              inclure_verification=True, verifier=None,
                              requete=_requete, jeton=None, credentiels=None):
    """Interroger le profil officiel une seule fois pour les champs demandés.

    L'absence de certification ne doit jamais être assimilée à False.
    """
    champs = []
    if inclure_abonnes:
        champs.append("follower_count")
    if inclure_verification:
        champs.append("is_verified")
    if not champs:
        return {"follower_count": None, "is_verified": None}
    verifier = verifier or (lambda: None)
    compte = normaliser_compte(compte)
    verifier()
    acces = jeton if jeton is not None else _jeton(requete=requete, credentiels=credentiels)
    if not isinstance(acces, str) or not acces:
        raise ResearchAccesRefuse("Research API : jeton absent pour le profil.")
    resultat = requete(
        URL_PROFIL + "?fields=" + ",".join(champs),
        data=json.dumps({"username": compte}).encode("utf-8"),
        headers={"Authorization": "Bearer " + acces, "Content-Type": "application/json"},
    )
    donnees = resultat.get("data") if isinstance(resultat, dict) else None
    if not isinstance(donnees, dict):
        raise ResearchErreur("Research API : données de profil absentes.")
    verification = donnees.get("is_verified")
    return {
        "follower_count": (_entier_non_negatif(donnees.get("follower_count"))
                           if inclure_abonnes else None),
        "is_verified": (verification if inclure_verification
                        and isinstance(verification, bool) else None),
    }


def collecter_metriques_profil_media_research(
        compte, variables, *, verifier=None, requete=_requete,
        jeton=None, credentiels=None):
    """Lire les compteurs choisis en une requête officielle par compte média.

    La réponse est une photographie du profil à la date de la requête ;
    les valeurs manquantes ne sont jamais imputées à zéro.
    """
    from .profils_medias import VARIABLES_PROFILS_MEDIAS
    variables = tuple(dict.fromkeys(variables))
    if not variables or any(v not in VARIABLES_PROFILS_MEDIAS for v in variables):
        raise ValueError("Sélection de métriques de profil invalide.")
    compte = normaliser_compte(compte)
    (verifier or (lambda: None))()
    acces = jeton if jeton is not None else _jeton(
        requete=requete, credentiels=credentiels)
    if not isinstance(acces, str) or not acces:
        raise ResearchAccesRefuse("Research API : jeton absent pour les métriques du profil.")
    resultat = requete(
        URL_PROFIL + "?fields=" + ",".join(variables),
        data=json.dumps({"username": compte}).encode("utf-8"),
        headers={"Authorization": "Bearer " + acces,
                 "Content-Type": "application/json"})
    donnees = resultat.get("data") if isinstance(resultat, dict) else None
    if not isinstance(donnees, dict):
        raise ResearchErreur("Research API : métriques du profil absentes.")
    return {variable: _entier_non_negatif(donnees.get(variable))
            for variable in variables}


def collecter_abonnes_research(compte, *, verifier=None, requete=_requete,
                               jeton=None, credentiels=None):
    """Compatibilité avec le collecteur historique de follower_count."""
    valeurs = collecter_profil_research(
        compte, inclure_abonnes=True, inclure_verification=False,
        verifier=verifier, requete=requete, jeton=jeton, credentiels=credentiels)
    if valeurs["follower_count"] is None:
        raise ResearchErreur("Research API : follower_count indisponible pour ce profil.")
    return valeurs["follower_count"]


def collecter_verification_research(compte, *, verifier=None, requete=_requete,
                                    jeton=None, credentiels=None):
    """Récupérer seulement le booléen vérifié/non vérifié."""
    valeurs = collecter_profil_research(
        compte, inclure_abonnes=False, inclure_verification=True,
        verifier=verifier, requete=requete, jeton=jeton, credentiels=credentiels)
    if valeurs["is_verified"] is None:
        raise ResearchErreur("Research API : is_verified indisponible pour ce profil.")
    return valeurs["is_verified"]


def normaliser_commentaire_research(donnee, publication_id, *, identifiant_parent=None):
    """Préparer un commentaire officiel avec son rattachement vérifié."""
    from .engagement import convertir_compteur
    if not isinstance(donnee, dict):
        return None
    identifiant = str(donnee.get("id") or "")
    if not re.fullmatch(r"\d{1,30}", identifiant):
        return None
    if (donnee.get("video_id") is not None
            and str(donnee["video_id"]) != str(publication_id)):
        return None
    texte = donnee.get("text")
    if not isinstance(texte, str) or not texte.strip():
        return None
    parent = donnee.get("parent_comment_id")
    parent = str(parent) if parent is not None else None
    if parent in (None, "", "0", str(publication_id)):
        parent = None
    if identifiant_parent is not None:
        if parent is not None and parent != str(identifiant_parent):
            return None
        parent = str(identifiant_parent)
    # TikTok ne propose pas de username stable dans l'endpoint Comments.
    # Le display_name peut apparaître dans certaines réponses officielles,
    # sans être un identifiant unique ni un champ demandable à coup sûr.
    # Conserver ce nom d'affichage séparément, sans fabriquer un auteur.
    nom_affiche = donnee.get("display_name")
    if not isinstance(nom_affiche, str):
        nom_affiche = ""
    nom_affiche = nom_affiche.strip()
    brut = {cle: donnee[cle] for cle in (
        "id", "video_id", "text", "like_count", "reply_count",
        "parent_comment_id", "create_time", "display_name") if cle in donnee}
    return {
        "id": identifiant, "publication_id": str(publication_id),
        "parent_id": parent, "est_reponse": bool(parent),
        "auteur": None, "nom_affiche": nom_affiche, "texte": texte.strip(),
        "date_brute": _entier_non_negatif(donnee.get("create_time")),
        "observe_le": datetime.now(timezone.utc).isoformat(),
        "likes": convertir_compteur(_entier_non_negatif(donnee.get("like_count"))),
        "id_observe": True, "brut": brut, "source": "research_api_officielle",
        "nombre_reponses_annonce": _entier_non_negatif(donnee.get("reply_count")),
    }


def collecter_commentaires_research(publication, limite=None, reponses=False, *,
                                    verifier=None, pause=time.sleep,
                                    requete=_requete, jeton=None, credentiels=None):
    """Interroger uniquement l'endpoint officiel, pour commentaires et réponses.

    Sans limite explicite, la pagination est automatique jusqu’à la fin
    des résultats accessibles ou à l’arrêt/quota TikTok, sans plafond local.
    Les appels existants avec une limite explicite restent pris en charge.
    Les résultats partiels restent exportables si un quota ou une erreur survient.
    """
    from .reponses import rattacher_reponses
    if not isinstance(publication, dict):
        raise ValueError("Publication invalide.")
    video_id = str(publication.get("id") or "")
    if not re.fullmatch(r"\d{1,30}", video_id):
        raise ValueError("Identifiant TikTok Research invalide.")
    automatique = limite is None
    if not automatique:
        if not 1 <= int(limite) <= 500:
            raise ValueError("Limite de commentaires : 1 à 500.")
        limite = int(limite)
    verifier = verifier or (lambda: None)
    annonces = ((publication.get("engagement") or {}).get("commentaires") or {}).get("valeur")
    resultats = {}
    diagnostic = {"api": "Research API officielle", "pages": 0, "requetes": 0,
                  "reponses_demandees": bool(reponses), "repli_selenium": False,
                  "pagination_automatique": automatique,
                  "maximum_pages": None if automatique else MAX_PAGES}
    etat = {"statut": "complet", "bloquer": False, "jeton": jeton, "epuise": False}

    def lire_pages(identifiant, *, reponse=False, objectif=50, curseur_initial=0):
        """Extraire des pages officielles, sans recopier ni exposer le jeton."""
        curseur = curseur_initial
        deja_vus = {curseur}
        pages = 0
        while ((limite is None or len(resultats) < limite)
               and (objectif is None or objectif > 0)
               and (automatique or diagnostic["pages"] < MAX_PAGES)):
            verifier()
            try:
                if etat["jeton"] is None:
                    etat["jeton"] = _jeton(requete=requete, credentiels=credentiels)
                corps = {
                    ("comment_id" if reponse else "video_id"): int(identifiant),
                    "max_count": 100 if objectif is None else min(100, objectif),
                    "cursor": curseur,
                }
                diagnostic["requetes"] += 1
                retour = requete(
                    _url_commentaires(), data=json.dumps(corps).encode("utf-8"),
                    headers={"Authorization": "Bearer " + etat["jeton"],
                             "Content-Type": "application/json"})
            except ResearchErreur as erreur:
                etat["statut"] = ("acces_refuse" if isinstance(
                    erreur, ResearchAccesRefuse) else "erreur_research")
                etat["bloquer"] = True
                diagnostic["erreur"] = type(erreur).__name__
                return False
            infos = retour.get("data") if isinstance(retour, dict) else None
            if not isinstance(infos, dict) or not isinstance(infos.get("comments"), list):
                etat["statut"] = "erreur_research"
                etat["bloquer"] = True
                diagnostic["erreur"] = "reponse_invalide"
                return False
            pages += 1
            diagnostic["pages"] += 1
            for donnee in infos["comments"]:
                item = normaliser_commentaire_research(
                    donnee, video_id, identifiant_parent=identifiant if reponse else None)
                if item and (reponse or not item["est_reponse"]):
                    if item["id"] not in resultats:
                        resultats[item["id"]] = item
                        if objectif is not None:
                            objectif -= 1
                        if objectif == 0 or (limite is not None and len(resultats) >= limite):
                            break
            if objectif == 0 or (limite is not None and len(resultats) >= limite):
                return False
            if not infos.get("has_more"):
                return True
            suivant = infos.get("cursor")
            if (not isinstance(suivant, int) or isinstance(suivant, bool)
                    or suivant < 0 or suivant in deja_vus):
                etat["statut"] = "pagination_incomplete"
                diagnostic["pagination_invalide"] = True
                return False
            deja_vus.add(suivant)
            curseur = suivant
            pause(0.25)
        if not automatique and diagnostic["pages"] >= MAX_PAGES:
            etat["statut"] = "pagination_incomplete"
        return False

    # Le mode manuel réserve 30 % de son objectif aux réponses.
    # La collecte Research automatique parcourt tous les parents accessibles.
    plafond_parents = (None if automatique else
                      limite if not reponses else max(1, (limite * 7 + 9) // 10))
    fin_parents = lire_pages(video_id, objectif=plafond_parents)
    if reponses and not etat["bloquer"] and (limite is None or len(resultats) < limite):
        parents = [item for item in resultats.values()
                   if not item["est_reponse"] and (item["nombre_reponses_annonce"] or 0) > 0]
        for parent in parents:
            if (etat["bloquer"] or (limite is not None and len(resultats) >= limite)
                    or (not automatique and diagnostic["pages"] >= MAX_PAGES)):
                break
            lire_pages(parent["id"], reponse=True,
                       objectif=None if automatique else limite-len(resultats))
    # La réserve peut produire un corpus partiel si TikTok ne retourne pas
    # de réponses ; signaler cette limite, sans annoncer une exhaustivité.
    if etat["statut"] == "complet":
        if limite is not None and len(resultats) >= limite:
            etat["statut"] = "limite"
        elif not fin_parents or reponses:
            etat["statut"] = "partiel"
        elif not resultats:
            etat["statut"] = "vide"
    statut = etat["statut"]
    return {
        "commentaires": rattacher_reponses(list(resultats.values())),
        "statut": statut,
        "message": {
            "complet": "Commentaires accessibles récupérés par la Research API.",
            "limite": "Plafond de commentaires Research atteint.",
            "vide": "Aucun commentaire retourné par la Research API.",
            "partiel": "Collecte Research partielle ou réponses non exhaustives.",
            "acces_refuse": "Research API : autorisation ou quota refusé.",
            "erreur_research": "Research API : erreur pendant la collecte des commentaires.",
            "pagination_incomplete": "Pagination Research incomplète.",
        }[statut],
        "exhaustif": statut in {"complet", "vide"} and not reponses,
        "limite": limite, "annonces": annonces,
        "recuperes": len(resultats), "diagnostic": diagnostic,
        "bloquer_requetes": etat["bloquer"],
        "source": "research_api_officielle",
    }
