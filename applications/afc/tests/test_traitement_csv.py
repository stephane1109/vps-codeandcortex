"""Tests des lectures et des filtres du tableau de contingence."""

import unittest
from pathlib import Path

import pandas as pd

from traitement_csv import (
    concatener_fichiers_csv, lire_csv, preparer_contingence,
    preparer_tableau_inerties,
)


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
        self.assertEqual(resultat.effectif_initial, 3)

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

    def test_preparation_sans_statistique_supplementaire(self):
        """Les filtres Python préparent le corpus, FactoMineR réalise l'AFC."""
        source = (BASE / "traitement_csv.py").read_text(encoding="utf-8")
        interface = (BASE / "application.py").read_text(encoding="utf-8")
        self.assertNotIn("np.outer(", source)
        self.assertNotIn("chi2 =", source)
        self.assertNotIn("effectifs_attendus:", source)
        self.assertNotIn("cellules_attendues_faibles:", source)
        self.assertNotIn("Répétitions Monte-Carlo", interface)
        self.assertNotIn("repetitions_monte_carlo", interface)
        self.assertNotIn("cellules_attendues_faibles", interface)
        self.assertIn("FactoMineR::CA()", interface)
        self.assertIn("FactoMineR::descfreq", interface)

    def test_inertie_des_axes_et_inertie_cumulee(self):
        """Afficher les pourcentages exacts fournis par FactoMineR::CA."""
        export_factominer = (
            "modalite;eigenvalue;percentage of variance;"
            "cumulative percentage of variance\n"
            "dim 1;0,25;62,5;62,5\n"
            "dim 2;0,15;37,5;100\n"
        ).encode("utf-8")
        tableau = preparer_tableau_inerties(export_factominer)
        self.assertEqual(
            list(tableau.columns),
            ["Axe", "Valeur propre", "Inertie (%)", "Inertie cumulée (%)"]
        )
        self.assertEqual(tableau["Axe"].tolist(), ["Axe 1", "Axe 2"])
        self.assertEqual(tableau["Inertie (%)"].tolist(), [62.5, 37.5])
        self.assertEqual(
            tableau["Inertie cumulée (%)"].tolist(), [62.5, 100.0])
        self.assertEqual(tableau["Valeur propre"].tolist(), [0.25, 0.15])

    def test_inertie_factominer_a_un_seul_axe(self):
        """Un tableau à un axe est également lisible."""
        export_factominer = (
            "modalite;eigenvalue;percentage of variance;"
            "cumulative percentage of variance\n"
            "dim 1;0,18;100;100\n"
        ).encode("utf-8")
        tableau = preparer_tableau_inerties(export_factominer)
        self.assertEqual(len(tableau), 1)
        self.assertEqual(tableau.loc[0, "Inertie (%)"], 100)

    def test_tableau_inerties_invalide(self):
        """Ne pas afficher des pourcentages absents ou non numériques."""
        with self.assertRaisesRegex(ValueError, "vide"):
            preparer_tableau_inerties(b"")
        with self.assertRaisesRegex(ValueError, "incomplet"):
            preparer_tableau_inerties(b"axe;inertie\n1;25\n")

    def test_graphique_et_tableau_inerties_dans_le_meme_onglet(self):
        """Le tableau complète l'histogramme, sans le remplacer."""
        interface = (BASE / "application.py").read_text(encoding="utf-8")
        fragment = interface.split("with onglet_inertie:", 1)[1].split(
            "with onglet_matrices:", 1)[0]
        self.assertIn('st.image(fichiers["15_inerties.png"]', fragment)
        self.assertIn('preparer_tableau_inerties(', fragment)
        self.assertIn('st.dataframe(', fragment)
        self.assertIn("Inertie cumulée (%)", fragment)
        self.assertIn("Télécharger le tableau des inerties (CSV)", fragment)

    def test_interface_sans_donnees_fictives(self):
        """L'interface doit exiger un CSV et ignorer les modes de démonstration."""
        interface = (BASE / "application.py").read_text(encoding="utf-8")
        traitement = (BASE / "traitement_csv.py").read_text(encoding="utf-8")
        self.assertIn('if not fichiers:', interface)
        self.assertIn("accept_multiple_files=True", interface)
        self.assertIn('tableau_source = importer_donnees(', interface)
        self.assertIn('donnees = concatener_fichiers_csv(tableaux_sources)', interface)
        self.assertNotIn("Utiliser l'échantillon de démonstration", interface)
        self.assertNotIn("Utiliser des données simulées (test uniquement)", interface)
        self.assertNotIn("generer_donnees_simulees", traitement)
        self.assertIn('preparer_contingence(', interface)
        self.assertIn('afficher_resultats(', interface)

    def test_fusion_csv_en_conservant_les_lignes_et_identifiants(self):
        """Les effectifs sont additionnés sans supprimer les doublons."""
        premier = lire_csv(
            b"publication_id;groupe;classe\n001;A;X\n002;B;Y\n"
        )
        second = lire_csv(
            b"publication_id;groupe;classe\n001;B;Y\n003;A;X\n"
        )
        copie_premier = premier.copy(deep=True)
        fusion = concatener_fichiers_csv([
            ("premier.csv", premier), ("second.csv", second)
        ])
        self.assertEqual(len(fusion), 4)
        self.assertEqual(
            fusion["publication_id"].tolist(), ["001", "002", "001", "003"]
        )
        self.assertEqual(fusion["groupe"].tolist(), ["A", "B", "B", "A"])
        self.assertEqual(list(fusion.columns), list(premier.columns))
        pd.testing.assert_frame_equal(premier, copie_premier)
        resultat_afc = preparer_contingence(
            fusion, "groupe", "classe", dedoublonner=False
        )
        self.assertEqual(resultat_afc.effectif_initial, 4)
        self.assertEqual(resultat_afc.effectif_final, 4)

    def test_fusion_alignement_par_nom_si_ordre_change(self):
        """Réordonner les colonnes sans décaler les réponses."""
        premier = lire_csv(b"identifiant;groupe;classe\n001;A;X\n")
        second = lire_csv(b"classe;identifiant;groupe\nY;002;B\n")
        fusion = concatener_fichiers_csv([
            ("a.csv", premier), ("b.csv", second)
        ])
        self.assertEqual(
            list(fusion.columns), ["identifiant", "groupe", "classe"]
        )
        self.assertEqual(fusion.iloc[1].to_dict(), {
            "identifiant": "002", "groupe": "B", "classe": "Y"
        })

    def test_fusion_refuse_structures_incompatibles(self):
        """Un fichier à colonnes différentes arrête la fusion."""
        premier = lire_csv(b"identifiant;groupe;classe\n001;A;X\n")
        second = lire_csv(b"identifiant;groupe;autre\n002;B;Y\n")
        with self.assertRaisesRegex(
            ValueError,
            r"b.csv.*colonnes manquantes : classe.*"
            r"colonnes supplémentaires : autre",
        ):
            concatener_fichiers_csv([
                ("a.csv", premier), ("b.csv", second)
            ])
        with self.assertRaisesRegex(ValueError, "Aucun fichier"):
            concatener_fichiers_csv([])

    def test_importation_unique_et_fusion_reimportable(self):
        """Un seul CSV conserve sa structure ; le corpus fusionné se relit."""
        premier = lire_csv(b"identifiant;groupe;classe\n001;A;X\n")
        copie = concatener_fichiers_csv([("a.csv", premier)])
        pd.testing.assert_frame_equal(premier, copie)
        second = lire_csv(b"identifiant;groupe;classe\n002;B;Y\n")
        fusion = concatener_fichiers_csv([
            ("a.csv", premier), ("b.csv", second)
        ])
        export = fusion.to_csv(
            index=False, sep=";", lineterminator="\n"
        ).encode("utf-8-sig")
        resultat = lire_csv(export)
        pd.testing.assert_frame_equal(fusion, resultat)

    def test_interface_import_multiple_sans_perte_des_analyses(self):
        """Vérifier les menus, la fusion et l'ensemble des sorties existantes."""
        interface = (BASE / "application.py").read_text(encoding="utf-8")
        self.assertIn('accept_multiple_files=True', interface)
        self.assertIn('concatener_fichiers_csv(tableaux_sources)', interface)
        self.assertIn('Télécharger le corpus fusionné (CSV)', interface)
        self.assertIn('construire_onglet_statistique_descriptive(donnees)', interface)
        self.assertIn('options=["AFC", "ACM"]', interface)
        self.assertIn('construire_interface_afc(', interface)
        self.assertIn('construire_interface_acm(', interface)
        self.assertIn('empreinte_import.digest()', interface)
        self.assertIn('mesures[3].metric("Fichiers réunis"', interface)

    def test_variable_identique(self):
        donnees = pd.DataFrame({"a": ["X", "Y"]})
        with self.assertRaisesRegex(ValueError, "distinctes"):
            preparer_contingence(donnees, "a", "a")


if __name__ == "__main__":
    unittest.main()
