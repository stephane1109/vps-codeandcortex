"""Sauvegarde facultative des collectes dans un ZIP récupérable après redémarrage."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from fastapi.testclient import TestClient

import webapp as web
from stockage.sauvegarde_progressive import (
    DOSSIER, enregistrer_point, fichier_point, lister_points, purger_points
)


class TestsSauvegardeProgressive(unittest.TestCase):
    def test_option_desactivee_par_defaut(self):
        with tempfile.TemporaryDirectory() as d:
            parametres=web.StartRequest(hashtag="test")
            self.assertFalse(parametres.sauvegarde_progressive)
            job=web.Job("a"*64,parametres,Path(d))
            job.records.append({"id":"1","author":"test","description":"Un texte"})
            self.assertIsNone(job.sauvegarder_point())
            self.assertFalse((Path(d)/DOSSIER).exists())

    def test_archive_atomique_remplacee_et_protegee_par_proprietaire(self):
        with tempfile.TemporaryDirectory() as d:
            owner="a"*64
            job=web.Job(owner,web.StartRequest(
                hashtag="manifestation",enrichir=True,sauvegarde_progressive=True),Path(d))
            premiere={"id":"101","author":"test","description":"Premier texte",
                      "url":"https://www.tiktok.com/@test/video/101","retenue":True}
            seconde={"id":"102","author":"test","description":"Deuxième texte",
                     "url":"https://www.tiktok.com/@test/video/102","retenue":True}
            job.publications.append(premiere)
            job.records.append(premiere)
            job.processed=10
            point=job.sauvegarder_point()
            self.assertEqual(point["traitees"],10)
            self.assertEqual(len(lister_points(d,owner)),1)
            cible=Path(d)/DOSSIER/(job.id+".zip")
            with ZipFile(cible) as archive:
                self.assertEqual(json.loads(archive.read("retenues.json"))[0]["id"],"101")
                self.assertIn("Premier texte",archive.read("textes.txt").decode())
                self.assertEqual(json.loads(archive.read("etat.json"))["statut"],"en_cours")
                self.assertNotIn(owner,archive.read("manifest.json").decode())

            job.records.append(seconde)
            job.publications.append(seconde)
            job.commentaires.append({"id":"c1","publication_id":"102","texte":"Réponse"})
            job.processed=12
            point=job.sauvegarder_point("stopped")
            self.assertEqual(point["statut"],"stopped")
            self.assertEqual(len(list((Path(d)/DOSSIER).glob("*.zip"))),1)
            with ZipFile(cible) as archive:
                self.assertIn("Deuxième texte",archive.read("textes.txt").decode())
                self.assertEqual(len(json.loads(archive.read("publications.json"))),2)
                self.assertTrue(json.loads(archive.read("parametres.json"))["sauvegarde_progressive"])
                self.assertEqual(json.loads(archive.read("commentaires.json"))[0]["texte"],"Réponse")
                self.assertNotIn("videos/", "\n".join(archive.namelist()))
            self.assertIsNone(fichier_point(d,job.id,"b"*64))

            # Même si le gestionnaire ne connaît plus cette collecte (redémarrage),
            # la sauvegarde persiste et est récupérable par le propriétaire.
            app=web.create_app(web.Manager(data_dir=d))
            with TestClient(app) as client:
                client.get("/")
                client.cookies.clear()
                client.cookies.set(web.COOKIE,owner)
                liste=client.get("/api/sauvegardes")
                self.assertEqual(liste.status_code,200)
                self.assertEqual(len(liste.json()["sauvegardes"]),1)
                lien=f"/api/sauvegardes/{job.id}/telecharger"
                reponse=client.get(lien)
                self.assertEqual(reponse.status_code,200)
                with ZipFile(io.BytesIO(reponse.content)) as archive:
                    self.assertEqual(json.loads(archive.read("etat.json"))["traitees"],12)
            with TestClient(app) as etranger:
                etranger.get("/")
                self.assertEqual(etranger.get("/api/sauvegardes").json()["sauvegardes"],[])
                self.assertEqual(etranger.get(f"/api/sauvegardes/{job.id}/telecharger").status_code,404)

    def test_worker_sauvegarde_aux_10_posts_et_a_la_fin(self):
        with tempfile.TemporaryDirectory() as d:
            job=web.Job("a"*64,web.StartRequest(
                hashtag="été",enrichir=True,sauvegarde_progressive=True),Path(d))
            urls=[f"https://www.tiktok.com/@test/video/{i}" for i in range(100,112)]
            def lire(_driver,url,*args,**kwargs):
                return {"id":url.rsplit("/",1)[-1],"url":url,
                        "author":"test","description":"Vidéo #été"}
            with (
                patch.object(web.scraper,"collect_links",return_value=urls),
                patch.object(web.scraper,"read_post",side_effect=lire),
                patch.object(job,"pause"),
                patch.object(job,"sauvegarder_point",wraps=job.sauvegarder_point) as sauvegardes,
            ):
                web.execute_job(job,driver_factory=lambda args:Mock())
            self.assertEqual(job.processed,12)
            self.assertEqual(sauvegardes.call_count,2)
            self.assertEqual(sauvegardes.call_args_list[0].args,())
            self.assertEqual(sauvegardes.call_args_list[1].args,("completed",))
            self.assertEqual(job.dernier_point_sauvegarde["traitees"],12)
            self.assertEqual(job.dernier_point_sauvegarde["retenues"],12)
            with ZipFile(Path(d)/DOSSIER/(job.id+".zip")) as archive:
                self.assertEqual(len(json.loads(archive.read("retenues.json"))),12)

    def test_erreur_de_disque_ne_stoppe_pas_la_collecte(self):
        with tempfile.TemporaryDirectory() as d:
            job=web.Job("a"*64,web.StartRequest(
                hashtag="test",sauvegarde_progressive=True),Path(d))
            with patch("stockage.sauvegarde_progressive.enregistrer_point",
                       side_effect=OSError("espace insuffisant")):
                self.assertIsNone(job.sauvegarder_point())
            self.assertIn("espace insuffisant",job.erreur_sauvegarde)
            self.assertFalse(job.stop.is_set())

    def test_purge_distincte_de_la_session_temporaire(self):
        with tempfile.TemporaryDirectory() as d:
            identifiant="1"*32
            enregistrer_point(d,identifiant,"a"*64,{"traitees":10},
                             "Texte",[],[],[])
            import os
            import time
            chemin=Path(d)/DOSSIER/(identifiant+".zip")
            ancien=time.time()-7200
            os.utime(chemin,(ancien,ancien))
            purger_points(d,3600)
            self.assertFalse(chemin.exists())
