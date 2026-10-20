"""Localiser des rapprochements de régions ; aucune attribution de cause ou preuve de copie."""
from pathlib import Path
import hashlib
import json

VERSION = 'regions-dino-v1'


def cle_localisation(dossier, image_a, image_b):
    """Invalider les résultats si les miniatures ou la méthode changent."""
    empreinte = hashlib.sha256(VERSION.encode())
    for numero in (image_a, image_b):
        empreinte.update((Path(dossier)/'miniatures_dino'/f'{numero}.jpg').read_bytes())
    return empreinte.hexdigest()


def extraire_regions(chemin, cache):
    """Encoder toute l'image sans recadrage central et garder la grille spatiale."""
    import numpy as np
    from PIL import Image
    import torch
    from video.embeddings import charger_dinov2
    contenu = Path(chemin).read_bytes()
    destination = Path(cache)/(hashlib.sha256(VERSION.encode()+contenu).hexdigest()+'.npz')
    if destination.is_file():
        with np.load(destination, allow_pickle=False) as donnees:
            return donnees['vecteurs'], tuple(int(n) for n in donnees['grille'])
    # Hors ligne : réutiliser les poids déjà nécessaires à l'analyse DINOv2.
    modele, preparer = charger_dinov2(False, 1)
    image = Image.open(chemin).convert('RGB')
    pas = modele.config.patch_size
    largeur, hauteur = image.size
    facteur = 336/max(largeur, hauteur)
    taille = (max(pas, round(largeur*facteur/pas)*pas), max(pas, round(hauteur*facteur/pas)*pas))
    image = image.resize(taille, Image.Resampling.BICUBIC)
    pixels = preparer(images=image, do_resize=False, do_center_crop=False, return_tensors='pt')
    with torch.inference_mode():
        regions = modele(**pixels).last_hidden_state[0, 1:, :].float()
        vecteurs = torch.nn.functional.normalize(regions, dim=-1).cpu().numpy()
    grille = (taille[1]//pas, taille[0]//pas)
    if len(vecteurs) != grille[0]*grille[1]:
        raise ValueError('Grille DINOv2 incompatible')
    Path(cache).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, vecteurs=vecteurs, grille=grille)
    return vecteurs, grille


def rapprocher_regions(vecteurs_a, grille_a, vecteurs_b, grille_b, maximum=6):
    """Choisir des voisins réciproques espacés, sans seuil de validation arbitraire."""
    import numpy as np
    scores = vecteurs_a @ vecteurs_b.T
    voisins_b = scores.argmax(axis=1)
    voisins_a = scores.argmax(axis=0)
    candidats = sorted(((float(scores[a,b]), a, int(b)) for a,b in enumerate(voisins_b)
                         if voisins_a[b] == a), reverse=True)
    retenus = []
    for score, a, b in candidats:
        ya, xa = divmod(a, grille_a[1]); yb, xb = divmod(b, grille_b[1])
        # Éviter six marqueurs contigus sur une seule texture ou un même bandeau.
        if any(max(abs(xa-r['xa']),abs(ya-r['ya'])) <= 1 or
               max(abs(xb-r['xb']),abs(yb-r['yb'])) <= 1 for r in retenus):
            continue
        retenus.append({'numero':len(retenus)+1,'score':score,'xa':xa,'ya':ya,'xb':xb,'yb':yb})
        if len(retenus) >= maximum: break
    for r in retenus:
        for cote, grille in (('a',grille_a),('b',grille_b)):
            x,y = r['x'+cote],r['y'+cote]
            r['zone_'+cote] = [x/grille[1], y/grille[0], (x+1)/grille[1], (y+1)/grille[0]]
    return retenus


def surligner_regions(chemin, regions, cote, destination):
    """Dessiner les mêmes numéros et couleurs sur les régions correspondantes."""
    from PIL import Image, ImageDraw
    image = Image.open(chemin).convert('RGB')
    image.thumbnail((672,672))
    # Agrandir les miniatures pour rendre les numéros lisibles, sans promettre de détail supplémentaire.
    facteur = 560/max(image.size)
    image = image.resize((round(image.width*facteur),round(image.height*facteur)))
    couleurs = ['#ff453a','#00b8d9','#ffcc00','#bf5af2','#30d158','#ff8c00']
    dessin = ImageDraw.Draw(image, 'RGBA')
    for r in regions:
        x1,y1,x2,y2 = r['zone_'+cote]
        boite = (round(x1*image.width),round(y1*image.height),round(x2*image.width)-1,round(y2*image.height)-1)
        couleur = couleurs[(r['numero']-1)%len(couleurs)]
        dessin.rectangle(boite, fill=couleur+'40', outline=couleur, width=3)
        x,y = boite[:2]
        dessin.rectangle((x,y,x+13,y+13),fill=couleur)
        dessin.text((x+3,y),str(r['numero']),fill='black')
    image.save(destination, quality=92)


def calculer_localisation(dossier, image_a, image_b):
    """Calculer uniquement la paire demandée et conserver des résultats privés réutilisables."""
    dossier = Path(dossier)
    sortie = dossier/'regions_dino'/cle_localisation(dossier,image_a,image_b)
    sortie.mkdir(parents=True,exist_ok=True)
    chemins = [dossier/'miniatures_dino'/f'{n}.jpg' for n in (image_a,image_b)]
    a,ga = extraire_regions(chemins[0],dossier/'cache_regions_dino')
    b,gb = extraire_regions(chemins[1],dossier/'cache_regions_dino')
    regions = rapprocher_regions(a,ga,b,gb)
    for cote,chemin in zip(('a','b'),chemins):
        surligner_regions(chemin,regions,cote,sortie/f'{cote}.jpg')
    resultat = {'statut':'termine','regions':regions,'methode':VERSION,'preuve_reemploi':False,
                'limite':'Régions proches sur miniatures. Les scores ne sont pas des probabilités ni une explication du score global.'}
    temporaire = sortie/'resultat.tmp'
    temporaire.write_text(json.dumps(resultat),encoding='utf-8')
    temporaire.replace(sortie/'resultat.json')
    return resultat


if __name__ == '__main__':
    import sys
    calculer_localisation(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]))
