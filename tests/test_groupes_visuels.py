import unittest
from video.groupes_visuels import regrouper_videos
from video.embeddings import comparer_embeddings
class TestsGroupes(unittest.TestCase):
    def test_semantique_exclue_du_reemploi(self):
        comparaisons=[{"a":"1","b":"2","type":"reemploi_sequence"},{"a":"2","b":"3","type":"fichier_identique"},{"a":"3","b":"4","type":"aucun_reemploi_detecte","semantiquement_similaires":True}]
        self.assertEqual(regrouper_videos(comparaisons)[0]["publications"],["1","2","3"])
    def test_cosinus_et_modeles_distincts(self):
        a={"statut":"mesure","vecteur":[1,0],"modele":"test","poids":"v1"}
        self.assertEqual(comparer_embeddings(a,a),1)
        self.assertIsNone(comparer_embeddings(a,{**a,"poids":"v2"}))

    def test_repartition_lot_entremedias(self):
        from video.lots import repartir_publications
        publications=[{"id":str(i),"author":"a" if i<3 else "b"} for i in range(6)]
        self.assertEqual([p["author"] for p in repartir_publications(publications)[:4]],["a","b","a","b"])
