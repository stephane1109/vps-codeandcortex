"""Période inclusive, bornes ouvertes, UTC et exclusion cohérente des exports."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from collecte.dates import evaluer_periode
import webapp as web

class TestsDates(unittest.TestCase):
    def test_bornes_inclusives_et_utc(self):
        for valeur in ('2026-10-01T00:00:00Z','2026-10-31T23:59:59+00:00'):
            self.assertEqual(evaluer_periode(valeur,'2026-10-01','2026-10-31'),'dans_periode')
        self.assertEqual(evaluer_periode('2026-11-01T00:30:00+02:00','2026-10-01','2026-10-31'),'dans_periode')
        self.assertEqual(evaluer_periode('2026-10-01T00:30:00+02:00','2026-10-01',None),'hors_periode')
        self.assertEqual(evaluer_periode('2026-09-01T10:00:00Z',None,'2026-10-01'),'dans_periode')
        self.assertEqual(evaluer_periode('2026-11-01T10:00:00Z','2026-10-01',None),'dans_periode')
    def test_absence_de_date_et_filtre_desactive(self):
        for valeur in ('',None,'invalide'):
            self.assertEqual(evaluer_periode(valeur),'sans_filtre')
            self.assertEqual(evaluer_periode(valeur,'2026-10-01'),'date_indeterminee')
    def test_validation_api_et_reprise_session(self):
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d,runner=lambda job:job.update(busy=False))
            with TestClient(web.create_app(manager)) as client:
                client.get('/'); entetes={'X-ScrapTikTok':'1'}
                for valeurs in ({'date_debut':'2026-02-30'},{'date_debut':'2026-10-31','date_fin':'2026-10-01'},{'date_fin':'20261001'}):
                    self.assertEqual(client.post('/api/jobs',headers=entetes,json={'hashtag':'test',**valeurs}).status_code,422)
                r=client.post('/api/jobs',headers=entetes,json={'hashtag':'test','enrichir':True,'date_debut':'2026-10-01','date_fin':'2026-10-31'})
                self.assertEqual(r.status_code,202,r.text)
                self.assertEqual(client.get('/api/session').json()['job']['date_fin'],'2026-10-31')
                self.assertIsNone(web.StartRequest(hashtag='test',date_debut='').date_debut)
    def test_periode_combinee_et_exports_par_source(self):
        for source in ('hashtags','comptes','presse'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as d:
                options={'source_collecte':source,'hashtag':'test','second_hashtag':'presse','enrichir':True,'date_debut':'2026-10-01','date_fin':'2026-10-31','collecter_commentaires':True,'french_only':True}
                if source=='comptes': options['comptes']=['media']
                if source=='presse': options['medias']=['lemonde']
                job=web.Job('test',web.StartRequest(**options),Path(d))
                dates=['2026-10-01T00:00:00Z','2026-10-31T23:59:59Z','2026-09-30T23:59:59Z','', '2026-10-10T00:00:00Z']
                publications=[{'id':str(i),'url':f'https://www.tiktok.com/@media/video/{i}','author':'media','created_at':date,'description':('Les journalistes présentent les informations et expliquent les événements de la journée. #test #presse' if i!=5 else 'Une autre publication. #test'),'engagement':{}} for i,date in enumerate(dates,1)]
                urls=[p['url'] for p in publications]
                with patch.object(web.scraper,'collect_links',return_value=urls),patch('collecte.comptes.collecter_compte',return_value=urls),patch.object(web.scraper,'read_post',side_effect=publications),patch.object(job,'pause'),patch('collecte.commentaires.collecter_commentaires',side_effect=lambda *a,**k:{'commentaires':[],'exhaustif':False}) as commentaires:
                    # La recherche ET interroge deux hashtags, puis dédoublonne les URL.
                    web.execute_job(job,driver_factory=lambda args:Mock())
                self.assertEqual(job.status,'completed')
                self.assertEqual((job.hors_periode,job.dates_indeterminees),(1,1))
                self.assertEqual([r['id'] for r in job.records],['1','2'])
                self.assertEqual(commentaires.call_count,2)
                brut=json.loads((job.directory/'publications.json').read_text())
                self.assertEqual([p['id'] for p in brut],['1','2','5'])
                self.assertTrue(job.archive_prete)
                with job.base.connexion() as base:
                    self.assertEqual(base.execute('SELECT COUNT(*) FROM publications').fetchone()[0],3)
    def test_sans_periode_conserve_publication_non_datee(self):
        with tempfile.TemporaryDirectory() as d:
            job=web.Job('test',web.StartRequest(hashtag='test'),Path(d))
            record={'id':'1','url':'https://www.tiktok.com/@media/video/1','author':'media','description':'Texte #test','created_at':''}
            with patch.object(web.scraper,'collect_links',return_value=[record['url']]),patch.object(web.scraper,'read_post',return_value=record),patch.object(job,'pause'):
                web.execute_job(job,driver_factory=lambda args:Mock())
            self.assertEqual(len(job.records),1)
