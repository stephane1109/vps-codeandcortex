"""Comparaison des fichiers puis des séquences ; registre sémantique distinct."""
from .empreintes import distance_phash
from .comparaison_orb import comparer_orb
from .comparaison_temporelle import aligner_sequences
from .embeddings import comparer_embeddings

def comparer_videos(a,b,seuils,verifier=lambda:None,options=None):
    options = options or {}
    resultat={"a":a["id"],"b":b["id"],"media_a":a.get("media_id"),"media_b":b.get("media_id"),
              "type":"indetermine","confiance":None,"segments":[],"comparaisons":[],"tronque":False}
    resultat["methodes"] = {"sha256":options.get("comparer_sha256",True), "phash_orb_temporel":options.get("comparer_sequences",True)}
    resultat["cosinus_semantique"]=comparer_embeddings(a.get("embedding",{}),b.get("embedding",{}))
    resultat["semantiquement_similaires"]=(resultat["cosinus_semantique"]>=seuils["cosinus_semantique"] if resultat["cosinus_semantique"] is not None else None)
    if options.get("comparer_sha256",True) and a["sha256"]==b["sha256"]:
        return {**resultat,"type":"fichier_identique","confiance":1.0,"preuve":"sha256"}
    if not options.get("comparer_sequences",True):
        return {**resultat,"type":"comparaison_sequences_desactivee"}
    candidats=[]
    for i,ia in enumerate(a["images"]):
        distances=sorted((distance_phash(ia["phash"],ib["phash"]),j) for j,ib in enumerate(b["images"]))
        # pHash sert au classement ; quelques meilleurs candidats ORB couvrent les recadrages.
        for rang,(distance,j) in enumerate(distances):
            if distance<=seuils["distance_phash"] or rang<2: candidats.append((distance,i,j))
    candidats.sort(); resultat["tronque"]=len(candidats)>seuils["paires_orb_max"]
    points=[]
    for distance,i,j in candidats[:seuils["paires_orb_max"]]:
        verifier(); ia=a["images"][i]; ib=b["images"][j]
        orb=comparer_orb(ia["orb"],ib["orb"],seuils)
        mesure={"temps_a":ia["temps_s"],"temps_b":ib["temps_s"],"distance_phash":distance,"orb":orb}
        resultat["comparaisons"].append(mesure)
        if orb["valide"] and (distance<=seuils["distance_phash"] or orb["inliers"]>=24):
            points.append({"temps_a":ia["temps_s"],"temps_b":ib["temps_s"],"phash_a":ia["phash"],"confiance":orb["confiance"],"distance_phash":distance,"inliers":orb["inliers"]})
    alignement=aligner_sequences(points,seuils)
    resultat.update(segments=alignement["segments"],confiance=alignement["confiance"],statut_temporel=alignement["statut"])
    if alignement["detecte"]:
        resultat["type"]="reemploi_sequence"
        # Une longue séquence doit couvrir les deux fichiers, pas seulement leur extrait analysé.
        segment=max(alignement["segments"],key=lambda s:s["fin_a_s"]-s["debut_a_s"])
        ca=(segment["fin_a_s"]-segment["debut_a_s"]+a["pas_s"])/a["duree_s"]
        cb=(segment["fin_b_s"]-segment["debut_b_s"]+b["pas_s"])/b["duree_s"]
        resultat["couverture_a"]=min(1,ca); resultat["couverture_b"]=min(1,cb)
        if min(ca,cb)>=seuils["couverture_quasi_identique"] and not a.get("tronque") and not b.get("tronque"):
            resultat["type"]="videos_visuellement_quasi_identiques"
    else:
        exploitables = all(sum(len(image["orb"]["descripteurs"]) >= 4 for image in v["images"]) >= seuils["images_min"] for v in (a,b))
        resultat["type"]="aucun_reemploi_detecte" if exploitables else "indetermine"
    resultat["cosinus_semantique"]=comparer_embeddings(a.get("embedding",{}),b.get("embedding",{}))
    resultat["semantiquement_similaires"]=(resultat["cosinus_semantique"]>=seuils["cosinus_semantique"] if resultat["cosinus_semantique"] is not None else None)
    return resultat
