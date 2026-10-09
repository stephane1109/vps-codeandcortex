"""Inventaire éditorial explicite et sélection de médias."""
import json
from pathlib import Path
from .verification_comptes import normaliser_compte
CONFIG = Path(__file__).resolve().parents[1] / "config"

def charger_inventaire(chemin=None):
    donnees = json.loads(Path(chemin or CONFIG / "comptes_presse.json").read_text(encoding="utf-8"))
    comptes = donnees["comptes"]
    identifiants = set()
    for compte in comptes:
        compte["compte"] = normaliser_compte(compte["compte"])
        if compte["id"] in identifiants:
            raise ValueError("Identifiant de média dupliqué dans l’inventaire.")
        identifiants.add(compte["id"])
    return comptes

def selectionner_medias(identifiants, inventaire=None):
    table = {m["id"]: m for m in (inventaire if inventaire is not None else charger_inventaire())}
    if any(i not in table for i in identifiants):
        raise ValueError("Média absent de l’inventaire.")
    return [table[i] for i in dict.fromkeys(identifiants)]
