import unittest
from collecte.engagement import extraire_engagement, convertir_compteur
from analyse.engagement import calculer_ratios
class TestsEngagement(unittest.TestCase):
    def test_zero_absence_et_brut(self):
        resultat = extraire_engagement({"stats":{"diggCount":0,"playCount":100}})
        self.assertEqual(resultat["likes"]["valeur"], 0)
        self.assertIsNone(resultat["partages"]["valeur"])
        self.assertEqual(calculer_ratios(resultat)["likes_par_vue"], 0)
    def test_compteurs_abreges_et_ambigus(self):
        self.assertEqual(convertir_compteur("1,2 K")["valeur"], 1200)
        self.assertTrue(convertir_compteur("1.2M")["estime"])
        self.assertIsNone(convertir_compteur("1,234")["valeur"])
        self.assertIsNone(convertir_compteur(-1)["valeur"])

    def test_stats_v2_partielles_completes_par_stats(self):
        r=extraire_engagement({"statsV2":{"diggCount":"0"},"stats":{"playCount":120,"shareCount":5}})
        self.assertEqual(r["likes"]["valeur"],0)
        self.assertEqual(r["vues"]["valeur"],120)
        self.assertEqual(r["partages"]["valeur"],5)
    def test_schema_inattendu_garde_les_textes(self):
        from collecte.metadonnees import extraire_metadonnees
        self.assertIsNone(extraire_engagement({"statsV2":[]})["vues"]["valeur"])
        self.assertIsNone(extraire_metadonnees({"video":"indisponible"},None)["duree_s"])
