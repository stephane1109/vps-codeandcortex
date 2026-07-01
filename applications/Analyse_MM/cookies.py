# cookies.py
# Gestion simple de cookies persistants dans le repertoire de travail de l'application.

from pathlib import Path

def info_cookies(rep_sortie: Path) -> str:
    p = Path(rep_sortie) / "cookies.txt"
    if p.exists():
        return f"Cookies présents : {p} ({p.stat().st_size} octets)"
    return "Aucun cookies.txt présent."

# Ici, l’upload et l’écriture sont gérés dans core_media.afficher_message_cookies
