"""Les miniatures et classements DINOv2 restent privés à la collecte."""
import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
import webapp as web

class TestsApiDino(unittest.TestCase):
    def test_classement_filtre_et_miniature_privee(self):
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d)
            with TestClient(web.create_app(manager)) as client:
                client.get('/')
                job=web.Job(client.cookies[web.COOKIE],web.StartRequest(hashtag='test',enrichir=True),Path(d))
                manager.jobs[job.id]=job
                (job.directory/'miniatures_dino').mkdir()
                (job.directory/'miniatures_dino'/'1.jpg').write_bytes(b'jpeg-test')
                (job.directory/'similarites_dino.json').write_text(json.dumps([{'a':'1','b':'2','score':.1},{'a':'2','b':'1','score':.1}]))
                resultat=client.get(f'/api/jobs/{job.id}/videos-similaires?video=1').json()
                self.assertEqual(resultat['videos_dino'],['1','2'])
                self.assertEqual(len(resultat['dinov2']),1)
                self.assertEqual(client.get(f'/api/jobs/{job.id}/miniatures-dino/1').content,b'jpeg-test')
                client.cookies.clear();client.get('/')
                self.assertEqual(client.get(f'/api/jobs/{job.id}/miniatures-dino/1').status_code,404)

    def test_regions_privees_paire_validee_et_erreur_modele(self):
        from unittest.mock import patch, MagicMock
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d)
            with TestClient(web.create_app(manager)) as client:
                client.get('/')
                job=web.Job(client.cookies[web.COOKIE],web.StartRequest(hashtag='test',enrichir=True),Path(d))
                job.busy=False
                manager.jobs[job.id]=job
                miniatures=job.directory/'miniatures_dino';miniatures.mkdir()
                for n in (1,2): (miniatures/f'{n}.jpg').write_bytes(b'image'+str(n).encode())
                (job.directory/'similarites_dino.json').write_text(json.dumps([{'correspondances':[{'image_a':1,'image_b':2}]}]))
                url=f'/api/jobs/{job.id}/regions-dino/1/2'
                self.assertEqual(client.get(url).json()['statut'],'non_calcule')
                self.assertEqual(client.get(url+'/../../3/4').status_code,404)
                self.assertEqual(client.get(f'/api/jobs/{job.id}/regions-dino/1/3').status_code,404)
                self.assertEqual(client.post(url,json={}).status_code,403)
                processus=MagicMock();processus.poll.return_value=1;processus.returncode=1
                with patch('ticket_gate.verifier_session_active',return_value=True),patch('webapp.subprocess.Popen',return_value=processus):
                    self.assertEqual(client.post(url,json={},headers={'X-ScrapTikTok':'1'}).status_code,202)
                    job.video_thread.join(timeout=3)
                self.assertFalse(job.video_busy)
                self.assertEqual(client.get(url).json()['statut'],'erreur')
                client.cookies.clear();client.get('/')
                self.assertEqual(client.get(url).status_code,404)
                self.assertEqual(client.get(url+'/a').status_code,404)
