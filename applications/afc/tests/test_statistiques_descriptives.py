"""Tests des statistiques descriptives sans dépendance à R ou Streamlit."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from statistiques_descriptives import (
    comparer_groupes,
    convertir_dates,
    convertir_nombres,
    preparer_echantillon_descriptif,
    preparer_mesures_engagement,
    produire_evolution,
    produire_histogramme,
    repartir_modalites,
    resumer_engagement,
)
from traitement_csv import lire_csv


DOSSIER_AFC = Path(__file__).resolve().parents[1]


class TestsStatistiquesDescriptives(unittest.TestCase):
    """Valider les dénominateurs, formats et interactions entre filtres."""

    def setUp(self):
        self.donnees = pd.DataFrame({
            "publication_id": ["1", "1", "2", "3", ""],
            "retenue": ["True", "True", "False", "True", "True"],
            "type_media": ["A", "A", "B", "B", "B"],
            "vues": ["100", "100", "200", "0", ""],
            "likes": ["10", "10", "20", "0", "5"],
            "commentaires": ["1", "1", "2", "0", "1"],
            "partages": ["2", "2", "3", "0", "1"],
            "favoris": ["3", "3", "4", "0", "1"],
            "date_publication": [
                "2026-10-24", "2026-10-24", "2026-10-25",
                "2026-10-25", "2026-10-26",
            ],
        })

    def test_filtrage_retenue_et_dedoublonnage_sans_mutation(self):
        original = self.donnees.copy(deep=True)
        resultat = preparer_echantillon_descriptif(
            self.donnees, uniquement_retenues=True, dedoublonner=True,
        )
        self.assertEqual(resultat["publication_id"].tolist(), ["1", "3", ""])
        pd.testing.assert_frame_equal(self.donnees, original)

    def test_filtre_par_type_media_et_filtre_vide(self):
        resultat = preparer_echantillon_descriptif(
            self.donnees, variable_filtre="type_media", modalites_filtre=["A"],
            uniquement_retenues=False,
        )
        self.assertEqual(len(resultat), 2)
        with self.assertRaisesRegex(ValueError, "Aucune publication"):
            preparer_echantillon_descriptif(
                self.donnees, variable_filtre="type_media",
                modalites_filtre=["Inexistant"],
            )

    def test_conversion_nombres_et_absences(self):
        valeurs = pd.Series([
            "1 250", "2\u202f300", "1.234", "1,234", "",
            "indisponible", "-5", "1.234,5",
        ])
        nombres = convertir_nombres(valeurs)
        self.assertEqual(nombres.iloc[:4].tolist(), [1250, 2300, 1234, 1234])
        self.assertTrue(nombres.iloc[4:7].isna().all())
        self.assertAlmostEqual(nombres.iloc[7], 1234.5)
        pourcentages = convertir_nombres(pd.Series(["2,83 %", "1.234 %"]), True)
        self.assertAlmostEqual(pourcentages.iloc[0], 2.83)
        self.assertAlmostEqual(pourcentages.iloc[1], 1.234)

    def test_taux_engagement_sans_division_par_zero(self):
        mesures, origines = preparer_mesures_engagement(self.donnees)
        self.assertIn("Taux d'engagement (%)", origines)
        self.assertAlmostEqual(mesures.iloc[0]["Taux d'engagement (%)"], 16.0)
        self.assertTrue(np.isnan(mesures.iloc[3]["Taux d'engagement (%)"]))
        self.assertTrue(np.isnan(mesures.iloc[4]["Taux d'engagement (%)"]))

    def test_pas_de_taux_avec_interaction_absente(self):
        donnees = self.donnees.drop(columns=["favoris"])
        mesures, _ = preparer_mesures_engagement(donnees)
        self.assertNotIn("Taux d'engagement (%)", mesures)

    def test_taux_present_conserve_et_complete(self):
        donnees = self.donnees.copy()
        donnees["taux_engagement"] = ["7,5", "", "", "", ""]
        mesures, origines = preparer_mesures_engagement(donnees)
        self.assertEqual(mesures.iloc[0]["Taux d'engagement (%)"], 7.5)
        self.assertEqual(mesures.iloc[1]["Taux d'engagement (%)"], 16.0)
        self.assertIn("compléments", origines["Taux d'engagement (%)"])

    def test_bilan_denominataires_par_variable(self):
        mesures, _ = preparer_mesures_engagement(self.donnees)
        bilan = resumer_engagement(mesures, len(self.donnees)).set_index(
            "Indicateur"
        )
        self.assertEqual(bilan.loc["Vues", "N valide"], 4)
        self.assertEqual(bilan.loc["Vues", "N absent"], 1)
        self.assertEqual(bilan.loc["Vues", "Absents (%)"], 20.0)
        self.assertEqual(bilan.loc["Likes", "N valide"], 5)
        self.assertEqual(bilan.loc["Likes", "N absent"], 0)
        self.assertEqual(bilan.loc["Vues", "Zéros"], 1)

    def test_histogrammes_effectifs_et_constant(self):
        valeurs = pd.Series([0, 0, 10, 20, 100, np.nan])
        for logarithmique in (False, True):
            distribution = produire_histogramme(
                valeurs, nombre_classes=5, logarithmique=logarithmique
            )
            self.assertEqual(int(distribution["Publications"].sum()), 5)
            self.assertEqual(distribution["Classe"].nunique(), 5)
        un_seul = produire_histogramme(pd.Series([7, 7, 7]))
        self.assertEqual(len(un_seul), 1)
        self.assertEqual(un_seul["Publications"].iloc[0], 3)

    def test_categories_et_comparaison_par_groupe(self):
        mesures, _ = preparer_mesures_engagement(self.donnees)
        repartition = repartir_modalites(self.donnees, "type_media")
        self.assertEqual(int(repartition["Effectif"].sum()), 5)
        groupes = comparer_groupes(
            self.donnees, mesures, "type_media", "Likes",
            minimum_observations=2,
        )
        self.assertEqual(set(groupes["Groupe"]), {"A", "B"})
        self.assertEqual(int(groupes["Publications"].sum()), 5)

    def test_dates_iso_et_timestamp(self):
        dates = convertir_dates(pd.Series([
            "2026-10-24", "1792800000", "1792800000000", "",
        ]))
        self.assertFalse(pd.isna(dates.iloc[0]))
        self.assertEqual(dates.iloc[1], dates.iloc[2])
        self.assertTrue(pd.isna(dates.iloc[3]))
        mesures, _ = preparer_mesures_engagement(self.donnees)
        evolution = produire_evolution(
            self.donnees, mesures, "date_publication", "Likes"
        )
        self.assertEqual(evolution["Publications"].tolist(), [2, 2, 1])

    def test_import_scraptiktok_reel(self):
        contenu = (DOSSIER_AFC / "engagement_exemple.csv").read_bytes()
        donnees = lire_csv(contenu)
        mesures, _ = preparer_mesures_engagement(donnees)
        self.assertEqual(len(donnees), 3)
        for indicateur in (
            "Vues", "Likes", "Commentaires", "Partages",
            "Favoris", "Taux d'engagement (%)",
        ):
            self.assertIn(indicateur, mesures)
        self.assertAlmostEqual(
            mesures["Vues"].iloc[0], 27378,
        )

    def test_onglet_nouveau_sans_suppression_afc_acm(self):
        interface = (DOSSIER_AFC / "application.py").read_text(
            encoding="utf-8"
        )
        module = (
            DOSSIER_AFC / "interface_statistiques_descriptives.py"
        ).read_text(encoding="utf-8")
        self.assertIn('["Statistique descriptive", "AFC / ACM"]', interface)
        self.assertIn("construire_onglet_statistique_descriptive(donnees)", interface)
        self.assertIn('options=["AFC", "ACM"]', interface)
        self.assertIn("def construire_interface_afc(", interface)
        self.assertIn("def construire_interface_acm(", interface)
        self.assertIn("preparer_contingence(", interface)
        self.assertIn("preparer_acm(", interface)
        self.assertIn("FactoMineR::MCA()", interface)
        self.assertIn("st.bar_chart(", module)
        self.assertIn("st.scatter_chart(", module)
        self.assertIn("st.line_chart(", module)
        self.assertIn("st.download_button(", module)


if __name__ == "__main__":
    unittest.main()
