"""Exécution autonome ou fonction appelée explicitement par une future interface."""
# Permettre aussi python analyse_desordre/lancement.py sans modifier les imports de l'application.
if __package__ in (None,''):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    __package__='analyse_desordre'

import argparse
import csv
import json
from pathlib import Path
import cv2
import pandas as pd
from .parametres import Parametres
from .extraction_images import extraire_images
from .mouvement_camera import compenser_camera, mesurer_instabilite
from .mouvements import mesurer_mouvements
from .irregularite_temporelle import mesurer_irregularite
from .indice import calculer_indice, resumer_mesures, INDICATEURS
from .engagement import charger_metadonnees, calculer_taux, VARIABLES_ENGAGEMENT
from .statistiques import calculer_correlations
from .graphiques import tracer_engagements

CHAMPS_TEMPORELS=('publication_id','debut_s','fin_s','intervalle_s','plan','statut','accord_camera','erreur_alignement',
                 'fraction_mobile',*INDICATEURS)


def analyser_video(chemin,parametres):
    """Mesurer un MP4 en mémoire bornée ; réinitialiser les différences après toute paire exclue."""
    bilan={};lignes=[];precedente=None;derniere_vitesse=None;dernier_mouvement=None;dernier_centre=None;plan=0
    for temps,image in extraire_images(chemin,parametres,bilan):
        if precedente is not None:
            temps_a,image_a=precedente;intervalle=temps-temps_a;centre=(temps+temps_a)/2
            mesure=compenser_camera(image_a,image,intervalle,parametres)
            ligne={'debut_s':temps_a,'fin_s':temps,'intervalle_s':intervalle,'plan':plan,'statut':mesure['statut']}
            if mesure['statut']=='mesure':
                mouvement=mesurer_mouvements(mesure['residuel'],mesure['valides'],mesure['diagonale'],intervalle,parametres)
                instabilite=mesurer_instabilite(mesure['vitesses_camera'],derniere_vitesse,centre-dernier_centre if dernier_centre is not None else intervalle)
                irregularite=mesurer_irregularite(mouvement['vitesse_residuelle'],dernier_mouvement)
                ligne.update(mouvement,instabilite_camera=instabilite,irregularite_temporelle=irregularite,
                    indice_desordre=calculer_indice(instabilite,mouvement['entropie_directionnelle'],irregularite,mouvement['vitesse_residuelle']),
                    accord_camera=mesure['accord_camera'],erreur_alignement=mesure['erreur_alignement'])
                derniere_vitesse=mesure['vitesses_camera'];dernier_mouvement=mouvement['vitesse_residuelle'];dernier_centre=centre
            else:
                derniere_vitesse=None;dernier_mouvement=None;dernier_centre=None
                if mesure['statut'] in ('changement_plan','changement_format'): plan+=1
            lignes.append(ligne)
        precedente=(temps,image)
    observe=sum(r['intervalle_s'] for r in lignes)
    valide=sum(r['intervalle_s'] for r in lignes if r['statut']=='mesure')
    resume={**bilan,**resumer_mesures(lignes),'duree_observee_s':observe,'duree_valide_s':valide,
            'couverture_mouvement':valide/observe if observe else 0,
            'changements_plan':sum(r['statut']=='changement_plan' for r in lignes),
            'paires_exclues':sum(r['statut']!='mesure' for r in lignes)}
    resume['statut']='mesure' if resume['indice_desordre'] is not None else 'insuffisant'
    if bilan.get('tronque') or bilan.get('decodage_incomplet'): resume['statut']='partiel'
    return resume,lignes


def enregistrer_indicateurs(resumes,sortie):
    """Publier un instantané complet après chaque vidéo, sans CSV partiellement lisible."""
    tableau=pd.DataFrame(resumes)
    for nom in (*INDICATEURS,*VARIABLES_ENGAGEMENT):
        if nom not in tableau: tableau[nom]=float('nan')
        tableau[nom]=pd.to_numeric(tableau[nom],errors='coerce')
    temporaire=sortie/'indicateurs_engagement.csv.tmp'
    tableau.to_csv(temporaire,index=False,encoding='utf-8-sig')
    temporaire.replace(sortie/'indicateurs_engagement.csv')
    return tableau


