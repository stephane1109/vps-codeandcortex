"""Embeddings CLIP facultatifs : similarité sémantique, jamais preuve de réemploi."""
from pathlib import Path

def calculer_embeddings(images, parametres):
    if not parametres["embeddings"]: return {"statut":"desactive","vecteur":None,"modele":None}
    import torch
    import open_clip
    from PIL import Image
    import cv2
    poids=parametres["poids_embeddings"]
    if not parametres["telecharger_modeles"] and not Path(poids).is_file():
        return {"statut":"poids_locaux_requis","vecteur":None,"modele":parametres["modele_embeddings"]}
    torch.set_num_threads(parametres["threads"])
    modele,_,preparer=open_clip.create_model_and_transforms(parametres["modele_embeddings"],pretrained=poids,device="cpu")
    modele.eval(); vecteurs=[]
    with torch.inference_mode():
        for entree in images[::max(1,len(images)//12)][:12]:
            tenseur=preparer(Image.fromarray(cv2.cvtColor(entree["image"],cv2.COLOR_BGR2RGB))).unsqueeze(0)
            vecteur=modele.encode_image(tenseur).float(); vecteur/=vecteur.norm(dim=-1,keepdim=True)
            vecteurs.append(vecteur)
        moyenne=torch.cat(vecteurs).mean(dim=0); moyenne/=moyenne.norm()
    return {"statut":"mesure","vecteur":moyenne.tolist(),"modele":parametres["modele_embeddings"],"poids":poids,"images":len(vecteurs)}

def comparer_embeddings(a,b):
    import math
    if a.get("statut")!="mesure" or b.get("statut")!="mesure" or (a.get("modele"),a.get("poids")) != (b.get("modele"),b.get("poids")): return None
    va=a["vecteur"]; vb=b["vecteur"]
    if len(va)!=len(vb) or not va: return None
    denominateur=math.sqrt(sum(x*x for x in va)*sum(x*x for x in vb))
    return max(-1,min(1,sum(x*y for x,y in zip(va,vb))/denominateur)) if denominateur else None
