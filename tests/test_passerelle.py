"""Protection du WebSocket et disponibilité distincte du moteur et de l’interface."""
import base64
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from interface.passerelle import origine_valide,mot_de_passe_valide
import webapp

class TestsPasserelle(unittest.TestCase):
    def test_origine_et_authentification(self):
        self.assertTrue(origine_valide({'origin':'https://scraptiktok.codeandcortex.fr','host':'scraptiktok.codeandcortex.fr'}))
        self.assertFalse(origine_valide({'origin':'https://externe.test','host':'scraptiktok.codeandcortex.fr'}))
        self.assertFalse(origine_valide({'host':'localhost'}))
        with patch.dict(webapp.os.environ,{'APP_ACCESS_PASSWORD':'secret','APP_ACCESS_USER':'test'}):
            self.assertFalse(mot_de_passe_valide({}))
            self.assertTrue(mot_de_passe_valide({'authorization':'Basic '+base64.b64encode(b'test:secret').decode()}))
    def test_routes_et_websocket_prives(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(webapp.os.environ,{'STREAMLIT_PORT':'65431'}):
            with TestClient(webapp.create_app(webapp.Manager(data_dir=d))) as client:
                accueil=client.get('/',follow_redirects=False)
                self.assertEqual(accueil.status_code,503)
                self.assertNotIn('location', accueil.headers)
                ancien=client.get('/interface/',follow_redirects=False)
                self.assertEqual(ancien.headers['location'],'/')
                self.assertTrue(client.cookies.get(webapp.COOKIE))
                for chemin in ['/classique', '/classique/', '/classique?controle=1', '/static/index.html', '/static/app.js', '/static/style.css']:
                    self.assertEqual(client.get(chemin, follow_redirects=False).status_code, 404)
                controle=client.get('/controle')
                self.assertEqual(controle.status_code,200)
                self.assertNotIn('search-form',controle.text)
                self.assertNotIn('video-options',controle.text)
                self.assertIn('browser-screen',controle.text)
                self.assertEqual(client.post('/api/jobs',json={'hashtag':'test'}).status_code,403)
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/_stcore/stream',headers={'origin':'https://externe.test'}): pass
                self.assertEqual(client.get('/static/js/inexistant.js').status_code,503)
                self.assertEqual(client.get('/healthz').status_code,503)
                client.cookies.clear()
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/_stcore/stream',headers={'origin':'http://testserver'}): pass

    def test_accueil_et_ressources_streamlit_a_la_racine(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(webapp.os.environ, {'STREAMLIT_PORT':'65431'}):
            with TestClient(webapp.create_app(webapp.Manager(data_dir=d))) as client:
                with patch('interface.passerelle.httpx.AsyncClient') as fabrique:
                    serveur=fabrique.return_value.__aenter__.return_value
                    serveur.request=AsyncMock(return_value=httpx.Response(200,text='<html>Streamlit</html>',headers={'content-type':'text/html'}))
                    accueil=client.get('/')
                    self.assertEqual(accueil.status_code,200)
                    self.assertEqual(accueil.text,'<html>Streamlit</html>')
                    self.assertEqual(serveur.request.call_args.args[1],'http://127.0.0.1:65431/')
                    self.assertTrue(client.cookies.get(webapp.COOKIE))
                    client.get('/static/js/index.js')
                    self.assertEqual(serveur.request.call_args.args[1],'http://127.0.0.1:65431/static/js/index.js')
                    self.assertEqual(client.get('/static/app.js').status_code,404)
                    self.assertEqual(client.get('/static/controle.css').status_code,200)
                    self.assertEqual(client.get('/static/controle.js').status_code,200)
                    self.assertEqual(client.get('/static/navigateur.js').status_code,200)

    def test_controle_detecte_cookie_different_sans_donner_acces_a_la_collecte(self):
        """Le navigateur CAPTCHA ne doit jamais obtenir la collecte d'une autre session."""
        import hashlib
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            manager = webapp.Manager(data_dir=d)
            with TestClient(webapp.create_app(manager)) as client:
                self.assertEqual(client.get("/controle").status_code, 200)
                cookie_original = client.cookies.get(webapp.COOKIE)
                job = webapp.Job(cookie_original, webapp.StartRequest(
                    hashtag="manifestation"), Path(d))
                manager.jobs[job.id] = job

                api = client.get("/api/session")
                self.assertEqual(api.status_code, 200)
                self.assertEqual(api.json()["job"]["id"], job.id)
                self.assertEqual(
                    api.json()["empreinte_session"],
                    hashlib.sha256(cookie_original.encode()).hexdigest()[:16],
                )
                instance = api.json()["instance"]
                self.assertEqual(len(instance), 24)
                self.assertEqual(client.get("/api/jobs/" + job.id).status_code, 200)

                client.cookies.clear()
                client.cookies.set(webapp.COOKIE, "b" * 64)
                refus = client.get("/api/jobs/" + job.id)
                self.assertEqual(refus.status_code, 404)
                autre = client.get("/api/session").json()
                self.assertIsNone(autre["job"])
                self.assertEqual(autre["instance"], instance)
                self.assertNotEqual(
                    autre["empreinte_session"], api.json()["empreinte_session"],
                )

    def test_controle_affiche_un_diagnostic_de_session_et_un_lien_direct(self):
        from pathlib import Path
        racine = Path(__file__).resolve().parents[1]
        controle = (racine / "static" / "controle.js").read_text(encoding="utf-8")
        client = (racine / "static" / "navigateur.js").read_text(encoding="utf-8")
        streamlit = (racine / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("instanceAttendue", controle)
        self.assertIn("sessionAttendue", controle)
        self.assertIn("autre instance du serveur", controle)
        self.assertIn("même session privée", controle)
        self.assertIn("erreur.status = response.status", client)
        self.assertIn("Ouvrir le navigateur TikTok dans un onglet séparé", streamlit)

    def test_ancien_drapeau_ne_reactive_aucune_interface_html(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(webapp.os.environ,{'UI_STREAMLIT':'0','STREAMLIT_PORT':'65431'}):
            with TestClient(webapp.create_app(webapp.Manager(data_dir=d))) as client:
                self.assertEqual(client.get('/classique').status_code,404)
                self.assertEqual(client.get('/').status_code,503)
                self.assertNotIn('search-form',client.get('/controle').text)
