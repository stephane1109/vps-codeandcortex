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
