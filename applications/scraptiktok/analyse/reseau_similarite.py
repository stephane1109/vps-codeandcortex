"""Graphe JSON : arêtes de réemploi et sémantiques explicitement séparées."""
from video.groupes_visuels import TYPES_REEMPLOI

def construire_reseau(publications, comparaisons):
    liens=[]
    for c in comparaisons:
        if c["type"] in TYPES_REEMPLOI:
            liens.append({"source":c["a"],"cible":c["b"],"type":c["type"],"score":c["confiance"],"segments":c.get("segments",[])})
        if c.get("semantiquement_similaires"):
            liens.append({"source":c["a"],"cible":c["b"],"type":"similarite_semantique","score":c["cosinus_semantique"],"preuve_reemploi":False})
    return {"noeuds":[{"id":p["id"],"media":p.get("media_id"),"date":p.get("created_at")} for p in publications],"liens":liens}
