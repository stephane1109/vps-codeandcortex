"""Vérifier la présence du texte IA dans le tableau d'engagement."""
import csv
import io
import unittest

from corpus.construction import COLONNES_ENGAGEMENT, lignes_engagement
from corpus.export_csv import serialiser_csv


class TestResumeIAEngagement(unittest.TestCase):
    def test_resume_collecte(self):
        """Conserver simultanément le statut et le texte obtenu."""
        publication = {
            "id": "1234567890123456789",
            "author": "exemple",
            "description": "Texte d'origine",
            "statut_resume_ia": "recupere",
            "resume_ia_tiktok": "Résumé IA de la publication, avec accent.",
            "engagement": {},
        }
        ligne = lignes_engagement([publication])[0]
        self.assertIn("statut_resume_ia", COLONNES_ENGAGEMENT)
        self.assertIn("resume_ia_tiktok", COLONNES_ENGAGEMENT)
        self.assertEqual(ligne["statut_resume_ia"], "recupere")
        self.assertEqual(
            ligne["resume_ia_tiktok"],
            "Résumé IA de la publication, avec accent.",
        )
        lecteur = csv.DictReader(
            io.StringIO(serialiser_csv([ligne], COLONNES_ENGAGEMENT)),
            delimiter=";",
        )
        self.assertEqual(
            next(lecteur)["resume_ia_tiktok"],
            "Résumé IA de la publication, avec accent.",
        )

    def test_resume_indisponible(self):
        """Une absence de résumé ne doit pas créer un texte fictif."""
        publication = {
            "id": "1234567890123456790",
            "author": "exemple",
            "description": "Texte d'origine",
            "statut_resume_ia": "non_trouve",
            "engagement": {},
        }
        ligne = lignes_engagement([publication])[0]
        self.assertIsNone(ligne["resume_ia_tiktok"])
        lecteur = csv.DictReader(
            io.StringIO(serialiser_csv([ligne], COLONNES_ENGAGEMENT)),
            delimiter=";",
        )
        self.assertEqual(next(lecteur)["resume_ia_tiktok"], "")


if __name__ == "__main__":
    unittest.main()
