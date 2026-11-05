"""Tests du croisement profils/hashtags sans modifier les autres modes."""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from connect_profil import ConnexionProfil


class TestCroisementProfilsResearch(unittest.TestCase):
    def creer_parametres(self, operateur="OR", moteur="research"):
        """Construire une collecte de profils avec plusieurs hashtags."""
        return SimpleNamespace(
            comptes=["compte_toulouse", "autre_compte"],
            hashtags=["manifestation", "lyceen", "mobilisation",
                      "education", "toulouse"],
            profil_moteur=moteur,
            operator=operateur,
            date_debut="2026-10-01",
            date_fin="2026-10-31",
        )

    def preparer_connexion(self, parametres):
        """Configurer le connecteur sans ouvrir de navigateur ou appeler TikTok."""
        connexion = ConnexionProfil.__new__(ConnexionProfil)
        connexion.verifier = lambda: None
        connexion.arguments = SimpleNamespace(limit=None)
        sources = connexion.preparer_sources(parametres)
        return connexion, sources

    def test_ou_transmis_a_research_des_la_decouverte(self):
        """Le moteur Research doit recevoir les cinq hashtags en OU."""
        parametres = self.creer_parametres()
        connexion, sources = self.preparer_connexion(parametres)
        self.assertEqual(connexion.research_operateur, "OR")
        self.assertEqual(connexion.research_hashtags, parametres.hashtags)
        self.assertEqual(connexion.research_hashtag, "manifestation")
        self.assertEqual(len(sources), 2)

        with patch("collecte.comptes.collecter_compte",
                   return_value=[]) as collecte:
            connexion.decouvrir(sources[0], {})
        options = collecte.call_args.kwargs
        self.assertEqual(options["research_hashtags"], parametres.hashtags)
        self.assertEqual(options["research_operateur"], "OR")
        self.assertEqual(options["research_debut"], "2026-10-01")
        self.assertEqual(options["research_fin"], "2026-10-31")
        self.assertEqual(options["hashtags"], parametres.hashtags)
        self.assertEqual(options["presse_moteur"], "research")

    def test_et_explicite_toujours_transmis(self):
        """Un utilisateur qui choisit ET doit pouvoir conserver ce choix."""
        parametres = self.creer_parametres(operateur="AND")
        connexion, sources = self.preparer_connexion(parametres)
        with patch("collecte.comptes.collecter_compte",
                   return_value=[]) as collecte:
            connexion.decouvrir(sources[0], {})
        self.assertEqual(collecte.call_args.kwargs["research_operateur"], "AND")
        self.assertEqual(collecte.call_args.kwargs["research_hashtags"],
                         parametres.hashtags)

    def test_autres_moteurs_inchanges(self):
        """La modification des requêtes ne concerne que la Research API."""
        parametres = self.creer_parametres(moteur="navigateur")
        connexion, sources = self.preparer_connexion(parametres)
        self.assertEqual(connexion.moteur_collecte, "navigateur")
        self.assertEqual(connexion.research_hashtags, [])
        self.assertIsNone(connexion.research_hashtag)
        self.assertEqual(len(sources), 2)

    def test_operateur_propre_aux_profils_et_a_la_navigation(self):
        """L'interface Profils possède OU par défaut, sans toucher aux Hashtags."""
        racine = Path(__file__).resolve().parents[1]
        interface = (racine / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(interface)
        self.assertIn('st.session_state.setdefault("operator_comptes", "OR")',
                      interface)
        self.assertIn(
            'key=("operator_comptes" if source == "comptes"',
            interface)
        self.assertIn(
            'else st.session_state.get("operator", "AND")',
            interface)
        self.assertIn(
            'else st.session_state.get("operator_comptes", "OR")',
            interface)


if __name__ == "__main__":
    unittest.main()
