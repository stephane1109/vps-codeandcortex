"""Collecte de vidéos publiques avec la TikTok Research API officielle.

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

VERSION_RESEARCH = "presse-research-officielle-v1"
URL_TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
URL_VIDEOS = "https://open.tiktokapis.com/v2/research/video/query/"
CHAMPS = ("id,username,video_description,create_time,region_code,like_count,"
          "comment_count,share_count,view_count,favorites_count,video_duration,hashtag_names,video_tag")
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
    if url not in (URL_TOKEN, _url_videos()):
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
    return {"contenu_genere_ia": indicateur_ia(video), "id": identifiant,
            "url": f"https://www.tiktok.com/@{auteur}/video/{identifiant}",
            "author": auteur, "description": description,
            "created_at": date_creation,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "hashtags": list(dict.fromkeys(hashtags)),
            "engagement": engagement, "source": "research_api_officielle",
            "status": "ok" if description else "empty_caption", "error": "",
            "region_code": video.get("region_code") if isinstance(video.get("region_code"), str) else None,
            "video_duration": _entier_non_negatif(video.get("video_duration"))}


def collecter_videos_presse_research(compte, limite, rapport, *, debut=None, fin=None,
                                    check=None, progress=None, requete=_requete,
                                    jeton=None, pause=time.sleep, aujourd_hui=None,
                                    credentiels=None, hashtag=None):
    """Recherche par compte ou hashtag, avec pagination et périodes bornées."""
    compte = normaliser_compte(compte) if compte is not None else None
    if hashtag is not None:
        from scraptiktok import normalize_hashtag
        hashtag = normalize_hashtag(hashtag)
    if compte is None and hashtag is None:
        raise ResearchErreur("Research API : renseigner un compte ou un hashtag.")
    verifier = check or (lambda: None)
    limite = max(1, min(int(limite), 1000))
    rapport.update(compte_attendu=compte, navigation_publications="research_officielle",
                   requete_recherche=(f"#{hashtag}" if hashtag else f"@{compte}") + " : Research API officielle",
                   discovered_urls=[], metadonnees_api={}, pages_research=0,
                   requetes_tentees=0, candidats_examines=0, auteurs_ecartes=0,
                   collecte_partielle=True, exhaustif=False,
                   fournisseur_donnees="TikTok Research API")
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
