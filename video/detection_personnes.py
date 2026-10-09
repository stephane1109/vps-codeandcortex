"""Silhouettes par HOG ; aucune identification ou attribut démographique."""
def detecter_personnes(images):
    import cv2
    detecteur=cv2.HOGDescriptor(); detecteur.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    mesures=[]
    for entree in images:
        image=entree["image"]
        if image.shape[0]<128 or image.shape[1]<64: continue
        boites,poids=detecteur.detectMultiScale(image,winStride=(8,8),padding=(8,8),scale=1.1)
        mesures.append({"temps_s":entree["temps_s"],"boites":[list(map(int,b)) for b in boites],"scores_bruts":[float(v) for v in poids]})
    return {"presence":any(m["boites"] for m in mesures) if mesures else None,"mesures":mesures,"confiance":None,"methode":"HOG, absence de détection ne prouve pas absence humaine"}
