"""Historique de 30 jours et sauvegarde des annotations de violence dans ScrapTikTok."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from io import BytesIO

from fastapi.testclient import TestClient

import webapp as web
from stockage.historique_analyses import retention_jours, retrouver, lister


class HistoriqueDesordreTests(unittest.TestCase):
    def test_archivage_annotations_reouverture_et_export_sans_mp4(self):
        with tempfile.TemporaryDirectory() as dossier:
            manager = web.Manager(data_dir=dossier)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                session_cookie = client.cookies[web.COOKIE]
                historique_cookie = client.cookies[web.HISTORIQUE_COOKIE]
                self.assertEqual(retention_jours(), 30)
                job = web.Job(session_cookie,
                              web.StartRequest(hashtag="test", enrichir=True),
                              Path(dossier), owner_historique=historique_cookie)
                job.update(busy=False, archive_prete=True, status="completed")
                manager.jobs[job.id] = job
                publication = {"id": "1234567890123",
                               "url": "https://www.tiktok.com/@media/video/1234567890123",
                               "description": "Une légende"}
                job.publications = [publication]
                (job.directory / "publications.json").write_text(
                    json.dumps([publication]), encoding="utf-8")
                videos = job.directory / "videos"
                videos.mkdir()
                (videos / "1234567890123.mp4").write_bytes(b"video-private")
                desordre = job.directory / "desordre_0123456789abcdef"
                desordre.mkdir()
                (desordre / "indicateurs_engagement.csv").write_text(
                    "publication_id;likes;indice_desordre\n1234567890123;50;30\n",
                    encoding="utf-8")
                (job.directory / "desordre_etat.json").write_text(
                    json.dumps({"statut": "termine", "dossier": desordre.name}),
                    encoding="utf-8")

                headers = {"X-ScrapTikTok": "1"}
                url = f"/api/jobs/{job.id}/desordre"
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    sauvegarde = client.post(url+"/sauvegarder", json={}, headers=headers)
                    self.assertEqual(sauvegarde.status_code, 200, sauvegarde.text)
                    self.assertEqual(sauvegarde.json()["retention_jours"], 30)

                    annotation = client.post(url+"/annotations", json={
                        "annotations":[{"publication_id":"1234567890123","violence_visible":1}]
                    }, headers=headers)
                    self.assertEqual(annotation.status_code, 200, annotation.text)
                    self.assertTrue(annotation.json()["historique_synchronise"])

                    variable = client.post(url+"/variables",json={
                        "nom":"Symbole de l'État"
                    },headers=headers)
                    self.assertEqual(variable.status_code,200,variable.text)
                    cle = variable.json()["variable"]["id"]
                    codage = client.post(url+"/codages",json={"annotations":[{
                        "variable_id":cle,"publication_id":"1234567890123","valeur":0
                    }]},headers=headers)
                    self.assertEqual(codage.status_code,200,codage.text)
                    self.assertTrue(codage.json()["historique_synchronise"])

                liste = client.get("/api/historique")
                self.assertEqual(liste.status_code, 200, liste.text)
                self.assertEqual(liste.json()["retention_jours"], 30)
                self.assertIn(job.id,[a["id"] for a in liste.json()["analyses"]])

                donnees_archives = retrouver(dossier, job.id, historique_cookie)
                self.assertIsNotNone(donnees_archives)
                repertoire_archive = donnees_archives[1]
                self.assertTrue((repertoire_archive/"desordre_etat.json").exists())
                self.assertTrue((repertoire_archive/desordre.name/"indicateurs_engagement.csv").exists())
                self.assertEqual(json.loads(
                    (repertoire_archive/"annotations_violence.json").read_text()
                )["1234567890123"], 1)
                self.assertEqual(json.loads(
                    (repertoire_archive/"codages_personnalises.json").read_text()
                )["valeurs"][cle]["1234567890123"], 0)
                self.assertFalse((repertoire_archive/"videos").exists())

                archive = client.get(f"/api/historique/{job.id}/archive")
                self.assertEqual(archive.status_code, 200)
                with ZipFile(BytesIO(archive.content)) as z:
                    self.assertIn("annotations_violence.json", z.namelist())
                    self.assertIn("codages_personnalises.json", z.namelist())
                    self.assertTrue(all(not x.endswith(".mp4") for x in z.namelist()))

                # Le cookie de la session de collecte expire avant le cookie
                # durable de l'historique : retrouver reste possible.
                manager.jobs.pop(job.id)
                client.cookies.set(web.COOKIE, "b"*64)
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    ouvert=client.post(f"/api/historique/{job.id}/ouvrir",
                                       json={},headers=headers)
                self.assertEqual(ouvert.status_code, 200, ouvert.text)
                self.assertEqual(ouvert.json()["id"], job.id)
                resultat=client.get(f"/api/jobs/{job.id}/desordre").json()
                self.assertEqual(resultat["codages_personnalises"]["valeurs"][cle]
                                 ["1234567890123"], 0)
                self.assertEqual(resultat["annotations_violence"]["oui"], 1)

    def test_history_session_non_proprietaire_refusee(self):
        with tempfile.TemporaryDirectory() as dossier:
            manager=web.Manager(data_dir=dossier)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                job=web.Job(client.cookies[web.COOKIE],
                            web.StartRequest(hashtag="test",enrichir=True),Path(dossier),
                            owner_historique="a"*64)
                job.update(busy=False,archive_prete=True)
                manager.jobs[job.id]=job
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    response=client.post(f"/api/jobs/{job.id}/desordre/sauvegarder",
                                         json={},headers={"X-ScrapTikTok":"1"})
                self.assertEqual(response.status_code,403)


if __name__=="__main__":
    unittest.main()
