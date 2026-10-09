"""Mesures vidéo et modules optionnels ; un échec local reste indéterminé."""
from .detection_plans import detecter_plans
from .mouvement import mesurer_mouvement
from .detection_personnes import detecter_personnes
from .detection_visages import detecter_visages
from .detection_texte import detecter_texte
from .classification import classer_format

def calculer_indicateurs(extraction, parametres):
    images=extraction["images"]
    mesures={"duree_s":extraction["duree_s"],"couverture_s":extraction["couverture_s"],"tronque":extraction["tronque"]}
    operations={"plans":lambda:detecter_plans(images,parametres["seuil_coupe"]),"mouvement":lambda:mesurer_mouvement(images),
                "personnes":lambda:detecter_personnes(images[::max(1,len(images)//20)][:20]),
                "visages":lambda:detecter_visages(images[::max(1,len(images)//20)][:20]),"texte":lambda:detecter_texte(images,parametres)}
    for nom,operation in operations.items():
        try: mesures[nom]=operation()
        except Exception as erreur: mesures[nom]={"statut":"indetermine","raison":type(erreur).__name__,"confiance":None}
    mesures["format"]=classer_format(mesures)
    return mesures
