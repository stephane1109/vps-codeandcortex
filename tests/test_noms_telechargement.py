"""Vérifier les noms de fichiers proposés au navigateur pour les exports."""
import unittest
from pathlib import Path

from webapp import entete_telechargement, nom_fichier_telechargement


class TestsNomsTelechargement(unittest.TestCase):
    def test_nom_de_collecte_et_type_export(self):
        """Le nom de collecte précède le type de fichier téléchargé."""
        self.assertEqual(
            nom_fichier_telechargement(
                "sauvegarde_test_3", "annotations", "csv"),
            "sauvegarde_test_3_annotations.csv")
        self.assertEqual(
            nom_fichier_telechargement(
                "Manifestations lycéennes", "sociometrie_liens", ".graphml"),
            "Manifestations_lycéennes_sociometrie_liens.graphml")

    def test_suppression_des_chemins_non_souhaites(self):
        """Un nom de collecte ne peut pas inclure un chemin de fichiers."""
        nom = nom_fichier_telechargement("../mouvement 2026", "engagement", ".csv")
        self.assertNotIn("/", nom)
        self.assertNotIn("..", nom)
        self.assertTrue(nom.endswith("_engagement.csv"))

    def test_nom_utf8_dans_entete_http(self):
        """Les accents sont transmis au navigateur sans erreur d'encodage."""
        nom = nom_fichier_telechargement(
            "Manifestations lycéennes", "analyse", "zip")
        entete = entete_telechargement(nom)
        self.assertIn("filename*=UTF-8''", entete["Content-Disposition"])
        self.assertIn("lyc%C3%A9ennes", entete["Content-Disposition"])

    def test_noms_generiques_remplaces_dans_les_routes(self):
        """Les anciens noms génériques ne sont plus servis aux nouvelles collectes."""
        source = (Path(__file__).resolve().parents[1]
                  / "webapp.py").read_text(encoding="utf-8")
        for ancien in (
            'filename="annotations_violence.csv"',
            'filename="codages_videos.csv"',
            'filename="correlations_violence.csv"',
            'filename="engagement.csv"',
        ):
            self.assertNotIn(ancien, source)
        self.assertIn("nom_fichier_telechargement(", source)


if __name__ == "__main__":
    unittest.main()
