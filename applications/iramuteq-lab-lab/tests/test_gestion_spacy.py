import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "backend" / "gestion_spacy.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("gestion_spacy", MODULE_PATH)
gestion_spacy = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gestion_spacy)


class GestionSpacyTests(unittest.TestCase):
    def test_correspondances_pos(self):
        attentes = {
            "NOUN": "nom",
            "PROPN": "nom",
            "VERB": "ver",
            "AUX": "aux",
            "ADJ": "adj",
            "ADV": "adv",
            "ADP": "pre",
            "PRON": "pro",
            "CCONJ": "con",
            "SCONJ": "con",
        }
        for pos_spacy, pos_iramuteq in attentes.items():
            self.assertEqual(gestion_spacy.convertir_pos(pos_spacy), pos_iramuteq)

    def test_categorie_inconnue(self):
        self.assertEqual(gestion_spacy.convertir_pos("DET"), "AUTRE_FORME")
        self.assertEqual(gestion_spacy.convertir_pos(""), "AUTRE_FORME")

    def test_format_nom_modele(self):
        self.assertIsNotNone(gestion_spacy.MODEL_PATTERN.fullmatch("en_core_web_md"))
        self.assertIsNotNone(gestion_spacy.MODEL_PATTERN.fullmatch("de_core_news_md"))
        self.assertIsNone(gestion_spacy.MODEL_PATTERN.fullmatch("../../modele"))


if __name__ == "__main__":
    unittest.main()
