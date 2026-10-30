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
