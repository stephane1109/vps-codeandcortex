"""Tests de persistance SQLite, sans modèle ni connexion Internet."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stockage_resultats import enregistrer_resultat, recuperer_resultats


class TestStockage(unittest.TestCase):
    def test_sauvegarde_et_reprise(self):
        with tempfile.TemporaryDirectory() as repertoire:
            chemin = str(Path(repertoire) / "resultats.sqlite3")
            enregistrer_resultat(
                "configuration-A", 1, "ok",
                {
                    "scores": {"éducation": 0.82, "tourisme": 0.13},
                    "categories_retenues": ["éducation"],
                    "categorie_principale": "éducation",
                },
                chemin,
            )
            repris = recuperer_resultats("configuration-A", chemin)
            self.assertEqual(repris[1]["statut_analyse"], "ok")
            self.assertEqual(repris[1]["categorie_principale"], "éducation")
            self.assertEqual(recuperer_resultats("configuration-B", chemin), {})

    def test_remplacement_meme_document(self):
        with tempfile.TemporaryDirectory() as repertoire:
            chemin = str(Path(repertoire) / "resultats.sqlite3")
            enregistrer_resultat(
                "A", 7, "erreur", {"erreur_analyse": "test"}, chemin
            )
            enregistrer_resultat(
                "A", 7, "ok",
                {
                    "categorie_principale": "santé",
                    "scores": {"santé": 0.9},
                }, chemin,
            )
            contenu = recuperer_resultats("A", chemin)
            self.assertEqual(len(contenu), 1)
            self.assertEqual(contenu[7]["statut_analyse"], "ok")
            self.assertNotIn("erreur_analyse", contenu[7])


if __name__ == "__main__":
    unittest.main()
