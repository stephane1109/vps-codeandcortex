"""Moteur Presse gallery-dl : conservation de Selenium et séparation des sources."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collecte.presse_gallerydl import PresseGalleryDL, extraire_publications
from connect_presse import ConnexionPresse
from webapp import StartRequest


def publication(identifiant="7701005447410552097", compte="lemondefr",
                description="Une manifestation en France."):
    return {
        "id": identifiant,
        "author": {"uniqueId": compte},
        "desc": description,
        "post_type": "video",
        "video": {"duration": 14},
        "createTime": 1750000000,
        "stats": {"playCount": 101, "diggCount": 5, "commentCount": 0},
    }


class GalleryDLPresseTests(unittest.TestCase):
    def test_extraction_metadonnees_sans_autres_comptes_ni_photos(self):
        lignes = [
            [2, "", publication()],
            [2, "", publication("7701005447410552098", "autre")],
            [2, "", {**publication("7701005447410552099"), "imagePost": {"images": []}}],
            [2, "", publication()],
            [-1, {"error": "OtherError", "message": "Réponse TikTok incomplète"}],
        ]
        sortie = extraire_publications(lignes, "lemondefr", 20)
        self.assertEqual(list(sortie), ["7701005447410552097"])
        fiche = sortie["7701005447410552097"]
        self.assertEqual(fiche["description"], "Une manifestation en France.")
        self.assertEqual(fiche["engagement"]["vues"]["valeur"], 101)
        self.assertEqual(fiche["engagement"]["commentaires"]["valeur"], 0)
        self.assertEqual(fiche["source"], "gallerydl_createur")
        self.assertEqual(fiche["author"], "lemondefr")

    def test_lancement_cli_sans_telechargement_ni_cookies(self):
        processus = Mock()
        processus.communicate.return_value = (
            json.dumps([[2, "", publication()]], ensure_ascii=False), ""
        )
        processus.poll.return_value = 0
        processus.returncode = 0
        args = SimpleNamespace(limit=5, timeout=3)
        moteur = PresseGalleryDL(args)
        with patch("collecte.presse_gallerydl.subprocess.Popen", return_value=processus) as appel:
            bilan = {}
            liens = moteur.decouvrir("lemondefr", bilan)
        self.assertEqual(
            liens, ["https://www.tiktok.com/@lemondefr/video/7701005447410552097"]
        )
        commande = appel.call_args.args[0]
        self.assertIn("--dump-json", commande)
        self.assertIn("--config-ignore", commande)
        self.assertIn("--post-range", commande)
        self.assertIn("1-5", commande)
        self.assertIn("tiktok.order-posts=desc", commande)
        self.assertIn("tiktok.videos=false", commande)
        self.assertNotIn("--cookies", commande)
        self.assertEqual(commande[-1], "https://www.tiktok.com/@lemondefr/posts")
        self.assertEqual(bilan["metadonnees_api"]["7701005447410552097"]["author"], "lemondefr")

    def test_pas_de_faux_compte_vide_lorsque_gallerydl_est_bloque(self):
        processus = Mock()
        processus.communicate.return_value = ("[]", "HTTP 403 Forbidden")
        processus.poll.return_value = 0
        processus.returncode = 1
        args = SimpleNamespace(limit=10, timeout=3)
        moteur = PresseGalleryDL(args)
        with patch("collecte.presse_gallerydl.subprocess.Popen", return_value=processus):
            rapport = {}
            with self.assertRaisesRegex(RuntimeError, "ne fournit aucune vidéo"):
                moteur.decouvrir("lemondefr", rapport)
        self.assertEqual(rapport["diagnostic"]["categorie"], "http_403")
        self.assertEqual(rapport["discovered_urls"], [])

    def test_selection_moteur_et_metadonnees_verifiees(self):
        requete = StartRequest(source_collecte="presse",
                               presse_moteur="gallerydl", medias=["lemonde"])
        self.assertEqual(requete.presse_moteur, "gallerydl")
        connecteur = ConnexionPresse(Mock())
        connecteur.preparer_sources(requete)
        self.assertEqual(connecteur.moteur_collecte, "gallerydl")
        connecteur.gallerydl_client = Mock()
        connecteur.arguments = SimpleNamespace(limit=3)
        connecteur.verifier = None
        source = {"id": "lemonde", "compte": "lemondefr"}
        rapport = {}
        connecteur.decouvrir(source, rapport)
        connecteur.gallerydl_client.decouvrir.assert_called_once()
        self.assertEqual(rapport["version_collecteur"], "gallerydl-presse-v1")

    def test_ui_et_dependances_sans_playwright(self):
        root = Path(__file__).resolve().parents[1]
        ui = (root / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('"gallerydl":"Méthode gallery-dl"', ui)
        source = (root / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("gallery-dl>=", source)
        self.assertNotIn("playwright>=", source)
        self.assertNotIn('"playwright":"Méthode Playwright"', ui)


if __name__ == "__main__":
    unittest.main()
