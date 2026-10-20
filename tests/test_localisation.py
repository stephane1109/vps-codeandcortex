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

    def test_bandes_noires_aplats_et_bruit_exclus(self):
        from PIL import Image
        from video.localisation import reperer_regions_informatives
        with tempfile.TemporaryDirectory() as d:
            hasard=np.random.default_rng(42)
            pixels=hasard.integers(0,8,(140,140,3),dtype=np.uint8)
            pixels[42:98]=hasard.integers(40,240,(56,140,3),dtype=np.uint8)
            pixels[56:70,28:42]=[180,60,90]  # Aplat coloré au milieu du contenu.
            chemin=Path(d)/'bandes.jpg';Image.fromarray(pixels).save(chemin,quality=85)
            masque=reperer_regions_informatives(chemin,(10,10)).reshape(10,10)
            self.assertFalse(masque[:3].any());self.assertFalse(masque[7:].any())
            self.assertFalse(masque[4,2]);self.assertGreater(masque.sum(),20)

    def test_images_uniformes_aucun_cadre(self):
        from PIL import Image
        from video.localisation import reperer_regions_informatives
        with tempfile.TemporaryDirectory() as d:
            for couleur in ('black','white','red'):
                chemin=Path(d)/'uniforme.jpg';Image.new('RGB',(140,140),couleur).save(chemin)
                masque=reperer_regions_informatives(chemin,(10,10))
                self.assertFalse(masque.any())
                self.assertEqual(rapprocher_regions(np.ones((100,3)),(10,10),np.ones((100,3)),(10,10),masque_a=masque),[])

    def test_masquage_avant_recherche_des_voisins(self):
        a=np.array([[1.,0.],[.8,.6]])
        b=np.array([[1.,0.],[.6,.8]])
        regions=rapprocher_regions(a,(1,2),b,(1,2),masque_a=np.array([False,True]),masque_b=np.array([False,True]))
        self.assertEqual(len(regions),1)
        self.assertEqual((regions[0]['xa'],regions[0]['xb']),(1,1))
