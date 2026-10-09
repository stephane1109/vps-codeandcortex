"""Protection du WebSocket et disponibilité distincte du moteur et de l’interface."""
import base64
import tempfile
import unittest
from unittest.mock import patch
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
                self.assertEqual(accueil.status_code,302)
                self.assertEqual(accueil.headers['location'],'/interface/')
                self.assertTrue(client.cookies.get(webapp.COOKIE))
                self.assertEqual(client.get('/classique').status_code,200)
                self.assertEqual(client.post('/api/jobs',json={'hashtag':'test'}).status_code,403)
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/interface/_stcore/stream',headers={'origin':'https://externe.test'}): pass
                self.assertEqual(client.get('/interface/').status_code,503)
                self.assertEqual(client.get('/healthz').status_code,503)
                client.cookies.clear()
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect('/interface/_stcore/stream',headers={'origin':'http://testserver'}): pass
