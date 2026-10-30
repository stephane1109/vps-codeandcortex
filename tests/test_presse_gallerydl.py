"""Moteur Presse gallery-dl : conservation de Selenium et séparation des sources."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collecte.presse_gallerydl import (PresseGalleryDL, extraire_publications, _derniere_etape, _type_erreur)
from collecte.gallerydl_liste import recuperer_liste
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
        self.assertIn("collecte.gallerydl_liste", commande)
        self.assertIn("--limite", commande)
        self.assertIn("5", commande)
        self.assertNotIn("--dump-json", commande)
        self.assertNotIn("--cookies", commande)
        self.assertNotIn("--post-range", commande)
        self.assertEqual(commande[commande.index("--compte") + 1], "lemondefr")
        self.assertEqual(bilan["metadonnees_api"]["7701005447410552097"]["author"], "lemondefr")

    def test_pas_de_faux_compte_vide_lorsque_gallerydl_est_bloque(self):
        processus = Mock()
        processus.communicate.return_value = ("[]", "ETAPE:liste_createur\n")
        processus.poll.return_value = 0
        processus.returncode = 0
        args = SimpleNamespace(limit=10, timeout=3)
        moteur = PresseGalleryDL(args)
        with patch("collecte.presse_gallerydl.subprocess.Popen", return_value=processus):
            rapport = {}
            with self.assertRaisesRegex(RuntimeError, "ne fournit aucune vidéo"):
                moteur.decouvrir("lemondefr", rapport)
        self.assertEqual(rapport["diagnostic"]["categorie"], "aucun_resultat")
        self.assertEqual(rapport["diagnostic"]["etape"], "liste_createur")
        self.assertEqual(rapport["discovered_urls"], [])

    def test_extraction_directe_sans_page_individuelle(self):
        """La méthode posts fournit directement les données itemList."""
        donnees = publication()

        class TiktokPostsExtractor:
            def __init__(self):
                self.nombre_posts = 0
                self.nombre_pages = 0

            def initialize(self):
                return None

            def _extract_posts_api_legacy(self, *args, **kwargs):
                return None

            def posts(self):
                self.nombre_posts += 1
                self._extract_posts_api_legacy()
                return {donnees["id"]: donnees}

            def items(self):
                self.nombre_pages += 1
                raise AssertionError("La lecture de pages vidéo est interdite.")

        extracteur = TiktokPostsExtractor()
        with patch("gallery_dl.extractor.find", return_value=extracteur):
            messages = recuperer_liste("lemondefr", 5, 5)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][2]["desc"], donnees["desc"])
        self.assertEqual(extracteur.nombre_posts, 1)
        self.assertEqual(extracteur.nombre_pages, 0)

    def test_diagnostic_etape_sans_fuite_des_requetes(self):
        journal = ("ETAPE:initialisation\nETAPE:resolution_profil\n"
                   "ETAPE:liste_createur\nERREUR:AbortExtraction\n"
                   "https://www.tiktok.com/api/?msToken=NE_PAS_AFFICHER")
        self.assertEqual(_derniere_etape(journal), "liste_createur")
        self.assertEqual(_type_erreur(journal), "AbortExtraction")
        self.assertEqual(_derniere_etape("erreur générique"), "non_identifiee")

    def test_erreur_code_retour_ne_devient_pas_profil_vide(self):
        processus = Mock()
        processus.communicate.return_value = ("", "ETAPE:resolution_profil\nERREUR:AbortExtraction")
        processus.poll.return_value = 0
        processus.returncode = 2
        client = PresseGalleryDL(SimpleNamespace(limit=5, timeout=3))
        with patch("collecte.presse_gallerydl.subprocess.Popen", return_value=processus):
            rapport = {}
            with self.assertRaisesRegex(RuntimeError, "pas pu accéder"):
                client.decouvrir("lemondefr", rapport)
        self.assertEqual(rapport["diagnostic"]["code"], "gallerydl_extraction_echec")
        self.assertEqual(rapport["diagnostic"]["etape"], "resolution_profil")

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
