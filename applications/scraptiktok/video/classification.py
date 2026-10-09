"""Règles visuelles transparentes, sans inférence de genre journalistique."""
def classer_format(indicateurs):
    visage=indicateurs.get("visages",{}).get("frontal_centre")
    texte=indicateurs.get("texte",{}).get("presence")
    coupes=indicateurs.get("plans",{}).get("coupes")
    if visage is not None and visage>=0.5: return {"valeur":"visage_frontal","confiance":None,"regle":"visage frontal centré dans au moins la moitié des images analysées"}
    if texte: return {"valeur":"texte_incruste","confiance":indicateurs["texte"].get("confiance"),"regle":"mots OCR de confiance >=60"}
    if coupes is not None and coupes>=3: return {"valeur":"montage_multiplans","confiance":None,"regle":"au moins trois coupes détectées sur l’échantillon"}
    return {"valeur":"indetermine","confiance":None,"regle":"indices insuffisants"}
