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
        self.assertIn("stats::chisq.test(", source)
        self.assertIn('type_modalite == "ligne"', source)
        self.assertIn('effectifs_autres <- colSums(tableau) - effectifs_modalite',
                      source)
        self.assertIn('effectifs_autres <- rowSums(tableau) - effectifs_modalite',
                      source)
        self.assertIn("significativite_modalites$p_value <= 0.05", source)
        self.assertIn('if (deux_axes) {', source)
        self.assertIn("abscisses_lignes[visibles_lignes]", source)
        self.assertIn("abscisses_colonnes[visibles_colonnes]", source)
        self.assertIn("resultat$row$coord", source)
        self.assertIn("resultat$col$coord", source)
        self.assertIn("18_significativite_modalites.csv", source)
        self.assertIn("18_significativite_modalites.csv", interface)
        self.assertIn("p ≤ 0,05", interface)
        self.assertIn('p.adjust(', source)

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
                 str(donnees), str(sorties), "999",
                 "Variable ligne", "Variable colonne", "Corpus test",
                 "300", "300"],
                capture_output=True, text=True, check=False, timeout=90,
            )
            self.assertEqual(
                processus.returncode, 0,
                processus.stderr or processus.stdout)
            with (sorties / "18_significativite_modalites.csv").open(
                    encoding="utf-8", newline="") as fichier:
                resultats = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(resultats), 7)
            ligne_neutre = next(
                ligne for ligne in resultats
                if ligne["type_modalite"] == "ligne"
                and ligne["modalite"] == "D"
            )
            self.assertGreater(
                float(ligne_neutre["p_value"].replace(",", ".")), 0.05)
            self.assertEqual(ligne_neutre["significative_005"], "FALSE")
            ligne_associee = next(
                ligne for ligne in resultats
                if ligne["type_modalite"] == "ligne"
                and ligne["modalite"] == "A"
            )
            self.assertLessEqual(
                float(ligne_associee["p_value"].replace(",", ".")), 0.05)
            self.assertEqual(ligne_associee["significative_005"], "TRUE")
            self.assertTrue((sorties / "13_plan_factoriel.png").is_file())
            self.assertTrue((sorties / "14_plan_factoriel.pdf").is_file())
            self.assertTrue((sorties / "07_coordonnees_lignes.csv").is_file())
            self.assertTrue((sorties / "08_coordonnees_colonnes.csv").is_file())


if __name__ == "__main__":
    unittest.main()
