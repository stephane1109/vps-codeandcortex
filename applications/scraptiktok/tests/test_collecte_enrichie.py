import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import webapp as web
from fastapi.testclient import TestClient

class TestsEnrichis(unittest.TestCase):
    def test_premier_profil_ouvre_la_verification_une_fois_pour_toute_la_selection(self):
        with tempfile.TemporaryDirectory() as dossier:
            job = web.Job('test', web.StartRequest(source_collecte='comptes', comptes=['lemondefr','franceinfo']), Path(dossier))
            validations = []
            def decouvrir(navigateur, arguments, compte, rapport, **options):
                validations.append(options['validation_initiale'])
                if options['validation_initiale']:
                    options['interact']('Vérifiez le premier profil.')
                return []
            with patch('collecte.comptes.collecter_compte', side_effect=decouvrir), patch.object(web, 'wait_for_user') as verifier:
                web.execute_job(job, driver_factory=lambda args: Mock())
            self.assertEqual(validations, [True, False])
            verifier.assert_called_once()
            self.assertFalse(job.busy)

    def test_erreur_tiktok_explicite_dans_resultats_et_journal(self):
        with tempfile.TemporaryDirectory() as dossier:
            job = web.Job('test', web.StartRequest(source_collecte='comptes', comptes=['lemondefr']), Path(dossier))
            def echouer(navigateur, arguments, compte, rapport, **options):
                rapport.update(diagnostic={'code':'erreur_tiktok'}, rechargements=1, discovery_stop='tiktok_error')
                raise RuntimeError('Erreur de chargement TikTok')
            pilote = Mock()
            with patch('collecte.comptes.collecter_compte', side_effect=echouer):
                web.execute_job(job, driver_factory=lambda args: pilote)
            self.assertFalse(job.busy)
            self.assertEqual(job.status, 'failed')
            self.assertIn('Something went wrong', job.message)
            self.assertNotIn('vérification', job.message)
            self.assertEqual(job.journal[0]['rapport']['rechargements'], 1)
            pilote.quit.assert_called_once()

    def test_presse_deux_hashtags_et_ou_jusqu_aux_exports(self):
        descriptions = ['#GRÈVE #école', '#grève', '#école', 'grève et école sans hashtags']
        comptes = ['lemondefr', 'franceinfo', 'lemondefr', 'franceinfo']
        publications = [{
            'id': str(100+i), 'url': f'https://www.tiktok.com/@{compte}/video/{100+i}',
            'author': compte, 'description': texte, 'engagement': {},
        } for i, (compte, texte) in enumerate(zip(comptes, descriptions))]
        for operateur, attendus in [('AND', ['100']), ('OR', ['100', '101', '102'])]:
            with self.subTest(operateur=operateur), tempfile.TemporaryDirectory() as d:
                job = web.Job('test', web.StartRequest(source_collecte='presse',
                    medias=['lemonde', 'franceinfo'], hashtag='grève', second_hashtag='école',
                    operator=operateur, french_only=False), Path(d))
                validations = []
                def decouvrir(navigateur, arguments, rapport, **options):
                    self.assertNotIn('compte_attendu', rapport)
                    validations.append(options['validation_initiale'])
                    if options['validation_initiale']: options['interact']('Vérification TikTok')
                    return [p['url'] for p in publications]
                def lire(navigateur, url, *args, **options):
                    return dict(next(p for p in publications if p['url'] == url))
                with patch.object(web.scraper, 'collect_links', side_effect=decouvrir) as collecte, patch.object(web, 'wait_for_user'), patch('collecte.comptes.collecter_compte') as profils, patch.object(web.scraper, 'read_post', side_effect=lire), patch.object(job, 'pause'):
                    web.execute_job(job, driver_factory=lambda args: Mock())
                self.assertEqual([c.args[2]['hashtag_url'] for c in collecte.call_args_list], ['https://www.tiktok.com/tag/gr%C3%A8ve', 'https://www.tiktok.com/tag/%C3%A9cole'])
                self.assertEqual(validations, [True, False])
                profils.assert_not_called()
                self.assertEqual([p['id'] for p in job.records], attendus)
                self.assertEqual(job.processed, 4)
                self.assertEqual(job.filtered, 4-len(attendus))
                bilan = job.snapshot()
                self.assertEqual(bilan['bilan_hashtags'], {'grève': 2, 'école': 2})
                self.assertEqual(bilan['correspondances_hashtags'], len(attendus))
                self.assertEqual(job.status, 'completed')
                self.assertTrue(job.archive_prete)
                export = json.loads((job.directory/'publications.json').read_text())
                self.assertEqual([p['id'] for p in export if p['retenue']], attendus)
                for p in publications:
                    self.assertEqual(p['url'] in job.path.read_text(), p['id'] in attendus)

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

    def test_echecs_navigation_ne_sont_pas_presentes_comme_medias_vides(self):
        self.assertIn('délai',web.expliquer_echec_source({},web.scraper.TimeoutException()))
        self.assertIn('navigateur',web.expliquer_echec_source({},web.scraper.WebDriverException()))
        rapport={'diagnostic':{'code':'erreur_reseau','erreur_reseau':'net::ERR_NAME_NOT_RESOLVED'}}
        self.assertIn('ERR_NAME_NOT_RESOLVED',web.expliquer_echec_source(rapport,web.scraper.WebDriverException()))

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

    def test_presse_filtre_auteur_lu_apres_collecte_hashtag(self):
        with tempfile.TemporaryDirectory() as dossier:
            job=web.Job('test',web.StartRequest(source_collecte='presse',medias=['lemonde'],hashtag='test'),Path(dossier))
            liens=['https://www.tiktok.com/@lemondefr/video/101','https://www.tiktok.com/@autre/video/102']
            # Une redirection éventuelle ne doit pas faire retenir un autre auteur.
            textes=[{'id':'101','url':liens[0],'author':'autre','description':'#test refusé'},
                    {'id':'102','url':liens[1],'author':'lemondefr','description':'#test retenu'}]
            with patch.object(web.scraper,'collect_links',return_value=liens) as collecte, patch.object(web.scraper,'read_post',side_effect=textes), patch.object(job,'pause'):
                web.execute_job(job,driver_factory=lambda args:Mock())
            collecte.assert_called_once()
            self.assertEqual([p['id'] for p in job.records],['102'])
            self.assertEqual([p['id'] for p in job.publications],['102'])
            self.assertEqual(job.processed,2)
            self.assertIn('1 publication(s) écartée(s) car l’auteur',job.message)
            self.assertNotIn('refusé',job.path.read_text())
