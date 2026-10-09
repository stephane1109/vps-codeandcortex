"""Mouvement apparent Farnebäck normalisé par diagonale et intervalle temporel."""
def mesurer_mouvement(images):
    import cv2
    import numpy as np
    mesures=[]
    for a,b in zip(images,images[1:]):
        precedent=cv2.cvtColor(a["image"],cv2.COLOR_BGR2GRAY); suivant=cv2.cvtColor(b["image"],cv2.COLOR_BGR2GRAY)
        if suivant.shape != precedent.shape: suivant=cv2.resize(suivant,(precedent.shape[1],precedent.shape[0]))
        flux=cv2.calcOpticalFlowFarneback(precedent,suivant,None,0.5,3,15,3,5,1.2,0)
        magnitude=np.linalg.norm(flux,axis=2); dt=b["temps_s"]-a["temps_s"]
        mesures.append({"temps_s":b["temps_s"],"pixels_medians":float(np.median(magnitude)),"normalise_par_s":float(np.median(magnitude))/(float(np.hypot(*precedent.shape))*dt) if dt>0 else None})
    connues=[m["normalise_par_s"] for m in mesures if m["normalise_par_s"] is not None]
    return {"mediane":float(np.median(connues)) if connues else None,"mesures":mesures,"confiance":None,"limite":"Coupes et déplacement de caméra peuvent influer sur le flux."}
