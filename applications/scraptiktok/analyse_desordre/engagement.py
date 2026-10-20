"""Lire les exports déjà collectés sans contacter TikTok ni modifier les compteurs."""
import csv
import json
import math
from pathlib import Path


TAUX=('likes_pour_1000_vues','commentaires_pour_1000_vues','partages_pour_1000_vues')
VARIABLES_ENGAGEMENT=('likes','commentaires','partages','vues',*TAUX)


def nombre_observe(valeur):
    """Les absences, valeurs négatives et chaînes abrégées ambiguës restent inconnues."""
    if isinstance(valeur,dict): valeur=valeur.get('valeur')
    if isinstance(valeur,bool) or valeur in (None,''): return None
    try: nombre=float(valeur)
    except (ValueError,TypeError): return None
    return nombre if math.isfinite(nombre) and nombre>=0 else None


def calculer_taux(publication):
    """Taux descriptifs pour 1 000 vues ; un dénominateur nul n'est pas une absence d'engagement."""
    compteurs=publication.get('engagement') or publication
    valeurs={nom:nombre_observe(compteurs.get(nom)) for nom in ('vues','likes','commentaires','partages')}
    vues=valeurs['vues']
    return {**valeurs,**{nom+'_pour_1000_vues':1000*valeurs[nom]/vues if vues and valeurs[nom] is not None else None
                        for nom in ('likes','commentaires','partages')}}


def charger_metadonnees(chemin):
    """Accepter publications.json et engagement.csv ; préserver les identifiants comme chaînes."""
    chemin=Path(chemin)
    if chemin.suffix.lower()=='.json':
        lignes=json.loads(chemin.read_text(encoding='utf-8-sig'))
        if not isinstance(lignes,list): raise ValueError('Le JSON doit contenir une liste de publications.')
    else:
        with chemin.open(encoding='utf-8-sig',newline='') as flux:
            exemple=flux.read(8192);flux.seek(0)
            try: dialecte=csv.Sniffer().sniff(exemple,delimiters=',;\t')
            except csv.Error: dialecte=csv.excel
            lignes=list(csv.DictReader(flux,dialect=dialecte))
    resultat={}
    for ligne in lignes:
        identifiant=str(ligne.get('publication_id') or ligne.get('id') or '')
        if not identifiant: raise ValueError('Une publication ne possède pas d’identifiant.')
        if identifiant in resultat: raise ValueError('Identifiant répété dans les métadonnées : '+identifiant)
        resultat[identifiant]=ligne
    return resultat
