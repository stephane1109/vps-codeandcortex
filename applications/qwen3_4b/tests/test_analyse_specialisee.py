"""Tests de l'exploration thématique avec JuriBERT et BERTweetFR."""
from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from analyse_specialisee import (
    interroger_encodeur_specialise, interroger_classification_zero_shot,
)
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


    def simulation_nli(self, valeurs=None):
        """Simuler les trois relations NLI sans solliciter les poids du modèle."""
        reponse = Mock()
        reponse.raise_for_status.return_value = None
        if valeurs is None:
            valeurs = [
                ("Droit", 0.04, 0.93, 0.03, "neutralite"),
                ("Indignation", 0.02, 0.96, 0.02, "neutralite"),
            ]
        reponse.json.return_value = {
            "scores": [
                {
                    "theme": titre,
                    "hypothese": f"Ce message exprime {titre}.",
                    "implication": implication,
                    "neutralite": neutralite,
                    "contradiction": contradiction,
                    "relation_predite": relation,
                }
                for titre, implication, neutralite, contradiction, relation
                in valeurs
            ],
            "texte_tronque": False,
        }
        session = Mock()
        session.post.return_value = reponse
        return session

    def test_nli_zero_shot_ne_confond_pas_politique_et_violence(self):
        """Valider l'interface des relations ; ce test ne mesure pas le modèle."""
        session = self.simulation_nli()
        resultat = interroger_classification_zero_shot(
            "Un commentaire politique sans violence.", GRILLE,
            session=session,
        )
        self.assertEqual(resultat["nli_relation_theme_1"], "neutralite")
        self.assertEqual(resultat["nli_neutralite_theme_1"], 0.93)
        self.assertEqual(resultat["nli_implication_theme_2"], 0.02)
        self.assertEqual(resultat["mode_analyse"], "nli_zero_shot")
        arguments = session.post.call_args
        self.assertTrue(arguments.args[0].endswith("/inferences"))
        self.assertEqual(
            arguments.kwargs["json"]["modele"], "nli_multilingue",
        )

    def test_nli_rejette_un_score_invalide(self):
        session = self.simulation_nli([
            ("Droit", 1.3, 0.0, 0.0, "implication"),
            ("Indignation", 0.1, 0.8, 0.1, "neutralite"),
        ])
        with self.assertRaisesRegex(ValueError, "hors de"):
            interroger_classification_zero_shot(
                "Une phrase.", GRILLE, session=session,
            )

    def test_nli_rejette_une_reponse_incomplete(self):
        session = self.simulation_nli()
        reponse = session.post.return_value
        reponse.json.return_value["scores"].pop()
        with self.assertRaisesRegex(ValueError, "incomplets"):
            interroger_classification_zero_shot(
                "Une phrase.", GRILLE, session=session,
            )

    def test_nli_conserve_le_diagnostic_du_service(self):
        session = Mock()
        reponse = Mock()
        reponse.status_code = 503
        reponse.text = "Modèle NLI non téléchargé"
        reponse.raise_for_status.side_effect = requests.HTTPError("503")
        session.post.return_value = reponse
        with self.assertRaisesRegex(
            requests.HTTPError, "Modèle NLI non téléchargé"
        ):
            interroger_classification_zero_shot(
                "Une phrase.", GRILLE, session=session,
            )


if __name__ == "__main__":
    unittest.main()
