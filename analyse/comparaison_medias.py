"""Résumé par média avec effectifs et valeurs manquantes explicites."""
from statistics import median

def comparer_medias(publications):
    groupes = {}
    for p in publications: groupes.setdefault(p.get("media_id") or p.get("author") or "indetermine", []).append(p)
    resultats = []
    for media, lignes in groupes.items():
        ligne = {"media":media,"publications":len(lignes)}
        for nom in ("vues","likes","partages","commentaires","favoris"):
            valeurs = [p.get("engagement",{}).get(nom,{}).get("valeur") for p in lignes]
            connues = [v for v in valeurs if v is not None]
            ligne[nom+"_mediane"] = median(connues) if connues else None
            ligne[nom+"_manquants"] = len(lignes)-len(connues)
        resultats.append(ligne)
    return resultats
