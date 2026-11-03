"""Tests de suppression de modalités et de recalcul automatique AFC."""
from pathlib import Path
import unittest

import pandas as pd

from traitement_csv import exclure_modalites_contingence, preparer_contingence


DOSSIER_APPLICATION = Path(__file__).resolve().parents[1]


class TestsExclusionModalites(unittest.TestCase):
    """Contrôler les modifications de tableaux avant leur analyse FactoMineR."""

    def setUp(self):
        # Trois modalités par variable et dix observations au total.
        self.donnees = pd.DataFrame({
            "lignes": ["A"] * 3 + ["B"] * 4 + ["C"] * 3,
            "colonnes": [
                "X", "X", "Y",
                "X", "Y", "Y", "Z",
                "X", "Z", "Z",
            ],
        })
        self.initiale = preparer_contingence(
            self.donnees, "lignes", "colonnes"
        )

    def test_supprimer_ligne_et_colonne_recompte_les_observations(self):
        preparation = exclure_modalites_contingence(
            self.initiale, ["A"], ["Z"]
        )
        self.assertEqual(self.initiale.effectif_final, 10)
        self.assertEqual(preparation.effectif_avant_exclusion_modalites, 10)
        self.assertEqual(preparation.effectif_final, 4)
        self.assertEqual(preparation.tableau.index.tolist(), ["B", "C"])
        self.assertEqual(preparation.tableau.columns.tolist(), ["X", "Y"])
        self.assertEqual(preparation.modalites_exclues_lignes, ("A",))
        self.assertEqual(preparation.modalites_exclues_colonnes, ("Z",))
        self.assertEqual(preparation.tableau.loc["B", "Y"], 2)
        self.assertEqual(preparation.tableau.loc["C", "Y"], 0)

    def test_fichier_source_et_tableau_initial_restent_inchanges(self):
        ancien = self.initiale.tableau.copy(deep=True)
        exclure_modalites_contingence(self.initiale, ["A"], ["Z"])
        pd.testing.assert_frame_equal(self.initiale.tableau, ancien)
        self.assertEqual(len(self.donnees), 10)
        restauree = exclure_modalites_contingence(self.initiale)
        pd.testing.assert_frame_equal(restauree.tableau, ancien)
        self.assertEqual(restauree.effectif_final, 10)

    def test_exclure_seulement_une_ligne_ou_une_colonne(self):
        lignes = exclure_modalites_contingence(self.initiale, ["A"])
        colonnes = exclure_modalites_contingence(
            self.initiale, colonnes_a_exclure=["Z"]
        )
        self.assertEqual(lignes.tableau.shape, (2, 3))
        self.assertEqual(colonnes.tableau.shape, (3, 2))
        self.assertEqual(lignes.effectif_final, 7)
        self.assertEqual(colonnes.effectif_final, 7)

    def test_marges_devenues_vides_sont_retires(self):
        # La seule observation en X appartient à A : supprimer A viderait X.
        donnees = pd.DataFrame({
            "lignes": ["A", "B", "B", "C", "C"],
            "colonnes": ["X", "Y", "Z", "Y", "Z"],
        })
        initiale = preparer_contingence(donnees, "lignes", "colonnes")
        preparation = exclure_modalites_contingence(initiale, ["A"])
        self.assertEqual(preparation.modalites_vides_colonnes, ("X",))
        self.assertEqual(preparation.tableau.shape, (2, 2))
        self.assertEqual(preparation.effectif_final, 4)

    def test_refuser_une_seule_modalite_active(self):
        with self.assertRaisesRegex(ValueError, "au moins deux"):
            exclure_modalites_contingence(self.initiale, ["A", "B"])
        with self.assertRaisesRegex(ValueError, "au moins deux"):
            exclure_modalites_contingence(
                self.initiale, colonnes_a_exclure=["X", "Y"]
            )

    def test_refuser_les_modalites_inexistantes(self):
        with self.assertRaisesRegex(ValueError, "absentes"):
            exclure_modalites_contingence(
                self.initiale, ["modalité_nontrouvé"]
            )
        with self.assertRaisesRegex(ValueError, "absentes"):
            exclure_modalites_contingence(
                self.initiale, colonnes_a_exclure=["inconnue"]
            )

    def test_supprimer_une_modalite_non_trouvee_presente_dans_le_csv(self):
        """Une modalité textuelle accentuée peut être écartée en lignes."""
        donnees = pd.DataFrame({
            "lignes": [
                "modalité_nontrouvé", "modalité_nontrouvé",
                "catégorie A", "catégorie A",
                "catégorie B", "catégorie B",
            ],
            "colonnes": ["X", "Y", "X", "Y", "X", "Y"],
        })
        initiale = preparer_contingence(donnees, "lignes", "colonnes")
        resultat = exclure_modalites_contingence(
            initiale, lignes_a_exclure=["modalité_nontrouvé"]
        )
        self.assertNotIn("modalité_nontrouvé", resultat.tableau.index)
        self.assertEqual(resultat.effectif_final, 4)
        self.assertIn("modalité_nontrouvé", initiale.tableau.index)

    def test_dedoublonner_une_modalite_supprimee(self):
        resultat = exclure_modalites_contingence(
            self.initiale, ["A", "A"], ["Z", "Z"]
        )
        self.assertEqual(resultat.modalites_exclues_lignes, ("A",))
        self.assertEqual(resultat.modalites_exclues_colonnes, ("Z",))
        self.assertEqual(resultat.effectif_final, 4)

    def test_interface_selection_et_recalcul_automatique(self):
        """Une suppression déclenche un nouveau calcul R et invalide l'ancien."""
        interface = (DOSSIER_APPLICATION / "application.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"Supprimer des lignes (modalités)"', interface
        )
        self.assertIn(
            '"Supprimer des colonnes (modalités)"', interface
        )
        self.assertIn(
            '"Rétablir toutes les lignes et colonnes"', interface
        )
        self.assertIn("exclure_modalites_contingence(", interface)
        self.assertIn("recalcul_automatique = (", interface)
        self.assertIn("if lancement_manuel or recalcul_automatique:", interface)
        self.assertIn("st.session_state[\"afc_portee_modalites\"]", interface)
        self.assertIn('"modalites_exclues_lignes":', interface)
        self.assertIn('"modalites_exclues_colonnes":', interface)
        self.assertIn('st.dataframe(preparation.tableau', interface)
        self.assertIn('st.session_state.pop("dernier_resultat", None)', interface)
        self.assertIn("afficher_resultats(", interface)
        self.assertIn('"13_plan_factoriel.png"', interface)
        self.assertIn('"06_valeurs_propres_inerties.csv"', interface)
        self.assertIn('"significativite_modalites_factominer.csv"', interface)


if __name__ == "__main__":
    unittest.main()
