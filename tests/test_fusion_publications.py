"""Tests de la concaténation des CSV de métriques de ScrapTikTok."""
import csv
import io
import unittest

from corpus.fusion_publications import fusionner_publications_csv


class TestsFusionPublications(unittest.TestCase):
    def test_concatener_fichiers_deux_separateurs_et_dedoublonner(self):
        """Les colonnes sont réunies sans compter deux fois une vidéo."""
        a = (
            "publication_id;url;vues;likes\n"
            "7702544004629531937;https://www.tiktok.com/@test/video/7702544004629531937;219;5\n"
            "7702544004629531938;https://www.tiktok.com/@test/video/7702544004629531938;120;3\n"
        ).encode("utf-8-sig")
        b = (
            "id,commentaires,region_code,likes\n"
            "7702544004629531937,1,FR,6\n"
            "7702544004629531939,0,BE,2\n"
        ).encode("utf-8")
        resultat = fusionner_publications_csv(
            [("publications.csv", a), ("engagement.csv", b)])
        self.assertEqual(resultat["total_initial"], 4)
        self.assertEqual(resultat["nombre_unique"], 3)
        self.assertEqual(resultat["doublons"], 1)
        self.assertEqual(resultat["doublons_divergents"], 1)
        self.assertIn("region_code", resultat["colonnes"])
        fichier = io.StringIO(resultat["csv"].decode("utf-8-sig"))
        lignes = list(csv.DictReader(fichier, delimiter=";"))
        self.assertEqual(len(lignes), 3)
        premiere = lignes[0]
        self.assertEqual(premiere["publication_id"], "7702544004629531937")
        self.assertEqual(premiere["vues"], "219")
        self.assertEqual(premiere["likes"], "5")
        self.assertEqual(premiere["commentaires"], "1")
        self.assertIn("engagement.csv", premiere["fichiers_sources"])

    def test_priorite_dernier_fichier_conserve_valeurs_precedentes(self):
        """Le dernier fichier peut mettre à jour une métrique sans vider les autres."""
        fichiers = [
            ("premier.csv", b"id;vues;likes\n7702544004629531937;100;5\n"),
            ("dernier.csv", b"id;likes\n7702544004629531937;8\n"),
        ]
        fusion = fusionner_publications_csv(fichiers, "dernier")
        self.assertEqual(fusion["nombre_unique"], 1)
        self.assertEqual(fusion["lignes"][0]["vues"], "100")
        self.assertEqual(fusion["lignes"][0]["likes"], "8")

    def test_rejeter_commentaires_et_ids_incorrects(self):
        """Une ligne de commentaire ne doit pas être confondue avec une vidéo."""
        with self.assertRaisesRegex(ValueError, "commentaires"):
            fusionner_publications_csv([
                ("commentaires.csv",
                 b"id;publication_id;parent_id;texte\n12;7702544004629531937;;Salut\n")
            ])
        with self.assertRaisesRegex(ValueError, "identifiant"):
            fusionner_publications_csv([
                ("publications.csv", b"id;vues\nabc;3\n")
            ])

    def test_aucune_modification_des_bases(self):
        """La concaténation est un traitement mémoire autonome."""
        result = fusionner_publications_csv([
            ("export.csv", b"id;vues\n7702544004629531937;0\n")
        ])
        self.assertEqual(result["lignes"][0]["vues"], "0")


if __name__ == "__main__":
    unittest.main()
