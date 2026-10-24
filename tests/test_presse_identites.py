"""Identités publiques : cache local vérifié, isolé par compte et périssable."""
import os
import tempfile
import unittest
from unittest.mock import patch

from collecte.presse_identites import lire_identite, enregistrer_identite


class PresseIdentitesTests(unittest.TestCase):
    def test_cache_verifie_ttl_et_independance_des_medias(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DATA_DIR": tmp}):
            self.assertIsNone(lire_identite("lemondefr", maintenant=1000))
            enregistrer_identite("lemondefr", "MS4wLjABAAAAIdentityForPublicMedia123", maintenant=1000)
            self.assertEqual(
                lire_identite("lemondefr", maintenant=1001),
                "MS4wLjABAAAAIdentityForPublicMedia123",
            )
            self.assertIsNone(lire_identite("autremedia", maintenant=1001))
            self.assertIsNone(lire_identite("lemondefr", maintenant=1000 + 31 * 86400))

    def test_identifiants_invalides_non_enregistres(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DATA_DIR": tmp}):
            with self.assertRaises(ValueError):
                enregistrer_identite("lemondefr", "bad secuid")
            self.assertIsNone(lire_identite("lemondefr"))


if __name__ == "__main__":
    unittest.main()
