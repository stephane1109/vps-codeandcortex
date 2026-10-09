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
        with tempfile.TemporaryDirectory() as d,patch.dict(webapp.os.environ,{'UI_STREAMLIT':'1','STREAMLIT_PORT':'65431'}):
            with TestClient(webapp.create_app(webapp.Manager(data_dir=d))) as client:
                accueil=client.get('/',follow_redirects=False)
                self.assertEqual(accueil.status_code,503)
                self.assertNotIn('location', accueil.headers)
                ancien=client.get('/interface/',follow_redirects=False)
                self.assertEqual(ancien.headers['location'],'/')
                self.assertTrue(client.cookies.get(webapp.COOKIE))
                self.assertEqual(client.get('/classique').status_code,200)
                self.assertEqual(client.post('/api/jobs',json={'hashtag':'test'}).status_code,403)
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/_stcore/stream',headers={'origin':'https://externe.test'}): pass
                self.assertEqual(client.get('/static/js/inexistant.js').status_code,503)
                self.assertEqual(client.get('/healthz').status_code,503)
                client.cookies.clear()
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/_stcore/stream',headers={'origin':'http://testserver'}): pass

    def test_accueil_et_ressources_streamlit_a_la_racine(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(webapp.os.environ, {'UI_STREAMLIT':'1','STREAMLIT_PORT':'65431'}):
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
                    self.assertEqual(client.get('/static/app.js').status_code,200)
                    self.assertEqual(client.get('/static/style.css').status_code,200)
