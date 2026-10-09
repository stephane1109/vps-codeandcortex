"""CSV UTF-8, cellules neutres pour tableurs et colonnes JSON conservées."""
import csv
import json
from pathlib import Path

def exporter_csv(chemin, lignes, colonnes=None):
    lignes = list(lignes); colonnes = colonnes or sorted({k for ligne in lignes for k in ligne})
    chemin = Path(chemin); temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    with temporaire.open("w", encoding="utf-8-sig", newline="") as flux:
        ecrivain = csv.DictWriter(flux, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        ecrivain.writeheader()
        for ligne in lignes:
            valeurs = {}
            for cle in colonnes:
                valeur = ligne.get(cle)
                texte = json.dumps(valeur, ensure_ascii=False, allow_nan=False) if isinstance(valeur, (dict, list)) else "" if valeur is None else str(valeur)
                valeurs[cle] = "'" + texte if texte.lstrip().startswith(("=", "+", "-", "@")) else texte
            ecrivain.writerow(valeurs)
    temporaire.replace(chemin)
