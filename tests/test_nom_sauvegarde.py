"""Tests du nom obligatoire des nouvelles collectes et de la migration SQLite."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from pydantic import ValidationError
from webapp import Job, StartRequest
from stockage.collectes_research import connexion, creer_plan, detail_plan


class TestsNomsSauvegarde(TestCase):
    def test_nom_sauvegarde_test_research(self):
        options = StartRequest(
            nom_sauvegarde="  Test manifestations 2026  ",
            source_collecte="presse", medias=["lemonde"],
            presse_moteur="research", test_research_10_publications=True,
            research_client_key="factice", research_client_secret="factice")
        self.assertEqual(options.nom_sauvegarde, "Test manifestations 2026")
        self.assertEqual(options.filename, "Test_manifestations_2026.txt")
        with TemporaryDirectory() as dossier:
            collecte = Job("a" * 64, options, Path(dossier))
            self.assertEqual(collecte.snapshot()["nom_sauvegarde"], options.nom_sauvegarde)
            with collecte.base.connexion() as base:
                parametres = base.execute(
                    "SELECT parametres FROM sessions WHERE id=?",
                    (collecte.id,)).fetchone()[0]
            self.assertIn('"nom_sauvegarde": "Test manifestations 2026"', parametres)

    def test_nom_vide_explicitement_refuse(self):
        # Les anciens réglages sauvegardés restent réouvrables sans nom.
        ancien = StartRequest(nom_sauvegarde="  ", source_collecte="presse",
                              medias=["lemonde"])
        self.assertEqual(ancien.nom_sauvegarde, "")
        with self.assertRaises(ValidationError):
            StartRequest(nom_sauvegarde="nom\ninterdit", source_collecte="presse",
                         medias=["lemonde"])

    def test_sqlite_pluri_journaliere_conserve_nom(self):
        with TemporaryDirectory() as dossier:
            parametres = {
                "source_collecte": "presse", "medias": ["lemonde"],
                "date_debut": "2026-10-01", "date_fin": "2026-10-31",
                "nom_sauvegarde": "Manifestations lycéennes 2026"
            }
            identifiant = creer_plan(
                dossier, "proprietaire_test", parametres,
                "2026-11-01", "2026-11-10")
            detail = detail_plan(dossier, identifiant, "proprietaire_test")
            self.assertEqual(detail["nom_sauvegarde"], "Manifestations lycéennes 2026")
            with connexion(dossier) as base:
                nom = base.execute("SELECT nom_sauvegarde FROM plans WHERE id=?",
                                   (identifiant,)).fetchone()[0]
            self.assertEqual(nom, "Manifestations lycéennes 2026")

    def test_migration_base_existante(self):
        with TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "collectes_research.sqlite3"
            with sqlite3.connect(chemin) as base:
                # Reproduire l'ancien schéma, avec les index attendus.
                base.execute("""
                    CREATE TABLE plans (
                        id TEXT PRIMARY KEY, proprietaire TEXT, statut TEXT,
                        debut_execution TEXT, fin_execution TEXT,
                        debut_corpus TEXT, fin_corpus TEXT, parametres TEXT,
                        source_index INTEGER, jour_index INTEGER,
                        prochaine_tentative TEXT, job_id TEXT, message TEXT,
                        cree_le TEXT, actualise_le TEXT)
                """)
                base.execute("INSERT INTO plans (id) VALUES ('ancien')")
            with connexion(dossier) as base:
                nom = base.execute(
                    "SELECT nom_sauvegarde FROM plans WHERE id='ancien'").fetchone()[0]
            self.assertEqual(nom, "")


if __name__ == "__main__":
    import unittest
    unittest.main()