def analyser_lot(videos,metadonnees,sortie,parametres=None,progression=None):
    """Entrée facultative : chemins locaux uniquement ; ne jamais écraser les exports collectés."""
    parametres=parametres or Parametres();videos=Path(videos);sortie=Path(sortie)
    if not videos.is_dir(): raise ValueError('Dossier MP4 introuvable.')
    publications=charger_metadonnees(metadonnees)
    fichiers={}
    for chemin in sorted(videos.rglob('*')):
        if not chemin.is_file() or chemin.suffix.lower()!='.mp4': continue
        identifiant=chemin.stem.removeprefix('id_')
        if identifiant in fichiers: raise ValueError('Plusieurs MP4 portent le même identifiant : '+identifiant)
        fichiers[identifiant]=chemin
    identifiants=sorted(set(fichiers)|set(publications))
    if not identifiants: raise ValueError('Aucune vidéo ni métadonnée disponible.')
    # Un dossier neuf protège les sources, les anciennes analyses et les exports principaux.
    sortie.mkdir(parents=True,exist_ok=False)
    (sortie/'parametres.json').write_text(json.dumps(parametres.dictionnaire(),indent=2),encoding='utf-8')
    from importlib.metadata import version
    import platform
    environnement={'python':platform.python_version(),'opencv':cv2.__version__,
        **{nom:version(nom) for nom in ('numpy','pandas','scipy','matplotlib')}}
    (sortie/'environnement.json').write_text(json.dumps(environnement,indent=2),encoding='utf-8')
    cv2.setNumThreads(1)
    resumes=[]
    with (sortie/'mesures_temporelles.csv').open('w',encoding='utf-8-sig',newline='') as flux:
        export=csv.DictWriter(flux,fieldnames=CHAMPS_TEMPORELS);export.writeheader()
        for rang,identifiant in enumerate(identifiants,1):
            if progression: progression(rang-1,len(identifiants),identifiant,'analyse_en_cours')
            publication=publications.get(identifiant,{})
            resume={'publication_id':identifiant,'url':publication.get('url'),
                    'metadonnees_presentes':identifiant in publications,**calculer_taux(publication)}
            try:
                if identifiant not in fichiers: raise FileNotFoundError('MP4 absent pour cette publication.')
                mesures,lignes=analyser_video(fichiers[identifiant],parametres);resume.update(mesures)
                for ligne in lignes: export.writerow({'publication_id':identifiant,**ligne})
            except (OSError,ValueError,cv2.error) as erreur:
                resume.update(statut='erreur',erreur=str(erreur))
            resumes.append(resume)
            enregistrer_indicateurs(resumes,sortie)
            if progression: progression(rang,len(identifiants),identifiant,resume['statut'])
    tableau=enregistrer_indicateurs(resumes,sortie)
    correlations=calculer_correlations(tableau,parametres)
    temporaire=sortie/'correlations_spearman.csv.tmp'
    pd.DataFrame(correlations).to_csv(temporaire,index=False,encoding='utf-8-sig')
    temporaire.replace(sortie/'correlations_spearman.csv')
    tracer_engagements(tableau,correlations,sortie)
    return {'dossier':str(sortie),'publications':len(resumes),'statuts':tableau['statut'].value_counts().to_dict()}


def principale():
    """Lancer explicitement cette analyse, sans navigateur, réseau ou modèle téléchargé."""
    arguments=argparse.ArgumentParser(description='Analyse autonome du désordre visuel et des engagements.',add_help=False)
    arguments.add_argument('-h','--help',action='help',help='Afficher cette aide et quitter.')
    arguments.add_argument('--videos',required=True,type=Path,help='Dossier des MP4 id_<identifiant>.mp4 ou <identifiant>.mp4.')
    arguments.add_argument('--metadonnees',required=True,type=Path,help='publications.json ou engagement.csv déjà collecté.')
    arguments.add_argument('--sortie',required=True,type=Path,help='Nouveau dossier réservé aux résultats.')
    arguments.add_argument('--frequence',type=float,default=10.,help='Images analysées par seconde (10 par défaut).')
    arguments.add_argument('--dimension',type=int,default=320,help='Dimension maximale des images en pixels.')
    arguments.add_argument('--duree-max',type=float,default=60.,help='Durée maximale par vidéo en secondes.')
    arguments.add_argument('--permutations',type=int,default=1999,help='Tirages Monte-Carlo pour Spearman.')
    options=arguments.parse_args()
    try:
        bilan=analyser_lot(options.videos,options.metadonnees,options.sortie,
            Parametres(frequence=options.frequence,dimension=options.dimension,duree_max=options.duree_max,permutations=options.permutations),
            lambda rang,total,identifiant,statut: print(f'{rang}/{total} — {identifiant} : {statut}',flush=True))
    except (ValueError,OSError) as erreur: arguments.exit(2,f'Analyse impossible : {erreur}\n')
    print(json.dumps(bilan,ensure_ascii=False,indent=2))


if __name__=='__main__': principale()
