"""Troisième moteur Presse : TikWM, service tiers, sans Selenium et sans secUid.

Contrat public : https://github.com/mehanon/tikwm (GET /api/user/posts).
Les données publiques sont reçues d'un intermédiaire non officiel : elles
peuvent être absentes, incomplètes ou différentes de celles de TikTok.
"""
from datetime import datetime, timezone
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .verification_comptes import normaliser_compte

VERSION_TIKWM = "presse-tikwm-profil-v1"
URL_TIKWM = "https://tikwm.com/api/user/posts"
LIMITE_PAGES = 60
TAILLE_PAGE = 34
LIMITE_OCTETS = 4_000_000


class TikwmErreur(RuntimeError):
    """Erreur du fournisseur externe TikWM, sans rapport avec les quotas TikTok."""


class TikwmRefus429(TikwmErreur):
    """Refus HTTP 429 provenant de TikWM : interrompre le lot."""


def _obtenir(url):
    """Lire une réponse JSON de l'adresse TikWM fixée dans ce module."""
    try:
        requete = Request(url, headers={
            "User-Agent": "ScrapTikTok/1.0",
            "Accept": "application/json",
        })
        with urlopen(requete, timeout=25) as reponse:
            if reponse.geturl().split("?", 1)[0] != URL_TIKWM:
                raise TikwmErreur("TikWM a redirigé la requête vers un autre endpoint.")
            contenu = reponse.read(LIMITE_OCTETS + 1)
            if len(contenu) > LIMITE_OCTETS:
                raise TikwmErreur("La réponse TikWM dépasse la limite de taille.")
            return contenu
    except HTTPError as erreur:
        if erreur.code == 429:
            raise TikwmRefus429("TikWM HTTP 429 : le fournisseur externe refuse la requête.") from erreur
        raise TikwmErreur(f"TikWM HTTP {erreur.code} : accès refusé ou service indisponible.") from erreur
    except (URLError, OSError, TimeoutError) as erreur:
        raise TikwmErreur("TikWM : échec réseau ou délai dépassé.") from erreur


def _page(donnees):
    """Valider la structure et distinguer les erreurs des résultats vides."""
    try:
        objet = json.loads(donnees) if isinstance(donnees, (str, bytes)) else donnees
    except (ValueError, UnicodeError, TypeError) as erreur:
        raise TikwmErreur("TikWM : réponse JSON invalide.") from erreur
    if not isinstance(objet, dict):
        raise TikwmErreur("TikWM : réponse mal formée.")
    code = objet.get("code")
    if str(code) == "429":
        raise TikwmRefus429("TikWM : code 429 dans la réponse du service.")
    if code not in (0, "0"):
        raise TikwmErreur(f"TikWM : code de réponse non réussi ({code}).")
    page = objet.get("data")
    if not isinstance(page, dict) or not isinstance(page.get("videos"), list):
        raise TikwmErreur("TikWM : liste videos absente de la réponse.")
    return page


def _compteur(valeur):
    """Préserver la distinction entre zéro constaté et donnée manquante."""
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, int) and valeur >= 0:
        return valeur
    if isinstance(valeur, str) and valeur.strip().isdecimal():
        return int(valeur.strip())
    return None


