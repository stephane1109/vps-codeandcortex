"""Inventaire éditorial explicite et sélection de médias."""
import json
from pathlib import Path
from .verification_comptes import normaliser_compte
CONFIG = Path(__file__).resolve().parents[1] / "config"

def charger_inventaire(chemin=None):
    donnees = json.loads(Path(chemin or CONFIG / "comptes_presse.json").read_text(encoding="utf-8"))
    comptes = donnees["comptes"]
    identifiants = set()
    noms_comptes = set()
    categories = {
        "presse_nationale", "presse_regionale",
        "presse_independante", "autres_medias",
    }
    for compte in comptes:
        compte["compte"] = normaliser_compte(compte["compte"])
        if compte["id"] in identifiants:
            raise ValueError("Identifiant de média dupliqué dans l’inventaire.")
        if compte["compte"] in noms_comptes:
            raise ValueError("Compte TikTok dupliqué dans l’inventaire.")
        if compte.get("categorie") not in categories:
            raise ValueError("Catégorie éditoriale inconnue dans l’inventaire.")
        identifiants.add(compte["id"])
        noms_comptes.add(compte["compte"])
    return comptes

def selectionner_medias(identifiants, inventaire=None):
    table = {m["id"]: m for m in (inventaire if inventaire is not None else charger_inventaire())}
    if any(i not in table for i in identifiants):
        raise ValueError("Média absent de l’inventaire.")
    return [table[i] for i in dict.fromkeys(identifiants)]
