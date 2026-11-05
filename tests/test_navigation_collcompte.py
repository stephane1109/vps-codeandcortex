"""Contrôler l'indépendance de l'onglet Collecte de compte."""

import ast
import unittest
from pathlib import Path


RACINE = Path(__file__).resolve().parents[1]


def lire_module(nom):
    """Lire le code exact d'un module du projet."""
    return (RACINE / nom).read_text(encoding="utf-8")


class TestNavigationCollecteCompte(unittest.TestCase):
    def test_module_autonome_conserve_la_decouverte(self):
        """La recherche territoriale, les preuves et les exports restent présents."""
        code = lire_module("collcompte.py")
        arbre = ast.parse(code)
        fonctions = {
            noeud.name for noeud in arbre.body
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("afficher_collecte_de_compte", fonctions)
        self.assertIn("territoire_recherche_hashtags_croises", code)
        self.assertIn("territoire_inventaire_choix", code)
        self.assertIn("territoire_arreter", code)
        self.assertIn("territoire_poursuivre", code)
        self.assertIn("URL vidéo justificative", code)
        self.assertIn("territoire_telecharger_csv", code)
        self.assertIn("territoire_telecharger_txt", code)

    def test_onglet_principal_et_formulaire_separes(self):
        """Collecte de compte ne figure plus dans les sous-onglets Profils."""
        texte = lire_module("streamlit_app.py")
        ast.parse(texte)
        self.assertIn(
            '"Collecte", "Collecte de compte", "Base de données"',
            texte)
        self.assertIn("with onglet_collecte_de_compte:", texte)
        self.assertIn("from collcompte import afficher_collecte_de_compte", texte)
        self.assertNotIn("onglet_profils_territoire", texte)
        self.assertNotIn("onglet_profils_collecte", texte)

        debut = texte.index('    elif source == "comptes":')
        fin = texte.index("    # L'aide est contextualisée", debut)
        formulaire = texte[debut:fin]
        self.assertIn('"Comptes TikTok"', formulaire)
        self.assertIn("comptes_csv_import_fichiers", formulaire)
        self.assertNotIn("afficher_collecte_de_compte", formulaire)

    def test_transfert_selection_complete(self):
        """Les comptes découverts restent disponibles dans Autres comptes."""
        interface = lire_module("collcompte.py")
        application = lire_module("streamlit_app.py")
        self.assertIn(
            'st.session_state["comptes_territoire_en_attente"] = ", ".join(selection)',
            interface)
        self.assertIn(
            'st.session_state["source_selection_en_attente"] = "comptes"',
            interface)
        self.assertIn(
            'st.session_state["source"] = "comptes"', application)
        self.assertIn(
            'st.session_state["comptes"] = transfert_territorial',
            application)

    def test_ancien_import_reste_compatible(self):
        """Les anciennes références au module Streamlit ne sont pas rompues."""
        compatibilite = lire_module("interface/decouverte_territoriale_ui.py")
        ast.parse(compatibilite)
        self.assertIn(
            "from collcompte import afficher_collecte_de_compte "
            "as afficher_decouverte_territoriale",
            compatibilite)


if __name__ == "__main__":
    unittest.main()
