"""Exécuter l'analyse facultative dans un processus séparé et publier un état atomique."""
import argparse
import csv
import json
from pathlib import Path
from importlib.util import find_spec

FICHIERS_EXPORTABLES={'indicateurs_engagement.csv','mesures_temporelles.csv','correlations_spearman.csv',
    'parametres.json','environnement.json','instabilite_camera.png','entropie_directionnelle.png',
    'irregularite_temporelle.png','vitesse_residuelle.png','indice_desordre.png'}


def dependances_disponibles():
    """Vérifier les dépendances sans charger OpenCV, SciPy ou Matplotlib dans le serveur."""
    return all(find_spec(nom) is not None for nom in ('cv2','numpy','pandas','scipy','matplotlib'))


def ecrire_etat(session,etat):
    """Remplacer le petit fichier d'état sans lecture concurrente d'un JSON incomplet."""
    chemin=Path(session)/'desordre_etat.json'
    temporaire=chemin.with_suffix('.tmp')
    temporaire.write_text(json.dumps(etat,ensure_ascii=False),encoding='utf-8');temporaire.replace(chemin)


def lire_etat(session):
    chemin=Path(session)/'desordre_etat.json'
    return json.loads(chemin.read_text(encoding='utf-8')) if chemin.is_file() else {'statut':'non_lance'}


def lire_tableau(chemin):
    """Convertir seulement les mesures numériques ; garder les grands identifiants exacts."""
    import math
    if not chemin.is_file(): return []
    with chemin.open(encoding='utf-8-sig',newline='') as flux:
        lignes=list(csv.DictReader(flux))
    textes={'publication_id','url','statut','erreur','indicateur','engagement','methode','raison'}
    for ligne in lignes:
        for nom,valeur in ligne.items():
            if nom in textes: continue
            if valeur=='': ligne[nom]=None;continue
            try:
                nombre=float(valeur);ligne[nom]=nombre if math.isfinite(nombre) else None
            except ValueError: pass
    return lignes


def executer(session,dossier,frequence,dimension,duree_max,telecharger_manquants=False):
    """Préparer les sources sur demande puis appeler le moteur autonome inchangé."""
    from .lancement import analyser_lot
    from .parametres import Parametres
    session=Path(session)
    etat={'statut':'en_cours','dossier':dossier,'terminees':0,'total':0,'etape':'Préparation','telecharger_manquants':telecharger_manquants}
    ecrire_etat(session,etat)
    def progression(rang,total,identifiant,statut):
        etat.update(phase='analyse',terminees=rang,total=total,etape='Vidéo '+identifiant+' : '+statut)
        if rang==total: etat['etape']='Calcul des corrélations et des graphiques'
        ecrire_etat(session,etat)
    try:
        import os
        import shutil
        from tempfile import TemporaryDirectory
        from .sources import retrouver_sources, url_telechargeable
        publications,fichiers=retrouver_sources(session)
        etat.update(total=len(publications),telecharges=0,erreurs_telechargement=[])
        if telecharger_manquants:
            from collecte.telechargement import telecharger_video
            limites={'espace_libre_min_mo':512,'taille_max_mo':150,'duree_max_s':duree_max}
            manquantes=[publication for publication in publications
                if str(publication.get('id') or publication.get('publication_id')) not in fichiers and url_telechargeable(publication)]
            etat.update(phase='telechargement',total=len(manquantes),terminees=0)
            for rang,publication in enumerate(manquantes,1):
                identifiant=str(publication.get('id') or publication.get('publication_id'))
                if identifiant in fichiers or not url_telechargeable(publication): continue
                etat.update(etape=f'Téléchargement du MP4 {rang}/{len(manquantes)} — {identifiant}')
                ecrire_etat(session,etat)
                try:
                    fichiers[identifiant]=telecharger_video({**publication,'id':identifiant},session/'videos',limites)
                    etat['telecharges']+=1
                except Exception as erreur:
                    etat['erreurs_telechargement'].append({'publication_id':identifiant,
                        'cause':getattr(erreur,'statut',type(erreur).__name__),'detail':str(erreur)[:200]})
                etat.update(terminees=rang)
                ecrire_etat(session,etat)
        etat.update(phase='analyse',terminees=0,total=len(publications),mp4_prets=len(fichiers),etape='Analyse des MP4 disponibles')
        ecrire_etat(session,etat)
        # Adapter les noms importés aux identifiants, sans modifier ni supprimer les originaux.
        # Les liens physiques sont temporaires ; les téléchargements restent dans videos/.
        with TemporaryDirectory(prefix='desordre_sources_',dir=session) as temporaire:
            for identifiant,chemin in fichiers.items():
                cible=Path(temporaire)/(identifiant+'.mp4')
                try: os.link(chemin,cible)
                except OSError: shutil.copy2(chemin,cible)
            bilan=analyser_lot(temporaire,session/'publications.json',session/dossier,
                Parametres(frequence=frequence,dimension=dimension,duree_max=duree_max),progression)
        etat.update(statut='termine' if set(bilan['statuts'])=={'mesure'} else 'partiel',
                    etape='Analyse terminée',bilan=bilan['statuts'])
    except Exception as erreur:
        etat.update(statut='echec',etape='Analyse interrompue',erreur=str(erreur)[:300])
    ecrire_etat(session,etat)


if __name__=='__main__':
    arguments=argparse.ArgumentParser(description='Traitement facultatif du désordre visuel.')
    arguments.add_argument('--session',required=True)
    arguments.add_argument('--dossier',required=True)
    arguments.add_argument('--frequence',type=float,default=10.)
    arguments.add_argument('--dimension',type=int,default=320)
    arguments.add_argument('--duree-max',type=float,default=30.)
    arguments.add_argument('--telecharger-manquants',action='store_true')
    options=arguments.parse_args()
    executer(options.session,options.dossier,options.frequence,options.dimension,options.duree_max,options.telecharger_manquants)
