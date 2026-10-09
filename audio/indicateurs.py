"""Durée et silence énergétique ; le non-silence n’est pas assimilé à la parole."""
import array
import math
import wave

def mesurer_audio(chemin, seuil_db=-40):
    avec_son=0; total=0
    with wave.open(str(chemin),"rb") as flux:
        if flux.getnchannels()!=1 or flux.getsampwidth()!=2: raise ValueError("Audio PCM mono 16 bits requis.")
        frequence=flux.getframerate(); duree=flux.getnframes()/frequence
        while True:
            bloc=flux.readframes(max(1,frequence//10))
            if not bloc: break
            echantillons=array.array("h",bloc)
            energie=math.sqrt(sum(float(x)*x for x in echantillons)/len(echantillons))/32768
            if energie>10**(seuil_db/20): avec_son+=len(echantillons)
            total+=len(echantillons)
    return {"presence":True,"duree_s":duree,"fraction_silence":1-avec_son/total if total else None,"seuil_db":seuil_db,"parole":None,"confiance":None}
