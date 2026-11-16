"""Tests du moteur zero-shot sans téléchargement de modèle."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

import pandas as pd

from moteur_zero_shot import (
    classifier_textes, exporter_documents_iramuteq,
    identifiant_categorie, preparer_categories, verifier_hypothese,
)


class FauxClassifieur:
    """Simuler les réponses de Hugging Face pour tester les transformations."""
    def __call__(self, textes, candidate_labels, hypothesis_template,
                 multi_label, batch_size, truncation):
        assert batch_size > 0 and truncation
        assert hypothesis_template.format(candidate_labels[0])
        return [{
            "labels": list(reversed(candidate_labels)),
            "scores": ([0.15, 0.83] if len(candidate_labels) == 2 else [0.8]),
        } for texte in textes]


@dataclass(frozen=True)
class FauxDocument:
    numero: int
    entete: str
    texte: str


class TestMoteurZeroShot(unittest.TestCase):
    def test_categories_libres_et_dedoublonnage(self):
        self.assertEqual(
            preparer_categories(
                "santé\nSanté\néducation\n\n# une ligne de commentaire\n"
            ),
            ["santé", "éducation"],
        )

    def test_categories_non_imposees(self):
        self.assertEqual(
            preparer_categories("tourisme\ngastronomie\ntransport", False),
            ["tourisme", "gastronomie", "transport"],
        )

    def test_hypothese(self):
        self.assertEqual(
            verifier_hypothese("Ce texte parle de {}. "),
            "Ce texte parle de {}.",
        )
        with self.assertRaises(ValueError):
            verifier_hypothese("Ce texte parle de politique.")

    def test_multilabel(self):
        sorties = classifier_textes(
            FauxClassifieur(), ["Texte A", "Texte B"],
            ["tourisme", "économie"], "Ce texte concerne {}.", True, 0.7,
        )
        self.assertEqual(len(sorties), 2)
        self.assertEqual(sorties[0]["categorie_principale"], "tourisme")
        self.assertEqual(sorties[0]["categories_retenues"], ["tourisme"])
        self.assertAlmostEqual(sorties[0]["scores"]["économie"], 0.15)

    def test_seuil_indetermine(self):
        sorties = classifier_textes(
            FauxClassifieur(), ["Texte A"],
            ["politique", "culture"], "Ce texte concerne {}.", False, 0.9,
        )
        self.assertEqual(sorties[0]["categorie_principale"], "indetermine")
        self.assertEqual(sorties[0]["categories_retenues"], [])

    def test_identifiant_stable(self):
        identifiant = identifiant_categorie("Santé publique")
        self.assertEqual(identifiant, identifiant_categorie("Santé publique"))
        self.assertNotEqual(
            identifiant, identifiant_categorie("Santé-publique")
        )

    def test_export_iramuteq_conserve_metadonnees(self):
        documents = [
            FauxDocument(
                1, "**** *source_original *profil_test", "un commentaire"
            )
        ]
        tableau = pd.DataFrame([{
            "numero_document": 1,
            "statut_analyse": "ok",
            "categorie_principale": "éducation",
            "classe_01": True,
            "classe_02": False,
        }])
        sortie = exporter_documents_iramuteq(
            documents, tableau, ["éducation", "tourisme"]
        ).decode("utf-8")
        self.assertIn("*profil_test", sortie)
        self.assertIn("*zs_principale_", sortie)
        self.assertIn(
            "*zs_" + identifiant_categorie("éducation") + "_oui", sortie
        )
        self.assertNotIn(
            "*zs_" + identifiant_categorie("tourisme") + "_oui", sortie
        )


if __name__ == "__main__":
    unittest.main()
