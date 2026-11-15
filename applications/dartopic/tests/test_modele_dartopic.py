"""Tests de régression des thèmes et du vocabulaire, sans téléchargement HF."""
from __future__ import annotations

import unittest

import numpy as np

from modele_dartopic import (
    ParametresDARTopic, _diagnostic_themes,
    _initialiser_nmf, construire_vectoriseur,
)


class TestPretraitementEtThemes(unittest.TestCase):

    def test_apostrophes_et_stopwords(self):
        textes = [
            "C'est ça, a, courage, manifestation, police",
            "C'est bien, a, bravo, police, violence",
            "C'est la violence, courage, police",
            "C'est la manifestation, police, injustice",
            "La manifestation et le courage",
        ]
        parametres = ParametresDARTopic(
            nombre_themes=2, frequence_minimale=1, frequence_maximale=1.0,
        )
        vectoriseur = construire_vectoriseur(
            parametres, ["est", "ça", "c", "la", "le", "et"],
        )
        vectoriseur.fit_transform(textes)
        vocabulaire = set(vectoriseur.get_feature_names_out())
        self.assertNotIn("c'est", vocabulaire)
        self.assertNotIn("est", vocabulaire)
        self.assertNotIn("a", vocabulaire)
        self.assertIn("violence", vocabulaire)
        self.assertIn("police", vocabulaire)

    def test_nmf_initialisation_differencie_les_themes(self):
        documents = (
            ["La police intervient dans la rue", "Des forces de police manifestent",
             "Les policiers interviennent", "La police est présente"] * 3
            + ["Les étudiants étudient en classe", "Les étudiants parlent de cours",
               "Les professeurs enseignent", "La classe et les cours"] * 3
        )
        parametres = ParametresDARTopic(
            nombre_themes=2, frequence_minimale=1, frequence_maximale=1.0,
        )
        matrice = construire_vectoriseur(parametres, ["la", "les", "en"]).fit_transform(documents)
        cible, poids = _initialiser_nmf(matrice, parametres)
        self.assertEqual(cible.shape, (24, 2))
        self.assertEqual(poids.shape, (2, matrice.shape[1]))
        self.assertTrue(np.allclose(cible.sum(axis=1), 1.0))
        self.assertGreater(float(np.abs(np.exp(poids[0]) - np.exp(poids[1])).sum()), 0.01)

    def test_diagnostic_signale_themes_identiques(self):
        distribution = np.array([
            [0.9, 0.1], [0.1, 0.9], [0.6, 0.4],
        ])
        listes = [["police", "violence", "manifestation"], ["police", "violence", "manifestation"]]
        bilan = _diagnostic_themes(distribution, listes)
        self.assertTrue(bilan["alerte_themes_similaires"])
        self.assertEqual(bilan["chevauchement_moyen_mots"], 1.0)


if __name__ == "__main__":
    unittest.main()
