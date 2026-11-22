"""Vérifier la génération PyVis et la conservation des relations observées."""
import unittest
from unittest.mock import patch
from html import escape

from analyse_sociometrique.reseaux import apercu, construire_reseau


class TestPreparationPyVis(unittest.TestCase):
    def test_apercu_ne_change_pas_le_graphe(self):
        """L'aperçu limite les éléments sans toucher au réseau source."""
        commentaires = [
            {"id": "c1", "publication_id": "v1", "parent_id": "",
             "source": "research", "auteur": ""},
            {"id": "c2", "publication_id": "v1", "parent_id": "c1",
             "source": "research", "auteur": ""},
        ]
        graphe = construire_reseau(
            commentaires, [{"id": "v1"}], "reponses", "collecte")
        visible = apercu(graphe, max_noeuds=300, max_liens=600)
        self.assertEqual(len(visible["liens"]), 1)
        self.assertEqual(len(graphe["liens"]), 1)
        self.assertTrue(visible["oriente"])
        self.assertEqual(len(visible["noeuds"]), 2)

    def test_identites_research_non_inventees(self):
        """Aucun auteur Research non vérifié n'est ajouté au graphe PyVis."""
        commentaires = [{"id": "c1", "publication_id": "v1",
                         "source": "research", "auteur": "pseudo_non_verifie"}]
        graphe = construire_reseau(
            commentaires, [{"id": "v1"}], "auteurs_videos", "collecte")
        self.assertEqual(graphe["statistiques"]["auteurs_distincts"], 0)
        self.assertEqual(graphe["noeuds"], [])


class TestHtmlPyVis(unittest.TestCase):
    def test_html_autonome_et_echappement(self):
        """Le survol n'injecte pas directement du HTML provenant des données."""
        try:
            from analyse_sociometrique.visualisation_pyvis import html_reseau_pyvis
        except ImportError:
            self.skipTest("Installer PyVis pour exécuter les tests de rendu.")
        graphe = {
            "oriente": True,
            "noeuds": [
                {"id": "commentaire:c1", "label": "<script>alerte</script>",
                 "type": "commentaire"},
                {"id": "commentaire:c2", "label": "Réponse",
                 "type": "commentaire"},
            ],
            "liens": [{"source": "commentaire:c2",
                       "cible": "commentaire:c1",
                       "poids": 2, "relation": "reponse_a"}],
        }
        html = html_reseau_pyvis(graphe)
        self.assertIn("vis-network", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<strong><script>", html)
        self.assertIn("commentaire:c1", html)

    def test_limites_du_rendu(self):
        """Les bornes évitent de saturer l'interface Streamlit."""
        try:
            from analyse_sociometrique.visualisation_pyvis import html_reseau_pyvis
        except ImportError:
            self.skipTest("Installer PyVis pour exécuter les tests de rendu.")
        with self.assertRaises(ValueError):
            html_reseau_pyvis({"noeuds": [], "liens": []}, hauteur=100)
        avec_trop_de_noeuds = {
            "noeuds": [{"id": str(i)} for i in range(501)],
            "liens": [],
        }
        with self.assertRaises(ValueError):
            html_reseau_pyvis(avec_trop_de_noeuds)


if __name__ == "__main__":
    unittest.main()
