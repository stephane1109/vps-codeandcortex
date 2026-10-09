"""Compteurs observés : zéro n’est jamais substitué à une valeur manquante."""
import math
import re
CHAMPS = {"likes": "diggCount", "vues": "playCount", "partages": "shareCount", "commentaires": "commentCount", "favoris": "collectCount"}

def convertir_compteur(brut):
    if brut is None or isinstance(brut, bool):
        return {"valeur": None, "brut": brut, "confiance": None, "estime": False}
    if isinstance(brut, (int, float)) and math.isfinite(brut) and brut >= 0:
        return {"valeur": int(brut), "brut": brut, "confiance": 1.0, "estime": False}
    texte = str(brut).strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*([kKmMbB]?)", texte)
    if not match:
        return {"valeur": None, "brut": brut, "confiance": None, "estime": False}
    nombre, suffixe = match.groups()
    # Sans suffixe, une virgule ou un point peut être un séparateur de milliers : ambigu.
    if not suffixe and not nombre.isdecimal():
        return {"valeur": None, "brut": brut, "confiance": None, "estime": False}
    multiplicateur = {"": 1, "k": 1000, "m": 1000000, "b": 1000000000}[suffixe.lower()]
    return {"valeur": int(float(nombre.replace(",", ".")) * multiplicateur), "brut": brut,
            "confiance": 0.7 if suffixe else 1.0, "estime": bool(suffixe)}

def extraire_engagement(element=None, dom=None, date=None):
    element = element if isinstance(element,dict) else {}
    ancien = element.get("stats") if isinstance(element.get("stats"),dict) else {}
    nouveau = element.get("statsV2") if isinstance(element.get("statsV2"),dict) else {}
    stats = {**ancien, **{k:v for k,v in nouveau.items() if v is not None}}
    dom = dom if isinstance(dom,dict) else {}
    resultat = {}
    for nom, cle in CHAMPS.items():
        brut = stats.get(cle)
        source = "page_json" if brut is not None else "page_dom"
        if brut is None:
            brut = (dom or {}).get(nom)
        resultat[nom] = {**convertir_compteur(brut), "source": source if brut is not None else None,
                         "observe_le": date}
    return resultat
