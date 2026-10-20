"""Traitement audiovisuel autonome et borné : python -m video.lots --session DOSSIER."""
from collections import defaultdict, deque
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import time

from corpus.export_json import exporter_json
from corpus.export_csv import exporter_csv
from corpus.construction import construire_exports
from corpus.export_iramuteq import exporter_iramuteq
from corpus.corpus_transcriptions import construire_transcriptions
from corpus.export_zip import exporter_zip
from stockage.base_donnees import BaseDonnees
from stockage.cache_video import cle_cache, lire_cache, ecrire_cache
from .parametres import charger_parametres, charger_seuils
from .empreintes import calculer_sha256, calculer_phash, IndexVisuel
from .comparaison_orb import extraire_orb
from .extraction_images import extraire_images
from .indicateurs import calculer_indicateurs
from .embeddings import calculer_embeddings
from .recherche_similaires import comparer_videos
from .groupes_visuels import regrouper_videos, TYPES_REEMPLOI
from analyse.codage_automatique import coder_variables
from analyse.reseau_similarite import construire_reseau
from analyse.circulation_visuelle import analyser_circulation
from analyse.comparaison_medias import comparer_medias


def repartir_publications(publications, debut=0):
    """Alterner les médias pour que les petits lots couvrent plusieurs sources."""
    files = defaultdict(deque)
    for publication in publications:
        files[publication.get("media_id") or publication.get("author") or "indetermine"].append(publication)
    reparties = []
    while any(files.values()):
        for file in files.values():
            if file: reparties.append(file.popleft())
    return reparties[debut:]


