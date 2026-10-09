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
from .empreintes import calculer_sha256, calculer_phash
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
    commentaires=json.loads((dossier / "commentaires.json").read_text()) if (dossier / "commentaires.json").exists() else []
    journal=json.loads((dossier / "journal.json").read_text()) if (dossier / "journal.json").exists() else {}
    debut=time.monotonic(); analyses=[]; erreurs=[]; mesures={}; comparaisons=[]
    base=BaseDonnees(dossier.parent.parent / "scraptiktok.sqlite")
    def verifier():
        if time.monotonic()-debut>parametres["duree_lot_max_s"]: raise TimeoutError("Durée maximale du lot atteinte.")
    def etat(statut, etape):
        exporter_json(dossier / "traitement_video.json", {"statut":statut,"etape":etape,"videos_analysees":len(analyses),"comparaisons":len(comparaisons),"erreurs":erreurs,"parametres":parametres,"seuils":seuils})
    etat("en_cours","préparation")
    try:
        for publication in repartir_publications(publications,parametres.get("debut_videos",0))[:parametres["videos_max"]]:
            verifier(); identifiant=str(publication["id"])
            if not identifiant.isdecimal():
                erreurs.append({"id":identifiant,"raison":"identifiant_invalide"}); continue
            etat("en_cours","vidéo " + identifiant)
            try:
                chemin=dossier / "videos" / (identifiant+".mp4")
                if chemin.is_symlink(): raise ValueError("Lien symbolique vidéo interdit.")
                if not chemin.exists() and parametres["telecharger_videos"]:
                    from collecte.telechargement import telecharger_video
                    chemin=telecharger_video(publication,dossier / "videos",parametres)
                if not chemin.exists(): raise FileNotFoundError("vidéo locale absente et téléchargement désactivé")
                if chemin.stat().st_size>parametres["taille_max_mo"]*1024**2: raise ValueError("vidéo trop volumineuse")
                if shutil.disk_usage(dossier).free<parametres["espace_libre_min_mo"]*1024**2: raise OSError("espace disque insuffisant")
                sha=calculer_sha256(chemin); cle=cle_cache(sha,parametres)
                resultat=lire_cache(base,cle)
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
                        "images":[{"temps_s":e["temps_s"],"phash":calculer_phash(e["image"]),"orb":extraire_orb(e["image"])} for e in extraction["images"]],
                        "indicateurs":indicateurs,"embedding":embedding}
                    del extraction
                    # Les modules activés mais indisponibles sont réessayés au prochain lot.
                    def incomplet(valeur):
                        if isinstance(valeur,dict):
                            return valeur.get("statut") in {"indetermine","poids_locaux_requis","dependance_absente"} or any(incomplet(v) for v in valeur.values())
                        return False
                    if not incomplet(resultat): ecrire_cache(base,cle,resultat)
                resultat={**resultat,"id":identifiant,"media_id":publication.get("media_id") or publication.get("author")}
                analyses.append({k:v for k,v in resultat.items() if k != "images"}); mesures[identifiant]=resultat["indicateurs"]
                exporter_json(dossier / "empreintes" / (identifiant+".json"),resultat)
            except TimeoutError: raise
            except Exception as erreur: erreurs.append({"id":identifiant,"raison":str(erreur)[:200],"type":type(erreur).__name__})
        for i,meta_a in enumerate(analyses):
            a=json.loads((dossier / "empreintes" / (meta_a["id"]+".json")).read_text())
            for meta_b in analyses[i+1:]:
                b=json.loads((dossier / "empreintes" / (meta_b["id"]+".json")).read_text())
                verifier()
                if len(comparaisons)>=parametres["paires_max"]: break
                etat("en_cours","comparaison " + a["id"] + " / " + b["id"])
                comparaisons.append(comparer_videos(a,b,seuils,verifier))
                exporter_json(dossier / "comparaisons.json",comparaisons)
    except TimeoutError as erreur: erreurs.append({"raison":str(erreur),"type":"limite_temps"})
    analyses_ids={a["id"] for a in analyses}
    ids_reemploi={c[k] for c in comparaisons if c["type"] in TYPES_REEMPLOI for k in ("a","b")}
    # Une absence de lien n’est interprétable que si toutes les paires du lot sont examinées.
    complet=(len(analyses)==len(publications) and len(comparaisons)==len(analyses)*(len(analyses)-1)//2 and not erreurs and not any(a.get("tronque") for a in analyses) and not any(c.get("tronque") or c["type"]=="indetermine" for c in comparaisons))
    codes=[coder_variables(p,mesures.get(p["id"]),True if p["id"] in ids_reemploi else False if complet and len(analyses)>1 else None) for p in publications]
    variables={c["publication_id"]:c["variables"] for c in codes}
    groupes=regrouper_videos(comparaisons)
    exporter_json(dossier / "groupes_visuels.json",groupes)
    exporter_json(dossier / "comparaisons.json",comparaisons)
    exporter_json(dossier / "variables_shs.json",codes)
    exporter_csv(dossier / "variables_shs.csv",[{"publication_id":c["publication_id"],**c["variables"],"confiances":c["confiances"]} for c in codes])
    exporter_json(dossier / "reseau_similarite.json",construire_reseau(publications,comparaisons))
    exporter_json(dossier / "circulation_visuelle.json",analyser_circulation(publications,comparaisons))
    exporter_csv(dossier / "comparaison_medias.csv",comparer_medias(publications))
    transcriptions={identifiant:i.get("transcription",{}) for identifiant,i in mesures.items()}
    exporter_json(dossier / "transcriptions.json",transcriptions)
    exporter_iramuteq(dossier / "corpus_transcriptions_iramuteq.txt",construire_transcriptions(transcriptions,variables))
    journal["audiovisuel"]={"statut":"termine" if complet else "partiel","videos_analysees":len(analyses),"erreurs":erreurs,"parametres":parametres,"seuils":seuils,"confiance":"heuristique_non_calibree"}
    construire_exports(dossier,publications,commentaires,journal,variables)
    etat("termine" if complet else "partiel","exports disponibles")
    exporter_zip(dossier,dossier / "archive.zip")
    return journal["audiovisuel"]


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
    resultat=analyser_lot(arguments.session,parametres)
    print(json.dumps(resultat,ensure_ascii=False))
    return 0 if resultat["statut"]=="termine" else 2

if __name__=="__main__": raise SystemExit(principale())
