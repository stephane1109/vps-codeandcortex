"""Charger les cookies TikTok explicitement fournis par l'administrateur.

Le fichier Netscape reste hors des exports. Aucun cookie n'est affiché,
recopié dans un rapport ou récupéré dans le navigateur personnel.
"""
import os
from pathlib import Path
import time


def charger_cookies_presse(contenu_fourni=None):
    """Accepter uniquement les cookies TikTok valides, avec une taille bornée."""
    chemin = os.getenv("SCRAPTIKTOK_COOKIES_FILE", "").strip()
    if contenu_fourni is None and not chemin:
        return []
    try:
        if contenu_fourni is None:
            with Path(chemin).open("rb") as flux:
                contenu = flux.read(1_048_577)
        else:
            contenu = contenu_fourni.encode("utf-8")
        if len(contenu) > 1_048_576:
            raise ValueError()
        lignes = contenu.decode("utf-8-sig").splitlines()
        if not lignes or "HTTP Cookie File" not in lignes[0]:
            raise ValueError()
        cookies = {}
        for ligne in lignes[1:]:
            http_seul = ligne.startswith("#HttpOnly_")
            if http_seul:
                ligne = ligne[len("#HttpOnly_"):]
            if not ligne or ligne.startswith("#"):
                continue
            domaine, sous_domaines, chemin_cookie, securise, expiration, nom, valeur = ligne.split("\t")
            hote = domaine.lstrip(".").lower()
            if hote != "tiktok.com" and not hote.endswith(".tiktok.com"):
                continue
            if (sous_domaines not in {"TRUE", "FALSE"} or securise not in {"TRUE", "FALSE"}
                    or not chemin_cookie.startswith("/") or not nom):
                raise ValueError()
            fin = int(expiration or "0")
            if fin > 0 and fin <= time.time():
                continue
            cookie = {"name": nom, "value": valeur, "domain": domaine,
                      "path": chemin_cookie, "secure": securise == "TRUE", "httpOnly": http_seul}
            if fin > 0:
                cookie["expires"] = fin
            cookies[(domaine, chemin_cookie, nom)] = cookie
        if not cookies:
            raise ValueError()
        return list(cookies.values())
    except (OSError, ValueError, UnicodeError):
        # Ne pas propager l'exception du parseur : elle pourrait contenir une ligne secrète.
        raise RuntimeError("Fichier de cookies TikTok absent, invalide, expiré ou sans cookie TikTok utilisable.") from None


def appliquer_cookies_selenium(navigateur, cookies=None):
    """Précharger les cookies avant la première navigation, sans requête ajoutée."""
    cookies = charger_cookies_presse() if cookies is None else cookies
    if cookies:
        try:
            navigateur.execute_cdp_cmd("Network.setCookies", {"cookies": cookies})
        except Exception:
            raise RuntimeError("Impossible de charger les cookies TikTok dans Selenium.") from None
    return len(cookies)
