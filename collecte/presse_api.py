"""Découverte de vidéos publiques TikTok par secUid, sans sélecteurs de page.

Méthode inspirée de bajaam/tt-dlp (MIT) : lire l'identité depuis
/embed/@compte puis parcourir /api/creator/item_list/ avec un curseur
temporel, comme le fait TikTok sur ses profils.

N'effectue ni téléchargement MP4, ni génération de signature, ni contournement
d'authentification. En cas de restriction TikTok, le diagnostic est explicite.
"""
import html
import json
import os
from pathlib import Path
import random
import re
import time
from http.cookiejar import MozillaCookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from .verification_comptes import normaliser_compte

HOTE = "https://www.tiktok.com"
SCRIPT_EMBED = re.compile(
    r'<script[^>]*id=["\']__FRONTITY_CONNECT_STATE__["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
SECUid = re.compile(r"^[A-Za-z0-9_+=.-]{15,256}$")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
MAX_PAGES = 90
MAX_BYTES = 4_000_000


class PresseApiError(RuntimeError):
    """Erreur de pagination TikTok, à rapporter sans annoncer de faux total."""


def _client():
    """Ouvrir exclusivement tiktok.com ; les cookies restent optionnels et secrets."""
    cookies = os.getenv("SCRAPTIKTOK_COOKIES_FILE", "").strip()
    if not cookies:
        return build_opener()
    chemin = Path(cookies)
    if not chemin.is_file():
        raise PresseApiError("Fichier de cookies TikTok configuré mais introuvable.")
    jar = MozillaCookieJar(str(chemin))
    try:
        jar.load(ignore_discard=True, ignore_expires=False)
    except (OSError, ValueError) as erreur:
        raise PresseApiError("Fichier de cookies TikTok illisible ou invalide.") from erreur
    return build_opener(HTTPCookieProcessor(jar))


def _obtenir(client, url, *, referer=None, timeout=20):
    entetes = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    if referer:
        entetes["Referer"] = referer
    try:
        with client.open(Request(url, headers=entetes), timeout=timeout) as reponse:
            contenu = reponse.read(MAX_BYTES + 1)
            if len(contenu) > MAX_BYTES:
                raise PresseApiError("Réponse TikTok trop volumineuse pour une page.")
            return contenu
    except HTTPError as erreur:
        raise PresseApiError(f"TikTok HTTP {erreur.code} : accès aux publications refusé.") from erreur
    except (URLError, OSError, TimeoutError) as erreur:
        raise PresseApiError("TikTok inaccessible : échec réseau ou délai dépassé.") from erreur


def extraire_identite_embed(page, compte):
    """Résoudre l'identifiant stable (secUid) depuis l'embed public du média."""
    if isinstance(page, bytes):
        page = page.decode("utf-8", "replace")
    match = SCRIPT_EMBED.search(page)
    if not match:
        raise PresseApiError("TikTok ne fournit pas l'identité secUid sur son embed public.")
    try:
        etat = json.loads(html.unescape(match.group(1)))
        racine = etat["source"]["data"]
        infos = racine.get(f"/embed/@{compte}") or racine.get(f"/embed/@{compte}/")
        info = infos["userInfo"]
    except (ValueError, KeyError, TypeError) as erreur:
        raise PresseApiError("Données d'identité du média indisponibles sur l'embed.") from erreur
    if not isinstance(info, dict):
        raise PresseApiError("Métadonnées d'identité TikTok mal formées.")
    auteur = info.get("uniqueId") or info.get("unique_id")
    try:
        auteur = normaliser_compte(auteur)
    except (TypeError, ValueError) as erreur:
        raise PresseApiError("Identité du média absente des données TikTok.") from erreur
    if auteur != compte:
        raise PresseApiError("L'embed renvoie un autre média ; collecte refusée.")
    if info.get("privateAccount"):
        raise PresseApiError("Le compte TikTok est privé.")
    secuid = str(info.get("secUid") or info.get("sec_uid") or "")
    if not SECUid.fullmatch(secuid):
        raise PresseApiError("secUid du média introuvable ou invalide.")
    return secuid


def extraire_page_createur(donnees, compte, secuid):
    """Valider l'auteur de chaque vidéo, même sans légende, et le curseur."""
    if not isinstance(donnees, dict):
        raise PresseApiError("Réponse du profil non JSON.")
    code = donnees.get("statusCode", donnees.get("status_code", 0))
    if code not in (None, 0, "0"):
        raise PresseApiError(f"TikTok refuse la liste du média (statut {code}).")
    objets = donnees.get("itemList", [])
    if not isinstance(objets, list):
        raise PresseApiError("Réponse TikTok sans liste de publications exploitable.")
    nouveaux, temps = [], []
    for item in objets:
        if not isinstance(item, dict):
            continue
        auteur = item.get("author")
        if not isinstance(auteur, dict):
            continue
        nom = auteur.get("uniqueId") or auteur.get("unique_id")
        uid = auteur.get("secUid") or auteur.get("sec_uid")
        # Ne jamais mélanger les vidéos de plusieurs médias.
        if uid and uid != secuid:
            continue
        try:
            if normaliser_compte(nom) != compte:
                continue
        except (ValueError, TypeError):
            continue
        identifiant = str(item.get("id") or "")
        if not identifiant.isdecimal() or not isinstance(item.get("video"), dict):
            continue
        nouveaux.append(f"{HOTE}/@{compte}/video/{identifiant}")
        try:
            horodatage = int(item.get("createTime") or 0)
        except (TypeError, ValueError):
            horodatage = 0
        if horodatage > 0:
            temps.append(horodatage)
    # TikTok renvoie hasMorePrevious pour les anciennes pages de profils,
    # contrairement aux résultats de recherche qui utilisent hasMore.
    suite = donnees.get("hasMorePrevious", donnees.get("hasMore"))
    return {
        "urls": list(dict.fromkeys(nouveaux)),
        "suite": suite in (True, 1, "1", "true"),
        "plus_ancienne": min(temps) * 1000 if temps else None,
        "nombre_brut": len(objets),
    }


def collecter_videos_presse_api(compte, limite, rapport, *, check=None,
                               progress=None, client=None, clock=None, pause=None):
    """Résoudre un média et énumérer ses vidéos sans inspecter l'onglet HTML.

    Les dépendances injectables client/clock/pause servent aux tests sans réseau.
    """
    compte = normaliser_compte(compte)
    check = check or (lambda: None)
    clock = clock or time.time
    pause = pause or time.sleep
    client = client if client is not None else _client()
    limite = max(1, min(int(limite), 1000))
    referer = f"{HOTE}/@{compte}"
    rapport.update(
        mode_decouverte="api_profil_secuid", compte_attendu=compte,
        requete_recherche=f"@{compte} : liste vidéos paginée (secUid)",
        url_rubrique_publications=referer,
        navigation_publications="api_liste_createur",
        pages_api=0, discovered_urls=[], collecte_partielle=True,
        exhaustif=False,
    )
    check()
    page_embed = _obtenir(client, f"{HOTE}/embed/@{compte}", referer=referer)
    secuid = extraire_identite_embed(page_embed, compte)
    rapport["secuid_resolu"] = True  # jamais afficher la valeur dans les logs
    cursor = int(clock()) * 1000
    liens = {}
    pages_vides = 0
    device_id = str(random.randint(7250000000000000000, 7325099899999994577))
    for numero in range(1, min(MAX_PAGES, (limite // 15) + 15) + 1):
        check()
        # Paramètres de client web inspirés du client MIT tt-dlp v1.4.
        # Les champs de contexte du navigateur font partie de la requête
        # ordinaire observée, sans forger de signature anti-bot.
        params = {
            "aid": "1988",
            "app_language": "en",
            "app_name": "tiktok_web",
            "browser_language": "en-US",
            "browser_name": "Mozilla",
            "browser_online": "true",
            "browser_platform": "Win32",
            "browser_version": "5.0 (Windows)",
            "channel": "tiktok_web",
            "cookie_enabled": "true",
            "count": "15",
            "cursor": str(cursor),
            "device_id": device_id,
            "device_platform": "web_pc",
            "focus_state": "true",
            "from_page": "user",
            "history_len": "2",
            "is_fullscreen": "false",
            "is_page_visible": "true",
            "language": "en",
            "os": "windows",
            "priority_region": "",
            "referer": "",
            "region": "US",
            "screen_height": "1080",
            "screen_width": "1920",
            "secUid": secuid,
            "type": "1",
            "tz_name": "UTC",
            "verifyFp": "verify_" + "".join(
                random.choices("0123456789abcdef", k=7)),
            "webcast_language": "en",
        }
        url = f"{HOTE}/api/creator/item_list/?{urlencode(params)}"
        try:
            contenu = _obtenir(client, url, referer=referer)
            donnees = json.loads(contenu)
        except (ValueError, TypeError) as erreur:
            raise PresseApiError("Liste de vidéos TikTok : réponse JSON invalide.") from erreur
        page = extraire_page_createur(donnees, compte, secuid)
        rapport["pages_api"] = numero
        ancien = len(liens)
        for video in page["urls"]:
            if len(liens) >= limite:
                break
            identifiant = video.rsplit("/", 1)[-1]
            liens.setdefault(identifiant, video)
        rapport["discovered_urls"] = list(liens.values())
        rapport["candidats_examines"] = len(liens)
        rapport["retenues_par_compte"] = {compte: len(liens)}
        if progress:
            progress(len(liens))
        if len(liens) >= limite:
            rapport["discovery_stop"] = "limit"
            break
        pages_vides = pages_vides + 1 if len(liens) == ancien else 0
        if not page["suite"]:
            rapport["discovery_stop"] = "fin_signalee_par_tiktok"
            break
        if pages_vides >= 3:
            rapport["discovery_stop"] = "pagination_stagnante"
            break
        prochain = page["plus_ancienne"] or (cursor - 7 * 86_400_000)
        if prochain >= cursor:
            prochain = cursor - 7 * 86_400_000
        if prochain <= 0:
            rapport["discovery_stop"] = "curseur_invalide"
            break
        cursor = prochain
        pause(1.5)
    else:
        rapport["discovery_stop"] = "budget_pages_api"
    rapport["collecte_partielle"] = len(liens) < limite
    return list(liens.values())
