"""Tests de l'export ZIP des collectes PostgreSQL sans serveur externe."""
import io
import json
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from stockage.export_zip_postgres import construire_archive_postgres


class CurseurFictif:
    def __init__(self, nom):
        self.nom = nom
        self.instructions = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, instruction, valeurs):
        self.instructions.append((instruction, valeurs))

    def fetchone(self):
        return (self.nom,) if self.nom else None


class ConnexionFictive:
    def __init__(self, nom):
        self.curseur = CurseurFictif(nom)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.curseur


class TestsExportPostgresZip(unittest.TestCase):
    def test_zip_postgres_contient_csv_json_et_nom_collecte(self):
        connexion = ConnexionFictive("Manifestations lycéennes")
        def exporter(cookie, type_, identifiant, categorie, format_):
            if format_ == "json":
                yield '[{"id":"7702544004629531937"}]'
            else:
                yield "\ufeffid;vues\n7702544004629531937;219\n"
        with patch("stockage.export_zip_postgres.ouvrir_connexion",
                   return_value=connexion), patch(
                       "stockage.export_zip_postgres.exporter_sauvegarde",
                       side_effect=exporter):
            fichier, nom = construire_archive_postgres(
                "cookie_prive", "collecte", "a" * 32)
        self.assertEqual(nom, "Manifestations_lycéennes.zip")
        try:
            with ZipFile(fichier) as archive:
                noms = set(archive.namelist())
                self.assertEqual(noms, {
                    "informations_export.json", "publications.csv",
                    "publications.json", "commentaires.csv", "commentaires.json"
                })
                self.assertEqual(
                    json.loads(archive.read("informations_export.json"))[
                        "nom_collecte"], "Manifestations lycéennes")
                self.assertIn(b"219", archive.read("publications.csv"))
        finally:
            fichier.close()
        self.assertIn("proprietaire_hash=%s", connexion.curseur.instructions[0][0])
        self.assertNotIn("cookie_prive",
                         str(connexion.curseur.instructions[0][1]))

    def test_aucun_export_si_collecte_inconnue(self):
        with patch("stockage.export_zip_postgres.ouvrir_connexion",
                   return_value=ConnexionFictive(None)):
            with self.assertRaises(ValueError):
                construire_archive_postgres("cookie_prive", "collecte", "a" * 32)

    def test_type_table_limite(self):
        with self.assertRaises(ValueError):
            construire_archive_postgres("cookie", "autre_table", "a" * 32)


if __name__ == "__main__":
    unittest.main()
