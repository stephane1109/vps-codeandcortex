"""Ratios descriptifs ; données manquantes et dénominateurs nuls préservés."""
def calculer_ratios(engagement):
    valeurs = {k:v.get("valeur") for k,v in engagement.items()}
    vues = valeurs.get("vues")
    resultat = {}
    for nom in ("likes","commentaires","partages","favoris"):
        valeur = valeurs.get(nom)
        resultat[nom + "_par_vue"] = valeur / vues if vues and valeur is not None else None
    connus = [valeurs.get(k) for k in ("likes","commentaires","partages")]
    resultat["interactions_par_vue"] = sum(connus)/vues if vues and all(v is not None for v in connus) else None
    return resultat
