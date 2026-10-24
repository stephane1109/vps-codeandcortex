"""Retrouver les médias de la session, indépendamment du calcul des indicateurs."""
from pathlib import Path
import json
import re


def construire_sources_visuelles(liens, publications):
    """Vidéos découvertes sur comptes/presse, même sans légende lisible.

    Les URL proviennent du contrôle d'auteur réalisé pendant la découverte.
    Ne jamais fabriquer du texte, une date ou des valeurs d'engagement.
    """
    from scraptiktok import canonical_post

    existants={str(p.get('id') or p.get('publication_id')) for p in publications}
    ajouts={}
    for adresse in liens:
        identite=canonical_post(adresse)
        if not identite:
            continue
        identifiant,url,auteur=identite
        if '/video/' not in url or identifiant in existants:
            continue
        ajouts.setdefault(identifiant,{
            'id':identifiant,'url':url,'author':auteur,
            'description':'','engagement':{},'retenue':False,
            'source':'decouverte_compte_presse','status':'legende_non_extraite',
        })
    return list(ajouts.values())


def lire_publications(session):
    """Métadonnées textuelles et vidéos découvertes sans texte, sans doublon."""
    session=Path(session)
    fichier=session/'publications.json'
    donnees=json.loads(fichier.read_text(encoding='utf-8-sig')) if fichier.is_file() else []
    publications=donnees if isinstance(donnees,list) else []
    complement=session/'sources_visuelles.json'
    if complement.is_file():
        visuelles=json.loads(complement.read_text(encoding='utf-8-sig'))
        if isinstance(visuelles,list):
            deja={str(p.get('id') or p.get('publication_id')) for p in publications}
            publications=[*publications,*(
                item for item in visuelles if isinstance(item,dict)
                and str(item.get('id') or '') not in deja
            )]
    return publications


def fichier_local(session,chemin):
    """Accepter seulement un MP4 non vide réellement contenu dans la session privée."""
    session=Path(session).resolve();chemin=Path(chemin)
    try:
        relatif=chemin.relative_to(session)
        if any((session/Path(*relatif.parts[:i])).is_symlink() for i in range(1,len(relatif.parts)+1)): return False
        return chemin.resolve().is_relative_to(session) and chemin.is_file() and chemin.suffix.lower()=='.mp4' and chemin.stat().st_size>0
    except (ValueError,OSError): return False


def retrouver_sources(session):
    """Suivre video_fichier, puis les noms canoniques dans videos, sous-dossiers compris."""
    session=Path(session).resolve();publications=lire_publications(session)
    fichiers={}
    repertoire=session/'videos'
    candidats={}
    if repertoire.is_dir() and not repertoire.is_symlink():
        for chemin in sorted(repertoire.rglob('*')):
            if fichier_local(session,chemin):
                candidats.setdefault(chemin.stem.removeprefix('id_'),chemin)
    for publication in publications:
        identifiant=str(publication.get('id') or publication.get('publication_id') or '')
        if not re.fullmatch(r'[0-9]+',identifiant): continue
        nom=publication.get('video_fichier')
        if isinstance(nom,str) and nom:
            chemin=session/nom
            if fichier_local(session,chemin): fichiers[identifiant]=chemin
        if identifiant not in fichiers and identifiant in candidats: fichiers[identifiant]=candidats[identifiant]
    return publications,fichiers


def url_telechargeable(publication):
    """Valider l'URL TikTok et son identifiant sans lancer de requête réseau."""
    identifiant=str(publication.get('id') or publication.get('publication_id') or '')
    url=publication.get('url')
    if not isinstance(url,str): return False
    return bool(re.fullmatch(r'https://(?:www\.)?tiktok\.com/@[^/?#]+/video/'+re.escape(identifiant)+r'(?:[/?#].*)?',url) and identifiant.isdecimal())


def inventaire_sources(session):
    publications,fichiers=retrouver_sources(session)
    manquantes=[p for p in publications if str(p.get('id') or p.get('publication_id')) not in fichiers]
    return {'publications_collectees':len(publications),'mp4_locaux':len(fichiers),
        'mp4_manquants':len(manquantes),'mp4_telechargeables':sum(url_telechargeable(p) for p in manquantes)}


def publications_sans_resultat(session,lignes,etat):
    """Afficher les publications absentes du résultat sans inventer de mesure."""
    presents={str(ligne.get('publication_id')) for ligne in lignes}
    erreurs={str(ligne['publication_id']):ligne for ligne in etat.get('erreurs_telechargement',[])}
    resultat=[]
    for publication in lire_publications(session):
        identifiant=str(publication.get('id') or publication.get('publication_id'))
        if identifiant in presents: continue
        presents.add(identifiant)
        erreur=erreurs.get(identifiant)
        resultat.append({'publication_id':identifiant,'url':publication.get('url'),
            'statut':'telechargement_echoue' if erreur else 'en_attente' if etat.get('statut')=='en_cours' else 'sans_resultat',
            'erreur':erreur.get('detail') if erreur else 'Aucun résultat enregistré pour cette publication.'})
    return resultat
