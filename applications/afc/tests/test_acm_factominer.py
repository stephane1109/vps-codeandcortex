"""Vérifier le mode ACM de l'application et les sorties FactoMineR."""
from __future__ import annotations

import csv
import math
import os
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
        self.assertIn("matrice_vtest <- as.matrix(resultat$var$v.test)", moteur_acm)
        self.assertIn("stats::pnorm(-abs(valeurs_vtest))", moteur_acm)
        self.assertIn('"20_diagnostic_filtre_pvalue.csv"', moteur_acm)
        self.assertIn('"20_diagnostic_filtre_pvalue.csv"', interface)
        self.assertIn("Contrôler les p-values de toutes les modalités", interface)
        self.assertNotIn(
            "match(rownames(caracteristiques), noms_modalites)", moteur_acm
        )
        self.assertIn('method = methode_calcul', moteur_acm)
        self.assertIn('"Tableau disjonctif complet (TDC)"', interface)
        self.assertIn('"Tableau de Burt"', interface)
        self.assertIn('methode_calcul=methode_calcul', interface)
        self.assertIn('methode_calcul,', interface)
        self.assertIn('"18_comparaison_inerties_tdc_burt.csv"', moteur_acm)
        self.assertIn('"tdc.csv"', moteur_acm)
        self.assertIn('"burt.csv"', moteur_acm)
        self.assertIn('"19_couleurs_variables.csv"', moteur_acm)
        self.assertIn('"19_couleurs_variables.csv"', interface)
        self.assertIn("variables_modalites <- rep(", moteur_acm)
        self.assertIn("resultat$call$X", moteur_acm)
        self.assertIn("palette = \"Dark 3\"", moteur_acm)
        self.assertIn("col = couleurs_modalites[visibles]", moteur_acm)
        self.assertIn('title = "Variables actives"', moteur_acm)
        self.assertIn("colonnes_numeriques <- vapply(", moteur_acm)
        self.assertIn("print(comparaison_formatee, row.names = FALSE)", moteur_acm)
        self.assertNotIn("round(comparaison_inerties, 4)", moteur_acm)
        self.assertIn('dessiner_plan(FALSE)', moteur_afc)
        self.assertIn('dessiner_plan(TRUE)', moteur_afc)
        self.assertIn('dessiner_plan(FALSE)', moteur_acm)
        self.assertIn('dessiner_plan(TRUE)', moteur_acm)
        self.assertNotIn("stats::chisq.test(", moteur_acm)
        self.assertNotIn("simulate.p.value", moteur_acm)
        self.assertIn("libelles_graphiques(", moteur_acm)
        self.assertIn("titre_graphique", moteur_acm)
        self.assertNotIn('main = paste("ACM —"', moteur_acm)
        self.assertIn("def diagnostiquer_echec_r(", interface)

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
                "19_couleurs_variables.csv",
                "20_diagnostic_filtre_pvalue.csv",
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
                "aux axes avec les valeurs-tests FactoMineR.",
            )
            for ligne in modalites:
                self.assertNotEqual(
                    ligne["p_value_min"], "",
                    "Chaque modalité doit avoir une p-value calculée.",
                )
                p_1 = float(ligne["p_value_axe_1"].replace(",", "."))
                v_1 = float(ligne["v_test_axe_1"].replace(",", "."))
                attendu = math.erfc(abs(v_1) / math.sqrt(2))
                self.assertAlmostEqual(p_1, attendu, places=8)
                self.assertEqual(
                    ligne["significative_005"] == "TRUE",
                    float(ligne["p_value_min"].replace(",", ".")) <= 0.05,
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
            with (sorties / "19_couleurs_variables.csv").open(
                encoding="utf-8", newline=""
            ) as fichier:
                couleurs_tdc = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(
                [ligne["variable"] for ligne in couleurs_tdc],
                ["vues_classe", "likes_classe", "type_media"],
            )
            self.assertEqual(
                len({ligne["couleur_hex"] for ligne in couleurs_tdc}), 3
            )
            self.assertEqual(
                [int(ligne["nombre_modalites"]) for ligne in couleurs_tdc],
                [3, 3, 3],
            )

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
                "19_couleurs_variables.csv",
                "20_diagnostic_filtre_pvalue.csv",
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
            rapport_burt = (sorties_burt / "00_rapport_acm.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("COMPARAISON DES INERTIES", rapport_burt)
            self.assertIn("dim 1", rapport_burt)
            self.assertIn("VALEURS-TESTS DE FactoMineR::MCA", rapport_burt)
            with (
                sorties_burt / "significativite_modalites_factominer.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                modalites_burt = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(modalites_burt), 9)
            self.assertTrue(all(
                ligne["p_value_min"] for ligne in modalites_burt
            ))
            with (sorties_burt / "19_couleurs_variables.csv").open(
                encoding="utf-8", newline=""
            ) as fichier:
                couleurs_burt = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(
                couleurs_tdc, couleurs_burt,
                "Les méthodes TDC et Burt doivent garder les mêmes couleurs.",
            )
            for tdc, burt in zip(inerties_tdc, inerties_burt):
                valeur_tdc = float(tdc["eigenvalue"].replace(",", "."))
                valeur_burt = float(burt["eigenvalue"].replace(",", "."))
                self.assertAlmostEqual(
                    valeur_burt, valeur_tdc**2, places=5,
                    msg="Les valeurs propres Burt doivent être les carrés "
                        "des valeurs propres du TDC.",
                )


    @unittest.skipUnless(
        factominer_disponible(),
        "Rscript avec FactoMineR non disponible dans cet environnement",
    )
    def test_burt_onze_variables_avec_accents_en_locale_c(self):
        """Vérifier le cas des titres longs et accents sous la locale C."""
        variables = [
            "vues_classe", "classe_taux_engagement", "presse_nationale",
            "presse_regio_dpt", "presse_indep", "presse_autre",
            "likes_classe", "commentaires_classe", "partages_classe",
            "favoris_classe", "duree_classe",
        ]
        with tempfile.TemporaryDirectory(prefix="acm_locale_") as repertoire:
            dossier = Path(repertoire)
            entree = dossier / "observations.tsv"
            sortie = dossier / "resultats"
            sortie.mkdir()
            with entree.open("w", encoding="utf-8", newline="") as fichier:
                ecrivain = csv.writer(fichier, delimiter="\t")
                ecrivain.writerow(variables)
                for i in range(180):
                    ecrivain.writerow([
                        ("faible", "modérée", "forte")[i % 3],
                        ("engagement faible", "engagement élevé")[(i // 2) % 2],
                        str((i // 3) % 2),
                        str((i // 4) % 2),
                        str((i // 5) % 2),
                        str((i // 7) % 2),
                        ("0-9", "10-99", "100-999")[(i // 3) % 3],
                        ("aucun", "présent")[(i // 5) % 2],
                        ("0", "1-9")[(i // 7) % 2],
                        ("0", "1-9")[(i // 11) % 2],
                        ("courte", "longue")[(i // 13) % 2],
                    ])
            environnement = os.environ.copy()
            environnement["LC_ALL"] = "C"
            environnement["LANG"] = "C"
            commande = [
                shutil.which("Rscript"), str(MOTEUR_ACM),
                str(entree), str(sortie), "Échantillon test",
                "180", "180", "Burt",
            ]
            execution = subprocess.run(
                commande,
                capture_output=True, text=True,
                errors="replace", timeout=120, check=False,
                env=environnement,
            )
            self.assertEqual(
                execution.returncode, 0,
                execution.stderr + "\n" + execution.stdout,
            )
            self.assertNotIn("mbcsToSbcs", execution.stderr)
            for nom in (
                "00_rapport_acm.txt",
                "13_plan_factoriel.png",
                "13_plan_factoriel_significatif.png",
                "14_plan_factoriel.pdf",
                "14_plan_factoriel_significatif.pdf",
                "15_inerties.png",
                "18_comparaison_inerties_tdc_burt.csv",
                "19_couleurs_variables.csv",
                "20_diagnostic_filtre_pvalue.csv",
            ):
                self.assertTrue((sortie / nom).is_file(), nom)
            with (sortie / "19_couleurs_variables.csv").open(
                encoding="utf-8", newline=""
            ) as fichier:
                palette = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(
                [ligne["variable"] for ligne in palette], variables
            )
            self.assertEqual(
                len({ligne["couleur_hex"] for ligne in palette}),
                len(variables),
            )
            self.assertEqual(
                sum(int(ligne["nombre_modalites"]) for ligne in palette),
                24,
                "Chaque variable active doit contribuer ses modalités.",
            )
            rapport = (sortie / "00_rapport_acm.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("presse_regio_dpt", rapport)
            self.assertIn("Tableau de Burt", rapport)



    @unittest.skipUnless(
        factominer_disponible(),
        "Rscript avec FactoMineR non disponible dans cet environnement",
    )
    def test_filtrage_burt_sur_900_observations(self):
        """Écarter le faux plan vide sur un échantillon corrélé de 900 lignes."""
        with tempfile.TemporaryDirectory(prefix="acm_900_") as dossier:
            racine = Path(dossier)
            entree = racine / "donnees.tsv"
            sortie = racine / "resultats"
            sortie.mkdir()
            with entree.open("w", encoding="utf-8", newline="") as fichier:
                ecrivain = csv.writer(fichier, delimiter="\t")
                ecrivain.writerow([
                    "vues_classe", "likes_classe", "type_media"
                ])
                for i in range(900):
                    profil = i % 3
                    ecrivain.writerow([
                        ["faibles", "moyennes", "fortes"][profil],
                        ["0-9", "10-99", "100-999"][
                            (profil + (i % 17 == 0)) % 3
                        ],
                        ["presse", "autres", "local"][
                            (profil + (i % 23 == 0)) % 3
                        ],
                    ])
            execution = subprocess.run(
                [
                    shutil.which("Rscript"), str(MOTEUR_ACM),
                    str(entree), str(sortie), "Corpus 900", "900",
                    "900", "Burt",
                ],
                capture_output=True, text=True, check=False, timeout=120,
            )
            self.assertEqual(
                execution.returncode, 0,
                execution.stderr or execution.stdout,
            )
            with (
                sortie / "significativite_modalites_factominer.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                lignes = list(csv.DictReader(fichier, delimiter=";"))
            self.assertEqual(len(lignes), 9)
            self.assertEqual(
                sum(ligne["significative_005"] == "TRUE" for ligne in lignes),
                sum(
                    float(ligne["p_value_min"].replace(",", ".")) <= 0.05
                    for ligne in lignes
                ),
            )
            self.assertGreater(
                sum(ligne["significative_005"] == "TRUE" for ligne in lignes),
                0,
                "Un corpus corrélé de 900 observations ne doit pas produire "
                "un faux plan vide par défaut de correspondance des noms.",
            )
            for ligne in lignes:
                self.assertTrue(ligne["p_value_axe_1"])
                self.assertTrue(ligne["v_test_axe_1"])
            with (
                sortie / "20_diagnostic_filtre_pvalue.csv"
            ).open(encoding="utf-8", newline="") as fichier:
                diagnostic = dict(
                    (ligne["indicateur"], ligne["valeur"])
                    for ligne in csv.DictReader(fichier, delimiter=";")
                )
            self.assertEqual(diagnostic["Observations analysées"], "900")
            self.assertEqual(
                diagnostic["Modalités avec p-value valide"], "9"
            )
            self.assertTrue(
                (sortie / "13_plan_factoriel_significatif.png").is_file()
            )


if __name__ == "__main__":
    unittest.main()
