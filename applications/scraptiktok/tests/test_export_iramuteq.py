import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from corpus.construction import construire_exports
from corpus.export_iramuteq import construire_corpus
from corpus.export_zip import exporter_zip
class TestsCorpus(unittest.TestCase):
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
