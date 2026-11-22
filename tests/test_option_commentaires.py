"""La case principale désactivée interdit la collecte des commentaires et réponses."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import webapp as web

class TestsOptionCommentaires(unittest.TestCase):
    def test_reponses_ne_reactivent_pas_commentaires(self):
        options=web.StartRequest(hashtag='test',collecter_commentaires=False,collecter_reponses=True)
        self.assertFalse(options.collecter_commentaires)
        self.assertFalse(options.collecter_reponses)

    def test_aucun_appel_collecteur_si_case_decochée(self):
        publication={'id':'123','url':'https://www.tiktok.com/@test/video/123','author':'test','description':'Texte #test'}
        with tempfile.TemporaryDirectory() as d:
            job=web.Job('test',web.StartRequest(hashtag='test',enrichir=True,french_only=False,
                collecter_commentaires=False,collecter_reponses=True),Path(d))
            with patch.object(web.scraper,'collect_links',return_value=[publication['url']]), patch.object(web.scraper,'read_post',return_value=publication), patch.object(job,'pause'), patch('collecte.commentaires.collecter_commentaires') as collecteur:
                web.execute_job(job,driver_factory=lambda args:Mock())
            self.assertEqual(job.status,'completed')
            self.assertEqual(len(job.records),1)
            collecteur.assert_not_called()
            self.assertEqual(job.snapshot()['commentaires_indisponibles'],0)

    def test_formulaire_ne_reactive_pas_la_case_principale(self):
        from types import SimpleNamespace
        from streamlit.testing.v1 import AppTest
        from collecte.presse import charger_inventaire
        envois=[]
        def repondre(chemin,session,autorisation,donnees=None):
            if chemin=='/api/session':return {'job':None}
            if chemin=='/api/presse':return {'medias':charger_inventaire()}
            if chemin=='/api/jobs':envois.append(donnees);return {}
            raise AssertionError(chemin)
        with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})),patch('interface.client.appeler_api',side_effect=repondre):
            page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            self.assertFalse(page.checkbox(key='collecter_commentaires').value)
            page.text_input(key='hashtag').set_value('test')
            page.checkbox(key='collecter_reponses').check()
            page.checkbox(key='collecter_commentaires').uncheck()
            next(b for b in page.button if b.label=='Lancer la collecte').click().run()
            self.assertFalse(page.exception)
            self.assertFalse(envois[-1]['collecter_commentaires'])
            self.assertFalse(envois[-1]['collecter_reponses'])
