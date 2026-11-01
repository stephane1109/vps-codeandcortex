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
MAX_PAGES = 60
TAILLE_MAX = 4_000_000
_cache_token = {"valeur": None, "expire": 0.0, "identite": None}
_verrou_token = threading.Lock()


class ResearchErreur(RuntimeError):
    """Erreur de l'API officielle, sans confusion avec l'API web secUid."""


class ResearchAccesRefuse(ResearchErreur):
    """Clés absentes, droits insuffisants ou quota officiel atteint."""


def identifiants_disponibles():
    return bool(os.getenv("TIKTOK_RESEARCH_CLIENT_KEY", "").strip()
                and os.getenv("TIKTOK_RESEARCH_CLIENT_SECRET", "").strip())


def _requete(url, *, data, headers):
    """POST vers deux URL officielles fixes, sans redirection vers un tiers."""
    if url not in (URL_TOKEN, _url_videos(), _url_commentaires(), _url_profil()):
        raise ResearchErreur("Endpoint Research non autorisé.")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=25) as resultat:
            if resultat.geturl() != url:
                raise ResearchErreur("Redirection Research inattendue.")
            contenu = resultat.read(TAILLE_MAX + 1)
            if len(contenu) > TAILLE_MAX:
                raise ResearchErreur("Réponse Research trop volumineuse.")
    except HTTPError as erreur:
        if erreur.code in (401, 403, 429):
            raise ResearchAccesRefuse(
                f"Research API HTTP {erreur.code} : autorisation, droits ou quota officiel à vérifier."
            ) from erreur
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
        if str(code) in ("rate_limit_exceeded", "access_token_invalid", "scope_not_authorized",
                         "scope_not_authorised", "unauthorized", "invalid_client"):
            raise ResearchAccesRefuse("Research API : droits, jeton ou quota refusés (" + str(code) + ").")
        raise ResearchErreur("Research API : réponse en erreur (" + str(code)[:60] + ").")
    return objet


def _url_videos():
    return URL_VIDEOS + "?fields=" + CHAMPS


def _url_commentaires():
    return URL_COMMENTAIRES + "?fields=" + CHAMPS_COMMENTAIRES


def _url_profil():
    return URL_PROFIL + "?fields=" + CHAMPS_PROFIL


