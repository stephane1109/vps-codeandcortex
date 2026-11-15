"""Tests sans télécharger les poids Qwen."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

CHEMIN = Path(__file__).resolve().parents[1] / "applications" / "qwen3_4b" / "codage_qwen.py"
spec = importlib.util.spec_from_file_location("codage_qwen_test", CHEMIN)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Reponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": json.dumps({
            "violence_evoquee": True, "violence_denoncee": True,
            "violence_justifiee": False, "violence_minimisee": False,
            "interpretation_indeterminee": False,
            "acteur_cible": "", "indice_textuel": "", "justification": "Exemple simulé"
        })}}


class Session:
    def __init__(self):
        self.payload = None

    def post(self, url, json=None, timeout=None):
        self.payload = json
        return Reponse()


class TestQwen(unittest.TestCase):
    def test_structure(self):
        session = Session()
        resultat = module.coder_commentaire("A" * 3500, "B" * 1500, session=session)
        self.assertIs(resultat["violence_denoncee"], True)
        self.assertTrue(resultat["texte_tronque"])
        self.assertTrue(resultat["contexte_tronque"])
        self.assertEqual(session.payload["model"], module.MODELE)
        self.assertEqual(session.payload["format"], module.SCHEMA_REPONSE)
        self.assertFalse(session.payload["think"])

    def test_schema_invalide(self):
        with self.assertRaises(ValueError):
            module.verifier_resultat({"violence_evoquee": "oui"})


if __name__ == "__main__":
    unittest.main()
