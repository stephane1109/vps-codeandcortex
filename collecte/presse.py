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

# Codage disjonctif des comptes connus, commun au TXT, aux CSV et aux collectes.
# Une absence de correspondance est une donnée manquante, et non un zéro.
from functools import lru_cache

CODES_CATEGORIES_PRESSE = {
    "presse_nationale": "presse_nationale",
    "presse_regionale": "presse_regio_dpt",
    "presse_independante": "presse_indep",
    "autres_medias": "presse_autre",
}


@lru_cache(maxsize=1)
def index_categories_presse():
    """Associer les identifiants TikTok aux catégories de l'inventaire officiel local."""
    return {media["compte"].casefold(): media["categorie"]
            for media in charger_inventaire()}


def categorie_presse_publication(publication):
    """Déterminer la catégorie à partir de l'auteur réel, quel que soit le mode."""
    if not isinstance(publication, dict):
        return None
    auteur = publication.get("author") or publication.get("profil")
    if not isinstance(auteur, str) or not auteur.strip():
        return None
    categorie = index_categories_presse().get(auteur.strip().lstrip("@").casefold())
    return categorie if categorie in CODES_CATEGORIES_PRESSE else None


def code_presse_publication(publication):
    """Renvoyer l'unique variable illustrative IRaMuTeQ applicable."""
    return CODES_CATEGORIES_PRESSE.get(categorie_presse_publication(publication))


def colonnes_categories_presse(publication):
    """Produire quatre colonnes : 1 pour la catégorie, 0 pour les autres, vide si inconnue."""
    code = code_presse_publication(publication)
    return {variable: (int(variable == code) if code else None)
            for variable in CODES_CATEGORIES_PRESSE.values()}
