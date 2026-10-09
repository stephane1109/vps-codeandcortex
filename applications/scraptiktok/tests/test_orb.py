import unittest
from fixtures_video import VIDEO,image_test
from video.comparaison_orb import extraire_orb,comparer_orb
from video.parametres import charger_seuils

@unittest.skipUnless(VIDEO,"Profil vidéo facultatif absent")
class TestsORB(unittest.TestCase):
    def test_recadrage_valide_et_image_differente_rejetee(self):
        import cv2
        a=image_test(); b=cv2.resize(a[12:228,16:304],(320,240)); seuils=charger_seuils()
        self.assertTrue(comparer_orb(extraire_orb(a),extraire_orb(b),seuils)["valide"])
        self.assertFalse(comparer_orb(extraire_orb(a),extraire_orb(image_test(50)),seuils)["valide"])
    def test_image_unie_indeterminee(self):
        import numpy as np
        signature=extraire_orb(np.zeros((240,320,3),dtype=np.uint8))
        resultat=comparer_orb(signature,signature,charger_seuils())
        self.assertIsNone(resultat["confiance"])
