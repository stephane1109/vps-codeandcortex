"""Cookies privés, réponses natives du profil et reprise manuelle Playwright."""
import json
import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collecte.cookies_presse import charger_cookies_presse, appliquer_cookies_selenium
from collecte.presse_playwright import PressePlaywright
from collecte.presse_api import PresseRateLimitError
from collecte.controle_playwright import ControlePlaywright
from webapp import StartRequest, create_app, wait_for_user, perform_action, BrowserAction


COOKIES = "# Netscape HTTP Cookie File\n#HttpOnly_.tiktok.com\tTRUE\t/\tTRUE\t0\tsessionid\tsecret-test\n"


class SessionPresseTests(unittest.TestCase):
    def test_cookies_uniquement_tiktok_non_expires(self):
        texte = COOKIES + "example.com\tFALSE\t/\tTRUE\t0\tautre\tprive\n" + \
            ".tiktok.com\tTRUE\t/\tTRUE\t1\texpire\tinutilisable\n"
        cookies = charger_cookies_presse(texte)
        self.assertEqual(len(cookies), 1)
        self.assertTrue(cookies[0]["httpOnly"])
        self.assertEqual(cookies[0]["name"], "sessionid")
        self.assertNotIn("expires", cookies[0])

    def test_fichier_env_et_priorite_import_utilisateur(self):
        with tempfile.TemporaryDirectory() as dossier:
            fichier = Path(dossier) / "cookies.txt"
            fichier.write_text(COOKIES)
            with patch.dict(os.environ, {"SCRAPTIKTOK_COOKIES_FILE": str(fichier)}):
                self.assertEqual(charger_cookies_presse()[0]["value"], "secret-test")
                self.assertEqual(charger_cookies_presse(COOKIES.replace("secret-test", "utilisateur"))[0]["value"], "utilisateur")

    def test_erreurs_sans_valeur_secrete(self):
        for texte in ("secret-test", COOKIES + "secret-test", "x" * 1_048_577,
                      COOKIES.replace(".tiktok.com", "tiktok.com.evil.test")):
            with self.subTest(taille=len(texte)), self.assertRaises(RuntimeError) as erreur:
                charger_cookies_presse(texte)
            self.assertNotIn("secret-test", str(erreur.exception))

    def test_selenium_charge_sans_naviguer(self):
        navigateur = Mock()
        self.assertEqual(appliquer_cookies_selenium(navigateur, charger_cookies_presse(COOKIES)), 1)
        navigateur.execute_cdp_cmd.assert_called_once()
        navigateur.get.assert_not_called()

    def test_secrets_absents_des_serialisations(self):
        options = StartRequest(hashtag="actualité", cookies_tiktok=COOKIES)
        for texte in (str(options), options.model_dump_json(), str(options.model_dump())):
            self.assertNotIn("secret-test", texte)
            self.assertNotIn("cookies_tiktok", texte)

    def test_erreur_api_ne_renvoie_pas_le_corps_secret(self):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {"APP_ACCESS_PASSWORD": ""}):
            client = TestClient(create_app(manager=Mock()))
            reponse = client.post("/api/jobs", headers={"x-scraptiktok": "1"},
                json={"source_collecte": "comptes", "cookies_tiktok": COOKIES})
        self.assertEqual(reponse.status_code, 422)
        self.assertNotIn("secret-test", reponse.text)
        self.assertNotIn('"input"', reponse.text)

    def recevoir(self, client, donnees, statut=200):
        requete = Mock(url="https://www.tiktok.com/api/post/item_list/?signature=NE_PAS_EXPORTER")
        requete.response.return_value.status = statut
        requete.response.return_value.body.return_value = donnees
        client._recevoir_publications(requete)

    def test_reponse_native_filtre_auteur_photos_et_doublons(self):
        client = PressePlaywright(SimpleNamespace(limit=10))
        client.compte_attendu = "lemondefr"
        item = {"id": "1234567890", "author": {"uniqueId": "lemondefr"},
                "video": {}, "desc": "Une légende", "stats": {"diggCount": 4}}
        self.recevoir(client, json.dumps({"itemList": [item, item,
            {**item, "id": "1234567891", "author": {"uniqueId": "autre"}},
            {"id": "1234567892", "author": item["author"], "imagePost": {}}]}).encode())
        self.assertEqual(list(client.publications_reseau), ["1234567890"])
        self.assertEqual(client.publications_reseau["1234567890"]["description"], "Une légende")
        self.assertNotIn("NE_PAS_EXPORTER", str(client.bilan_reseau))

    def test_reponse_vide_ne_signifie_pas_absence_de_videos(self):
        client = PressePlaywright(SimpleNamespace(limit=10))
        client.compte_attendu = "lemondefr"
        self.recevoir(client, b"")
        self.assertEqual(client.bilan_reseau["reponses_vides"], 1)
        self.assertEqual(client.publications_reseau, {})

    def test_429_ne_propose_pas_de_reprise_manuelle(self):
        client = PressePlaywright(SimpleNamespace(limit=10, interactive=True), interaction=Mock())
        client.compte_attendu = "lemondefr"
        self.recevoir(client, b"", statut=429)
        with patch("collecte.presse_playwright._script", return_value="captcha"):
            with self.assertRaises(PresseRateLimitError):
                client._surveiller_page({})
        client.interaction.assert_not_called()

    def test_fenetre_manuelle_une_fois_dans_le_meme_navigateur(self):
        interaction = Mock()
        client = PressePlaywright(SimpleNamespace(interactive=True), interaction=interaction)
        self.assertTrue(client._intervenir("Vérifier"))
        self.assertFalse(client._intervenir("Vérifier encore"))
        controle, message = interaction.call_args.args
        self.assertIs(controle.client, client)
        self.assertEqual(message, "Vérifier")

    def test_gestes_playwright_ne_lancent_pas_selenium(self):
        client = SimpleNamespace(page=Mock())
        client.page.evaluate.return_value = [100, 200]
        controle = ControlePlaywright(client)
        with patch("webapp.ActionChains", side_effect=AssertionError("Selenium interdit")):
            perform_action(controle, BrowserAction(kind="pointer_down", points=[{"x": 0.5, "y": 0.5}]))
            perform_action(controle, BrowserAction(kind="pointer_up", points=[{"x": 0.6, "y": 0.5}]))
        client.page.mouse.down.assert_called_once()
        client.page.mouse.up.assert_called_once()

    def test_continuer_reutilise_la_fenetre_playwright_et_nettoie_la_capture(self):
        controle = ControlePlaywright(SimpleNamespace(page=Mock()))
        controle.nature_intervention = Mock(return_value="")
        controle.fermer_invitation = Mock()
        controle.get_screenshot_as_png = Mock(return_value=b"image")
        job = Mock(lock=threading.RLock(), status="discovering", message="Recherche", commands=queue.Queue())
        job.commands.put("continue")
        wait_for_user(controle, job, "Vérifier")
        controle.fermer_invitation.assert_called_once()
        self.assertEqual(job.update.call_args.kwargs["frame"], b"")

    def test_import_visible_dans_interface_presse_playwright(self):
        from streamlit.testing.v1 import AppTest
        from collecte.presse import charger_inventaire
        def repondre(chemin, session, autorisation, donnees=None, **options):
            if chemin == "/api/session": return {"job": None}
            if chemin == "/api/presse": return {"medias": charger_inventaire()}
            if chemin == "/api/sauvegardes": return {"sauvegardes": []}
            if chemin == "/api/presse/limitation": return {"actif": False}
            if chemin == "/api/collecte/limites": return {
                "maximum_publications_par_source": 1000, "maximum_sources_par_collecte": 29,
                "maximum_commentaires_par_video": 500}
            if chemin == "/healthz": return {}
            raise RuntimeError("API non utilisée dans ce test")
        with patch("streamlit.context", SimpleNamespace(cookies={"scraptiktok_session": "a" * 64}, headers={})), \
             patch("interface.client.appeler_api", side_effect=repondre):
            page = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py")).run()
            page.radio(key="source").set_value("presse").run()
            page.radio(key="presse_moteur").set_value("playwright").run()
            self.assertFalse(page.exception)
            self.assertTrue(any(e.label == "Importer les cookies TikTok (.txt, format Netscape)"
                                for e in page.get("file_uploader")))


if __name__ == "__main__":
    unittest.main()
