"""Tests de non-régression du format IRaMuTeQ et de l'indexation."""
import unittest

import numpy as np
import pandas as pd

from lecture_iramuteq import analyser_corpus, exporter_iramuteq, tableau_documents
from traitements import construire_croisement, enrichir_documents


class TestCorpusIRaMuTeQ(unittest.TestCase):
    def setUp(self):
        self.source = (
            "**** *source_original *profil_bfmtv *id_123 *texte_commentaire\n"
            "Première ligne.\nSeconde ligne.\n\n"
            "**** *source_ia *profil_autre *id_124\n"
            "Un autre texte.\n\n"
            "**** *source_original *profil_autre *id_125\n"
            "\n"
        )
        self.documents = analyser_corpus(self.source.encode("utf-8"))
        self.tableau = tableau_documents(self.documents)

    def test_import_avec_variables_et_textes(self):
        self.assertEqual(len(self.documents), 3)
        self.assertIn("Seconde ligne.", self.documents[0].texte)
        self.assertEqual(self.tableau.loc[0, "variable_profil"], "bfmtv")
        self.assertEqual(self.tableau.loc[1, "variable_id"], "124")
        self.assertEqual(self.documents[2].texte, "")

    def test_export_conserve_entete(self):
        export = exporter_iramuteq(
            self.documents, {1: "theme_00", 2: "hors_theme", 3: "non_analyse"},
            "bertopic",
        ).decode("utf-8")
        self.assertIn(
            "**** *source_original *profil_bfmtv *id_123 *texte_commentaire *bertopic_theme_00",
            export,
        )
        self.assertIn("**** *source_ia *profil_autre *id_124 *bertopic_hors_theme", export)
        self.assertIn("Seconde ligne.", export)

    def test_affectations_partielles(self):
        resultat = enrichir_documents(
            self.tableau, np.array([0, 1]), [0, -1], [0.9, 0.2],
            np.array([[0.9], [0.0]]), [0],
        )
        self.assertEqual(resultat.loc[0, "theme_dominant"], "theme_00")
        self.assertEqual(resultat.loc[1, "statut_analyse"], "hors_theme")
        self.assertEqual(resultat.loc[2, "theme_dominant"], "non_analyse")
        self.assertTrue(pd.isna(resultat.loc[1, "probabilite_theme"]))
        self.assertAlmostEqual(resultat.loc[0, "probabilite_theme_00"], 0.9)

    def test_croisements(self):
        resultat = enrichir_documents(
            self.tableau, np.array([0, 1]), [0, -1], [0.9, 0.1],
        )
        comptes, proportions = construire_croisement(resultat, "variable_profil")
        self.assertEqual(int(comptes.to_numpy().sum()), 2)
        self.assertAlmostEqual(float(proportions.loc["bfmtv"].sum()), 100.0)

    def test_entete_invalide(self):
        with self.assertRaises(ValueError):
            analyser_corpus("Texte sans en-tête.")

    def test_indices_incoherents(self):
        with self.assertRaises(ValueError):
            enrichir_documents(self.tableau, np.array([0]), [0, 1], [0.9])


if __name__ == "__main__":
    unittest.main()
