"""Vérifier les coordonnées, l'absence de seuil et le cache local des régions."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from video.localisation import rapprocher_regions, cle_localisation, surligner_regions


class TestsLocalisation(unittest.TestCase):
    def test_regions_reciproques_et_coordonnees(self):
        a = np.eye(16, dtype=np.float32)
        permutation = np.roll(np.arange(16), 4)
        b = a[permutation]
        regions = rapprocher_regions(a,(4,4),b,(4,4))
        self.assertGreater(len(regions),1)
        for r in regions:
            self.assertEqual(r['score'],1)
            self.assertEqual(r['ya']*4+r['xa'], permutation[r['yb']*4+r['xb']])
            for cote in ('a','b'):
                self.assertTrue(all(0<=x<=1 for x in r['zone_'+cote]))
        for i,r in enumerate(regions):
            for precedent in regions[:i]:
                self.assertGreater(max(abs(r['xa']-precedent['xa']),abs(r['ya']-precedent['ya'])),1)

    def test_aucune_probabilite_ni_seuil_de_validation(self):
        regions = rapprocher_regions(np.array([[1.,0.]]),(1,1),np.array([[-1.,0.]]),(1,1))
        self.assertEqual(regions[0]['score'],-1)

    def test_cache_invalide_si_miniature_change_et_dessin(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'miniatures_dino'; p.mkdir()
            for n in (1,2): Image.new('RGB',(80,160),'white').save(p/f'{n}.jpg')
            avant = cle_localisation(d,1,2)
            Image.new('RGB',(80,160),'black').save(p/'1.jpg')
            self.assertNotEqual(avant,cle_localisation(d,1,2))
            sortie = Path(d)/'zones.jpg'
            surligner_regions(p/'1.jpg',[{'numero':1,'zone_a':[0,0,.25,.25]}],'a',sortie)
            image = Image.open(sortie)
            self.assertEqual(image.size,(280,560))
            self.assertNotEqual(image.getpixel((1,1)),(0,0,0))
