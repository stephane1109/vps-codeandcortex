"""Tests de la reprise SQLite indépendante de la session Streamlit."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from sauvegarde_analyse import (
    FichierRestaure, charger_analyse, enregistrer_analyse,
    enregistrer_resultat, enregistrer_resultats_lot,
    lister_analyses, restaurer_resultats,
)


class TestSauvegardeAnalyse(unittest.TestCase):
    def setUp(self):
        """Isoler chaque test dans un répertoire temporaire."""
        self.repertoire = tempfile.TemporaryDirectory()
        self.environnement = patch.dict(
            os.environ, {"QWEN_DATA_DIR": self.repertoire.name}
        )
        self.environnement.start()
        self.fichiers = [
            FichierRestaure(
                "commentaires.csv",
                "id_video;texte\n123;Une critique politique\n124;Une violence dénoncée\n"
                .encode("utf-8"),
            )
        ]
        self.reglages = {
            "qwen_prompt_matrice": "Classifier la violence.",
            "qwen_modele_selectionne": "bertweetfr",
            "qwen_approche_specialisee": "nli",
            "qwen_themes_proposes": [
                {
                    "titre": "Dénonciation de la violence",
                    "definition": "Le texte critique un acte violent explicite.",
                }
            ],
        }

    def tearDown(self):
        """Libérer le répertoire et les variables temporaires."""
        self.environnement.stop()
        self.repertoire.cleanup()

    def preparer_analyse(self, cle="test"):
        """Créer une entrée de sauvegarde avec sources et paramètres."""
        enregistrer_analyse(
            cle=cle,
            parametres={"modele": "bertweetfr", "approche_specialisee": "nli"},
            widgets=self.reglages,
            fichiers=self.fichiers,
            nombre_textes=2,
        )

    def tableau_initial(self):
        """Construire une grille avec colonnes pandas nullable."""
        return pd.DataFrame({
            "numero_document": [1, 2],
            "texte": ["Une critique politique", "Une violence dénoncée"],
            "statut_codage": ["non_traite", "non_traite"],
            "theme_1": pd.Series([pd.NA, pd.NA], dtype="boolean"),
            "nli_implication_theme_1": pd.Series(
                [pd.NA, pd.NA], dtype="Float64"
            ),
            "source_texte": ["commentaire", "commentaire"],
        })

    def test_aucun_travail_avant_une_analyse(self):
        self.assertEqual(lister_analyses(), [])

    def test_restaurer_octets_et_widgets_originaux(self):
        self.preparer_analyse()
        sauvegardes = lister_analyses()
        self.assertEqual(len(sauvegardes), 1)
        self.assertEqual(sauvegardes[0]["nombre_textes"], 2)
        restaurer = charger_analyse("test")
        self.assertEqual(restaurer["fichiers"][0].name, "commentaires.csv")
        self.assertEqual(
            restaurer["fichiers"][0].getvalue(), self.fichiers[0].getvalue()
        )
        self.assertEqual(
            restaurer["widgets"]["qwen_themes_proposes"],
            self.reglages["qwen_themes_proposes"],
        )

    def test_ecriture_par_texte_et_reprise_des_resultats(self):
        self.preparer_analyse()
        tableau = self.tableau_initial()
        tableau.at[0, "statut_codage"] = "nli_zero_shot"
        tableau.at[0, "nli_implication_theme_1"] = 0.07
        tableau.at[0, "nli_neutralite_theme_1"] = 0.89
        tableau.at[0, "nli_relation_theme_1"] = "neutralite"
        enregistrer_resultat("test", 1, tableau.loc[0])
        restaure, nombre = restaurer_resultats(self.tableau_initial(), "test")
        self.assertEqual(nombre, 1)
        self.assertEqual(restaure.at[0, "statut_codage"], "nli_zero_shot")
        self.assertAlmostEqual(
            restaure.at[0, "nli_implication_theme_1"], 0.07
        )
        self.assertEqual(
            restaure.at[0, "nli_relation_theme_1"], "neutralite"
        )
        self.assertEqual(restaure.at[1, "statut_codage"], "non_traite")

    def test_erreurs_sauvegardees_egalement(self):
        self.preparer_analyse()
        tableau = self.tableau_initial()
        tableau.at[1, "statut_codage"] = "erreur_service"
        tableau.at[1, "erreur_codage"] = "HTTP 503"
        enregistrer_resultat("test", 2, tableau.loc[1])
        restaure, nombre = restaurer_resultats(self.tableau_initial(), "test")
        self.assertEqual(nombre, 1)
        self.assertEqual(restaure.at[1, "erreur_codage"], "HTTP 503")

    def test_analyses_distinctes_ne_se_melangent_pas(self):
        self.preparer_analyse("a")
        self.preparer_analyse("b")
        tableau = self.tableau_initial()
        tableau.at[0, "statut_codage"] = "similarite"
        enregistrer_resultat("a", 1, tableau.loc[0])
        _, nombre_b = restaurer_resultats(self.tableau_initial(), "b")
        self.assertEqual(nombre_b, 0)
        self.assertEqual(len(lister_analyses()), 2)

    def test_sauvegarder_un_csv_repris_en_une_transaction(self):
        self.preparer_analyse()
        tableau = self.tableau_initial()
        tableau.at[0, "statut_codage"] = "ok"
        tableau.at[0, "theme_1"] = False
        tableau.at[1, "statut_codage"] = "erreur_service"
        tableau.at[1, "erreur_codage"] = "Interruption Ollama"
        self.assertEqual(enregistrer_resultats_lot("test", tableau), 2)
        resultat, nombre = restaurer_resultats(self.tableau_initial(), "test")
        self.assertEqual(nombre, 2)
        self.assertFalse(bool(resultat.at[0, "theme_1"]))
        self.assertEqual(
            resultat.at[1, "erreur_codage"], "Interruption Ollama"
        )

    def test_aucune_colonne_source_interne_copiee_dans_un_resultat(self):
        self.preparer_analyse()
        tableau = self.tableau_initial()
        tableau["type_source"] = "texte_auteur"
        enregistrer_resultat("test", 1, tableau.loc[0])
        restauration, _ = restaurer_resultats(
            self.tableau_initial(), "test"
        )
        self.assertNotIn("type_source", restauration.columns)


if __name__ == "__main__":
    unittest.main()
