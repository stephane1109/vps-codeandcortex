"""Régression : Presse conserve Selenium, ajoute Playwright sans repli implicite."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import scraptiktok as moteur
from collecte.presse_playwright import PressePlaywright, _liens_compte, _profil_correct, LIENS_VIDEOS_JS
from connect_presse import ConnexionPresse
from webapp import StartRequest


def adresse(compte, identifiant):
    return f"https://www.tiktok.com/@{compte}/video/{identifiant}"


class PressePlaywrightTests(unittest.TestCase):
    def test_choix_valide_et_selenium_conserve(self):
        from collecte.presse import charger_inventaire
        media = charger_inventaire()[0]["id"]
        for methode in ("api", "research", "navigateur", "playwright"):
            with self.subTest(methode=methode):
                champs = {"source_collecte": "presse", "presse_moteur": methode,
                          "medias": [media]}
                if methode == "research":
                    champs.update(research_client_key="test", research_client_secret="test")
                options = StartRequest(**champs)
                self.assertEqual(options.presse_moteur, methode)

    def test_filtrage_profil_avec_identite_et_sans_photos(self):
        self.assertTrue(_profil_correct("https://www.tiktok.com/@lemondefr", "lemondefr"))
        self.assertFalse(_profil_correct("https://www.tiktok.com/@autre", "lemondefr"))
        self.assertFalse(_profil_correct("https://www.tiktok.com/@lemondefr/video/123", "lemondefr"))
        adresses = [
            adresse("lemondefr", "123"), adresse("autre", "124"),
            "https://www.tiktok.com/@lemondefr/photo/125",
            adresse("lemondefr", "123"), adresse("lemondefr", "126"),
        ]
        self.assertEqual(_liens_compte(adresses, "lemondefr", 10),
                         [adresse("lemondefr", "123"), adresse("lemondefr", "126")])

    def test_collecte_profil_playwright_sans_appel_au_moteur_selenium(self):
        arguments = SimpleNamespace(limit=2, timeout=5, delay=0, max_scrolls=2)
        client = PressePlaywright(arguments)
        client.page = Mock()
        client.page.url = "https://www.tiktok.com/@lemondefr"
        client._visiter = Mock()
        client.page.evaluate.side_effect = lambda script, *args: (
            [adresse("lemondefr", "123"), adresse("autre", "124"),
             adresse("lemondefr", "126")] if script == LIENS_VIDEOS_JS else
            {"statut": "clic", "type": "lien_profil"} if "const attendu" in str(script)
            else False
        )
        bilan = {}
        resultat = client.decouvrir("lemondefr", bilan)
        self.assertEqual(resultat, [adresse("lemondefr", "123"),
                                   adresse("lemondefr", "126")])
        self.assertEqual(bilan["presse_moteur"], "playwright")
        self.assertEqual(bilan["discovery_stop"], "limit")
        client._visiter.assert_called_once()

    def test_playwright_ouvre_la_rubrique_avant_les_videos(self):
        from collecte.navigation_videos import NAVIGUER_VIDEOS_JS
        arguments = SimpleNamespace(limit=1, timeout=5, delay=0, max_scrolls=1)
        client = PressePlaywright(arguments)
        client.page = Mock()
        client.page.url = "https://www.tiktok.com/@bfmtv"
        client._visiter = Mock()
        mouvements = []
        def evaluer(code, *args):
            if code == NAVIGUER_VIDEOS_JS:
                mouvements.append("clic_videos")
                return {"statut": "clic", "type": "lien_profil",
                        "destination": "https://www.tiktok.com/@bfmtv?tab=videos"}
            if code == LIENS_VIDEOS_JS:
                self.assertIn("clic_videos", mouvements)
                mouvements.append("lecture_videos")
                return [adresse("bfmtv", "7701005447410552097")]
            return False
        client.page.evaluate.side_effect = evaluer
        resultat = client.decouvrir("bfmtv", {})
        self.assertEqual(resultat, [adresse("bfmtv", "7701005447410552097")])
        self.assertEqual(mouvements, ["clic_videos", "lecture_videos"])

    def test_page_tiktok_en_erreur_ne_passe_pas_pour_onglet_charge(self):
        from collecte.navigation_videos import NAVIGUER_VIDEOS_JS, DIAGNOSTIC_VIDEOS_JS
        args = SimpleNamespace(limit=2, timeout=0.1, delay=0, max_scrolls=0,
                               interactive=False)
        client = PressePlaywright(args)
        client.page = Mock()
        client.page.url = "https://www.tiktok.com/@lemondefr"
        client._visiter = Mock()
        client.statut_http = 200
        def controle(rapport):
            rapport["etat_page"] = {
                "etat": "complete", "erreur_tiktok": True, "liens": 0
            }
            return True
        client._surveiller_page = controle
        def evaluer(code, *arguments):
            if code == NAVIGUER_VIDEOS_JS:
                return {"statut": "selectionne_sans_publications",
                        "type": "onglet", "route": "/@lemondefr"}
            if code == LIENS_VIDEOS_JS:
                return []
            if code == DIAGNOSTIC_VIDEOS_JS:
                return {"route": "/@lemondefr", "grilles": 0,
                        "liens_video_auteur": 0}
            return []
        client.page.evaluate.side_effect = evaluer
        bilan = {}
        with self.assertRaisesRegex(RuntimeError, "erreur"):
            client.decouvrir("lemondefr", bilan)
        self.assertEqual(bilan["diagnostic"]["code"], "erreur_tiktok_playwright")
        self.assertEqual(bilan["diagnostic"]["navigation"], "selectionne_sans_publications")
        self.assertEqual(bilan["diagnostic"]["statut_http"], 200)
        self.assertEqual(bilan["navigation_publications"], "videos_selectionne_sans_contenu")
        self.assertEqual(bilan["discovered_urls"], [])

    def test_lire_publication_playwright_reutilise_le_json_et_le_resume(self):
        import json
        url = adresse("lemondefr", "1234567890")
        donnee = {
            "url": url,
            "payloads": [json.dumps({"id": "1234567890", "desc": "Texte original.",
                                     "author": {"uniqueId": "lemondefr"}})],
            "resume_ia_tiktok": "Résumé autonome produit par TikTok.",
        }
        client = PressePlaywright(SimpleNamespace(timeout=5, inclure_texte_genere_ia=True))
        client.page = Mock()
        client._visiter = Mock()
        with patch("collecte.presse_playwright._script", return_value=donnee):
            fiche = client.lire(url)
        self.assertEqual(fiche["description"], "Texte original.")
        self.assertEqual(fiche["resume_ia_tiktok"], "Résumé autonome produit par TikTok.")
        self.assertEqual(fiche["statut_resume_ia"], "recupere")

    def test_connecteur_oriente_la_decouverte_et_la_lecture_vers_playwright(self):
        connexion = object.__new__(ConnexionPresse)
        connexion.moteur_collecte = "playwright"
        connexion.medias_selectionnes = {"lemonde": {"id": "lemonde", "compte": "lemondefr"}}
        connexion.arguments = SimpleNamespace(limit=2)
        connexion.verifier = None
        connexion.playwright_client = Mock()
        rapport = {}
        connexion.decouvrir({"id": "lemonde", "compte": "lemondefr"}, rapport)
        connexion.playwright_client.decouvrir.assert_called_once()
        self.assertEqual(rapport["presse_moteur"], "playwright")
        url = adresse("lemondefr", "1234567890")
        connexion.lire_publication(url)
        connexion.playwright_client.lire.assert_called_once_with(url)

    def test_deploiement_et_interface_contiennent_le_nouveau_moteur(self):
        racine = Path(__file__).resolve().parents[1]
        ui = (racine / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('"playwright":"Méthode Playwright"', ui)
        dependencies = (racine / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("playwright>=", dependencies)
        self.assertIn("playwright", (racine / "collecte/presse_playwright.py").read_text())


if __name__ == "__main__":
    unittest.main()
