import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from corpus.construction import construire_exports
from corpus.export_iramuteq import construire_corpus
from corpus.export_zip import exporter_zip
class TestsCorpus(unittest.TestCase):
    def test_corpus_archive_identique_au_txt_avec_options_et_commentaires(self):
        contenu = ("*date_2026-10-08 *profil_@bfmtv *partages_42 *comment_123\r\n"
                   "Texte avec accents é et emoji 🍋.\r\n#manifestation #lycéen\r\n\r\n"
                   "Commentaire 1 :\r\nRéaction conservée.\r\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d)
            source = dossier / "textes.txt"
            source.write_bytes(contenu)
            # Le JSON et les commentaires bruts ne doivent pas recomposer le TXT choisi.
            publications = [{"id": "123", "author": "bfmtv", "description": "Autre mise en forme",
                             "engagement": {}, "retenue": True}]
            with patch("corpus.construction.construire_legendes") as reconstruire:
                construire_exports(dossier, publications, [], {}, texte_source=source)
                reconstruire.assert_not_called()
            exporter_zip(dossier, dossier / "archive.zip")
            self.assertEqual((dossier / "corpus_iramuteq.txt").read_bytes(), source.read_bytes())
            with zipfile.ZipFile(dossier / "archive.zip") as archive:
                self.assertEqual(archive.read("corpus_iramuteq.txt"), contenu)
                self.assertEqual(archive.read("textes.txt"), contenu)

    def test_regeneration_par_lot_conserve_le_txt_et_ses_choix(self):
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d)
            publications = [{"id": "123", "author": "media", "description": "Texte brut",
                             "engagement": {}, "retenue": True}]
            for contenu in (b"Texte seul\n", b""):
                with self.subTest(contenu=contenu):
                    (dossier / "textes.txt").write_bytes(contenu)
                    (dossier / "corpus_iramuteq.txt").write_text("Ancien corpus divergent")
                    # Le traitement vidéo passe les variables SHS, sans source explicite.
                    construire_exports(dossier, publications, [], {}, {"123": {"format": "reportage"}})
                    self.assertEqual((dossier / "corpus_iramuteq.txt").read_bytes(), contenu)
                    exporter_zip(dossier, dossier / "archive.zip")
                    with zipfile.ZipFile(dossier / "archive.zip") as archive:
                        self.assertEqual(archive.read("corpus_iramuteq.txt"), archive.read("textes.txt"))

    def test_source_explicitement_attendue_absente_ne_cree_pas_un_autre_corpus(self):
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d)
            with self.assertRaises(FileNotFoundError):
                construire_exports(dossier, [], [], {}, texte_source=dossier / "textes.txt")
            self.assertFalse((dossier / "corpus_iramuteq.txt").exists())

    def test_variables_et_injection(self):
        s=construire_corpus([{"id":"1","texte":"Texte\n**** *faux_oui","variables":{"média":"Presse régionale","audio":None}}])
        self.assertEqual(s.count("****"),1)
        self.assertIn("*media_presse_regionale *audio_indetermine",s)
        self.assertNotIn("*faux",s)
    def test_exports_bruts_et_zip(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); brut="Texte *étoile*"
            construire_exports(d,[{"id":"123","author":"media","description":brut,"engagement":{}}],[],{})
            self.assertEqual(json.loads((d/"publications.json").read_text())[0]["description"],brut)
            (d/"traitement.log").write_text("secret"); (d/"cookies.sqlite").write_text("secret")
            (d/"lien.json").symlink_to(d/"publications.json")
            exporter_zip(d,d/"archive.zip")
            with zipfile.ZipFile(d/"archive.zip") as z:
                self.assertIn("corpus_iramuteq.txt",z.namelist())
                self.assertNotIn("traitement.log",z.namelist()); self.assertNotIn("cookies.sqlite",z.namelist()); self.assertNotIn("lien.json",z.namelist())
