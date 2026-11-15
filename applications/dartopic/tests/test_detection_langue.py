"""Tests sans téléchargement des modèles linguistiques et neuronaux."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from detection_langue import classifier_texte
from lecture_iramuteq import analyser_corpus, tableau_documents


class DetecteurSimule:
    def __init__(self, langue="FRENCH", confiance=0.92, autre=0.08):
        self.langue = langue
        self.confiance = confiance
        self.autre = autre

    def compute_language_confidence_values(self, texte):
        return [
            SimpleNamespace(
                language=SimpleNamespace(name=self.langue),
                value=self.confiance,
            ),
            SimpleNamespace(
                language=SimpleNamespace(name="ENGLISH" if self.langue != "ENGLISH" else "FRENCH"),
                value=self.autre,
            ),
        ]


class TestDetectionLangue(unittest.TestCase):
    def test_francais(self):
        resultat = classifier_texte(
            "Cette manifestation prend beaucoup d'ampleur", DetecteurSimule(),
        )
        self.assertEqual(resultat["statut_langue"], "francais")

    def test_hors_francais(self):
        resultat = classifier_texte(
            "These demonstrations are continuing", DetecteurSimule("ENGLISH"),
        )
        self.assertEqual(resultat["statut_langue"], "hors_francais")

    def test_tres_court_indetermine(self):
        resultat = classifier_texte("Merci", DetecteurSimule())
        self.assertEqual(resultat["statut_langue"], "indetermine")

    def test_confiance_insuffisante(self):
        resultat = classifier_texte(
            "Cette manifestation est partout maintenant",
            DetecteurSimule(confiance=0.51, autre=0.49),
        )
        self.assertEqual(resultat["statut_langue"], "indetermine")

    def test_import_iramuteq_non_modifie(self):
        documents = analyser_corpus("**** *profil_a\nBonjour le monde\n")
        self.assertEqual(tableau_documents(documents).loc[0, "variable_profil"], "a")


if __name__ == "__main__":
    unittest.main()