def _fiche(video, compte):
    """Vérifier l'identité du média avant l'ajout de la publication."""
    if not isinstance(video, dict) or not isinstance(video.get("author"), dict):
        return None
    try:
        auteur = normaliser_compte(
            video["author"].get("unique_id") or video["author"].get("uniqueId") or "")
    except (TypeError, AttributeError, ValueError):
        return None
    if auteur != compte:
        return None
    identifiant = str(video.get("video_id") or video.get("id") or "")
    if not re.fullmatch(r"\d{5,30}", identifiant):
        return None
    # Une photo dépourvue de fichier vidéo n'est pas un MP4 à analyser.
    if video.get("images") and not video.get("play"):
        return None
    description = video.get("title")
    description = description.strip() if isinstance(description, str) else ""
    date = ""
    try:
        horodatage = int(video.get("create_time"))
        if horodatage > 0:
            date = datetime.fromtimestamp(horodatage, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    engagement = {}
    for nom, cle in {
        "vues": "play_count", "likes": "digg_count",
        "commentaires": "comment_count", "partages": "share_count",
        "favoris": "collect_count",
    }.items():
        nombre = _compteur(video.get(cle))
        if nombre is not None:
            engagement[nom] = {"valeur": nombre, "brut": str(video[cle])}
    return {
        "id": identifiant,
        "url": f"https://www.tiktok.com/@{compte}/video/{identifiant}",
        "author": compte,
        "description": description,
        "created_at": date,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "hashtags": list(dict.fromkeys(re.findall(r"#(\w+)", description))),
        "engagement": engagement, "source": "tikwm_tiers",
        "status": "ok" if description else "empty_caption", "error": "",
    }


def collecter_videos_presse_tikwm(compte, limite, rapport, *,
                                 check=None, progress=None, obtenir=None, pause=None):
    """Paginer TikWM par unique_id, avec contrôle des auteurs et doublons.

    obtenir et pause sont injectables pour les tests sans accès Internet.
    Aucune requête n'est émise vers TikTok par ce moteur.
    """
    compte = normaliser_compte(compte)
    limite = max(1, min(int(limite), 1000))
    check = check or (lambda: None)
    obtenir = obtenir or _obtenir
    pause = pause or time.sleep
    urls, metadonnees = {}, {}
    curseur = "0"
    curseurs_vus = set()
    pages_stagnantes = 0
    rapport.update(
        compte_attendu=compte, mode_decouverte="tikwm_profil",
        requete_recherche=f"@{compte} : vidéos paginées (TikWM)",
        navigation_publications="tikwm_profil",
        url_rubrique_publications=f"https://www.tiktok.com/@{compte}",
        pages_api=0, pages_tikwm=0, requetes_tentees=0,
        candidats_examines=0, auteurs_ecartes=0,
        discovered_urls=[], metadonnees_api={},
        collecte_partielle=True, exhaustif=False,
        fournisseur_donnees="TikWM (service tiers non officiel)",
    )
    for numero in range(1, LIMITE_PAGES + 1):
        check()
        if curseur in curseurs_vus:
            rapport["discovery_stop"] = "curseur_tikwm_repetitif"
            break
        curseurs_vus.add(curseur)
        taille = min(TAILLE_PAGE, limite - len(urls))
        if taille <= 0:
            rapport["discovery_stop"] = "limit"
            break
        adresse = URL_TIKWM + "?" + urlencode({
            "unique_id": compte, "count": taille, "cursor": curseur,
        })
        rapport["etape_api"] = "pagination_tikwm"
        rapport["requetes_tentees"] += 1
        try:
            donnees = _page(obtenir(adresse))
        except TikwmRefus429:
            rapport["discovery_stop"] = "tikwm_http_429"
            raise
        videos = donnees["videos"]
        rapport["pages_api"] = numero
        rapport["pages_tikwm"] = numero
        rapport["candidats_examines"] += len(videos)
        precedent = len(urls)
        for video in videos:
            fiche = _fiche(video, compte)
            if fiche is None:
                rapport["auteurs_ecartes"] += 1
                continue
            if fiche["id"] not in urls and len(urls) < limite:
                urls[fiche["id"]] = fiche["url"]
                metadonnees[fiche["id"]] = fiche
        rapport["discovered_urls"] = list(urls.values())
        rapport["metadonnees_api"] = dict(metadonnees)
        rapport["retenues_par_compte"] = {compte: len(urls)}
        if progress:
            progress(len(urls))
        if len(urls) >= limite:
            rapport["discovery_stop"] = "limit"
            break
        pages_stagnantes = pages_stagnantes + 1 if precedent == len(urls) else 0
        if not donnees.get("hasMore"):
            rapport["discovery_stop"] = "fin_signalee_par_tikwm"
            break
        suivant = donnees.get("cursor")
        if not isinstance(suivant, (str, int)) or not str(suivant):
            rapport["discovery_stop"] = "curseur_tikwm_absent"
            break
        if pages_stagnantes >= 3:
            rapport["discovery_stop"] = "pagination_tikwm_stagnante"
            break
        curseur = str(suivant)
        pause(1.5)
    else:
        rapport["discovery_stop"] = "limite_pages_tikwm"
    rapport["collecte_partielle"] = len(urls) < limite
    return list(urls.values())
