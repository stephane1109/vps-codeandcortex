"""Embeddings CLIP facultatifs : similarité sémantique, jamais preuve de réemploi."""
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def charger_modele(modele, poids, threads):
    """Réutiliser un seul modèle CPU pendant les lots successifs du processus."""
    import torch
    import open_clip
    torch.set_num_threads(threads)
    reseau, _, preparer = open_clip.create_model_and_transforms(modele, pretrained=poids, device="cpu")
    reseau.eval()
    return reseau, preparer


def calculer_embeddings(images, parametres):
    if not parametres["embeddings"]: return {"statut":"desactive","vecteur":None,"modele":None}
    import torch
    from PIL import Image
    import cv2
    poids=parametres["poids_embeddings"]
    if not parametres["telecharger_modeles"] and not Path(poids).is_file():
        return {"statut":"poids_locaux_requis","vecteur":None,"modele":parametres["modele_embeddings"]}
    torch.set_num_threads(parametres["threads"])
    modele,preparer=charger_modele(parametres["modele_embeddings"],poids,parametres["threads"])
    vecteurs=[]
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


def construire_similarites_semantiques(comparaisons):
    """Exporter les proximités de contenu indépendamment des preuves de réemploi."""
    return sorted([
        {**{cle:c.get(cle) for cle in ('a','b','url_a','url_b','media_a','media_b')},
         'score_cosinus':c['cosinus_semantique'], 'type':'similarite_semantique_visuelle',
         'preuve_reemploi':False}
        for c in comparaisons if c.get('semantiquement_similaires')
    ], key=lambda ligne: (-ligne['score_cosinus'],ligne['a'],ligne['b']))


@lru_cache(maxsize=1)
def charger_dinov2(autoriser_telechargement, threads):
    """Charger uniquement DINOv2-small sur CPU, y compris depuis le cache hors ligne."""
    import torch
    import os
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_FLAX", "0")
    from transformers import AutoImageProcessor, AutoModel
    torch.set_num_threads(threads)
    nom = 'facebook/dinov2-small'
    preparer = AutoImageProcessor.from_pretrained(nom, local_files_only=not autoriser_telechargement, use_fast=False)
    modele = AutoModel.from_pretrained(nom, local_files_only=not autoriser_telechargement).to('cpu').eval()
    return modele, preparer


def calculer_dinov2(images, parametres, verifier=lambda: None):
    """Conserver un CLS normalisé par image, sans moyenne entre images."""
    resultat = {'modele':'facebook/dinov2-small','statut':'desactive','images':[]}
    if not parametres.get('dinov2', True): return resultat
    try:
        import torch
        import cv2
        import faiss  # Vérifier l'index avant d'engager une inférence coûteuse.
        from PIL import Image
        modele, preparer = charger_dinov2(parametres['telecharger_modeles'], parametres['threads'])
    except ImportError as erreur:
        return {**resultat,'statut':'dependance_absente','raison':type(erreur).__name__}
    except OSError:
        return {**resultat,'statut':'modele_indisponible',
                'raison':'Poids DINOv2 absents du cache ou téléchargement impossible.'}
    with torch.inference_mode():
        for entree in images:
            verifier()
            pixels = preparer(images=Image.fromarray(cv2.cvtColor(entree['image'], cv2.COLOR_BGR2RGB)), return_tensors='pt')
            vecteur = modele(**pixels).last_hidden_state[:, 0, :].float()
            vecteur = torch.nn.functional.normalize(vecteur, dim=-1)
            resultat['images'].append({'temps_s':entree['temps_s'],'vecteur':vecteur[0].tolist()})
    return {**resultat,'statut':'mesure' if resultat['images'] else 'aucune_image'}
