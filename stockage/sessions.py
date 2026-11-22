"""Dossiers de session enrichie, sans dépendance audiovisuelle."""
import re
from pathlib import Path

def creer_dossier_session(racine, identifiant):
    if not re.fullmatch(r"[a-f0-9]{32}", identifiant): raise ValueError("Identifiant de session invalide.")
    dossier = Path(racine) / "sessions" / identifiant
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier
