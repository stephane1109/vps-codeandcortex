"""Contrôler la sélection statistique des modalités sur le plan AFC."""
from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


DOSSIER_AFC = Path(__file__).resolve().parents[1]
MOTEUR_R = DOSSIER_AFC / "moteur_afc.R"


def environnement_r_disponible() -> bool:
    """Vérifier R et FactoMineR avant un essai de calcul complet."""
    executable = shutil.which("Rscript")
    if executable is None:
        return False
    try:
        resultat = subprocess.run(
            [executable, "-e",
             "quit(status=if(requireNamespace('FactoMineR', quietly=TRUE)) 0 else 1)"],
            capture_output=True, check=False, timeout=20,
        )
        return resultat.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class TestsSignificativiteModalites(unittest.TestCase):
    def test_selection_explicite_sur_plan_deux_axes(self):
        """Ne pas filtrer les données de l'AFC, seulement les points du plan."""
        source = MOTEUR_R.read_text(encoding="utf-8")
        interface = (DOSSIER_AFC / "application.py").read_text(
            encoding="utf-8")
        self.assertIn("FactoMineR::CA(", source)
        self.assertIn("FactoMineR::descfreq(", source)
        self.assertIn('type_modalite == "ligne"', source)
        self.assertIn("significativite_modalites$significative_005", source)
        self.assertIn("p_values <= 0.05", source)
        self.assertIn('if (deux_axes) {', source)
        self.assertIn("abscisses_lignes[visibles_lignes]", source)
        self.assertIn("abscisses_colonnes[visibles_colonnes]", source)
        self.assertIn("resultat$row$coord", source)
        self.assertIn("resultat$col$coord", source)
        self.assertIn("significativite_modalites_factominer.csv", source)
        self.assertIn("significativite_modalites_factominer.csv", interface)
        self.assertIn("p ≤ 0,05", interface)
        self.assertNotIn("p.adjust(", source)
        self.assertNotIn("p_ajustee_bh", source)
        self.assertNotIn("tester_modalite <- function(", source)
        self.assertNotIn("stats::chisq.test(", source)
        self.assertNotIn("simulate.p.value", source)
        self.assertNotIn("V de Cramér", source)
        self.assertNotIn("repetitions <-", source)
        self.assertIn("summary(resultat, nbelements = Inf", source)
        self.assertNotIn('"02_effectifs_attendus.csv"', source)
        self.assertNotIn('"03_residus_pearson.csv"', source)


    @unittest.skipUnless(
        environnement_r_disponible(),
        "Rscript avec FactoMineR n'est pas disponible dans cet environnement",
    )
    def test_calcul_reel_modalite_non_significative(self):
        """Un profil neutre reste dans les CSV, pas dans la sélection 2D."""
        with tempfile.TemporaryDirectory(prefix="afc_test_") as dossier:
            racine = Path(dossier)
            donnees = racine / "contingence.tsv"
            sorties = racine / "sorties"
            sorties.mkdir()
            with donnees.open("w", encoding="utf-8", newline="") as fichier:
                ecrivain = csv.writer(fichier, delimiter="\t")
                ecrivain.writerows([
                    ["modalite", "Colonne1", "Colonne2", "Colonne3"],
                    ["A", 70, 5, 5],
                    ["B", 5, 70, 5],
                    ["C", 5, 5, 70],
                    ["D", 20, 20, 20],
                ])
            processus = subprocess.run(
                [shutil.which("Rscript"), str(MOTEUR_R),
                 str(donnees), str(sorties),
                 "Variable ligne", "Variable colonne", "Corpus test",
                 "300", "300"],
                capture_output=True, text=True, check=False, timeout=90,
            )
            self.assertEqual(
                processus.returncode, 0,
                processus.stderr or processus.stdout)
            with (sorties / "significativite_modalites_factominer.csv").open(
                    encoding="utf-8", newline="") as fichier:
                resultats = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(resultats), 7)
            ligne_neutre = next(
                ligne for ligne in resultats
                if ligne["type_modalite"] == "ligne"
                and ligne["modalite"] == "D"
            )
            self.assertEqual(ligne_neutre["p_value_min"], "")
            self.assertEqual(ligne_neutre["significative_005"], "FALSE")
            ligne_associee = next(
                ligne for ligne in resultats
                if ligne["type_modalite"] == "ligne"
                and ligne["modalite"] == "A"
            )
            self.assertLessEqual(
                float(ligne_associee["p_value_min"].replace(",", ".")), 0.05)
            self.assertEqual(ligne_associee["significative_005"], "TRUE")
            self.assertEqual(
                ligne_associee["methode"],
                "FactoMineR::descfreq (test hypergéométrique)")
            self.assertTrue((sorties / "13_plan_factoriel.png").is_file())
            self.assertTrue((sorties / "14_plan_factoriel.pdf").is_file())
            self.assertTrue((sorties / "07_coordonnees_lignes.csv").is_file())
            self.assertTrue((sorties / "08_coordonnees_colonnes.csv").is_file())


    def test_rapport_factoriel_avec_un_seul_axe(self):
        """Le rapport ne doit pas appeler summary.CA pour un axe unique."""
        source = MOTEUR_R.read_text(encoding="utf-8")
        self.assertIn("if (nombre_axes >= 2L) {", source)
        self.assertIn("resume_factominer <- produire_resume_factominer(", source)
        self.assertIn("capture.output(print(resultat$eig))", source)
        self.assertIn("capture.output(print(resultat$row$coord))", source)
        self.assertIn("capture.output(print(resultat$col$coord))", source)

    @unittest.skipUnless(
        environnement_r_disponible(),
        "Rscript avec FactoMineR n'est pas disponible dans cet environnement",
    )
    def test_calcul_reel_un_axe_apres_suppression_ligne_ou_colonne(self):
        """Une AFC 2 x 3 ou 3 x 2 doit produire le rapport et les exports."""
        tableaux = {
            "deux_lignes": [
                ["modalite", "X", "Y", "Z"],
                ["A", 40, 10, 15],
                ["B", 10, 35, 20],
            ],
            "deux_colonnes": [
                ["modalite", "X", "Y"],
                ["A", 40, 10],
                ["B", 10, 35],
                ["C", 15, 20],
            ],
        }
        for nom, lignes in tableaux.items():
            with self.subTest(tableau=nom):
                with tempfile.TemporaryDirectory(
                        prefix="afc_un_axe_") as dossier:
                    racine = Path(dossier)
                    entree = racine / "contingence.tsv"
                    sortie = racine / "sorties"
                    sortie.mkdir()
                    with entree.open("w", encoding="utf-8",
                                     newline="") as fichier:
                        csv.writer(fichier, delimiter="\t").writerows(lignes)
                    processus = subprocess.run(
                        [shutil.which("Rscript"), str(MOTEUR_R),
                         str(entree), str(sortie), "Lignes", "Colonnes",
                         "Tableau réduit", "130", "130"],
                        capture_output=True, text=True,
                        check=False, timeout=90,
                    )
                    self.assertEqual(
                        processus.returncode, 0,
                        processus.stderr or processus.stdout)
                    for fichier in (
                        "00_rapport_afc.txt",
                        "06_valeurs_propres_inerties.csv",
                        "07_coordonnees_lignes.csv",
                        "08_coordonnees_colonnes.csv",
                        "13_plan_factoriel.png",
                        "14_plan_factoriel.pdf",
                        "15_inerties.png",
                        "16_resultats_statistiques.csv",
                        "significativite_modalites_factominer.csv",
                    ):
                        self.assertTrue(
                            (sortie / fichier).is_file(),
                            f"{fichier} absent pour {nom}",
                        )
                    rapport = (sortie / "00_rapport_afc.txt").read_text(
                        encoding="utf-8")
                    self.assertIn("Un seul axe factoriel", rapport)
                    self.assertIn("Modalités en lignes : coordonnées", rapport)
                    self.assertIn("Modalités en colonnes : coordonnées", rapport)


if __name__ == "__main__":
    unittest.main()
