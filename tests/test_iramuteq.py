"""Tests de non-régression des deux lecteurs IRaMuTeQ."""
import importlib.util
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "applications"
CORPUS = (
    "**** *source_original *hatg_manifestations *id_7700347271031885078 *texte_commentaire\n"
    "Question ?\nSuite du commentaire !\n\n"
    "**** *source_ia *profil_bfmtv *vues_classe_10k_100k\n"
    "Évocation de faits, sans interprétation forcée.\n"
    "**** *source_original *profil_autre *texte_commentaire\n\n"
)


def importer(chemin):
    spec = importlib.util.spec_from_file_location("lecteur_test", chemin)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLecture(unittest.TestCase):
    def _verifier(self, dossier):
        lecteur = importer(RACINE / dossier / "lecture_iramuteq.py")
        documents = lecteur.analyser_corpus(CORPUS.encode("utf-8-sig"))
        self.assertEqual(len(documents), 3)
        self.assertEqual(documents[0].texte, "Question ?\nSuite du commentaire !")
        self.assertEqual(documents[0].variables[2], "id_7700347271031885078")
        tableau = lecteur.tableau_documents(documents)
        self.assertEqual(tableau.loc[0, "variable_id"], "7700347271031885078")
        self.assertEqual(tableau.loc[1, "variable_vues"], "classe_10k_100k")
        self.assertEqual(tableau.loc[2, "nombre_caracteres"], 0)
        sortie = lecteur.exporter_iramuteq(documents, {1: "justification"}, "qwen_position")
        self.assertIn(b"*qwen_position_justification", sortie)
        retour = lecteur.analyser_corpus(sortie)
        self.assertEqual(retour[0].texte, documents[0].texte)
        self.assertEqual(len(retour), 3)
        self.assertTrue(lecteur.exporter_csv(tableau).startswith(b"\xef\xbb\xbf"))
        with self.assertRaises(ValueError):
            lecteur.analyser_corpus("Document sans entête")

    def test_dartopic(self):
        self._verifier("dartopic")

    def test_qwen(self):
        self._verifier("qwen3_4b")


if __name__ == "__main__":
    unittest.main()
