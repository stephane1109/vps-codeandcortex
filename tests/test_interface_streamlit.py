"""Formulaire Streamlit, sélection des médias et conservation des filtres."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from collecte.presse import charger_inventaire
from video.recherche_similaires import comparer_videos
from video.parametres import charger_seuils
from webapp import OptionsVideo, StartRequest

class TestsInterface(unittest.TestCase):
    def test_formulaire_et_selection_complete_des_medias(self):
        def repondre(chemin,*a,**kw):
            if chemin=='/api/session': return {'job':None}
            if chemin=='/api/configuration': return {'video_disponible':False}
            if chemin=='/api/presse': return {'medias':charger_inventaire()}
            raise AssertionError(chemin)
        with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})),patch('interface.client.appeler_api',side_effect=repondre):
            page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            self.assertFalse(page.exception)
            self.assertEqual([onglet.label for onglet in page.tabs], ['Collecte','Aide'])
            self.assertFalse(any('vidéo' in e.label.lower() for e in page.expander))
            self.assertFalse(any(c.key in {'comparer_sha256','comparer_sequences'} for c in page.checkbox))
            self.assertFalse(any(b.label=='Comparer les vidéos' for b in page.button))
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
            page.button(key='tous_medias').click().run()
            identifiants = [m['id'] for m in charger_inventaire()]
            self.assertEqual(page.session_state['medias'], identifiants)
            self.assertTrue(all(page.checkbox(key='media_'+m).value for m in identifiants))
            self.assertEqual(len(StartRequest(source_collecte='presse',medias=page.session_state['medias']).sources),len(identifiants))
            page.checkbox(key='media_lemonde').uncheck().run()
            self.assertEqual(len(page.session_state['medias']),len(identifiants)-1)
            page.radio(key='source').set_value('hashtags').run()
            page.radio(key='source').set_value('presse').run()
            self.assertFalse(page.checkbox(key='media_lemonde').value)
            self.assertTrue(page.checkbox(key='media_politis_fr').value)
            page.radio(key='source').set_value('hashtags').run()
            self.assertFalse(page.exception)
            page.date_input(key='date_debut').set_value('2026-10-01').run()
            self.assertFalse(page.exception)
    def test_catalogue_actualise_et_envoi_de_tous_les_medias_sans_ancien_hashtag(self):
        inventaire = charger_inventaire()
        catalogue = inventaire[:1]
        envois = []
        def repondre(chemin, session, autorisation, donnees=None):
            if chemin == '/api/session': return {'job': None}
            if chemin == '/api/presse': return {'medias': catalogue}
            if chemin == '/api/jobs':
                envois.append(donnees)
                return {}
            raise AssertionError(chemin)
        with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})), patch('interface.client.appeler_api',side_effect=repondre):
            page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            page.text_input(key='hashtag').set_value('filtre_ancien')
            next(b for b in page.button if b.label=='Lancer la collecte').click().run()
            catalogue = inventaire
            page.radio(key='source').set_value('presse').run()
            self.assertEqual(sum(c.key.startswith('media_') for c in page.checkbox),len(inventaire))
            self.assertEqual(page.text_input(key='hashtag_comptes').value,'')
            page.button(key='tous_medias').click().run()
            next(b for b in page.button if b.label=='Lancer la collecte').click().run()
            self.assertFalse(page.exception)
            self.assertEqual(envois[-1]['medias'],[m['id'] for m in inventaire])
            self.assertEqual(envois[-1]['hashtag'],'')
            self.assertEqual(len(StartRequest(**envois[-1]).sources),len(inventaire))
            page.radio(key='source').set_value('hashtags').run()
            self.assertEqual(page.text_input(key='hashtag').value,'filtre_ancien')

    def test_presse_transmet_deux_hashtags_et_le_choix_et_ou(self):
        envois = []
        def repondre(chemin, session, autorisation, donnees=None):
            if chemin == '/api/session': return {'job': None}
            if chemin == '/api/presse': return {'medias': charger_inventaire()}
            if chemin == '/api/jobs':
                envois.append(donnees)
                return {}
            raise AssertionError(chemin)
        with patch('streamlit.context', SimpleNamespace(cookies={'scraptiktok_session':'a'*64}, headers={})), patch('interface.client.appeler_api', side_effect=repondre):
            page = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            self.assertFalse(page.checkbox(key='txt_date').value)
            self.assertTrue(page.checkbox(key='txt_profil').value)
            self.assertTrue(page.checkbox(key='txt_url').value)
            page.radio(key='source').set_value('presse').run()
            page.button(key='tous_medias').click().run()
            for operateur in ('AND', 'OR'):
                page.text_input(key='hashtag_comptes').set_value('#GRÈVE')
                page.text_input(key='second_hashtag_comptes').set_value('#école')
                page.radio(key='operator').set_value(operateur)
                page.checkbox(key='collecter_reponses').check()
                page.checkbox(key='txt_date').check()
                page.checkbox(key='txt_profil').uncheck()
                page.checkbox(key='txt_url').uncheck()
                next(b for b in page.button if b.label == 'Lancer la collecte').click().run()
                self.assertFalse(page.exception)
                requete = StartRequest(**envois[-1])
                self.assertEqual(requete.hashtags, ['GRÈVE', 'école'])
                self.assertEqual(requete.operator, operateur)
                self.assertEqual(len(requete.sources), len(charger_inventaire()))
                self.assertTrue(envois[-1]['collecter_commentaires'])
                self.assertEqual(envois[-1]['variables_txt'], ['date'])
            nombre_envois = len(envois)
            page.date_input(key='date_debut').set_value('2026-10-01')
            page.date_input(key='date_fin').set_value('2026-10-09')
            next(b for b in page.button if b.label == 'Effacer la période').click().run()
            self.assertFalse(page.exception)
            self.assertIsNone(page.date_input(key='date_debut').value)
            self.assertIsNone(page.date_input(key='date_fin').value)
            self.assertEqual(len(envois), nombre_envois)

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

    def test_resultats_affichent_compteurs_et_commentaires(self):
        import tempfile
        from webapp import Job
        from collecte.engagement import extraire_engagement
        with tempfile.TemporaryDirectory() as d:
            tache = Job('a'*64, StartRequest(hashtag='test', collecter_commentaires=True), Path(d))
            tache.records.append({'id':'1', 'author':'media', 'url':'https://www.tiktok.com/@media/video/1',
                'description':'Oui !', 'langue_detection':'unknown',
                'engagement':extraire_engagement({'stats':{'diggCount':0,'commentCount':12}})})
            tache.commentaires.append({'publication_id':'1','texte':'Bravo'})
            tache.update(busy=False, status='completed')
            def repondre(chemin,*a,**kw):
                if chemin=='/api/session': return {'job':tache.snapshot()}
                if chemin=='/api/presse': return {'medias':charger_inventaire()}
                if chemin.startswith('/api/jobs/'): return tache.snapshot()
                raise AssertionError(chemin)
            with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})), patch('interface.client.appeler_api',side_effect=repondre):
                page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
                self.assertFalse(page.exception)
                tableau = page.dataframe[0].value
                self.assertEqual(tableau.iloc[0]['Likes'], '0')
                self.assertEqual(tableau.iloc[0]['Nombre de commentaires'], '12')
                self.assertEqual(tableau.iloc[0]['Vues'], 'Indisponible')
                self.assertEqual(tableau.iloc[0]['Langue'], 'Indéterminée')
                self.assertTrue(page.checkbox(key='collecter_commentaires').value)
                self.assertTrue(any('1 texte(s) de commentaires' in m.value for m in page.markdown))

    def test_reprise_des_variables_independantes(self):
        import tempfile
        from webapp import Job
        for variables in ([], ['url'], ['date','profil'], ['date','profil','url']):
            with self.subTest(variables=variables), tempfile.TemporaryDirectory() as dossier:
                tache = Job('a'*64, StartRequest(hashtag='test', variables_txt=variables), Path(dossier))
                tache.update(busy=False, status='completed')
                def repondre(chemin,*a,**kw):
                    if chemin=='/api/session': return {'job':tache.snapshot()}
                    if chemin=='/api/presse': return {'medias':charger_inventaire()}
                    if chemin.startswith('/api/jobs/'): return tache.snapshot()
                    raise AssertionError(chemin)
                with patch('streamlit.context',SimpleNamespace(cookies={'scraptiktok_session':'a'*64},headers={})), patch('interface.client.appeler_api',side_effect=repondre):
                    page=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
                    self.assertFalse(page.exception)
                    for variable in ('date','profil','url'):
                        self.assertEqual(page.checkbox(key='txt_'+variable).value, variable in variables)

    def test_liberer_acces_depuis_barre_laterale_conserve_la_collecte(self):
        import tempfile
        from webapp import Job
        with tempfile.TemporaryDirectory() as dossier:
            tache = Job('a'*64, StartRequest(hashtag='actualite'), Path(dossier))
            tache.update(status='attention')
            tache.video_busy = True
            appels = []
            def repondre(chemin, *a, **kw):
                if chemin == '/api/session': return {'job': tache.snapshot()}
                if chemin == '/api/presse': return {'medias': charger_inventaire()}
                if chemin == f'/api/jobs/{tache.id}/stop':
                    appels.append(chemin)
                    tache.update(busy=False, status='stopped')
                    return {'ok': True}
                if chemin == f'/api/jobs/{tache.id}/video/stop':
                    appels.append(chemin)
                    tache.video_busy = False
                    return {'ok': True}
                if chemin == f'/api/jobs/{tache.id}': return tache.snapshot()
                raise AssertionError(chemin)
            statut = {"enabled": True, "statut": "actif", "active": 1, "max_active": 8,
                      "heartbeat_ms": 300000, "message": ""}
            def liberer(*args, **kwargs):
                statut["statut"] = "released"
                return True
            with patch('ticket_gate.keep_ticket_alive', side_effect=lambda *a: dict(statut)), patch('ticket_gate.release_ticket_for_session', side_effect=liberer), patch('streamlit.context' , SimpleNamespace(cookies={'scraptiktok_session':'a'*64}, headers={})), patch('interface.client.appeler_api', side_effect=repondre):
                page = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
                self.assertFalse(page.exception)
                self.assertEqual(page.sidebar.button(key='liberer_acces').label, "Libérer l'accès")
                page.sidebar.button(key='liberer_acces').click().run()
                self.assertFalse(page.exception)
                self.assertEqual(appels, [f'/api/jobs/{tache.id}/stop', f'/api/jobs/{tache.id}/video/stop'])
                self.assertEqual(page.session_state['collecte']['id'], tache.id)
                self.assertTrue(any(b.label == "Reprendre l'accès" for b in page.sidebar.button))
                self.assertTrue(any('Accès libéré' in message.value for message in page.sidebar.info))
