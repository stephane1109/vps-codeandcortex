"""Validation géométrique des correspondances ORB par homographie RANSAC."""
def extraire_orb(image):
    import cv2
    gris = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    points, descripteurs = cv2.ORB_create(nfeatures=1200, edgeThreshold=15, nlevels=12, scaleFactor=1.15).detectAndCompute(gris,None)
    return {"points":[list(p.pt) for p in points], "descripteurs":descripteurs.tolist() if descripteurs is not None else [],
            "apercu":cv2.resize(gris,(64,64)).tolist(), "largeur":int(image.shape[1]),"hauteur":int(image.shape[0])}

def comparer_orb(a,b,seuils):
    import cv2
    import numpy as np
    inconnu = {"valide":False,"confiance":None,"inliers":0,"correspondances":0,"ratio_inliers":None,"couverture_a":None,"couverture_b":None,"statut":"descripteurs_insuffisants"}
    if len(a["descripteurs"]) < 4 or len(b["descripteurs"]) < 4: return inconnu
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(np.asarray(a["descripteurs"],dtype=np.uint8),np.asarray(b["descripteurs"],dtype=np.uint8),k=2)
    bons = [paire[0] for paire in matches if len(paire)==2 and paire[0].distance < seuils["orb_ratio"]*paire[1].distance]
    # Un seul appariement par point de destination pour éviter le gonflement du score.
    uniques = {}
    for match in sorted(bons,key=lambda m:m.distance): uniques.setdefault(match.trainIdx,match)
    bons = list(uniques.values())
    if len(bons)<4: return {**inconnu,"correspondances":len(bons),"statut":"sans_correspondance"}
    pa = np.float32([a["points"][m.queryIdx] for m in bons]); pb = np.float32([b["points"][m.trainIdx] for m in bons])
    cv2.setRNGSeed(0)
    matrice, masque = cv2.findHomography(pa,pb,cv2.RANSAC,seuils["ransac_pixels"])
    if matrice is None or masque is None or not np.isfinite(matrice).all(): return {**inconnu,"statut":"geometrie_indeterminee"}
    selection = masque.ravel().astype(bool); n = int(selection.sum()); ratio = n/len(bons)
    def couverture(points, largeur, hauteur):
        if len(points)<3: return 0.0
        return float(cv2.contourArea(cv2.convexHull(points)))/(largeur*hauteur)
    ca = couverture(pa[selection],a["largeur"],a["hauteur"]); cb = couverture(pb[selection],b["largeur"],b["hauteur"])
    # La diversité temporelle porte sur la zone appariée, pas sur le fond autour d'un logo.
    def empreinte_zone(donnees, points):
        from .empreintes import calculer_phash
        if 'apercu' not in donnees or len(points)<3: return None
        x0,y0 = points.min(axis=0); x1,y1 = points.max(axis=0)
        x0,x1 = int(x0*64/donnees['largeur']), min(64,int(x1*64/donnees['largeur'])+1)
        y0,y1 = int(y0*64/donnees['hauteur']), min(64,int(y1*64/donnees['hauteur'])+1)
        return calculer_phash(np.asarray(donnees['apercu'],dtype=np.uint8)[y0:y1,x0:x1]) if x1>x0 and y1>y0 else None
    valide = n>=seuils["orb_inliers_min"] and ratio>=seuils["orb_ratio_inliers"] and min(ca,cb)>=seuils["orb_couverture_min"]
    return {"valide":valide,"confiance":round(ratio*min(1,n/30),4),"inliers":n,"correspondances":len(bons),
            "ratio_inliers":ratio,"couverture_a":ca,"couverture_b":cb,"phash_zone_a":empreinte_zone(a,pa[selection]),"phash_zone_b":empreinte_zone(b,pb[selection]),"homographie":matrice.tolist(),"statut":"mesure"}
