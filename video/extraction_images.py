"""Décodage borné en temps, nombre d’images et résolution."""
from pathlib import Path
import math
import time

def extraire_images(chemin, parametres, dossier=None, verifier=lambda: None):
    import cv2
    cv2.setNumThreads(parametres["threads"])
    capture = cv2.VideoCapture(str(chemin))
    if not capture.isOpened(): raise ValueError("Vidéo illisible.")
    images = []; debut = time.monotonic()
    try:
        fps = capture.get(cv2.CAP_PROP_FPS); nombre = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(nombre) or nombre <= 0:
            raise ValueError("Durée ou cadence vidéo indéterminée.")
        duree = nombre / fps
        maximum = min(duree,parametres["duree_max_s"])
        if dossier: Path(dossier).mkdir(parents=True,exist_ok=True)
        for numero in range(parametres["images_max"]):
            verifier()
            if time.monotonic()-debut > min(120,parametres["duree_lot_max_s"]): break
            seconde = numero*parametres["pas_images_s"]
            if seconde >= maximum: break
            capture.set(cv2.CAP_PROP_POS_MSEC, seconde*1000)
            succes, image = capture.read()
            if not succes: break
            hauteur, largeur = image.shape[:2]
            facteur = min(1,parametres["dimension_max"]/max(hauteur,largeur))
            image = cv2.resize(image,(max(1,round(largeur*facteur)),max(1,round(hauteur*facteur))))
            chemin_image = None
            if dossier:
                chemin_image = Path(dossier)/f"{numero:05d}.jpg"
                if not cv2.imwrite(str(chemin_image),image): raise OSError("Écriture d’image impossible.")
            images.append({"temps_s":seconde,"image":image,"chemin":str(chemin_image) if chemin_image else None})
        if not images: raise ValueError("Aucune image décodable.")
        fin = min(duree, images[-1]["temps_s"]+parametres["pas_images_s"])
        return {"images":images,"duree_s":duree,"fps":fps,"largeur":largeur,"hauteur":hauteur,
                "couverture_s":fin,"tronque":fin < duree-1/fps,"pas_s":parametres["pas_images_s"]}
    finally: capture.release()
