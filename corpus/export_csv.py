"""CSV UTF-8, cellules neutres pour tableurs et colonnes JSON conservées."""
import csv
import json
import io
from pathlib import Path

def serialiser_csv(lignes, colonnes=None):
    """Produit le même CSV protégé pour un téléchargement ou un fichier."""
    lignes = list(lignes); colonnes = colonnes or sorted({k for ligne in lignes for k in ligne})
    with io.StringIO(newline="") as flux:
        ecrivain = csv.DictWriter(flux, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        ecrivain.writeheader()
        for ligne in lignes:
            valeurs = {}
            for cle in colonnes:
                valeur = ligne.get(cle)
                texte = json.dumps(valeur, ensure_ascii=False, allow_nan=False) if isinstance(valeur, (dict, list)) else "" if valeur is None else str(valeur)
                valeurs[cle] = "'" + texte if texte.lstrip().startswith(("=", "+", "-", "@")) else texte
            ecrivain.writerow(valeurs)
        return flux.getvalue()

def exporter_csv(chemin, lignes, colonnes=None):
    chemin = Path(chemin); temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(serialiser_csv(lignes, colonnes), encoding="utf-8-sig", newline="")
    temporaire.replace(chemin)
