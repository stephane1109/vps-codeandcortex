"""Gestion des refus HTTP 429 de l'API web TikTok.

Un délai de blocage n'est appliqué QUE lorsqu'un Retry-After explicite a
été envoyé par TikTok. Sinon, afficher l'échec sans fabriquer une heure de
restriction. Les anciennes pauses locales sont ignorées en lecture.
Ne modifie ni les tickets Redis Home ni les cookies TikTok.
"""
import fcntl
import json
import os
from pathlib import Path
import time


def _chemins():
    repertoire = Path(os.getenv("DATA_DIR") or Path.cwd() / "data")
    return repertoire / "tiktok_api_429.json", repertoire / "tiktok_api_429.lock"


def _etat_inactif(*, ancien_429=False, origine=None):
    resultat = {
        "actif": False,
        "quota_officiel_applicable": False,
        "retry_after_explicite": False,
    }
    if ancien_429:
        resultat.update(
            ancien_429_sans_delai=True,
            origine=origine or "sans_retry_after",
            message="TikTok a renvoyé HTTP 429 sans indiquer de durée. "
                    "Aucune pause d'une heure n'est imposée par ScrapTikTok.",
        )
    return resultat


def _lire(fichier, maintenant):
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(contenu, dict):
        return None
    origine = str(contenu.get("origine") or "pause_locale")
    # La version v5 créait une pause locale d'une heure sans preuve de durée
    # côté TikTok. Elle ne doit pas bloquer les utilisateurs après correction.
    if origine != "retry_after_tiktok":
        return _etat_inactif(ancien_429=True, origine=origine)
    try:
        fin = float(contenu.get("jusqua", 0))
    except (TypeError, ValueError):
        return None
    if fin <= maintenant:
        return _etat_inactif()
    return {
        "actif": True,
        "restant_secondes": max(1, int(fin - maintenant + 0.999)),
        "jusqua": int(fin),
        "origine": origine,
        "retry_after_explicite": True,
        "quota_officiel_applicable": False,
    }


def consulter_limitation(*, maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    fichier, verrou = _chemins()
    if not fichier.parent.exists():
        return _etat_inactif()
    try:
        with verrou.open("a+") as flux:
            fcntl.flock(flux, fcntl.LOCK_SH)
            etat = _lire(fichier, maintenant)
    except OSError:
        etat = None
    return etat or _etat_inactif()


def enregistrer_limitation(retry_after=None, *, maintenant=None):
    """Enregistrer le 429, ne bloquer que sur Retry-After explicite.

    Sans Retry-After, l'application interrompt la collecte qui a échoué,
    mais ne planifie aucune relance ni ne crée un blocage arbitraire.
    Un Retry-After déjà actif ne peut pas être raccourci.
    """
    maintenant = time.time() if maintenant is None else maintenant
    try:
        delai = int(retry_after)
    except (TypeError, ValueError):
        delai = None
    valable = delai is not None and 0 < delai <= 86400
    fichier, verrou = _chemins()
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with verrou.open("a+") as flux:
        fcntl.flock(flux, fcntl.LOCK_EX)
        precedent = _lire(fichier, maintenant)
        if precedent and precedent.get("actif"):
            fin_precedente = precedent["jusqua"]
        else:
            fin_precedente = 0
        if valable:
            fin = max(maintenant + delai, fin_precedente)
            origine = "retry_after_tiktok"
        elif fin_precedente > maintenant:
            fin = fin_precedente
            origine = "retry_after_tiktok"
        else:
            fin = maintenant
            origine = "sans_retry_after"
        temporaire = fichier.with_suffix(".tmp")
        temporaire.write_text(
            json.dumps({"jusqua": int(fin), "origine": origine,
                        "dernier_429": int(maintenant)}),
            encoding="utf-8",
        )
        temporaire.replace(fichier)
    return consulter_limitation(maintenant=maintenant)
