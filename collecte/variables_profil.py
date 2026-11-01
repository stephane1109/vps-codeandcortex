"""Validations des variables illustratives de profil TikTok."""
import re


def normaliser_region(valeur):
    """Renvoyer un code pays officiel ou None, jamais un lieu supposé."""
    if not isinstance(valeur, str):
        return None
    code = valeur.strip().upper()
    return code if re.fullmatch(r"[A-Z]{2}", code) else None


def modalite_verification(valeur):
    """Distinguer la certification négative d'une donnée manquante."""
    if valeur is True:
        return "oui"
    if valeur is False:
        return "non"
    return "indetermine"
