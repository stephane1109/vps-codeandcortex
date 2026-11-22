"""Régression des analyses sociométriques à partir de plusieurs CSV."""
import csv
import io
import unittest

from analyse_sociometrique.import_csv import preparer_import, analyser_import
from analyse_sociometrique.reseaux import exporter


def tableau_csv(colonnes, lignes):
    """Générer des CSV UTF-8 cohérents avec les exports ScrapTikTok."""
    sortie = io.StringIO()
    auteur = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";")
    auteur.writeheader()
    auteur.writerows(lignes)
    return sortie.getvalue().encode("utf-8-sig")


class TestImportSociometriqueCSV(unittest.TestCase):
    def setUp(self):
        self.commentaires_un = tableau_csv(
            ["id", "publication_id", "parent_id", "source", "auteur"],
            [
                {"id": "c1", "publication_id": "7001", "parent_id": "",
                 "source": "page_visible", "auteur": "temoin.1"},
                {"id": "c2", "publication_id": "7001", "parent_id": "c1",
                 "source": "research", "auteur": "non_verifie"},
            ],
        )
        self.commentaires_deux = tableau_csv(
            ["id", "publication_id", "parent_id", "source", "auteur"],
            [
                {"id": "c2", "publication_id": "7001", "parent_id": "c1",
                 "source": "research", "auteur": "non_verifie"},
                {"id": "c3", "publication_id": "7002", "parent_id": "",
                 "source": "page_visible", "auteur": "temoin.1"},
            ],
        )
        self.engagement = tableau_csv(
            ["publication_id", "url", "vues", "likes"],
            [{"publication_id": "7001", "url": "https://example.org/7001",
              "vues": "100", "likes": "20"}],
        )

    def test_fusion_et_dedoublonnage(self):
        """Les doublons sont retirés par couple vidéo-commentaire."""
        donnees = preparer_import(
            [("commentaires1.csv", self.commentaires_un),
             ("commentaires2.csv", self.commentaires_deux)],
            [("engagement.csv", self.engagement)])
        self.assertEqual(len(donnees["commentaires"]), 3)
        self.assertEqual(donnees["doublons"], 1)
        self.assertEqual(len(donnees["publications"]), 2)
        self.assertEqual(donnees["publications"][0]["vues"], "100")

    def test_reseaux_et_metriques(self):
        """Les graphes existants et leurs exports restent accessibles."""
        donnees = preparer_import(
            [("a.csv", self.commentaires_un),
             ("b.csv", self.commentaires_deux)],
            [("engagement.csv", self.engagement)])
        projection = analyser_import(donnees, "videos_communes")
        self.assertEqual(projection["statistiques"]["liens"], 1)
        noeuds = exporter(projection, "noeuds.csv").decode("utf-8-sig")
        self.assertIn("vues", noeuds)
        self.assertIn("100", noeuds)
        reponses = analyser_import(donnees, "reponses")
        self.assertEqual(reponses["statistiques"]["liens"], 1)
        self.assertTrue(exporter(reponses, "graphml"))
        self.assertTrue(exporter(reponses, "gexf"))

    def test_absence_auteur_research(self):
        """Les auteurs non vérifiés par Research ne deviennent pas des profils."""
        contenu = tableau_csv(
            ["id", "publication_id", "parent_id", "source", "auteur"],
            [{"id": "c1", "publication_id": "7001", "parent_id": "",
              "source": "research", "auteur": "pseudo_sans_preuve"}])
        donnees = preparer_import([("research.csv", contenu)])
        graphe = analyser_import(donnees, "auteurs_videos")
        self.assertEqual(graphe["statistiques"]["auteurs_distincts"], 0)
        self.assertEqual(graphe["statistiques"]["liens"], 0)

    def test_csv_uniquement_entetes(self):
        """Signaler explicitement une collecte sans commentaire exporté."""
        contenu = tableau_csv(
            ["id", "publication_id", "parent_id", "source", "auteur"], [])
        with self.assertRaisesRegex(ValueError, "uniquement les en-têtes"):
            preparer_import([("commentaires_vide.csv", contenu)])

    def test_identifiants_vides(self):
        """Distinguer une ligne vide d'un commentaire sans ID."""
        contenu = tableau_csv(
            ["id", "publication_id", "parent_id", "source", "auteur"],
            [{"id": "", "publication_id": "7001", "parent_id": "",
              "source": "research", "auteur": ""}])
        with self.assertRaisesRegex(ValueError, "1 ligne\\(s\\) lue\\(s\\)"):
            preparer_import([("commentaires_sans_id.csv", contenu)])

    def test_csv_incomplet(self):
        """L'identifiant du commentaire et celui de la vidéo sont requis."""
        contenu = tableau_csv(["publication_id"], [{"publication_id": "7001"}])
        with self.assertRaises(ValueError):
            preparer_import([("invalide.csv", contenu)])


if __name__ == "__main__":
    unittest.main()
