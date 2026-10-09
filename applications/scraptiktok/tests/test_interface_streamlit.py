"""Formulaire Streamlit, conservation des choix et activation des vraies méthodes."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from collecte.presse import charger_inventaire
from video.recherche_similaires import comparer_videos
from video.parametres import charger_seuils
from webapp import OptionsVideo

class TestsInterface(unittest.TestCase):
    def test_formulaire_et_methodes_toujours_visibles(self):
        def repondre(chemin,*a,**kw):
            if chemin=='/api/session': return {'job':None}
            if chemin=='/api/configuration': return {'video_disponible':False}
            if chemin=='/api/presse': return {'medias':charger_inventaire()}
            raise AssertionError(chemin)
        with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})),patch('interface.client.appeler_api',side_effect=repondre):
            page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            self.assertFalse(page.exception)
            self.assertTrue(page.checkbox(key='comparer_sha256').value)
            self.assertTrue(page.checkbox(key='comparer_sequences').value)
            self.assertTrue(any('pas activée' in i.value for i in page.info))
            self.assertTrue(next(b for b in page.button if b.label=='Analyser les vidéos').disabled)
            page.radio(key='source').set_value('comptes').run()
            self.assertFalse(page.exception)
            page.text_input(key='comptes').set_value('@lemondefr').run()
            page.radio(key='source').set_value('presse').run()
            self.assertTrue(any('Le Monde' in c.label for c in page.checkbox))
            page.checkbox(key='media_lemonde').check().run()
            self.assertEqual(page.session_state['medias'], ['lemonde'])
            page.radio(key='source').set_value('hashtags').run()
            page.radio(key='source').set_value('presse').run()
            self.assertTrue(page.checkbox(key='media_lemonde').value)
            page.radio(key='source').set_value('hashtags').run()
            self.assertFalse(page.exception)
            page.date_input(key='date_debut').set_value('2026-10-01').run()
            self.assertFalse(page.exception)
    def test_sha_et_orb_sont_effectivement_optionnels(self):
        a={'id':'1','sha256':'idem','images':[]}; b={**a,'id':'2'}
        seuils=charger_seuils()
        self.assertEqual(comparer_videos(a,b,seuils,options={'comparer_sequences':False})['type'],'fichier_identique')
        sans=comparer_videos(a,b,seuils,options={'comparer_sha256':False,'comparer_sequences':False})
        self.assertEqual(sans['type'],'comparaison_sequences_desactivee')
        self.assertFalse(sans['methodes']['sha256'])
        self.assertIsNone(sans['confiance'])
        self.assertEqual(comparer_videos(a,b,seuils,options={'comparer_sha256':False})['type'],'indetermine')
        self.assertFalse(OptionsVideo(comparer_sequences=False).comparer_sequences)

    def test_etape_navigateur_streamlit(self):
        import tempfile
        from webapp import Job, StartRequest
        with tempfile.TemporaryDirectory() as d:
            tache=Job('a'*64,StartRequest(hashtag='test'),Path(d))
            tache.update(status='attention')
            def repondre(chemin,*a,**kw):
                if chemin=='/api/session': return {'job':tache.snapshot()}
                if chemin=='/api/configuration': return {'video_disponible':False}
                if chemin=='/api/presse': return {'medias':charger_inventaire()}
                if chemin.startswith('/api/jobs/'): return tache.snapshot()
                raise AssertionError(chemin)
            with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})),patch('interface.client.appeler_api',side_effect=repondre):
                page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
                self.assertFalse(page.exception)
                self.assertTrue(any('Vérifiez TikTok' in i.value for i in page.info))