def analyser_lot(dossier, parametres=None, seuils=None):
    dossier=Path(dossier).resolve()
    if not (dossier / "publications.json").is_file(): raise ValueError("Session sans publications.json.")
    parametres=parametres or charger_parametres(); seuils=seuils or charger_seuils()
    with (dossier / ".video.lock").open("w") as verrou:
        try: fcntl.flock(verrou,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as erreur: raise RuntimeError("Un traitement utilise déjà cette session.") from erreur
        return traiter_lot(dossier,parametres,seuils)


def traiter_lot(dossier, parametres, seuils):
    publications=json.loads((dossier / "publications.json").read_text())
    publications=[{**p,"id":str(p["id"])} for p in publications]
    commentaires=json.loads((dossier / "commentaires.json").read_text()) if (dossier / "commentaires.json").exists() else []
    journal=json.loads((dossier / "journal.json").read_text()) if (dossier / "journal.json").exists() else {}
    debut=time.monotonic(); analyses=[]; erreurs=[]; mesures={}; comparaisons=[]
    base=BaseDonnees(dossier.parent.parent / "scraptiktok.sqlite")
    # Une base par propriétaire et profil protège les collectes des autres utilisateurs.
    import hashlib
    with base.connexion() as connexion:
        ligne=connexion.execute("SELECT proprietaire FROM sessions WHERE id=?",(dossier.name,)).fetchone()
    proprietaire=ligne[0] if ligne else "corpus_local"
    profil={k:v for k,v in parametres.items() if k not in {"debut_videos","videos_max","paires_max","duree_lot_max_s","telecharger_videos","nettoyer_videos","exclure_videos","reessayer_options"}}
    signature=hashlib.sha256(json.dumps(["index_v2",profil,seuils],sort_keys=True).encode()).hexdigest()
    espace=hashlib.sha256(proprietaire.encode()).hexdigest()
    index=IndexVisuel(dossier.parent.parent / "index_visuel" / espace / (signature+".sqlite"))
    try:
        def incomplet(valeur):
            """Réessayer une option dont le modèle ou la dépendance était indisponible."""
            if isinstance(valeur,dict):
                return valeur.get('statut') in {'indetermine','poids_locaux_requis','dependance_absente'} or any(incomplet(v) for v in valeur.values())
            return False
        deja_traites=set()
        for publication in publications:
            identifiant=str(publication['id'])
            if not identifiant.isdecimal(): continue
            fichier=dossier / "empreintes" / (identifiant+".json")
            if fichier.is_file():
                ancienne=json.loads(fichier.read_text())
                mp4=dossier / 'videos' / ('id_'+identifiant+'.mp4')
                if not mp4.exists() and not mp4.is_symlink(): mp4=dossier / 'videos' / (identifiant+'.mp4')
                fichier_identique=(not mp4.exists() or (mp4.stat().st_size==ancienne.get('fichier_taille') and mp4.stat().st_mtime_ns==ancienne.get('fichier_mtime_ns')))
                if not mp4.is_symlink() and fichier_identique and ancienne.get('signature_index')==signature and (not incomplet(ancienne) or not parametres.get('reessayer_options',True)) and index.lire_video(identifiant):
                    analyses.append(ancienne); mesures[identifiant]=ancienne['indicateurs']; deja_traites.add(identifiant)
        def verifier():
            if time.monotonic()-debut>parametres["duree_lot_max_s"]: raise TimeoutError("Durée maximale du lot atteinte.")
        def etat(statut, etape):
            exporter_json(dossier / "traitement_video.json", {"statut":statut,"etape":etape,"videos_total":len(publications),"videos_analysees":len(analyses),"comparaisons":len(comparaisons),"erreurs":erreurs,"parametres":parametres,"seuils":seuils})
        etat("en_cours","préparation")
        try:
            for publication in [p for p in repartir_publications(publications,parametres.get("debut_videos",0)) if str(p["id"]) not in deja_traites and str(p["id"]) not in parametres.get("exclure_videos",[])][:parametres["videos_max"]]:
                verifier(); identifiant=str(publication["id"])
                if not identifiant.isdecimal():
                    erreurs.append({"id":identifiant,"raison":"identifiant_invalide"}); continue
                etat("en_cours","vidéo " + identifiant)
                try:
                    chemin=dossier / "videos" / ("id_"+identifiant+".mp4")
                    if not chemin.exists() and not chemin.is_symlink():
                        chemin=dossier / "videos" / (identifiant+".mp4")
                    if chemin.is_symlink(): raise ValueError("Lien symbolique vidéo interdit.")
                    if not chemin.exists() and parametres["telecharger_videos"]:
                        from collecte.telechargement import telecharger_video
                        chemin=telecharger_video(publication,dossier / "videos",parametres)
                    if not chemin.exists(): raise FileNotFoundError("vidéo locale absente et téléchargement désactivé")
                    if chemin.stat().st_size>parametres["taille_max_mo"]*1024**2: raise ValueError("vidéo trop volumineuse")
                    if shutil.disk_usage(dossier).free<parametres["espace_libre_min_mo"]*1024**2: raise OSError("espace disque insuffisant")
                    sha=calculer_sha256(chemin); cle=cle_cache(sha,parametres)
                    resultat=index.lire_video(identifiant)
                    if resultat and (resultat['sha256']!=sha or incomplet(resultat)): resultat=None
                    if resultat is None:
                        extraction=extraire_images(chemin,parametres,dossier / "images" / identifiant if parametres["conserver_images"] else None,verifier)
                        indicateurs=calculer_indicateurs(extraction,parametres)
                        verifier()
                        try: embedding=calculer_embeddings(extraction["images"],parametres)
                        except Exception as erreur: embedding={"statut":"indetermine","raison":type(erreur).__name__,"vecteur":None}
                        if parametres["audio"] or parametres["transcription"]:
                            from audio.extraction import extraire_audio
                            from audio.indicateurs import mesurer_audio
                            from audio.transcription import transcrire_audio
                            try:
                                piste=extraire_audio(chemin,dossier / "audio" / (identifiant+".wav"),parametres["duree_max_s"],parametres["threads"])
                                indicateurs["audio"]=mesurer_audio(piste["chemin"]) if piste["presence"] else piste
                                if piste["presence"]:
                                    try: indicateurs["transcription"]=transcrire_audio(piste["chemin"],parametres)
                                    except Exception as erreur: indicateurs["transcription"]={"statut":"indetermine","raison":type(erreur).__name__,"segments":[],"parole":None}
                            except Exception as erreur: indicateurs["audio"]={"statut":"indetermine","raison":type(erreur).__name__,"presence":None}
                        resultat={"sha256":sha,"duree_s":extraction["duree_s"],"pas_s":extraction["pas_s"],"tronque":extraction["tronque"],
                            "images":[],
                            "indicateurs":indicateurs,"embedding":embedding}
                        resultat.update(id=identifiant,media_id=publication.get("media_id") or publication.get("author"),
                                        url=publication.get("url"),signature_index=signature)
                        index.enregistrer_video(resultat,extraction['images'] if parametres.get('comparer_sequences',True) else [])
                        del extraction
                    resultat={**resultat,"fichier_taille":chemin.stat().st_size,"fichier_mtime_ns":chemin.stat().st_mtime_ns,"id":identifiant,"media_id":publication.get("media_id") or publication.get("author")}
                    index.preparer_candidats(identifiant,seuils,verifier)
                    resultat['recherche_tronquee']=index.tronque
                    analyses.append({k:v for k,v in resultat.items() if k != "images"}); mesures[identifiant]=resultat["indicateurs"]
                    exporter_json(dossier / "empreintes" / (identifiant+".json"),resultat)
                    # Le nettoyage est explicite ; les vignettes restent dans l'index privé.
                    if parametres.get('nettoyer_videos',False): chemin.unlink()
                except TimeoutError: raise
                except Exception as erreur: erreurs.append({"id":identifiant,"raison":str(erreur)[:200],"type":type(erreur).__name__})
            for a_id,b_id,candidats in index.base.execute("SELECT a,b,candidats FROM paires WHERE resultat IS NULL ORDER BY a,b LIMIT ?",(parametres['paires_max'],)).fetchall():
                verifier()
                a=index.lire_video(a_id); b=index.lire_video(b_id)
                etat("en_cours","comparaison " + a_id + " / " + b_id)
                resultat=comparer_videos(a,b,seuils,verifier,parametres,json.loads(candidats),index)
                resultat.update(url_a=a.get('url'),url_b=b.get('url'),
                                fichier_a="id_"+a_id+".mp4",fichier_b="id_"+b_id+".mp4")
                with index.base:
                    index.base.execute("UPDATE paires SET resultat=? WHERE a=? AND b=?",(json.dumps(resultat),a_id,b_id))
                comparaisons.append(resultat)
        except TimeoutError as erreur: erreurs.append({"raison":str(erreur),"type":"limite_temps"})
        anciennes_erreurs=journal.get('audiovisuel',{}).get('erreurs',[])
        ids_reussis={a['id'] for a in analyses}
        erreurs=erreurs+[e for e in anciennes_erreurs if e.get('id') and e['id'] not in ids_reussis and e not in erreurs]
        # Conserver l'ensemble des preuves directes du corpus privé, entre les lots.
        comparaisons=list(index.liens())
        attente=index.base.execute("SELECT count(*) FROM paires WHERE resultat IS NULL").fetchone()[0]
        ids_reemploi={c[k] for c in comparaisons if c["type"] in TYPES_REEMPLOI for k in ("a","b")}
        complet=(len(analyses)==len(publications) and not erreurs and not attente
                 and not index.tronque and not any(a.get('tronque') or a.get('recherche_tronquee') for a in analyses))
        if index.tronque:
            erreurs.append({'type':'index_sature','raison':'Recherche de candidats plafonnée ; absence de lien non concluante.'})
        # Les anciennes publications restent des nœuds du réseau inter-collectes.
        publications_reseau={str(p['id']):p for p in publications}
        for identifiant in {c[k] for c in comparaisons for k in ("a","b")}:
            if identifiant not in publications_reseau:
                meta=index.lire_video(identifiant)
                publications_reseau[identifiant]={'id':identifiant,'media_id':meta.get('media_id'),'url':meta.get('url')}
        publications_reseau=list(publications_reseau.values())
        codes=[coder_variables(p,mesures.get(p["id"]),True if p["id"] in ids_reemploi else None) for p in publications]
        variables={c["publication_id"]:c["variables"] for c in codes}
        groupes=regrouper_videos(comparaisons)
        groupes_par_id={identifiant:g['id'] for g in groupes for identifiant in g['publications']}
        for publication in publications:
            identifiant=str(publication['id'])
            champs={'groupe_visuel':groupes_par_id.get(identifiant,'aucun'),
                    'reemploi_visuel':'detecte' if identifiant in ids_reemploi else 'indetermine'}
            publication.update(champs)
            variables[identifiant].update(champs)
        exporter_json(dossier / "groupes_visuels.json",groupes)
        exporter_csv(dossier / "correspondances_visuelles.csv",[
            {**{k:c.get(k) for k in ('a','b','url_a','url_b','media_a','media_b','fichier_a','fichier_b','type','confiance')},
             **{k:segment.get(k) for k in ('debut_a_s','fin_a_s','debut_b_s','fin_b_s')}}
            for c in comparaisons for segment in c['segments']])
        exporter_json(dossier / "comparaisons.json",comparaisons)
        exporter_json(dossier / "variables_shs.json",codes)
        urls_publications = {str(p["id"]): p.get("url") for p in publications}
        exporter_csv(dossier / "variables_shs.csv",[{"publication_id":c["publication_id"],"id_":str(c["publication_id"]),"url":urls_publications.get(str(c["publication_id"])),**c["variables"],"confiances":c["confiances"]} for c in codes])
        exporter_json(dossier / "reseau_similarite.json",construire_reseau(publications_reseau,comparaisons))
        exporter_json(dossier / "circulation_visuelle.json",analyser_circulation(publications_reseau,comparaisons))
        exporter_csv(dossier / "comparaison_medias.csv",comparer_medias(publications))
        transcriptions={identifiant:i.get("transcription",{}) for identifiant,i in mesures.items()}
        exporter_json(dossier / "transcriptions.json",transcriptions)
        exporter_iramuteq(dossier / "corpus_transcriptions_iramuteq.txt",construire_transcriptions(transcriptions,variables))
        journal["audiovisuel"]={"statut":"termine" if complet else "partiel","videos_analysees":len(analyses),"videos_restantes":max(0,len(publications)-len(analyses)),"paires_en_attente":attente,"erreurs":erreurs,"parametres":parametres,"seuils":seuils,"confiance":"heuristique_non_calibree"}
        construire_exports(dossier,publications,commentaires,journal,variables)
        etat("termine" if complet else "partiel","exports disponibles")
        exporter_zip(dossier,dossier / "archive.zip")
        return journal["audiovisuel"]
    finally:
        index.fermer()


def principale():
    parseur=argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--session",type=Path,required=True,help="Dossier d’une session enrichie")
    parseur.add_argument("--parametres",type=Path,help="Surcharge JSON des paramètres bornés")
    parseur.add_argument("--debut",type=int,default=None,help="Décalage dans les publications alternées par média")
    arguments=parseur.parse_args()
    parametres=charger_parametres(arguments.parametres)
    if arguments.debut is not None:
        if arguments.debut < 0: parseur.error("Le décalage doit être positif ou nul.")
        parametres["debut_videos"]=arguments.debut
    # Les lots successifs ne gardent jamais les images du lot précédent en mémoire.
    limite=time.monotonic()+parametres['duree_lot_max_s']; precedent=None; echecs=set()
    while True:
        restant=limite-time.monotonic()
        if restant<=0: break
        options={**parametres,'duree_lot_max_s':restant,'exclure_videos':sorted(echecs),'reessayer_options':precedent is None}
        resultat=analyser_lot(arguments.session,options)
        echecs.update(e['id'] for e in resultat['erreurs'] if e.get('id'))
        progression=(resultat['videos_analysees'],resultat['paires_en_attente'],len(echecs))
        if (not resultat['videos_restantes'] and not resultat['paires_en_attente']) or progression==precedent:
            break
        precedent=progression
    print(json.dumps(resultat,ensure_ascii=False))
    return 0 if resultat["statut"]=="termine" else 2

if __name__=="__main__": raise SystemExit(principale())
