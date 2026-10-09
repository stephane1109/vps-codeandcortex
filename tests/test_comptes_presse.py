import unittest
from collecte.verification_comptes import normaliser_compte, verifier_profil
from collecte.presse import charger_inventaire, selectionner_medias
from webapp import StartRequest

class TestsComptes(unittest.TestCase):
    def test_normalisation_et_validation(self):
        self.assertEqual(normaliser_compte("https://www.tiktok.com/@LeMondeFR/"), "lemondefr")
        for valeur in ("https://evil.test/@media", "../etc", "@", "a/b"):
            with self.assertRaises(ValueError): normaliser_compte(valeur)
    def test_inventaire_et_sources(self):
        self.assertGreaterEqual(len(charger_inventaire()), 2)
        self.assertEqual(selectionner_medias(["lemonde"])[0]["compte"], "lemondefr")
        with self.assertRaises(ValueError): selectionner_medias(["inconnu"])
        self.assertTrue(StartRequest(source_collecte="comptes", comptes=["lemondefr"]).enrichie)
        with self.assertRaises(ValueError): StartRequest(source_collecte="comptes")
    def test_badge_ne_prouve_pas_propriete(self):
        resultat = verifier_profil("lemondefr", {"uniqueId":"lemondefr", "verified":True})
        self.assertTrue(resultat["concordant"])
        self.assertEqual(resultat["proprietaire_editorial"], "indetermine")
