"""Exécuter le collecteur sur des pages dynamiques locales, sans requête à TikTok.

Activer avec SCRAPTIKTOK_TEST_NAVIGATEUR=1 et un Chromium installé ; le routage
Playwright remplace toutes les réponses par nos pages HTML de test.
"""
import os
from types import SimpleNamespace
import unittest

from collecte.presse_playwright import PressePlaywright


@unittest.skipUnless(os.getenv("SCRAPTIKTOK_TEST_NAVIGATEUR") == "1", "Navigateur de test facultatif")
class ProfilsDansNavigateurTests(unittest.TestCase):
    def setUp(self):
        self.client = PressePlaywright(SimpleNamespace(timeout=16, limit=1,
            delay=0, max_scrolls=0, idle_rounds=1)).ouvrir()
        self.addCleanup(self.client.fermer)
        self.requetes = []

    def charger(self, javascript, *, debut=""):
        page = "<!doctype html><html><head><meta charset='utf-8'><title>Profil de test</title></head><body><main>" + debut + "</main><script>" + javascript + "</script></body></html>"
        def repondre(route):
            self.requetes.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=page)
        self.client.context.route("**/*", repondre)

    def test_grille_initiale_tardive_a_douze_secondes(self):
        self.charger('''setTimeout(() => {
          document.querySelector('main').innerHTML = '<div data-e2e="user-post-item-list"><a href="/@lemondefr/video/1234567890">Vidéo</a></div>';
        }, 12500);''')
        rapport = {}
        self.assertEqual(self.client.decouvrir("lemondefr", rapport),
            ["https://www.tiktok.com/@lemondefr/video/1234567890"])
        self.assertEqual(rapport["discovery_stop"], "limit")
        self.assertTrue(self.requetes)

    def test_reponse_native_avec_cookie_avant_navigation_et_sans_grille(self):
        import json
        self.client.context.add_cookies([{"name": "session_test", "value": "prive",
            "domain": ".tiktok.com", "path": "/", "httpOnly": True, "secure": True}])
        self.charger("fetch('/api/post/item_list/?test=1');", debut="Something went wrong")
        requetes = []
        def repondre_api(route):
            requetes.append(route.request.headers.get("cookie", ""))
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "statusCode": 0, "itemList": [{"id": "1234567890",
                "author": {"uniqueId": "lemondefr"}, "video": {}, "desc": "Texte reçu"}]}))
        self.client.context.route("**/api/post/item_list/**", repondre_api)
        rapport = {}
        self.assertEqual(self.client.decouvrir("lemondefr", rapport),
                         ["https://www.tiktok.com/@lemondefr/video/1234567890"])
        self.assertIn("session_test=prive", requetes[0])
        self.assertEqual(rapport["metadonnees_api"]["1234567890"]["description"], "Texte reçu")
        self.assertNotIn("session_test", str(rapport))

    def test_page_en_erreur_permet_intervention_et_reprise(self):
        self.client.args.timeout = 0.3
        self.client.args.interactive = True
        self.charger("", debut="Something went wrong")
        controles = []
        def intervenir(controle, message):
            # Simuler seulement notre page de test, jamais un CAPTCHA réel.
            controles.append(controle)
            self.assertTrue(controle.get_screenshot_as_png().startswith(b'\x89PNG'))
            controle.client.page.evaluate("""() => {
                document.querySelector('main').innerHTML = '<a href="/@lemondefr/video/1234567890">Vidéo</a>';
            }""")
        self.client.interaction = intervenir
        self.assertEqual(self.client.decouvrir("lemondefr", {}),
                         ["https://www.tiktok.com/@lemondefr/video/1234567890"])
        self.assertEqual(len(controles), 1)

    def test_429_api_interrompt_sans_fenetre_ni_requete_supplementaire(self):
        from collecte.presse_api import PresseRateLimitError
        from unittest.mock import Mock
        self.client.args.interactive = True
        self.client.interaction = Mock()
        self.charger("fetch('/api/post/item_list/?test=1');")
        self.client.context.route("**/api/post/item_list/**",
                                  lambda route: route.fulfill(status=429, body=""))
        with self.assertRaises(PresseRateLimitError):
            self.client.decouvrir("lemondefr", {})
        self.client.interaction.assert_not_called()

    def test_onglet_tardif_et_premier_clic_avant_attachement_react(self):
        self.charger('''setTimeout(() => {
          document.querySelector('main').innerHTML = '<button role="tab" aria-selected="false">Vidéos</button><div id="resultats"></div>';
        }, 2500);
        setTimeout(() => document.querySelector('button').addEventListener('click', () => {
          document.querySelector('button').setAttribute('aria-selected','true');
          document.getElementById('resultats').innerHTML = '<div data-e2e="user-post-item-list"><a href="/@lemondefr/video/1234567891">Vidéo</a></div>';
        }), 3300);''')
        self.assertEqual(self.client.decouvrir("lemondefr", {}),
            ["https://www.tiktok.com/@lemondefr/video/1234567891"])

    def test_dernier_scroll_conserve_le_nouveau_lien_et_exclut_autres_auteurs(self):
        self.client.args.limit = 2
        self.client.args.max_scrolls = 1
        self.charger('''window.addEventListener('wheel', () => setTimeout(() => {
          document.querySelector('[data-e2e="user-post-item-list"]').insertAdjacentHTML('beforeend',
            '<a href="/@autre/video/9876543210">Autre compte</a><a href="/@lemondefr/photo/1234567893">Photo</a><a href="/@lemondefr/video/1234567892">Deuxième vidéo</a>');
        }, 500), {once:true});''', debut='''<div data-e2e="user-post-item-list"><a href="/@lemondefr/video/1234567890">Première vidéo</a></div>''')
        rapport = {}
        self.assertEqual(self.client.decouvrir("lemondefr", rapport), [
            "https://www.tiktok.com/@lemondefr/video/1234567890",
            "https://www.tiktok.com/@lemondefr/video/1234567892"])
        self.assertEqual(rapport["pagination_profil"][-1]["liens_apres"], 2)

    def test_captcha_reel_dans_le_dom_est_signale(self):
        self.charger("", debut='<div id="captcha">Vérification requise</div>')
        rapport = {}
        with self.assertRaises(RuntimeError): self.client.decouvrir("lemondefr", rapport)
        self.assertEqual(rapport["diagnostic"]["code"], "verification_tiktok")

    def test_invitation_facultative_fermee_avec_son_bouton(self):
        self.charger('''document.querySelector('button').onclick = () => {
          document.querySelector('[data-e2e="login-modal"]').remove();
          document.querySelector('main').innerHTML = '<div data-e2e="user-post-item-list"><a href="/@lemondefr/video/1234567890">Vidéo</a></div>';
        };''', debut='''<div data-e2e="login-modal"><button aria-label="Fermer">Fermer</button></div>''')
        self.assertEqual(self.client.decouvrir("lemondefr", {}),
            ["https://www.tiktok.com/@lemondefr/video/1234567890"])


if __name__ == "__main__":
    unittest.main()
