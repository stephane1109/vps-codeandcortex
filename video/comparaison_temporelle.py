"""Alignement monotone avec vitesse et lacunes bornées, indépendant des embeddings."""
def aligner_sequences(correspondances, seuils):
    points = sorted(correspondances,key=lambda c:(c["temps_a"],c["temps_b"]))
    if not points: return {"detecte":False,"segments":[],"confiance":None,"statut":"aucune_correspondance"}
    longueurs = [1]*len(points); parents = [-1]*len(points)
    for i,p in enumerate(points):
        for j in range(i-1,-1,-1):
            q = points[j]; da=p["temps_a"]-q["temps_a"]; db=p["temps_b"]-q["temps_b"]
            if da>seuils["ecart_max_s"]: break
            if da<=0 or db<=0 or db>seuils["ecart_max_s"]: continue
            if not seuils["vitesse_min"] <= db/da <= seuils["vitesse_max"]: continue
            if longueurs[j]+1>longueurs[i]: longueurs[i]=longueurs[j]+1; parents[i]=j
    fins = sorted(range(len(points)),key=lambda i:longueurs[i],reverse=True)
    segments=[]; utilises=set()
    for fin in fins:
        chaine=[]; i=fin
        while i>=0: chaine.append(i); i=parents[i]
        chaine.reverse()
        if any(i in utilises for i in chaine): continue
        debut=points[chaine[0]]; dernier=points[chaine[-1]]
        da=dernier["temps_a"]-debut["temps_a"]; db=dernier["temps_b"]-debut["temps_b"]
        # Les logos fixes / images répétées ne constituent pas une preuve de séquence.
        diversite = len({points[i].get("phash_a") for i in chaine})
        if len(chaine)<seuils["images_min"] or min(da,db)<seuils["duree_min_s"] or diversite<2: continue
        utilises.update(chaine)
        segments.append({"debut_a_s":debut["temps_a"],"fin_a_s":dernier["temps_a"],"debut_b_s":debut["temps_b"],"fin_b_s":dernier["temps_b"],
            "images":len(chaine),"vitesse_b_sur_a":db/da,"confiance":sum(points[i]["confiance"] for i in chaine)/len(chaine),"correspondances":[points[i] for i in chaine]})
    return {"detecte":bool(segments),"segments":segments,"confiance":max((s["confiance"] for s in segments),default=None),"statut":"reemploi_detecte" if segments else "preuve_temporelle_insuffisante"}
