"""Vérifier le mode ACM de l'application et les sorties FactoMineR."""
from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from traitement_csv import preparer_acm


DOSSIER_AFC = Path(__file__).resolve().parents[1]
MOTEUR_ACM = DOSSIER_AFC / "moteur_acm.R"


def factominer_disponible() -> bool:
    """Détecter Rscript et FactoMineR pour les tests d'intégration ACM."""
    executable = shutil.which("Rscript")
    if not executable:
        return False
    try:
        processus = subprocess.run(
            [executable, "-e",
             "quit(status=if(requireNamespace('FactoMineR', quietly=TRUE)) 0 else 1)"],
            capture_output=True, timeout=20, check=False,
        )
        return processus.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class TestsACM(unittest.TestCase):
    def setUp(self):
        self.donnees = pd.DataFrame({
            "publication_id": ["1", "2", "3", "4", "5", "6", "7", "8"],
            "retenue": ["True"] * 8,
            "vues_classe": ["faibles", "fortes"] * 4,
            "likes_classe": ["0-9", "10-99", "0-9", "10-99"] * 2,
            "type_media": ["presse", "autre", "presse", "autre"] * 2,
            "region_code": ["FR"] * 8,
        })

    def test_acm_trois_variables(self):
        preparation = preparer_acm(
            self.donnees,
            ["vues_classe", "likes_classe", "type_media"],
        )
        self.assertEqual(preparation.donnees.shape, (8, 3))
        self.assertEqual(preparation.effectif_initial, 8)
        self.assertEqual(preparation.effectif_final, 8)
        self.assertEqual(preparation.donnees["type_media"].nunique(), 2)

    def test_rejeter_moins_de_trois_variables_et_doublons(self):
        for noms in [
            ["vues_classe", "likes_classe"],
            ["vues_classe", "vues_classe", "likes_classe"],
        ]:
            with self.subTest(noms=noms):
                with self.assertRaisesRegex(ValueError, "trois variables"):
                    preparer_acm(self.donnees, noms)

    def test_modalite_constante_et_inconnue(self):
        with self.assertRaisesRegex(ValueError, "au moins deux modalités"):
            preparer_acm(
                self.donnees,
                ["vues_classe", "likes_classe", "region_code"],
            )
        with self.assertRaisesRegex(ValueError, "absentes"):
            preparer_acm(
                self.donnees,
                ["vues_classe", "likes_classe", "variable_inexistante"],
            )

    def test_exclusion_rend_variable_constante(self):
        with self.assertRaisesRegex(ValueError, "au moins deux modalités"):
            preparer_acm(
                self.donnees,
                ["vues_classe", "likes_classe", "type_media"],
                modalites_a_exclure={"vues_classe": ["faibles"]},
            )

    def test_exclusion_et_restaurer_original(self):
        donnees = self.donnees.copy()
        donnees.loc[len(donnees)] = [
            "9", "True", "intermédiaires", "0-9", "presse", "FR"
        ]
        variables = ["vues_classe", "likes_classe", "type_media"]
        preparee = preparer_acm(
            donnees, variables,
            modalites_a_exclure={"vues_classe": ["intermédiaires"]},
        )
        initiale = preparer_acm(donnees, variables)
        self.assertEqual(preparee.effectif_final, 8)
        self.assertEqual(preparee.effectif_avant_exclusion_modalites, 9)
        self.assertEqual(initiale.effectif_final, 9)
        self.assertEqual(len(donnees), 9)

    def test_filtres_et_dedoublonnage_acm(self):
        donnees = self.donnees.copy()
        donnees.loc[len(donnees)] = [
            "1", "True", "faibles", "0-9", "presse", "FR"
        ]
        preparation = preparer_acm(
            donnees,
            ["vues_classe", "likes_classe", "type_media"],
            dedoublonner=True,
        )
        self.assertEqual(preparation.effectif_initial, 9)
        self.assertEqual(preparation.effectif_final, 8)

    def test_interfaces_distinctes_et_plan_complet_prioritaire(self):
        interface = (DOSSIER_AFC / "application.py").read_text(
            encoding="utf-8"
        )
        moteur_afc = (DOSSIER_AFC / "moteur_afc.R").read_text(
            encoding="utf-8"
        )
        moteur_acm = MOTEUR_ACM.read_text(encoding="utf-8")
        self.assertIn('options=["AFC", "ACM"]', interface)
        self.assertIn("def construire_interface_acm(", interface)
        self.assertIn('value=False,\n            key=f"filtrer_modalites_', interface)
        self.assertIn('"13_plan_factoriel_significatif.png"', interface)
        self.assertIn("FactoMineR::CA(", moteur_afc)
        self.assertIn("FactoMineR::MCA(", moteur_acm)
        self.assertIn("FactoMineR::descfreq(", moteur_afc)
        self.assertIn("FactoMineR::dimdesc(", moteur_acm)
        self.assertIn('method = methode_calcul', moteur_acm)
        self.assertIn('"Tableau disjonctif complet (TDC)"', interface)
        self.assertIn('"Tableau de Burt"', interface)
        self.assertIn('methode_calcul=methode_calcul', interface)
        self.assertIn('methode_calcul,', interface)
        self.assertIn('"18_comparaison_inerties_tdc_burt.csv"', moteur_acm)
        self.assertIn('"tdc.csv"', moteur_acm)
        self.assertIn('"burt.csv"', moteur_acm)
        self.assertIn('dessiner_plan(FALSE)', moteur_afc)
        self.assertIn('dessiner_plan(TRUE)', moteur_afc)
        self.assertIn('dessiner_plan(FALSE)', moteur_acm)
        self.assertIn('dessiner_plan(TRUE)', moteur_acm)
        self.assertNotIn("stats::chisq.test(", moteur_acm)
        self.assertNotIn("simulate.p.value", moteur_acm)

    @unittest.skipUnless(
        factominer_disponible(),
        "Rscript avec FactoMineR non disponible dans cet environnement",
    )
    def test_integration_mca_trois_variables(self):
        """Valider réellement MCA, dimdesc et les deux variantes du plan."""
        with tempfile.TemporaryDirectory(prefix="acm_test_") as dossier:
            racine = Path(dossier)
            entree = racine / "categoriels.tsv"
            sorties = racine / "resultats"
            sorties.mkdir()
            with entree.open("w", encoding="utf-8", newline="") as fichier:
                ecrivain = csv.writer(fichier, delimiter="\t")
                ecrivain.writerow(["vues_classe", "likes_classe", "type_media"])
                for i in range(120):
                    profil = i % 3
                    # Quelques décalages évitent une structure parfaitement
                    # déterministe tout en conservant des associations.
                    profil_likes = (profil + (i % 11 == 0)) % 3
                    profil_media = (profil + (i % 7 == 0)) % 3
                    ecrivain.writerow([
                        ["faibles", "moyennes", "fortes"][profil],
                        ["0-9", "10-99", "100-999"][profil_likes],
                        ["presse", "autres", "local"][profil_media],
                    ])
            processus = subprocess.run(
                [shutil.which("Rscript"), str(MOTEUR_ACM),
                 str(entree), str(sorties), "Corpus test", "120", "120"],
                capture_output=True, text=True, check=False, timeout=90,
            )
            self.assertEqual(
                processus.returncode, 0,
                processus.stderr or processus.stdout,
            )
            for nom in [
                "00_rapport_acm.txt",
                "06_valeurs_propres_inerties.csv",
                "07_coordonnees_modalites.csv",
                "08_contributions_modalites.csv",
                "09_cos2_modalites.csv",
                "13_plan_factoriel.png",
                "13_plan_factoriel_significatif.png",
                "14_plan_factoriel.pdf",
                "14_plan_factoriel_significatif.pdf",
                "15_inerties.png",
                "significativite_modalites_factominer.csv",
            ]:
                self.assertTrue((sorties / nom).is_file(), f"Fichier absent : {nom}")
            rapport = (sorties / "00_rapport_acm.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("FactoMineR::dimdesc", rapport)
            with (
                sorties / "significativite_modalites_factominer.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                modalites = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(modalites), 9)
            self.assertTrue(
                any(m["significative_005"] == "TRUE" for m in modalites),
                "Le filtre ACM doit reconnaître les modalités associées "
                "aux axes avec FactoMineR::dimdesc.",
            )
            with (
                sorties / "06_valeurs_propres_inerties.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                inerties_tdc = list(csv.DictReader(fichier, delimiter=";"))
            with (
                sorties / "18_comparaison_inerties_tdc_burt.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                comparaison = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(comparaison), len(inerties_tdc))
            self.assertTrue((sorties / "tdc.csv").is_file())
            self.assertTrue((sorties / "burt.csv").is_file())

            # Calculer également l'ACM Burt avec les mêmes observations.
            sorties_burt = racine / "resultats_burt"
            sorties_burt.mkdir()
            processus_burt = subprocess.run(
                [shutil.which("Rscript"), str(MOTEUR_ACM),
                 str(entree), str(sorties_burt), "Corpus test",
                 "120", "120", "Burt"],
                capture_output=True, text=True, check=False, timeout=90,
            )
            self.assertEqual(
                processus_burt.returncode, 0,
                processus_burt.stderr or processus_burt.stdout,
            )
            for nom in [
                "06_valeurs_propres_inerties.csv",
                "07_coordonnees_modalites.csv",
                "13_plan_factoriel.png",
                "13_plan_factoriel_significatif.png",
                "18_comparaison_inerties_tdc_burt.csv",
                "significativite_modalites_factominer.csv",
            ]:
                self.assertTrue(
                    (sorties_burt / nom).is_file(),
                    f"Export Burt absent : {nom}",
                )
            with (
                sorties_burt / "06_valeurs_propres_inerties.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                inerties_burt = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(inerties_tdc), len(inerties_burt))
            for tdc, burt in zip(inerties_tdc, inerties_burt):
                valeur_tdc = float(tdc["eigenvalue"].replace(",", "."))
                valeur_burt = float(burt["eigenvalue"].replace(",", "."))
                self.assertAlmostEqual(
                    valeur_burt, valeur_tdc**2, places=5,
                    msg="Les valeurs propres Burt doivent être les carrés "
                        "des valeurs propres du TDC.",
                )


if __name__ == "__main__":
    unittest.main()
