import unittest
from analyse.codage_automatique import coder_variables
from analyse.engagement import calculer_ratios
class TestsCodage(unittest.TestCase):
    def test_absences_non_inventees(self):
        c=coder_variables({"id":"1","author":"media"})
        self.assertTrue(all(c["variables"][k]=="indetermine" for k in ("personnes","visages","audio","reemploi","parole")))
    def test_mesures_et_confiances_conservees(self):
        brut={"mouvement":{"mediane":.03,"confiance":None},"visages":{"presence":True,"confiance":.5}}
        c=coder_variables({"id":"1"},brut,True)
        self.assertEqual(c["mesures_brutes"],brut)
        self.assertEqual(c["variables"]["mouvement"],"fort")
        self.assertEqual(c["variables"]["reemploi"],"detecte")
        self.assertEqual(c["confiances"]["visages"],.5)
