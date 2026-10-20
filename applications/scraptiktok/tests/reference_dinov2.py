"""Référence reproductible, sans vidéo redistribuée : fournir deux MP4 locaux.

python tests/reference_dinov2.py --brut /chemin/brut.mp4 --autre /chemin/rue.mp4 --sortie /tmp/reference
La source Brut doit contenir les plages 24–42 s et 70–88 s (deux magasins distincts).
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
from video.embeddings import calculer_dinov2
from video.extraction_images import extraire_images
from video.empreintes import IndexDino, calculer_sha256
from video.parametres import charger_parametres
from video.recherche_similaires import qualifier_dinov2


def principale():
    p=argparse.ArgumentParser(); p.add_argument('--brut',type=Path,required=True);p.add_argument('--autre',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True)
    args=p.parse_args();args.sortie.mkdir(parents=True,exist_ok=True)
    cas=[('1','reference',args.brut,24,18,None,18),('2','copie_reencodee',args.brut,24,18,None,32),
         ('3','extrait',args.brut,30,9,None,28),('4','recadrage',args.brut,24,18,'crop=iw*0.7:ih*0.7,scale=320:-2',28),
         ('5','autre_magasin_meme_type_scene',args.brut,70,18,None,28),('6','rue_sans_rapport',args.autre,0,6,None,28)]
    parametres=charger_parametres();parametres.update(telecharger_modeles=True,pas_images_s=3)
    index=IndexDino(args.sortie/'index'); debut=time.monotonic();statuts=[]
    try:
        for identifiant,nom,source,debut_s,duree,filtre,crf in cas:
            cible=args.sortie/(nom+'.mp4')
            commande=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(debut_s),'-i',str(source),'-t',str(duree),'-an']
            if filtre: commande+=['-vf',filtre]
            subprocess.run(commande+['-c:v','libx264','-crf',str(crf),str(cible)],check=True)
            extraction=extraire_images(cible,parametres)
            embeddings=calculer_dinov2(extraction['images'],parametres)
            if embeddings['statut']!='mesure': raise RuntimeError(str(embeddings))
            index.enregistrer({'id':identifiant,'sha256':calculer_sha256(cible),'url':'reference:'+nom},extraction['images'],embeddings['images'])
            statuts.append({'video':nom,'images_decodees':len(extraction['images']),'embeddings':len(embeddings['images'])})
            print(nom,len(embeddings['images']),flush=True)
        index.preparer()
        resultats=[qualifier_dinov2(r,3) for r in index.rechercher('1')]
        noms={c[0]:c[1] for c in cas}
        bilan={'modele':'facebook/dinov2-small','pas_s':3,'duree_execution_s':time.monotonic()-debut,'statuts':statuts,
               'classement':[{'rang':i+1,'video':noms[r['b']],'score':r['score'],'nature':r['nature'],'meilleure':r['meilleure']} for i,r in enumerate(resultats)]}
        (args.sortie/'scores.json').write_text(json.dumps(bilan,indent=2,ensure_ascii=False))
        print(json.dumps(bilan,indent=2,ensure_ascii=False),flush=True)
        assert {r['b'] for r in resultats[:3]}=={'2','3','4'},'Les copies connues ne sont pas toutes dans les trois premiers résultats.'
    finally: index.fermer()

if __name__=='__main__': principale()
