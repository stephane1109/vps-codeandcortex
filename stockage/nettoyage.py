"""Purge bornée aux dossiers de sessions identifiés ; sessions actives exclues."""
import re
import shutil
import time
from pathlib import Path

def nettoyer_sessions(racine, base, retention_s, actives=()):
    supprimees = []
    dossier = Path(racine) / "sessions"
    if not dossier.exists(): return supprimees
    for chemin in dossier.iterdir():
        if chemin.is_symlink() or not chemin.is_dir() or not re.fullmatch(r"[a-f0-9]{32}",chemin.name): continue
        if chemin.name in actives or time.time()-chemin.stat().st_mtime <= retention_s: continue
        shutil.rmtree(chemin); base.supprimer_session(chemin.name); supprimees.append(chemin.name)
    return supprimees
