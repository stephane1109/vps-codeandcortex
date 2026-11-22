"""Vérification syntaxique et observation du profil, sans déduire sa propriété."""
import re
from urllib.parse import urlsplit

def normaliser_compte(valeur):
    valeur = valeur.strip()
    if valeur.startswith("https://"):
        url = urlsplit(valeur)
        if url.hostname not in {"www.tiktok.com", "tiktok.com"} or not re.fullmatch(r"/@[A-Za-z0-9_.]+/?", url.path):
            raise ValueError("Indiquez un identifiant ou une URL de profil TikTok.")
        valeur = url.path.strip("/")
    valeur = valeur.removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9_.]{2,24}", valeur) or valeur.endswith("."):
        raise ValueError("Identifiant TikTok invalide (2 à 24 lettres, chiffres, points ou tirets bas).")
    return valeur.lower()

def verifier_profil(compte, instantane):
    attendu = normaliser_compte(compte)
    observe = instantane.get("uniqueId")
    try: concordant = normaliser_compte(observe) == attendu if observe else None
    except ValueError: concordant = False
    return {"compte": attendu, "identifiant_observe": observe, "concordant": concordant,
            "badge_tiktok": instantane.get("verified"), "proprietaire_editorial": "indetermine"}


def observer_profil(navigateur, compte):
    """Lit uniquement les données de profil publiées dans la page courante."""
    import json
    from scraptiktok import canonical_post
    donnees = navigateur.execute_script("return Array.from(document.querySelectorAll('script[type=\"application/json\"]')).map(e=>e.textContent);") or []
    attendu = normaliser_compte(compte)
    def trouver(objet):
        if isinstance(objet,dict):
            if str(objet.get("uniqueId", "")).lower() == attendu: return objet
            for valeur in objet.values():
                trouve = trouver(valeur)
                if trouve: return trouve
        elif isinstance(objet,list):
            for valeur in objet:
                trouve = trouver(valeur)
                if trouve: return trouve
        return None
    for texte in donnees:
        try: profil = trouver(json.loads(texte))
        except (ValueError,TypeError,RecursionError): continue
        if profil: return verifier_profil(attendu,profil)
    return verifier_profil(attendu,{})
