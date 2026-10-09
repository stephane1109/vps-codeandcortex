"""Circulation descriptive inter-médias, sans attribution automatique d’une source."""
from datetime import datetime
from video.groupes_visuels import TYPES_REEMPLOI

def analyser_circulation(publications, comparaisons):
    table={p["id"]:p for p in publications}; lignes=[]
    for c in comparaisons:
        if c["type"] not in TYPES_REEMPLOI: continue
        a=table[c["a"]]; b=table[c["b"]]
        ma=a.get("media_id") or a.get("author"); mb=b.get("media_id") or b.get("author")
        if not ma or not mb or ma==mb: continue
        premiere=None
        try:
            da=datetime.fromisoformat(a["created_at"]); db=datetime.fromisoformat(b["created_at"])
            if da!=db: premiere=a["id"] if da<db else b["id"]
        except (KeyError,ValueError,TypeError): pass
        lignes.append({"a":a["id"],"b":b["id"],"media_a":ma,"media_b":mb,"premiere_publication_observee":premiere,"origine_prouvee":False,"type":c["type"],"segments":c.get("segments",[])})
    return lignes
