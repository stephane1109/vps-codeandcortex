"""Verrou de précaution HTTP 429 partagé via le volume persistant ScrapTikTok.

Ne modifie ni les tickets Redis de la Home ni les cookies TikTok. Le quota
officiel TikTok v2 ne s'applique PAS à l'API interne /api/creator/item_list.
"""
import fcntl
import json
import os
from pathlib import Path
import time


def _chemins():
    repertoire = Path(os.getenv("DATA_DIR") or Path.cwd() / "data")
    return repertoire / "tiktok_api_429.json", repertoire / "tiktok_api_429.lock"


def pause_par_defaut():
    """Politique locale : une heure par défaut, PAS une restriction TikTok connue."""
    try:
        secondes = int(os.getenv("SCRAPTIKTOK_API_429_PAUSE_SECONDS", "3600"))
    except (TypeError, ValueError):
        secondes = 3600
    return max(60, min(86400, secondes))


def _lire(fichier, maintenant):
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(contenu, dict):
        return None
    try:
        fin = float(contenu.get("jusqua", 0))
    except (TypeError, ValueError):
        return None
    if fin <= maintenant:
        return None
    reste = max(1, int(fin - maintenant + 0.999))
    return {
        "actif": True,
        "restant_secondes": reste,
        "jusqua": int(fin),
        "origine": str(contenu.get("origine") or "pause_locale"),
        "pause_defaut_secondes": pause_par_defaut(),
        "quota_officiel_applicable": False,
    }


def consulter_limitation(*, maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    fichier, verrou = _chemins()
    if not fichier.parent.exists():
        return {"actif": False, "pause_defaut_secondes": pause_par_defaut(),
                "quota_officiel_applicable": False}
    try:
        with verrou.open("a+") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            etat = _lire(fichier, maintenant)
    except OSError:
        etat = None
    return etat or {"actif": False, "pause_defaut_secondes": pause_par_defaut(),
                    "quota_officiel_applicable": False}


def enregistrer_limitation(retry_after=None, *, maintenant=None):
    """Respecter Retry-After en secondes ou la politique locale de précaution.

    Ne jamais réduire une pause en cours à la suite d'un nouveau refus.
    Aucun essai automatique pendant la période de repos.
    """
    maintenant = time.time() if maintenant is None else maintenant
    try:
        delai = int(retry_after)
    except (TypeError, ValueError):
        delai = None
    valable = delai is not None and 0 < delai <= 86400
    attente = delai if valable else pause_par_defaut()
    fichier, verrou = _chemins()
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with verrou.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        precedent = _lire(fichier, maintenant)
        fin = max(maintenant + attente, precedent["jusqua"] if precedent else 0)
        origine = "retry_after_tiktok" if valable else "pause_locale"
        if precedent and precedent["jusqua"] > maintenant + attente:
            origine = precedent["origine"]
        temporaire = fichier.with_suffix(".tmp")
        temporaire.write_text(
            json.dumps({"jusqua": int(fin), "origine": origine}),
            encoding="utf-8",
        )
        temporaire.replace(fichier)
    return consulter_limitation(maintenant=maintenant)
