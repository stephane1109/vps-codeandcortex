"""Whisper facultatif sur CPU ; segments, scores et langue conservés."""
from pathlib import Path

def transcrire_audio(chemin, parametres):
    if not parametres["transcription"]: return {"statut":"desactive","segments":[],"parole":None,"langue":None}
    from faster_whisper import WhisperModel
    modele=parametres["modele_whisper"]
    moteur=WhisperModel(modele,device="cpu",compute_type="int8",cpu_threads=parametres["threads"],num_workers=1,local_files_only=not parametres["telecharger_modeles"])
    segments,info=moteur.transcribe(str(chemin),beam_size=1,vad_filter=True)
    resultat=[{"debut_s":s.start,"fin_s":s.end,"texte":s.text,"log_probabilite_moyenne":s.avg_logprob,"probabilite_sans_parole":s.no_speech_prob} for s in segments]
    return {"statut":"transcrit","segments":resultat,"parole":bool(resultat),"langue":info.language,"confiance_langue":info.language_probability,"modele":modele,"confiance":None}