def _jeton(requete=_requete, maintenant=time.monotonic, *, credentiels=None):
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
        if (_cache_token["identite"] == identité and _cache_token["valeur"]
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
                                    credentiels=None, hashtag=None, exclusions=()):
    """Recherche par compte ou hashtag avec NOT et pagination."""
    compte = normaliser_compte(compte) if compte is not None else None
    if hashtag is not None:
        from scraptiktok import normalize_hashtag
        hashtag = normalize_hashtag(hashtag)
    if compte is None and hashtag is None:
        raise ResearchErreur("Research API : renseigner un compte ou un hashtag.")
    from .selection_hashtags import normaliser_liste_hashtags
    from .exclusion_hashtags import hashtags_a_exclure
    hashtags_exclus = normaliser_liste_hashtags(exclusions)
    if hashtag and hashtag.casefold() in {nom.casefold() for nom in hashtags_exclus}:
        raise ResearchErreur("Un hashtag recherché ne peut pas être exclu.")
    verifier = check or (lambda: None)
    limite = max(1, min(int(limite), 1000))
    rapport.update(compte_attendu=compte, navigation_publications="research_officielle",
                   requete_recherche=(f"#{hashtag}" if hashtag else f"@{compte}") + " : Research API officielle",
                   discovered_urls=[], metadonnees_api={}, pages_research=0,
                   requetes_tentees=0, candidats_examines=0, auteurs_ecartes=0,
                   collecte_partielle=True, exhaustif=False,
                   fournisseur_donnees="TikTok Research API",
                   hashtags_exclus=list(hashtags_exclus), exclus_hashtags_api=0)
    verifier()
    # Vérifier d'abord les dates ; aucune requête sur une période invalide.
    periodes = list(_dates(debut, fin, aujourd_hui=aujourd_hui))
    acces = jeton if jeton is not None else _jeton(requete=requete, credentiels=credentiels)
    if not isinstance(acces, str) or not acces:
        raise ResearchAccesRefuse("Research API : jeton absent.")
    contenus = {}
    vus = set()
    for borne_debut, borne_fin in periodes:
        curseur = None
        search_id = None
        curseurs_vus = set()
        while rapport["pages_research"] < MAX_PAGES and len(contenus) < limite:
            verifier()
            requete_corps = {
                "query": {"and": [{"field_name": "hashtag_name" if hashtag else "username",
                                   "operation": "EQ", "field_values": [hashtag or compte]}]},
                "start_date": borne_debut, "end_date": borne_fin,
                "max_count": min(100, limite - len(contenus)),
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
            rapport["requetes_tentees"] += 1
            try:
                reponse = requete(
                    _url_videos(), data=json.dumps(requete_corps).encode("utf-8"),
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
                if fiche and (not hashtag or any(
                        str(tag).lstrip("#").casefold() == hashtag.casefold()
                        for tag in fiche.get("hashtags", []))):
                    contenus[identifiant] = fiche
                else:
                    rapport["auteurs_ecartes"] += 1
                if len(contenus) >= limite:
                    break
            rapport["metadonnees_api"] = contenus.copy()
            rapport["discovered_urls"] = [f["url"] for f in contenus.values()]
            rapport["retenues_par_compte"] = {compte: len(contenus)}
            if progress:
                progress(len(contenus))
            if len(contenus) >= limite:
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
        if len(contenus) >= limite or rapport["pages_research"] >= MAX_PAGES:
            break
    if rapport["pages_research"] >= MAX_PAGES and len(contenus) < limite:
        rapport["discovery_stop"] = "plafond_pages_research"
    else:
        rapport.setdefault("discovery_stop", "fin_des_periodes")
    rapport["collecte_partielle"] = len(contenus) < limite
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
    brut = {cle: donnee[cle] for cle in (
        "id", "video_id", "text", "like_count", "reply_count",
        "parent_comment_id", "create_time") if cle in donnee}
    return {
        "id": identifiant, "publication_id": str(publication_id),
        "parent_id": parent, "est_reponse": bool(parent),
        "auteur": None, "texte": texte.strip(),
        "date_brute": _entier_non_negatif(donnee.get("create_time")),
        "observe_le": datetime.now(timezone.utc).isoformat(),
        "likes": convertir_compteur(_entier_non_negatif(donnee.get("like_count"))),
        "id_observe": True, "brut": brut, "source": "research_api_officielle",
        "nombre_reponses_annonce": _entier_non_negatif(donnee.get("reply_count")),
    }


def collecter_commentaires_research(publication, limite=50, reponses=False, *,
                                    verifier=None, pause=time.sleep,
                                    requete=_requete, jeton=None, credentiels=None):
    """Interroger uniquement l'endpoint officiel, pour commentaires et réponses.

    Le plafond est commun aux commentaires et à leurs réponses. Les résultats
    partiels restent exportables si un quota ou une erreur survient.
    """
    from .reponses import rattacher_reponses
    if not isinstance(publication, dict):
        raise ValueError("Publication invalide.")
    video_id = str(publication.get("id") or "")
    if not re.fullmatch(r"\d{1,30}", video_id):
        raise ValueError("Identifiant TikTok Research invalide.")
    if not 1 <= int(limite) <= 500:
        raise ValueError("Limite de commentaires : 1 à 500.")
    limite = int(limite)
    verifier = verifier or (lambda: None)
    annonces = ((publication.get("engagement") or {}).get("commentaires") or {}).get("valeur")
    resultats = {}
    diagnostic = {"api": "Research API officielle", "pages": 0, "requetes": 0,
                  "reponses_demandees": bool(reponses), "repli_selenium": False}
    etat = {"statut": "complet", "bloquer": False, "jeton": jeton, "epuise": False}

    def lire_pages(identifiant, *, reponse=False, objectif=50, curseur_initial=0):
        """Extraire des pages officielles, sans recopier ni exposer le jeton."""
        curseur = curseur_initial
        deja_vus = {curseur}
        pages = 0
        while len(resultats) < limite and objectif > 0 and pages < MAX_PAGES:
            verifier()
            try:
                if etat["jeton"] is None:
                    etat["jeton"] = _jeton(requete=requete, credentiels=credentiels)
                corps = {
                    ("comment_id" if reponse else "video_id"): int(identifiant),
                    "max_count": min(100, objectif), "cursor": curseur,
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
                        objectif -= 1
                        if objectif == 0 or len(resultats) >= limite:
                            break
            if objectif == 0 or len(resultats) >= limite:
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
        if pages >= MAX_PAGES:
            etat["statut"] = "pagination_incomplete"
        return False

    # Sans réponses : conserver la limite totale sur les seuls commentaires.
    # Avec réponses : réserver 30 % du quota aux premières réponses disponibles.
    plafond_parents = limite if not reponses else max(1, (limite * 7 + 9) // 10)
    fin_parents = lire_pages(video_id, objectif=plafond_parents)
    if reponses and not etat["bloquer"] and len(resultats) < limite:
        parents = [item for item in resultats.values()
                   if not item["est_reponse"] and (item["nombre_reponses_annonce"] or 0) > 0]
        for parent in parents:
            if etat["bloquer"] or len(resultats) >= limite:
                break
            lire_pages(parent["id"], reponse=True, objectif=limite-len(resultats))
    # La réserve peut produire un corpus partiel si TikTok ne retourne pas
    # de réponses ; signaler cette limite, sans annoncer une exhaustivité.
    if etat["statut"] == "complet":
        if len(resultats) >= limite:
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
