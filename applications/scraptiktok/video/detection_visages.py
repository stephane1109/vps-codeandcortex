"""Détection de visages frontaux ; face caméra seulement comme indice visuel."""
def detecter_visages(images):
    import cv2
    detecteur=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
    if detecteur.empty(): return {"presence":None,"frontal_centre":None,"mesures":[],"confiance":None}
    mesures=[]
    for entree in images:
        image=entree["image"]; h,w=image.shape[:2]
        boites=detecteur.detectMultiScale(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),scaleFactor=1.1,minNeighbors=5,minSize=(24,24))
        centre=any(abs((x+largeur/2)/w-.5)<.25 and largeur*hauteur/(w*h)>.03 for x,y,largeur,hauteur in boites)
        mesures.append({"temps_s":entree["temps_s"],"boites":[list(map(int,b)) for b in boites],"frontal_centre":bool(centre)})
    return {"presence":any(m["boites"] for m in mesures) if mesures else None,
            "frontal_centre":sum(m["frontal_centre"] for m in mesures)/len(mesures) if mesures else None,
            "mesures":mesures,"confiance":None,"limite":"Un visage frontal ne prouve pas une adresse au spectateur."}
