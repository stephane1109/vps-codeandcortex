"""Tester le choix explicite entre export TXT et CSV des commentaires."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from corpus.construction import construire_exports
from corpus.export_zip import archive_avec_texte, exporter_zip
from webapp import Job, StartRequest


class TestsExportCommentairesCSVouTXT(unittest.TestCase):
    def publication(self):
        """Produire une vidéo minimale avec un compteur indépendant des textes."""
        return {
            "id": "7012345678901234567",
            "url": "https://www.tiktok.com/@lemondefr/video/7012345678901234567",
            "author": "lemondefr",
            "description": "Manifestation pacifique",
            "created_at": "2026-10-25T12:00:00+00:00",
            "engagement": {
                "commentaires": {"valeur": 15, "brut": "15"},
                "vues": {"valeur": 100, "brut": "100"},
            },
            "retenue": True,
        }

    def commentaires(self):
        """Produire une réaction et une réponse liées à la même vidéo."""
        return [
            {"id": "101", "publication_id": "7012345678901234567",
             "auteur": "alice", "texte": "Avis original du commentaire",
             "est_reponse": False},
            {"id": "102", "publication_id": "7012345678901234567",
             "auteur": "bob", "texte": "Réponse à cet avis",
             "est_reponse": True, "parent_id": "101"},
        ]

    def travail(self, dossier, inclure_txt):
        """Initialiser une collecte sans contacter TikTok."""
        parametres = StartRequest(
            source_collecte="presse", medias=["lemonde"],
            nom_sauvegarde="Test commentaires",
            presse_moteur="api", collecter_commentaires=True,
            collecter_reponses=True,
            inclure_commentaires_txt=inclure_txt,
            variables_txt=["profil", "id", "commentaires"],
        )
        travail = Job("a" * 64, parametres, Path(dossier))
        travail.records = [self.publication()]
        travail.publications = travail.records.copy()
        travail.commentaires = self.commentaires()
        return travail

    def test_option_independante_des_commentaires_et_reponses(self):
        """Décocher le TXT ne désactive pas la collecte des réactions."""
        pour_csv = StartRequest(
            source_collecte="presse", medias=["lemonde"],
            collecter_commentaires=True, collecter_reponses=True,
            inclure_commentaires_txt=False)
        self.assertTrue(pour_csv.collecter_commentaires)
        self.assertTrue(pour_csv.collecter_reponses)
        self.assertFalse(pour_csv.inclure_commentaires_txt)
        sans_collecte = StartRequest(
            hashtag="lyceens",
            collecter_commentaires=False, collecter_reponses=True,
            inclure_commentaires_txt=True)
        self.assertFalse(sans_collecte.collecter_reponses)
        self.assertFalse(sans_collecte.inclure_commentaires_txt)
        ancien = StartRequest(
            collecter_commentaires=True)
        self.assertTrue(ancien.inclure_commentaires_txt)

    def test_txt_decoche_commentaires_absents_compteurs_presents(self):
        """Les textes sont absents du TXT, mais pas le nombre de commentaires."""
        with tempfile.TemporaryDirectory() as dossier:
            travail = self.travail(dossier, False)
            contenu = travail.texte_a_exporter()
            self.assertIn("Manifestation pacifique", contenu)
            self.assertIn("*comment_15", contenu)
            self.assertNotIn("Avis original du commentaire", contenu)
            self.assertNotIn("Réponse à cet avis", contenu)
            self.assertFalse(travail.snapshot()["inclure_commentaires_txt"])
            self.assertEqual(travail.snapshot()["commentaires_collectes"], 2)

    def test_txt_coche_conserve_commentaires_et_reponses(self):
        """L'option cochée conserve le comportement antérieur."""
        with tempfile.TemporaryDirectory() as dossier:
            travail = self.travail(dossier, True)
            contenu = travail.texte_a_exporter()
            self.assertIn("Avis original du commentaire", contenu)
            self.assertIn("Réponse à cet avis", contenu)
            self.assertIn("Commentaire 1", contenu)
            self.assertIn("Réponse 2", contenu)

    def test_archive_csv_uniquement_et_stockage_interne(self):
        """Le ZIP ne contient que le CSV pour les textes des commentaires."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            travail = self.travail(dossier, False)
            (racine / "textes.txt").write_text(
                travail.texte_a_exporter(), encoding="utf-8")
            construire_exports(
                racine, travail.publications, travail.commentaires, {},
                texte_source=racine / "textes.txt",
                inclure_commentaires_txt=False)
            self.assertTrue((racine / "commentaires.json").is_file())
            self.assertTrue((racine / "commentaires.csv").is_file())
            self.assertFalse(
                (racine / "corpus_commentaires_iramuteq.txt").exists())
            with (racine / "commentaires.csv").open(
                    newline="", encoding="utf-8-sig") as fichier:
                lignes = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(lignes), 2)
            self.assertEqual(lignes[0]["texte"], "Avis original du commentaire")
            self.assertEqual(lignes[1]["texte"], "Réponse à cet avis")
            exporter_zip(
                racine, racine / "archive.zip",
                commentaires_csv_uniquement=True)
            with ZipFile(racine / "archive.zip") as archive:
                noms = archive.namelist()
                self.assertIn("commentaires.csv", noms)
                for fichier in (
                    "commentaires.json", "commentaires.txt",
                    "corpus_commentaires_iramuteq.txt"):
                    self.assertNotIn(fichier, noms)
                self.assertNotIn(
                    "Avis original du commentaire",
                    archive.read("textes.txt").decode("utf-8"))
            with archive_avec_texte(
                    racine / "archive.zip",
                    travail.texte_a_exporter(),
                    commentaires_csv_uniquement=True) as source:
                with ZipFile(source) as archive:
                    self.assertIn("commentaires.csv", archive.namelist())
                    self.assertNotIn("commentaires.txt", archive.namelist())

    def test_archive_avec_txt_coche(self):
        """Lorsque demandé, le ZIP conserve le corpus séparé des commentaires."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            travail = self.travail(dossier, True)
            (racine / "textes.txt").write_text(
                travail.texte_a_exporter(), encoding="utf-8")
            construire_exports(
                racine, travail.publications, travail.commentaires, {},
                texte_source=racine / "textes.txt",
                inclure_commentaires_txt=True)
            exporter_zip(racine, racine / "archive.zip")
            with ZipFile(racine / "archive.zip") as archive:
                self.assertIn(
                    "corpus_commentaires_iramuteq.txt", archive.namelist())
                self.assertIn("commentaires.json", archive.namelist())
                self.assertIn("commentaires.csv", archive.namelist())
                self.assertIn(
                    "Avis original du commentaire",
                    archive.read("textes.txt").decode("utf-8"))

    def test_formulaire_position_et_parametre(self):
        """La seconde case n'est pas confondue avec le compteur de commentaires."""
        page = (Path(__file__).resolve().parents[1] /
                "streamlit_app.py").read_text(encoding="utf-8")
        nom = 'st.checkbox("Collecter les textes des commentaires"'
        option = '"Inclure les textes des commentaires dans le fichier TXT"'
        self.assertIn(nom, page)
        self.assertIn(option, page)
        self.assertLess(page.index(nom), page.index(option))
        self.assertIn('key="inclure_commentaires_txt"', page)
        self.assertIn('valeurs["inclure_commentaires_txt"] = bool(', page)


if __name__ == "__main__":
    unittest.main()
