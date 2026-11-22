"""Écriture atomique des données structurées."""
import json
from pathlib import Path

def exporter_json(chemin, contenu):
    chemin = Path(chemin); chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporaire.replace(chemin)
