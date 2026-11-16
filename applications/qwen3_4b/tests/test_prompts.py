"""Tests de non-régression des modes prompt et grille structurée de Qwen."""
from __future__ import annotations

import unittest
from unittest.mock import Mock

from codage_qwen import (
    CHAMPS_BOOLEENS, PROMPT_LIBRE_DEFAUT, coder_commentaire,
    verifier_resultat,
)


class TestAnalyseQwen(unittest.TestCase):
    def test_prompt_libre_sans_schema(self):
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": "Le commentaire évoque une question éducative."}
        }
        session = Mock()
        session.post.return_value = reponse
        resultat = coder_commentaire(
            "Un commentaire éducatif", consigne="Repère le thème éducatif.",
            mode_analyse="libre", session=session,
        )
        self.assertEqual(resultat["mode_analyse"], "libre")
        self.assertIn("question éducative", resultat["reponse_qwen"])
        charge = session.post.call_args.kwargs["json"]
        self.assertNotIn("format", charge)
        self.assertIn("Repère le thème éducatif.", charge["messages"][0]["content"])

    def test_codage_ancien_schema_preserve(self):
        import json
        valeurs = {champ: False for champ in CHAMPS_BOOLEENS}
        valeurs.update({
            "acteur_cible": "", "indice_textuel": "", "justification": "RAS",
        })
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": json.dumps(valeurs)}
        }
        session = Mock()
        session.post.return_value = reponse
        resultat = coder_commentaire(
            "Pas de violence.", mode_analyse="structure", session=session,
        )
        self.assertFalse(resultat["violence_evoquee"])
        self.assertEqual(resultat["mode_analyse"], "structure")
        charge = session.post.call_args.kwargs["json"]
        self.assertIn("format", charge)

    def test_prompt_vide_refuse(self):
        with self.assertRaisesRegex(ValueError, "prompt"):
            coder_commentaire(
                "Une phrase", consigne="   ", mode_analyse="libre",
            )

    def test_erreur_http_ollama_avec_detail(self):
        import requests
        reponse = Mock()
        reponse.status_code = 500
        reponse.text = "llama runner process has terminated"
        reponse.raise_for_status.side_effect = requests.HTTPError("500")
        session = Mock()
        session.post.return_value = reponse
        with self.assertRaisesRegex(
            requests.HTTPError,
            "Modèle sollicité : .* ; Contexte demandé : .*"
        ) as contexte:
            coder_commentaire(
                "Commentaire d'essai",
                consigne="Analyse ce commentaire.",
                mode_analyse="libre",
                session=session,
            )
        self.assertIn(
            "llama runner process has terminated", str(contexte.exception)
        )

    def test_reponse_ollama_vide_explicitement_signalee(self):
        reponse = Mock()
        reponse.json.return_value = {"message": {"content": ""}}
        session = Mock()
        session.post.return_value = reponse
        with self.assertRaisesRegex(ValueError, "message.content"):
            coder_commentaire(
                "Commentaire d'essai",
                consigne="Analyse ce commentaire.",
                mode_analyse="libre",
                session=session,
            )

    def test_schema_rejette_les_chaine_boolean(self):
        valeurs = {champ: "false" for champ in CHAMPS_BOOLEENS}
        valeurs.update({
            "acteur_cible": "", "indice_textuel": "", "justification": "",
        })
        with self.assertRaises(ValueError):
            verifier_resultat(valeurs)


if __name__ == "__main__":
    unittest.main()
