import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import webapp as web
from fastapi.testclient import TestClient

class TestsEnrichis(unittest.TestCase):
    def test_compte_export_sqlite_et_commentaires(self):
        with tempfile.TemporaryDirectory() as d:
            job=web.Job("test",web.StartRequest(source_collecte="comptes",comptes=["media"],collecter_commentaires=True),Path(d))
            record={"id":"123","url":"https://www.tiktok.com/@media/video/123","author":"media","description":"Un texte","engagement":{}}
            with patch("collecte.comptes.collecter_compte",return_value=[record["url"]]), patch.object(web.scraper,"read_post",return_value=record), patch.object(job,"pause"), patch("collecte.commentaires.collecter_commentaires",return_value={"commentaires":[],"statut":"indisponible_ou_vide","exhaustif":False}):
                web.execute_job(job,driver_factory=lambda args:Mock())
            self.assertEqual(job.status,"completed"); self.assertTrue(job.archive_prete)
            self.assertEqual(json.loads((job.directory/"publications.json").read_text())[0]["id"],"123")
            with job.base.connexion() as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM publications").fetchone()[0],1)
    def test_plusieurs_medias_un_inaccessible_et_un_accessible(self):
        with tempfile.TemporaryDirectory() as d:
            job=web.Job("test",web.StartRequest(source_collecte="presse",medias=["lemonde","franceinfo"]),Path(d))
            record={"id":"123", "url":"https://www.tiktok.com/@franceinfo/video/123", "author":"franceinfo", "description":"Une actualité en France.", "engagement":{}}
            def decouvrir(navigateur, arguments, compte, rapport, **options):
                if compte == 'lemondefr':
                    rapport['discovery_stop']='blocked'
                    raise RuntimeError('CAPTCHA')
                return [record['url']]
            with patch('collecte.comptes.collecter_compte',side_effect=decouvrir) as comptes, patch.object(web.scraper,'read_post',return_value=record), patch.object(job,'pause'):
                web.execute_job(job,driver_factory=lambda args:Mock())
            self.assertEqual([c.args[2] for c in comptes.call_args_list],['lemondefr','franceinfo'])
            self.assertEqual(job.status,'partial')
            self.assertIn(record['description'],job.path.read_text())
            bilan=job.snapshot()['bilan_sources']
            self.assertEqual([b['liens'] for b in bilan],[0,1])
            self.assertIn('Vérification TikTok',bilan[0]['message'])

    def test_api_archive_proprietaire_et_video_optionnelle(self):
        with tempfile.TemporaryDirectory() as d:
            def terminer(job): job.update(busy=False,status="completed")
            manager=web.Manager(data_dir=d,runner=terminer)
            with TestClient(web.create_app(manager)) as client:
                client.get("/"); headers={"X-ScrapTikTok":"1"}
                r=client.post("/api/jobs",headers=headers,json={"source_collecte":"presse","medias":["lemonde"]})
                self.assertEqual(r.status_code,202,r.text); identifiant=r.json()["id"]
                with patch.dict(web.os.environ,{"INSTALL_VIDEO":"0"}):
                    self.assertEqual(client.post(f"/api/jobs/{identifiant}/video",headers=headers,json={}).status_code,409)
                with TestClient(web.create_app(manager)) as autre:
                    autre.get("/")
                    self.assertEqual(autre.get(f"/api/jobs/{identifiant}/archive").status_code,404)
                    self.assertEqual(autre.post(f"/api/jobs/{identifiant}/video/stop",headers=headers,json={}).status_code,404)


    def test_texte_sans_dependances_audiovisuelles(self):
        import subprocess,sys
        code="""
import sys,importlib.abc
class Blocage(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'cv2','numpy','torch','open_clip','faster_whisper','yt_dlp','PIL'}:
            raise ImportError('Dépendance audiovisuelle interdite dans ce test')
sys.meta_path.insert(0,Blocage())
import webapp
s=webapp.StartRequest(source_collecte='presse',medias=['lemonde'])
assert s.enrichie
from corpus.export_iramuteq import construire_corpus
assert '****' in construire_corpus([{'id':'1','texte':'Texte'}])
"""
        subprocess.run([sys.executable,"-c",code],check=True,capture_output=True)
