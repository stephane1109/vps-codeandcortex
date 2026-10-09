import unittest
from video.comparaison_temporelle import aligner_sequences
from video.parametres import charger_seuils

class TestsTemps(unittest.TestCase):
    def points(self): return [{"temps_a":i,"temps_b":i+10,"phash_a":str(i),"confiance":.9} for i in range(5)]
    def test_decalage_et_vitesse(self):
        p=self.points(); self.assertTrue(aligner_sequences(p,charger_seuils())["detecte"])
        for v in p: v["temps_b"]*=1.5
        self.assertTrue(aligner_sequences(p,charger_seuils())["detecte"])
    def test_ordre_inverse_et_logo_fixe_rejetes(self):
        p=self.points()
        for v in p: v["temps_b"]=20-v["temps_a"]
        self.assertFalse(aligner_sequences(p,charger_seuils())["detecte"])
        p=self.points()
        for v in p: v["phash_a"]="unique"
        self.assertFalse(aligner_sequences(p,charger_seuils())["detecte"])
    def test_trop_peu_images(self):
        self.assertFalse(aligner_sequences(self.points()[:2],charger_seuils())["detecte"])
