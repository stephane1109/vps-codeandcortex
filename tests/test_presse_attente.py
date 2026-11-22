"""Profils dynamiques : rendus tardifs, dernière pagination et causes d'échec."""
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import scraptiktok as moteur
from collecte.navigation_videos import NAVIGUER_VIDEOS_JS, DIAGNOSTIC_VIDEOS_JS
from collecte.presse_playwright import PressePlaywright, LIENS_VIDEOS_JS, SCROLL_JS
from collecte.presse_api import PresseApiError, PresseRateLimitError
from webapp import expliquer_echec_source


def adresse(numero, compte="lemondefr"):
    return f"https://www.tiktok.com/@{compte}/video/{numero}"


class Horloge:
    def __init__(self):
        self.temps = 0.0

    def maintenant(self):
        return self.temps

    def attendre(self, millisecondes):
        self.temps += millisecondes / 1000


class AttentePresseTests(unittest.TestCase):
    def preparer(self, *, limite=1, delai=20, defilements=1):
        horloge = Horloge()
        client = PressePlaywright(SimpleNamespace(limit=limite, timeout=delai,
            delay=0, max_scrolls=defilements, idle_rounds=3))
        client.page = Mock()
        client.page.url = "https://www.tiktok.com/@lemondefr"
        client.page.wait_for_timeout.side_effect = horloge.attendre
        client._visiter = Mock()
        client._surveiller_page = Mock(return_value=True)
        return client, horloge

    def lancer(self, client, horloge, rapport=None):
        with patch("collecte.presse_playwright.time.monotonic", horloge.maintenant):
            return client.decouvrir("lemondefr", rapport if rapport is not None else {})

    def test_onglet_apparu_apres_quatre_secondes_est_ouvert(self):
        client, horloge = self.preparer(defilements=0)
        clics = []
        def evaluer(code, *args):
            if code == NAVIGUER_VIDEOS_JS:
                if horloge.temps < 4: return {"statut": "introuvable"}
                clics.append(horloge.temps)
                return {"statut": "clic"}
            if code == LIENS_VIDEOS_JS: return [adresse(100)] if clics else []
            return {}
        client.page.evaluate.side_effect = evaluer
        self.assertEqual(self.lancer(client, horloge), [adresse(100)])
        self.assertEqual(len(clics), 1)
        self.assertGreaterEqual(clics[0], 4)

    def test_clic_avant_attachement_react_est_retente_sans_rafale(self):
        client, horloge = self.preparer(defilements=0)
        clics = []
        def evaluer(code, *args):
            if code == NAVIGUER_VIDEOS_JS:
                clics.append(horloge.temps)
                return {"statut": "clic"}
            if code == LIENS_VIDEOS_JS: return [adresse(100)] if len(clics) >= 2 else []
            return {}
        client.page.evaluate.side_effect = evaluer
        self.assertEqual(self.lancer(client, horloge), [adresse(100)])
        self.assertEqual(len(clics), 2)
        self.assertGreaterEqual(clics[1] - clics[0], 2)

    def test_premiere_grille_apparait_a_douze_secondes(self):
        client, horloge = self.preparer(defilements=0)
        client.page.evaluate.side_effect = lambda code, *args: (
            {"statut": "introuvable"} if code == NAVIGUER_VIDEOS_JS else
            [adresse(100)] if code == LIENS_VIDEOS_JS and horloge.temps >= 12 else [])
        self.assertEqual(self.lancer(client, horloge), [adresse(100)])
        self.assertGreaterEqual(horloge.temps, 12)

    def test_dernier_defilement_lit_les_nouveaux_liens(self):
        client, horloge = self.preparer(limite=2, defilements=1)
        def evaluer(code, *args):
            if code == NAVIGUER_VIDEOS_JS: return {"statut": "deja_actif"}
            if code == LIENS_VIDEOS_JS:
                return [adresse(100), adresse(101)] if horloge.temps >= 3 else [adresse(100)]
            return {}
        client.page.evaluate.side_effect = evaluer
        bilan = {}
        self.assertEqual(self.lancer(client, horloge, bilan), [adresse(100), adresse(101)])
        self.assertEqual(bilan["pagination_profil"][0]["liens_apres"], 2)
        self.assertEqual(bilan["discovery_stop"], "limit")
        client.page.mouse.wheel.assert_called_once()

    def test_page_vide_attend_le_budget_et_donne_la_cause(self):
        client, horloge = self.preparer(delai=2)
        client.page.evaluate.side_effect = lambda code, *args: (
            {"statut": "introuvable"} if code == NAVIGUER_VIDEOS_JS else
            {"grilles": 0, "liens_video_auteur": 0} if code == DIAGNOSTIC_VIDEOS_JS else [])
        bilan = {}
        with self.assertRaises(RuntimeError): self.lancer(client, horloge, bilan)
        self.assertEqual(horloge.temps, 2)
        self.assertEqual(bilan["discovery_stop"], "delai_sans_publications")
        self.assertIn("2.0 seconde", expliquer_echec_source(bilan, RuntimeError()))
        client.page.mouse.wheel.assert_not_called()

    def test_exception_du_script_ne_devient_pas_zero_video(self):
        client, horloge = self.preparer()
        def evaluer(code, *args):
            if code == NAVIGUER_VIDEOS_JS: return {"statut": "introuvable"}
            raise ValueError("Script invalide")
        client.page.evaluate.side_effect = evaluer
        bilan = {}
        with self.assertRaises(moteur.WebDriverException): self.lancer(client, horloge, bilan)
        self.assertEqual(bilan["diagnostic"]["code"], "erreur_navigateur")

    def test_arret_utilisateur_propage(self):
        client, horloge = self.preparer()
        class Arret(Exception): pass
        client.check = Mock(side_effect=Arret())
        with self.assertRaises(Arret): self.lancer(client, horloge)
        client.page.evaluate.assert_not_called()

    def test_captcha_connexion_et_refus_http_sont_identifies(self):
        for nature, statut, code in (("captcha", 200, "verification_tiktok"),
                                     ("connexion", 200, "connexion_sans_publications_publiques"),
                                     ("", 429, "refus_http_playwright")):
            with self.subTest(code=code):
                client = PressePlaywright(SimpleNamespace())
                client.statut_http = statut
                bilan = {}
                with patch("collecte.presse_playwright._script", side_effect=[nature, False]):
                    with self.assertRaises(RuntimeError): client._surveiller_page(bilan)
                self.assertEqual(bilan["diagnostic"]["code"], code)

    def test_captcha_apres_premiers_resultats_conserve_les_liens(self):
        client, horloge = self.preparer(limite=2)
        bilan = {}
        def surveiller(rapport):
            if client.page.mouse.wheel.called:
                rapport.update(discovery_stop="blocked", diagnostic={"code": "verification_tiktok"})
                raise RuntimeError("CAPTCHA")
            return True
        client._surveiller_page.side_effect = surveiller
        client.page.evaluate.side_effect = lambda code, *args: (
            {"statut": "deja_actif"} if code == NAVIGUER_VIDEOS_JS else
            [adresse(100)] if code == LIENS_VIDEOS_JS else {})
        self.assertEqual(self.lancer(client, horloge, bilan), [adresse(100)])
        self.assertTrue(bilan["collecte_interrompue"])
        self.assertEqual(bilan["diagnostic"]["code"], "verification_tiktok")

    def test_playwright_respecte_le_mode_navigateur_du_deploiement(self):
        fabrique = Mock()
        api = SimpleNamespace(sync_playwright=fabrique)
        for headless in (True, False):
            with self.subTest(headless=headless), patch.dict(sys.modules,
                    {"playwright": Mock(), "playwright.sync_api": api}):
                client = PressePlaywright(SimpleNamespace(timeout=20, headless=headless))
                try:
                    client.ouvrir()
                    options = fabrique.return_value.start.return_value.chromium.launch.call_args.kwargs
                    self.assertEqual(options["headless"], headless)
                finally:
                    client.fermer()

    def test_message_selenium_conserve_la_cause_dans_l_etape(self):
        bilan = {"diagnostic": {"exception": "RuntimeError"}, "recherches_compte": [
            {"diagnostic": {"code": "verification_tiktok"}}]}
        self.assertEqual(expliquer_echec_source(bilan, RuntimeError()),
                         "Vérification TikTok non terminée.")

    def test_secuid_affiche_son_erreur_precise_et_conserve_le_429(self):
        self.assertIn("secUid absent", expliquer_echec_source({}, PresseApiError("secUid absent")))
        self.assertIn("HTTP 429", expliquer_echec_source({}, PresseRateLimitError()))


if __name__ == "__main__":
    unittest.main()
