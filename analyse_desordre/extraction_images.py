"""Décodage séquentiel : deux images utiles au maximum dans le moteur d'analyse."""
from pathlib import Path
import math
import cv2


def extraire_images(chemin, parametres, bilan):
    """Émettre des images réduites horodatées ; signaler les limites du décodage."""
    lecteur=cv2.VideoCapture(str(Path(chemin)))
    try:
        if not lecteur.isOpened(): raise ValueError('MP4 illisible ou codec indisponible.')
        fps=lecteur.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps<=0: raise ValueError('Fréquence de la vidéo indisponible.')
        total=lecteur.get(cv2.CAP_PROP_FRAME_COUNT)
        bilan.update(fps_source=fps,duree_annoncee_s=total/fps if total>0 else None,
                     images_decodees=0,images_extraites=0,horodatage_reconstitue=False,tronque=False)
        prochain=0.; precedent=-1.; numero=0
        while True:
            ok,image=lecteur.read()
            if not ok: break
            temps=lecteur.get(cv2.CAP_PROP_POS_MSEC)/1000
            if not math.isfinite(temps) or (numero>0 and temps<=precedent):
                temps=max(numero/fps,precedent+1/fps);bilan['horodatage_reconstitue']=True
            precedent=temps;numero+=1;bilan['images_decodees']=numero
            if temps>parametres.duree_max:
                bilan['tronque']=True;break
            if temps+1e-8<prochain: continue
            prochain=temps+1/parametres.frequence
            h,w=image.shape[:2];facteur=min(1,parametres.dimension/max(h,w))
            image=cv2.resize(image,(max(8,round(w*facteur)),max(8,round(h*facteur))),interpolation=cv2.INTER_AREA)
            bilan['images_extraites']+=1;bilan['dernier_temps_s']=temps
            yield temps,cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        if numero==0: raise ValueError('Aucune image décodée.')
        bilan['decodage_incomplet']=bool(not bilan['tronque'] and total>0 and numero<total-1)
    finally:
        lecteur.release()
