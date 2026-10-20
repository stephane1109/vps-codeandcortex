"""Référence locale : fournir le dossier produit par reference_dinov2.py, sans téléchargement."""
import argparse
import json
from pathlib import Path
import tempfile
import time
import cv2
from video.localisation import calculer_localisation


def principale():
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument('--reference',type=Path,required=True)
    analyseur.add_argument('--sortie',type=Path,required=True)
    arguments = analyseur.parse_args()
    with tempfile.TemporaryDirectory() as temporaire:
        dossier=Path(temporaire);miniatures=dossier/'miniatures_dino';miniatures.mkdir()
        for numero,nom in enumerate(('reference','recadrage','rue_sans_rapport'),1):
            lecteur=cv2.VideoCapture(str(arguments.reference/(nom+'.mp4')))
            ok,image=lecteur.read();lecteur.release()
            if not ok: raise RuntimeError('Vidéo non décodée : '+nom)
            hauteur,largeur=image.shape[:2];facteur=224/max(hauteur,largeur)
            cv2.imwrite(str(miniatures/f'{numero}.jpg'),cv2.resize(image,(round(largeur*facteur),round(hauteur*facteur))))
        debut=time.monotonic()
        copie=calculer_localisation(dossier,1,2)
        differente=calculer_localisation(dossier,1,3)
        # Le recadrage connu conserve 70 % du centre : contrôler les centres des régions.
        erreurs=[]
        for region in copie['regions']:
            a,b=region['zone_a'],region['zone_b']
            ca=((a[0]+a[2])/2,(a[1]+a[3])/2)
            cb=((b[0]+b[2])/2,(b[1]+b[3])/2)
            erreurs.append(max(abs((ca[i]-.15)/.7-cb[i]) for i in (0,1)))
        assert sum(e<.1 for e in erreurs)>=4, 'Les régions ne suivent pas le recadrage connu.'
        assert min(r['score'] for r in copie['regions'])>max(r['score'] for r in differente['regions'])
        bilan={'copie_recadree':copie,'scene_differente':differente,'erreurs_coordonnees_recadrage':erreurs,
               'duree_s':time.monotonic()-debut,'note':'Mesures sur ces seules images, aucun seuil universel déduit.'}
        arguments.sortie.write_text(json.dumps(bilan,indent=2,ensure_ascii=False))
        print(json.dumps({'duree_s':bilan['duree_s'],'erreurs':erreurs}))


if __name__=='__main__': principale()
