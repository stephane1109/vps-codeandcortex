"""Tests d'import, d'annotation, de réouverture et d'export autonome."""
import csv
import io
import unittest
from tempfile import TemporaryDirectory

from annotation_csv_autonome import (
    importer_tableau, ajouter_variable, enregistrer_annotations,
    exporter_tableau, lire_page, lister_projets,
)


class TestAnnotationCSVAutonome(unittest.TestCase):
    def setUp(self):
        self.temporaire = TemporaryDirectory()
        self.addCleanup(self.temporaire.cleanup)
        self.cookie = "a" * 64
        self.contenu = (
            "publication_id;url;legende;likes;statut_resume_ia;resume_ia_tiktok\n"
            "7123456789012345678;https://www.tiktok.com/@x/video/7123456789012345678;"
            "Manifestation;125;recupere;Résumé des événements\n"
            "7123456789012345679;https://www.tiktok.com/@x/video/7123456789012345679;"
            "Lycéens;85;non_trouve;\n"
        ).encode("utf-8")
        self.projet = importer_tableau(
            self.temporaire.name, self.cookie, "Etude manifestations", self.contenu)
        self.id = self.projet["id"]

    def test_import_et_proprietaire(self):
        """Les textes, compteurs et identifiants restent intacts."""
        page = lire_page(self.temporaire.name, self.cookie, self.id)
        self.assertEqual(page["lignes"][0]["likes"], "125")
        self.assertEqual(
            page["lignes"][0]["resume_ia_tiktok"], "Résumé des événements")
        self.assertEqual(len(lister_projets(self.temporaire.name, self.cookie)), 1)
        with self.assertRaises(ValueError):
            lire_page(self.temporaire.name, "b" * 64, self.id)

    def test_variable_binaire_et_reprise(self):
        """Le codage persiste et l'export conserve les colonnes du CSV."""
        etat = ajouter_variable(
            self.temporaire.name, self.cookie, self.id, "violence_visible")
        self.assertEqual(etat["revision"], 1)
        resultat = enregistrer_annotations(
            self.temporaire.name, self.cookie, self.id,
            [{"publication_id": "7123456789012345678",
              "codages": {"violence_visible": "Oui (1)"}}],
            revision=1)
        self.assertEqual(resultat["revision"], 2)
        page = lire_page(self.temporaire.name, self.cookie, self.id)
        self.assertEqual(page["lignes"][0]["violence_visible"], "Oui (1)")
        self.assertEqual(page["lignes"][1]["violence_visible"], "Non évaluée")
        donnees = exporter_tableau(self.temporaire.name, self.cookie, self.id)
        lecteur = csv.DictReader(io.StringIO(donnees), delimiter=";")
        premiere, seconde = list(lecteur)
        self.assertEqual(premiere["violence_visible"], "Oui (1)")
        self.assertEqual(seconde["violence_visible"], "Non évaluée")
        self.assertEqual(premiere["resume_ia_tiktok"], "Résumé des événements")

    def test_modalites_et_revision(self):
        """Refuser les modalités inconnues et les versions anciennes."""
        ajouter_variable(
            self.temporaire.name, self.cookie, self.id,
            "representation", "categorielle", ["pacifique", "repression"])
        with self.assertRaises(ValueError):
            enregistrer_annotations(
                self.temporaire.name, self.cookie, self.id,
                [{"publication_id": "7123456789012345678",
                  "codages": {"representation": "inconnue"}}], 1)
        with self.assertRaises(ValueError):
            enregistrer_annotations(
                self.temporaire.name, self.cookie, self.id, [], 0)

    def test_identifiants_dupliques(self):
        """Un CSV ambigu ne peut pas devenir un projet d'annotation."""
        double = self.contenu + self.contenu.splitlines()[1] + b"\n"
        with self.assertRaises(ValueError):
            importer_tableau(
                self.temporaire.name, self.cookie, "Double", double)


if __name__ == "__main__":
    unittest.main()
