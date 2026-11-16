"""Tests de l'exploration thématique avec JuriBERT et BERTweetFR."""
from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from analyse_specialisee import interroger_encodeur_specialise
from configuration_qwen import MODELES_PROPOSES, MODELES_SPECIALISES


GRILLE = [
    {"titre": "Droit", "definition": "Normes juridiques et légalité."},
    {"titre": "Indignation", "definition": "Réaction émotionnelle explicite."},
]


class TestModelesSpecialises(unittest.TestCase):
    def simulation(self, noms, valeurs):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "scores": [
                {"theme": theme, "similarite_cosinus": valeur}
                for theme, valeur in zip(noms, valeurs)
            ],
            "texte_tronque": False,
        }
        session = Mock()
        session.post.return_value = response
        return session

    def test_six_modeles_dans_le_menu(self):
        self.assertEqual(len(MODELES_PROPOSES), 6)
        self.assertIn("juribert", MODELES_PROPOSES)
        self.assertIn("bertweetfr", MODELES_PROPOSES)

    def test_modeles_francais_utilisent_transformers_pas_ollama(self):
        for identifiant in MODELES_SPECIALISES:
            with self.subTest(modele=identifiant):
                session = self.simulation(["Droit", "Indignation"], [0.73, 0.12])
                resultat = interroger_encodeur_specialise(
                    "Une condamnation judiciaire.", GRILLE, identifiant,
                    session=session,
                )
                self.assertEqual(resultat["similarite_theme_1"], 0.73)
                self.assertEqual(resultat["similarite_theme_2"], 0.12)
                self.assertEqual(resultat["mode_analyse"], "similarite")
                args = session.post.call_args
                self.assertTrue(args.args[0].endswith("/similarites"))
                self.assertEqual(args.kwargs["json"]["modele"], identifiant)

    def test_score_hors_intervalle_refuse(self):
        session = self.simulation(["Droit", "Indignation"], [1.3, 0.2])
        with self.assertRaisesRegex(ValueError, "hors de"):
            interroger_encodeur_specialise(
                "Une phrase.", GRILLE, "juribert", session=session,
            )

    def test_erreur_service_conserve_diagnostic(self):
        session = Mock()
        reponse = Mock()
        reponse.status_code = 503
        reponse.text = "Modèle absent"
        reponse.raise_for_status.side_effect = requests.HTTPError("503")
        session.post.return_value = reponse
        with self.assertRaisesRegex(requests.HTTPError, "Modèle absent"):
            interroger_encodeur_specialise(
                "Une phrase.", GRILLE, "bertweetfr", session=session,
            )


if __name__ == "__main__":
    unittest.main()
