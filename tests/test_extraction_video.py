import json
import shutil
import tempfile
import unittest
from pathlib import Path
from fixtures_video import VIDEO,ecrire_video
from video.extraction_images import extraire_images
from video.parametres import charger_parametres,charger_seuils
from video.lots import analyser_lot

@unittest.skipUnless(VIDEO,"Profil vidéo facultatif absent")
class TestsVideo(unittest.TestCase):
    def test_limites_decodage(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.mp4"; ecrire_video(p)
            param=charger_parametres(); param.update(images_max=3,dimension_max=160)
            r=extraire_images(p,param)
            self.assertEqual(len(r["images"]),3); self.assertTrue(r["tronque"])
            self.assertLessEqual(max(r["images"][0]["image"].shape[:2]),160)
    def test_lot_reemploi_recadre_et_exports(self):
        with tempfile.TemporaryDirectory() as d:
            dossier=Path(d)/"sessions"/("a"*32); (dossier/"videos").mkdir(parents=True)
            ecrire_video(dossier/"videos/1.mp4")
            ecrire_video(dossier/"videos/2.mp4",recadrer=True)
            ecrire_video(dossier/"videos/3.mp4",graines=(51,52,53,54,55))
            publications=[{"id":str(i),"author":"media"+str(i),"description":"Une description en français.","media_id":"m"+str(i),"engagement":{}} for i in (1,2,3)]
            (dossier/"publications.json").write_text(json.dumps(publications))
            param=charger_parametres(); param.update(conserver_images=False)
            r=analyser_lot(dossier,param)
            self.assertEqual(r["statut"],"termine",r)
            comparaisons=json.loads((dossier/"comparaisons.json").read_text())
            self.assertIn(comparaisons[0]["type"],("reemploi_sequence","videos_visuellement_quasi_identiques"))
            self.assertTrue(all(c["type"]=="aucun_reemploi_detecte" for c in comparaisons[1:]))
            self.assertTrue((dossier/"archive.zip").is_file())
            self.assertIn("*reemploi_detecte",(dossier/"corpus_iramuteq.txt").read_text())
            param["videos_max"]=1
            r=analyser_lot(dossier,param)
            self.assertEqual(r["statut"],"partiel")
            self.assertIn("*reemploi_indetermine",(dossier/"corpus_iramuteq.txt").read_text())
    def test_sha_identique_sans_comparaison_orb(self):
        from video.recherche_similaires import comparer_videos
        a={"id":"1","sha256":"hash"}; b={"id":"2","sha256":"hash"}
        self.assertEqual(comparer_videos(a,b,charger_seuils())["type"],"fichier_identique")

    def test_semantique_ne_valide_pas_sequence(self):
        from video.recherche_similaires import comparer_videos
        embedding={"statut":"mesure","modele":"fixture","poids":"v1","vecteur":[1,0]}
        a={"id":"1","sha256":"a","images":[],"embedding":embedding}
        b={**a,"id":"2","sha256":"b"}
        r=comparer_videos(a,b,charger_seuils())
        self.assertTrue(r["semantiquement_similaires"])
        self.assertEqual(r["type"],"indetermine")
