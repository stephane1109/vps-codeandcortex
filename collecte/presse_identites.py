"""Cache local d'identités de médias publics (pas de cookies ni d'accès privé).

Réutilise un secUid confirmé par une page de publications appartenant au
compte demandé. Ne débloque aucune requête refusée par TikTok.
"""
import fcntl
import json
import os
import re
import time
from pathlib import Path

from .verification_comptes import normaliser_compte

_SECUID = re.compile(r"^[A-Za-z0-9_-]{20,200}$")
_DUREE = 30 * 86400


def _chemins():
    repertoire = Path(os.getenv("DATA_DIR") or Path.cwd() / "data")
    return repertoire / "presse_identites.json", repertoire / "presse_identites.lock"


def _lire(fichier):
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        return contenu if isinstance(contenu, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def lire_identite(compte, *, maintenant=None):
    """Retrouver seulement une identité publique récente et bien formée."""
    compte = normaliser_compte(compte)
    fichier, verrou = _chemins()
    if not fichier.parent.is_dir():
        return None
    try:
        with verrou.open("a+") as flux:
            fcntl.flock(flux, fcntl.LOCK_SH)
            entree = _lire(fichier).get(compte)
    except OSError:
        return None
    if not isinstance(entree, dict):
        return None
    secuid = entree.get("secuid")
    horodatage = entree.get("verifie_le")
    maintenant = time.time() if maintenant is None else maintenant
    if not isinstance(secuid, str) or not _SECUID.fullmatch(secuid):
        return None
    if not isinstance(horodatage, (float, int)) or not 0 <= maintenant - horodatage <= _DUREE:
        return None
    return secuid


def enregistrer_identite(compte, secuid, *, maintenant=None):
    """Enregistrer une identité déjà corroborée par les vidéos de ce média."""
    compte = normaliser_compte(compte)
    if not isinstance(secuid, str) or not _SECUID.fullmatch(secuid):
        raise ValueError("secUid invalide")
    maintenant = time.time() if maintenant is None else maintenant
    fichier, verrou = _chemins()
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with verrou.open("a+") as flux:
        fcntl.flock(flux, fcntl.LOCK_EX)
        donnees = _lire(fichier)
        donnees[compte] = {"secuid": secuid, "verifie_le": maintenant}
        # Éliminer les identités trop anciennes et mal formées pour
        # garder le fichier très petit, indépendamment du nombre de collectes.
        donnees = {
            cle: entree for cle, entree in donnees.items()
            if isinstance(entree, dict)
            and isinstance(entree.get("secuid"), str)
            and _SECUID.fullmatch(entree["secuid"])
            and isinstance(entree.get("verifie_le"), (int, float))
            and 0 <= maintenant - entree["verifie_le"] <= _DUREE
        }
        temporaire = fichier.with_suffix(".tmp")
        temporaire.write_text(json.dumps(donnees), encoding="utf-8")
        temporaire.replace(fichier)
