"""Tester les limites d'identification des commentaires TikTok Research.

Le nom affiché n'est pas un identifiant de profil fiable. Les réseaux de
réponses restent calculables à partir des identifiants des commentaires.
"""

import ast
import unittest
from pathlib import Path

from collecte.researchapi import normaliser_commentaire_research
from analyse_sociometrique.import_csv import preparer_import, analyser_import


RACINE = Path(__file__).resolve().parents[1]


class TestCommentairesResearchSociometrie(unittest.TestCase):
    def test_nom_affiche_conserve_sans_inventer_auteur(self):
        """Un nom d'affichage ne doit pas devenir un username sociométrique."""
        commentaire = normaliser_commentaire_research({
            "id": 12345678901234567,
            "video_id": 98765432101234567,
            "text": "Exemple de commentaire",
            "display_name": "Participant",
        }, "98765432101234567")
        self.assertIsNotNone(commentaire)
        self.assertIsNone(commentaire["auteur"])
        self.assertEqual(commentaire["nom_affiche"], "Participant")
        self.assertEqual(commentaire["brut"]["display_name"], "Participant")
        self.assertEqual(commentaire["source"], "research_api_officielle")

    def test_absence_nom_affiche_est_conservee(self):
        """Une réponse sans display_name ne fabrique aucune information."""
        commentaire = normaliser_commentaire_research({
            "id": 12345678901234568,
            "video_id": 98765432101234567,
            "text": "Une autre réponse",
        }, "98765432101234567")
        self.assertIsNone(commentaire["auteur"])
        self.assertEqual(commentaire["nom_affiche"], "")

    def test_import_research_permet_le_reseau_de_reponses(self):
        """Les ID de commentaires permettent une relation parent-enfant."""
        csv_commentaires = (
            "id;publication_id;parent_id;auteur;texte;source\\n"
            "111;900;;;Premier commentaire;research_api_officielle\\n"
            "112;900;111;;Réponse;research_api_officielle\\n"
        ).replace("\\n", "\n")
        donnees = preparer_import([
            ("commentaires.csv", csv_commentaires.encode("utf-8"))
        ])
        self.assertEqual(donnees["commentaires_research"], 2)
        self.assertEqual(donnees["auteurs_candidats"], 0)
        self.assertEqual(donnees["reponses_observees"], 1)
        reseau = analyser_import(donnees, "reponses")
        self.assertEqual(reseau["statistiques"]["liens"], 1)
        reseau_auteurs = analyser_import(donnees, "auteurs_videos")
        self.assertEqual(reseau_auteurs["statistiques"]["liens"], 0)

    def test_import_sans_reponses_explique_le_graphe_vide(self):
        """Un corpus de commentaires parents ne crée pas de fausses réponses."""
        texte = (
            "id;publication_id;parent_id;auteur;texte;source\\n"
            "111;900;;;Commentaire isolé;research_api_officielle\\n"
        ).replace("\\n", "\n")
        donnees = preparer_import([("commentaires.csv", texte.encode("utf-8"))])
        self.assertEqual(donnees["reponses_observees"], 0)
        self.assertTrue(any("Aucune réponse entre commentaires" in message
                            for message in donnees["diagnostics"]))

    def test_export_csv_et_interface_documentent_la_limite(self):
        """Préserver la colonne auteur et ajouter le nom non unique séparément."""
        export = (RACINE / "corpus" / "construction.py").read_text(encoding="utf-8")
        interface = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(export)
        ast.parse(interface)
        self.assertIn('"auteur", "nom_affiche", "ville_etude", "texte"', export)
        self.assertNotIn('st.session_state["sociometrie_csv_mode"] = "reponses"',
                         interface)
        self.assertIn("Aucune réponse collectée", interface)


if __name__ == "__main__":
    unittest.main()
