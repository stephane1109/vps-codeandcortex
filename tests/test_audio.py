"""Mesures énergétiques sans modèle et activation indépendante des options."""
import array
import tempfile
import unittest
import wave
from pathlib import Path
from audio.indicateurs import mesurer_audio
from audio.transcription import transcrire_audio
from video.embeddings import calculer_embeddings
from video.parametres import charger_parametres

class TestsAudio(unittest.TestCase):
    def test_silence_non_assimile_a_parole(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"silence.wav"
            with wave.open(str(p),"wb") as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
                f.writeframes(array.array("h",[0]*16000).tobytes())
            mesure=mesurer_audio(p)
            self.assertEqual(mesure["duree_s"],1)
            self.assertEqual(mesure["fraction_silence"],1)
            self.assertIsNone(mesure["parole"])
    def test_modeles_desactives_sans_import_lourd(self):
        parametres=charger_parametres()
        self.assertEqual(transcrire_audio("inexistant.wav",parametres)["statut"],"desactive")
        self.assertEqual(calculer_embeddings([],parametres)["statut"],"desactive")
