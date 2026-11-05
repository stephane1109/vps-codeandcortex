"""Vérifier que OU est proposé par défaut pour les hashtags."""

import ast
import inspect
import unittest
from pathlib import Path

from collecte.researchapi import collecter_videos_presse_research
from webapp import StartRequest


RACINE = Path(__file__).resolve().parents[1]


class TestOperateurOuDefaut(unittest.TestCase):
    def test_ou_est_le_defaut_de_la_requete_api(self):
        """Le modèle n'impose plus ET à une collecte sans opérateur."""
        self.assertEqual(StartRequest.model_fields["operator"].default, "OR")
        self.assertEqual(
            StartRequest.model_fields["operator_presse"].default, "OR")

    def test_ou_est_le_defaut_de_la_research_api(self):
        """Le connecteur Research emploie OU lorsqu'aucun opérateur n'est donné."""
        signature = inspect.signature(collecter_videos_presse_research)
        self.assertEqual(signature.parameters["operateur"].default, "OR")

    def test_collecte_par_hashtag_ou_par_compte_par_defaut(self):
        """L'API transmet OU sans supprimer la sélection explicite ET."""
        for source in ("hashtags", "comptes"):
            with self.subTest(source=source):
                donnees = {
                    "source_collecte": source,
                    "hashtags_saisis": ["manifestation", "lyceen"],
                    "hashtag_moteur": "navigateur",
                    "profil_moteur": "navigateur",
                }
                if source == "comptes":
                    donnees["comptes"] = ["compte_toulouse"]
                parametres = StartRequest.model_validate(donnees)
                self.assertEqual(parametres.operator, "OR")
                donnees["operator"] = "AND"
                explicite = StartRequest.model_validate(donnees)
                self.assertEqual(explicite.operator, "AND")

    def test_interface_ou_est_initialise_par_defaut(self):
        """L'interface affiche OU sur les nouvelles collectes."""
        interface = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(interface)
        self.assertIn('st.session_state.setdefault("operator", "OR")', interface)
        self.assertIn('st.session_state.setdefault("operator_comptes", "OR")',
                      interface)
        self.assertIn('"Combiner les hashtags", ["OR", "AND"]', interface)
        self.assertIn('"Combiner les hashtags de presse", ["OR", "AND"]',
                      interface)
        self.assertIn('else st.session_state.get("operator", "OR")', interface)
        self.assertIn('ancienne.get("operator","OR")', interface)

    def test_et_strict_reste_disponible(self):
        """Le mode ET multi-hashtags reste activable sur demande."""
        connecteur = (RACINE / "connect_htag.py").read_text(encoding="utf-8")
        ast.parse(connecteur)
        self.assertIn(
            'getattr(parametres, "operator", "OR") == "AND"', connecteur)
        modele = (RACINE / "webapp.py").read_text(encoding="utf-8")
        self.assertIn('self.operator = "AND"', modele)


if __name__ == "__main__":
    unittest.main()
