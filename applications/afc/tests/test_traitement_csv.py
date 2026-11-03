"""Tests des lectures et des filtres du tableau de contingence."""

import unittest
from pathlib import Path

import pandas as pd

from traitement_csv import lire_csv, preparer_contingence


BASE = Path(__file__).resolve().parent.parent


class TestTraitementCSV(unittest.TestCase):
    """Vérifie les cas usuels de données ScrapTikTok."""

    def test_import_reel(self):
        contenu = (BASE / "engagement_exemple.csv").read_bytes()
        donnees = lire_csv(contenu)
        self.assertEqual(len(donnees), 3)
        self.assertIn("classe_taux_engagement", donnees.columns)
        self.assertEqual(donnees["publication_id"].iloc[0], "7700232234451733792")
        self.assertIn("type_media", donnees.columns)

    def test_afc_sur_echantillon(self):
        donnees = lire_csv((BASE / "engagement_exemple.csv").read_bytes())
        resultat = preparer_contingence(
            donnees, "vues_classe", "classe_taux_engagement"
        )
        self.assertEqual(resultat.tableau.shape, (2, 2))
        self.assertEqual(resultat.effectif_final, 3)
        self.assertEqual(resultat.tableau.to_numpy().sum(), 3)
        self.assertGreater(resultat.cellules_attendues_faibles, 0)

    def test_import_virgules(self):
        donnees = lire_csv(b"groupe,classe\na,x\nb,y\n")
        resultat = preparer_contingence(donnees, "groupe", "classe")
        self.assertEqual(resultat.tableau.shape, (2, 2))

    def test_doublons_et_retenue(self):
        donnees = pd.DataFrame({
            "publication_id": ["a", "a", "b", "c", ""],
            "retenue": ["True", "True", "False", "True", "True"],
            "a": ["X", "X", "Y", "Y", "X"],
            "b": ["I", "I", "I", "J", "J"],
        })
        resultat = preparer_contingence(donnees, "a", "b", dedoublonner=True)
        self.assertEqual(resultat.effectif_initial, 5)
        self.assertEqual(resultat.effectif_apres_filtre, 4)
        self.assertEqual(resultat.effectif_final, 3)

    def test_manquantes(self):
        donnees = pd.DataFrame({"a": ["X", "Y", "X", ""], "b": ["I", "J", "J", "I"]})
        sans = preparer_contingence(donnees, "a", "b")
        avec = preparer_contingence(donnees, "a", "b", inclure_manquantes=True)
        self.assertEqual(sans.effectif_final, 3)
        self.assertEqual(avec.effectif_final, 4)

    def test_modalites_indeterminees(self):
        donnees = pd.DataFrame({"a": ["X", "Y", "X", "abonnes_indetermine"], "b": ["I", "J", "J", "I"]})
        resultat = preparer_contingence(donnees, "a", "b")
        self.assertEqual(resultat.effectif_final, 3)

    def test_filtrage_facultatif(self):
        donnees = pd.DataFrame({
            "a": ["X", "Y", "X", "Y"],
            "b": ["I", "J", "J", "I"],
            "media": ["A", "A", "A", "B"],
        })
        resultat = preparer_contingence(
            donnees, "a", "b", variable_filtre="media", modalites_filtre=["A"]
        )
        self.assertEqual(resultat.effectif_final, 3)

    def test_cardinalite(self):
        donnees = pd.DataFrame({"a": [str(x) for x in range(100)], "b": ["I", "J"] * 50})
        with self.assertRaisesRegex(ValueError, "Trop de modalités"):
            preparer_contingence(donnees, "a", "b")

    def test_interface_sans_donnees_fictives(self):
        """L'interface doit exiger un CSV et ignorer les modes de démonstration."""
        interface = (BASE / "application.py").read_text(encoding="utf-8")
        traitement = (BASE / "traitement_csv.py").read_text(encoding="utf-8")
        self.assertIn('if fichier is None:', interface)
        self.assertIn('donnees = importer_donnees(contenu, separateur, encodage)', interface)
        self.assertNotIn("Utiliser l'échantillon de démonstration", interface)
        self.assertNotIn("Utiliser des données simulées (test uniquement)", interface)
        self.assertNotIn("generer_donnees_simulees", traitement)
        self.assertIn('preparer_contingence(', interface)
        self.assertIn('afficher_resultats(', interface)

    def test_variable_identique(self):
        donnees = pd.DataFrame({"a": ["X", "Y"]})
        with self.assertRaisesRegex(ValueError, "distinctes"):
            preparer_contingence(donnees, "a", "a")


if __name__ == "__main__":
    unittest.main()
