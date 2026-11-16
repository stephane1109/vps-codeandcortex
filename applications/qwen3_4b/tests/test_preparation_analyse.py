"""Tests de non-régression des boutons d'analyse Qwen."""
from __future__ import annotations

import unittest

from preparation_analyse import evaluer_commandes_analyse


class TestPreparationAnalyse(unittest.TestCase):
    def test_import_csv_avec_grille_active_tous_les_boutons(self):
        etat = evaluer_commandes_analyse(
            20, 0, "Classe le commentaire.", "theses", True, True,
        )
        self.assertTrue(etat["tester"])
        self.assertTrue(etat["lancer"])
        self.assertFalse(etat["relancer"])
        self.assertEqual(etat["causes"], [])

    def test_controle_ollama_indisponible_ne_bloque_plus(self):
        etat = evaluer_commandes_analyse(
            20, 0, "Classe le commentaire.", "theses", True, False,
        )
        self.assertTrue(etat["tester"])
        self.assertTrue(etat["lancer"])
        self.assertTrue(etat["avertissement_service"])

    def test_grille_invalide_signalee(self):
        etat = evaluer_commandes_analyse(
            20, 0, "Classe le commentaire.", "theses", False, True,
        )
        self.assertFalse(etat["tester"])
        self.assertFalse(etat["lancer"])
        self.assertIn("grille", etat["causes"][0].lower())

    def test_reessayer_sans_commentaire_restant(self):
        etat = evaluer_commandes_analyse(
            0, 2, "Classe le commentaire.", "theses", True, True,
        )
        self.assertFalse(etat["lancer"])
        self.assertTrue(etat["relancer"])

    def test_aucun_texte_non_vide(self):
        etat = evaluer_commandes_analyse(
            0, 0, "Classe le commentaire.", "libre", True, True,
        )
        self.assertFalse(etat["tester"])
        self.assertTrue(any("Aucun commentaire" in cause for cause in etat["causes"]))

    def test_modes_anciens_independants_de_la_grille(self):
        for mode in ("libre", "structure"):
            with self.subTest(mode=mode):
                etat = evaluer_commandes_analyse(
                    1, 0, "Analyse.", mode, False, True,
                )
                self.assertTrue(etat["lancer"])

    def test_prompt_vide_signale(self):
        etat = evaluer_commandes_analyse(
            5, 0, "  ", "theses", True, True,
        )
        self.assertFalse(etat["lancer"])
        self.assertTrue(any("prompt" in cause for cause in etat["causes"]))


if __name__ == "__main__":
    unittest.main()
