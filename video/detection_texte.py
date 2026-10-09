"""OCR facultatif ; confiance native Tesseract conservée, sans traduction."""
import shutil

def detecter_texte(images, parametres):
    if not parametres["ocr"]: return {"statut":"desactive","presence":None,"mesures":[],"confiance":None}
    if not shutil.which("tesseract"): return {"statut":"dependance_absente","presence":None,"mesures":[],"confiance":None}
    import pytesseract
    import cv2
    mesures=[]
    for entree in images[::max(1,len(images)//parametres["ocr_images_max"])][:parametres["ocr_images_max"]]:
        donnees=pytesseract.image_to_data(cv2.cvtColor(entree["image"],cv2.COLOR_BGR2RGB),lang=parametres["ocr_langues"],output_type=pytesseract.Output.DICT,timeout=15)
        mots=[{"texte":t,"confiance":float(donnees["conf"][i]),"boite":[donnees[k][i] for k in ("left","top","width","height")]} for i,t in enumerate(donnees["text"]) if t.strip()]
        mesures.append({"temps_s":entree["temps_s"],"mots":mots})
    fiables=[m for ligne in mesures for m in ligne["mots"] if m["confiance"]>=60]
    return {"statut":"mesure","presence":bool(fiables),"mesures":mesures,"confiance":sum(m["confiance"] for m in fiables)/len(fiables)/100 if fiables else None}
