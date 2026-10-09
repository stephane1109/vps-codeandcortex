"""Coupes estimées entre images échantillonnées ; pas de précision image par image."""
def detecter_plans(images, seuil=0.35):
    import cv2
    differences=[]; precedent=None
    for entree in images:
        hsv=cv2.cvtColor(entree["image"],cv2.COLOR_BGR2HSV)
        hist=cv2.calcHist([hsv],[0,1],None,[32,32],[0,180,0,256]); cv2.normalize(hist,hist)
        if precedent is not None:
            distance=float(cv2.compareHist(precedent,hist,cv2.HISTCMP_BHATTACHARYYA))
            differences.append({"temps_s":entree["temps_s"],"distance":distance,"coupe":distance>=seuil})
        precedent=hist
    return {"coupes":sum(d["coupe"] for d in differences),"mesures":differences,"seuil":seuil,"confiance":None}
