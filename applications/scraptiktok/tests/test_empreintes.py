import hashlib
import tempfile
import unittest
from pathlib import Path
from fixtures_video import VIDEO, image_test
from video.empreintes import calculer_sha256, calculer_phash, distance_phash

class TestsEmpreintes(unittest.TestCase):
    def test_sha_identite_binaire(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a"; p.write_bytes(b"corpus")
            self.assertEqual(calculer_sha256(p),hashlib.sha256(b"corpus").hexdigest())
    @unittest.skipUnless(VIDEO,"Profil vidéo facultatif absent")
    def test_phash_compression_et_difference(self):
        import cv2
        image=image_test(); _,octets=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,65])
        h=calculer_phash(image)
        self.assertLess(distance_phash(h,calculer_phash(cv2.imdecode(octets,1))),10)
        self.assertGreater(distance_phash(h,calculer_phash(image_test(47))),16)
