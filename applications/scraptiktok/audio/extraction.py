"""Extraction locale FFmpeg bornée ; absence audio distincte d’un échec."""
import json
import subprocess
from pathlib import Path

def extraire_audio(video, destination, duree_max_s=180, threads=1):
    resultat=subprocess.run(["ffprobe","-v","error","-select_streams","a","-show_entries","stream=codec_type","-of","json",str(video)],capture_output=True,text=True,timeout=30,check=True)
    if not json.loads(resultat.stdout).get("streams"): return {"presence":False,"chemin":None,"statut":"sans_piste"}
    Path(destination).parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-threads",str(threads),"-i",str(video),"-t",str(duree_max_s),"-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(destination)],capture_output=True,timeout=120,check=True)
    return {"presence":True,"chemin":str(destination),"statut":"extrait"}
