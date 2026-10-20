"""Variables illustratives : indices automatiques, mesures et indéterminés conservés."""
from .discretisation import discretiser

def coder_variables(publication, indicateurs=None, reemploi=None, parametres=None):
    i=indicateurs or {}; mouvement=i.get("mouvement",{}).get("mediane")
    def presence(valeur): return "detecte" if valeur is True else "non_detecte" if valeur is False else "indetermine"
    variables={"media":publication.get("media_id") or publication.get("author") or "indetermine",
        "categorie":publication.get("categorie_media") or "indetermine",
        "format":i.get("format",{}).get("valeur","indetermine"),
        "mouvement":discretiser(mouvement,[0.002,0.01],["faible","moyen","fort"]),
        "plans":discretiser(i.get("plans",{}).get("coupes"),[1,3],["sans_coupe_detectee","quelques_coupes","multiplans"]),
        "personnes":presence(i.get("personnes",{}).get("presence")),"visages":presence(i.get("visages",{}).get("presence")),
        "texte":presence(i.get("texte",{}).get("presence")),"audio":presence(i.get("audio",{}).get("presence")),
        "parole":presence(i.get("transcription",{}).get("parole")),"reemploi":presence(reemploi)}
    if parametres is not None:
        # « no » signifie désactivé ; une mesure activée mais échouée reste indéterminée.
        for option in ('ocr','transcription','embeddings','comparer_sha256','comparer_sequences',
                       'telecharger_modeles','telecharger_videos','conserver_images','nettoyer_videos'):
            if option in parametres:
                variables[option]='yes' if parametres[option] else 'no'
        for option,champ in (('ocr','texte'),('transcription','parole')):
            if parametres.get(option) is False: variables[champ]='no'
        if not (parametres.get('audio',False) or parametres.get('transcription',False)):
            variables['audio']='no'
        if not (parametres.get('comparer_sha256',True) or parametres.get('comparer_sequences',True)):
            variables['reemploi']='no'
    return {"publication_id":publication["id"],"variables":variables,
            "mesures_brutes":i,"confiances":{k:v.get("confiance") for k,v in i.items() if isinstance(v,dict)},
            "methode":"regles_automatiques_v1","calibration":"non_calibree"}
