"""Téléchargement facultatif depuis une URL de publication validée, sans cookies exportés."""
from pathlib import Path
import subprocess
import sys
import shutil

def telecharger_video(publication, dossier, parametres):
    from scraptiktok import canonical_post
    identite=canonical_post(publication["url"])
    if not identite or identite[0]!=str(publication["id"]): raise ValueError("URL ou identifiant vidéo invalide.")
    dossier=Path(dossier); dossier.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(dossier).free < parametres["espace_libre_min_mo"]*1024**2: raise OSError("Espace disque insuffisant.")
    cible=dossier/(identite[0]+".mp4")
    commande=[sys.executable,"-m","yt_dlp","--no-playlist","--no-progress","--no-warnings","--socket-timeout","20","--retries","1",
        "--max-filesize",str(parametres["taille_max_mo"])+"M","--match-filter",f"duration <= {parametres['duree_max_s']}",
        "-f","best[ext=mp4]/best","--no-part","-o",str(cible),"--",identite[1]]
    try: subprocess.run(commande,capture_output=True,timeout=180,check=True)
    except (subprocess.SubprocessError,OSError):
        cible.unlink(missing_ok=True)
        raise
    if not cible.exists() or not cible.stat().st_size: raise ValueError("Vidéo non téléchargée (accès ou limite).")
    if cible.stat().st_size > parametres["taille_max_mo"]*1024**2:
        cible.unlink(); raise ValueError("Vidéo trop volumineuse.")
    return cible
