"""Paramètres bornés, communs aux traitements par lots et au cache."""
import json
from pathlib import Path
CONFIG = Path(__file__).resolve().parents[1] / "config"

def charger_parametres(chemin=None):
    valeurs = json.loads((CONFIG / "parametres_video.json").read_text())
    if chemin: valeurs.update(json.loads(Path(chemin).read_text()))
    bornes = {"debut_videos":(0,100000),"pas_images_s":(0.25,30),"images_max":(3,300),"dimension_max":(128,720),"duree_max_s":(3,600),
              "taille_max_mo":(1,500),"videos_max":(1,100),"paires_max":(1,1000),"duree_lot_max_s":(30,7200),
              "threads":(1,4),"ocr_images_max":(1,30),"espace_libre_min_mo":(128,100000)}
    for cle,(bas,haut) in bornes.items():
        valeur = valeurs[cle]
        if isinstance(valeur,bool) or not isinstance(valeur,(int,float)) or not bas <= valeur <= haut:
            raise ValueError(f"Paramètre hors limites : {cle} ({bas} à {haut}).")
    for cle in ("debut_videos","images_max","dimension_max","videos_max","paires_max","threads","ocr_images_max"):
        if not isinstance(valeurs[cle],int): raise ValueError(f"Entier requis : {cle}.")
    for cle in ("comparer_sha256","comparer_sequences","ocr","embeddings","audio","transcription","telecharger_modeles","telecharger_videos","conserver_images"):
        if not isinstance(valeurs[cle],bool): raise ValueError(f"Booléen requis : {cle}.")
    return valeurs

def charger_seuils():
    return json.loads((CONFIG / "seuils_similarite.json").read_text())
