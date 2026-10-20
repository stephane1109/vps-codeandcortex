"""Composantes connexes de réemploi ; transitivité, pas identité de tous les membres."""
TYPES_REEMPLOI={"fichier_identique","reemploi_sequence","videos_visuellement_quasi_identiques"}

def regrouper_videos(comparaisons):
    parents={}
    def racine(x):
        parents.setdefault(x,x)
        while parents[x]!=x: parents[x]=parents[parents[x]]; x=parents[x]
        return x
    for c in sorted(comparaisons,key=lambda c:(c["a"],c["b"])):
        if c["type"] in TYPES_REEMPLOI: parents[racine(c["b"])]=racine(c["a"])
    groupes={}
    for identifiant in parents: groupes.setdefault(racine(identifiant),[]).append(identifiant)
    # Un identifiant déterministe évite une renumérotation à chaque ordre de lecture.
    import hashlib
    return [{"id":"groupe_"+hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()[:12],
             "publications":sorted(ids),"relation":"composante_connexe_reemploi",
             "liens_directs":[{"a":c["a"],"b":c["b"]} for c in comparaisons
                              if c["type"] in TYPES_REEMPLOI and c["a"] in ids and c["b"] in ids]}
            for ids in sorted(groupes.values(),key=lambda ids:sorted(ids))]
