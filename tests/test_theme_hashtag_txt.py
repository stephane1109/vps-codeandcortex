"""Tests de l'option de suppression des modalités thématiques des fichiers TXT."""
import unittest

from webapp import StartRequest, entete_sources_ia, text_export


class TestThemeHashtagTxt(unittest.TestCase):
    def setUp(self):
        self.publication = {
            "id": "1234567890123456789",
            "author": "compte",
            "description": "Texte original",
            "resume_ia_tiktok": "Texte du résumé IA",
            "hashtags_correspondants": ["manifestation"],
            "hashtags": ["manifestation"],
        }

    def test_comportement_historique(self):
        """Les anciens paramètres conservent la variable thématique."""
        self.assertTrue(StartRequest.model_fields[
            "inclure_theme_hashtag_txt"].default)
        texte = text_export([self.publication], True,
                            inclure_texte_genere_ia=True)
        self.assertEqual(texte.count("*theme_manifestation"), 2)
        self.assertIn("*source_original", texte)
        self.assertIn("*source_ia", texte)

    def test_exclusion_du_theme(self):
        """Décocher retire uniquement le thème des deux segments."""
        texte = text_export(
            [self.publication], True, inclure_texte_genere_ia=True,
            inclure_theme_hashtag_txt=False)
        self.assertNotIn("*theme_", texte)
        self.assertIn("*source_original", texte)
        self.assertIn("*source_ia", texte)
        self.assertIn("Texte original", texte)
        self.assertIn("Texte du résumé IA", texte)

    def test_entete_autonome(self):
        """Conserver les autres métadonnées même sans le thème."""
        entete = entete_sources_ia(
            self.publication, "original",
            variables="**** *profil_compte *id_123", inclure_theme_hashtag=False)
        self.assertIn("*source_original", entete)
        self.assertIn("*profil_compte", entete)
        self.assertIn("*id_123", entete)
        self.assertNotIn("*theme_", entete)


if __name__ == "__main__":
    unittest.main()
