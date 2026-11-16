"""Tests des annotations indépendantes pour des prompts divers."""
from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from codage_multithemes import (
    PROMPT_MATRICE_DEFAUT,
    coder_multithemes, codes_themes, proposer_themes_depuis_prompt,
    schema_annotation, segmenter_texte, valider_annotation, valider_themes,
)


THEMES = [
    {"titre": "Critique", "definition": "Un jugement négatif explicite."},
    {"titre": "Émotion", "definition": "Un sentiment explicitement manifesté."},
]


class TestCodageMultithemes(unittest.TestCase):
    def simulation(self, donnees):
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": json.dumps(donnees, ensure_ascii=False)}
        }
        session = Mock()
        session.post.return_value = reponse
        return session

    def annotation(self):
        return {
            "theme_1": True, "indice_theme_1": "C nul",
            "probabilite_theme_1": 0.91,
            "theme_2": True, "indice_theme_2": "jss deg",
            "probabilite_theme_2": 0.74,
            "incertitude_interpretation": False,
            "probabilite_incertitude": 0.11,
            "justification": "Critique et émotion exprimées.",
        }

    def test_prompt_par_defaut_court_pour_contexte_1024(self):
        self.assertLess(len(PROMPT_MATRICE_DEFAUT), 700)
        self.assertIn("Dénonciation de la violence", PROMPT_MATRICE_DEFAUT)
        self.assertIn("Indignation face à la violence", PROMPT_MATRICE_DEFAUT)
        self.assertIn("persécuteur", PROMPT_MATRICE_DEFAUT)

    def test_themes_determines_par_prompt(self):
        grille = valider_themes([
            {"titre": "Mobilité", "definition": "Discours sur les transports."},
        ])
        self.assertEqual(codes_themes(grille), ["theme_1"])
        self.assertEqual(
            list(schema_annotation(grille)["properties"]),
            [
                "theme_1", "indice_theme_1",
                "probabilite_theme_1", "incertitude_interpretation",
                "probabilite_incertitude", "justification",
            ],
        )

    def test_lecture_rapide_avec_delai_reduit(self):
        texte = "C nul jss deg"
        session = self.simulation(self.annotation())
        resultat = coder_multithemes(
            texte, themes=THEMES, session=session, timeout_lecture=60,
        )
        self.assertEqual(session.post.call_count, 1)
        self.assertEqual(
            session.post.call_args.kwargs["timeout"], (10, 60)
        )
        self.assertTrue(resultat["theme_1"])

    def test_delai_hors_limites_refuse(self):
        with self.assertRaisesRegex(ValueError, "délai"):
            coder_multithemes(
                "Texte", themes=THEMES, timeout_lecture=1,
            )

    def test_commentaire_sms_plusieurs_themes(self):
        texte = "C nul jss deg"
        session = self.simulation(self.annotation())
        resultat = coder_multithemes(
            texte, themes=THEMES, session=session
        )
        self.assertTrue(resultat["theme_1"])
        self.assertTrue(resultat["theme_2"])
        self.assertEqual(resultat["probabilite_theme_1"], 0.91)
        self.assertEqual(resultat["probabilite_incertitude"], 0.11)
        self.assertEqual(resultat["nombre_segments"], 1)

    def test_texte_long_toujours_meme_grille(self):
        texte = "Un paragraphe descriptif détaillé. " * 90
        morceaux = segmenter_texte(texte, longueur_max=650)
        self.assertGreater(len(morceaux), 1)
        self.assertEqual(morceaux[0][:15], texte[:15])
        self.assertEqual(morceaux[-1][-20:], texte[-20:])
        donnees = {
            "theme_1": False, "indice_theme_1": "",
            "probabilite_theme_1": 0.07,
            "theme_2": False, "indice_theme_2": "",
            "probabilite_theme_2": 0.04,
            "incertitude_interpretation": False,
            "probabilite_incertitude": 0.03,
            "justification": "Aucun jugement ni sentiment explicite.",
        }
        session = self.simulation(donnees)
        resultat = coder_multithemes(texte, themes=THEMES, session=session)
        self.assertEqual(resultat["nombre_segments"], session.post.call_count)
        self.assertFalse(resultat["theme_1"])
        self.assertFalse(resultat["texte_tronque"])

    def test_citation_invente_signale_une_incertitude(self):
        resultats = valider_annotation(
            self.annotation(), "Ce texte n'a aucun indice.", THEMES
        )
        self.assertTrue(resultats["incertitude_interpretation"])
        self.assertEqual(resultats["probabilite_incertitude"], 1.0)
        self.assertEqual(resultats["indice_theme_1"], "")

    def test_score_invalide_refuse(self):
        annotation = self.annotation()
        annotation["probabilite_theme_1"] = 1.7
        with self.assertRaisesRegex(ValueError, "Score hors"):
            valider_annotation(annotation, "C nul jss deg", THEMES)

    def test_proposition_avec_theme_du_chercheur(self):
        session = self.simulation({
            "themes": [
                {"titre": "Tourisme", "definition": "Discours sur le tourisme."}
            ]
        })
        resultats = proposer_themes_depuis_prompt(
            "Repérer le tourisme.", ["Un séjour à la mer."],
            session=session,
        )
        self.assertEqual(resultats[0]["titre"], "Tourisme")
        charge = session.post.call_args.kwargs["json"]
        self.assertIn("Repérer le tourisme.", charge["messages"][1]["content"])

    def test_grille_duplicate_refusee(self):
        with self.assertRaisesRegex(ValueError, "plusieurs fois"):
            valider_themes([THEMES[0], dict(THEMES[0])])


if __name__ == "__main__":
    unittest.main()
