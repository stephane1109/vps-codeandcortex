"""Composantes connexes de réemploi ; transitivité, pas identité de tous les membres."""
TYPES_REEMPLOI={"fichier_identique","reemploi_sequence","videos_visuellement_quasi_identiques"}

def regrouper_videos(comparaisons):
    parents={}
    def racine(x):
        parents.setdefault(x,x)
        while parents[x]!=x: parents[x]=parents[parents[x]]; x=parents[x]
        return x
    for c in comparaisons:
        if c["type"] in TYPES_REEMPLOI: parents[racine(c["b"])]=racine(c["a"])
    groupes={}
    for identifiant in parents: groupes.setdefault(racine(identifiant),[]).append(identifiant)
    return [{"id":f"groupe_{i+1}","publications":sorted(ids),"relation":"composante_connexe_reemploi"} for i,ids in enumerate(groupes.values())]
