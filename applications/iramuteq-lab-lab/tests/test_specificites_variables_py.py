"""Tests du parcours complémentaire de spécificités par variables étoilées.

La route et le moteur historiques ne sont ni importés ni modifiés par ces tests.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp.specificites_variables import calculer_specificites_variables


class TestSpecificitesVariables(unittest.TestCase):
    def test_export_et_apercu_de_deux_modalites(self) -> None:
        """L'aperçu doit contenir des formes des deux origines du discours."""
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "source_specificites.rds"
            source.write_bytes(b"fichier-rds-simule")

            def execution_simulee(commande, **_parametres):
                sortie = Path(commande[-1])
                sortie.joinpath("specificites_formes_variables.csv").write_text(
                    "variable,modalite,forme,score_specificite,p_ajustee_bh\n"
                    + "".join(f"source,original,mot{i},2,0.01\n" for i in range(600))
                    + "".join(f"source,ia,resume{i},-2,0.02\n" for i in range(600)),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(
                    args=commande,
                    returncode=0,
                    stdout=json.dumps({
                        "variable_label": "source",
                        "n_modalities": 2,
                        "n_forms": 1200,
                        "modalities": ["original", "ia"],
                    }),
                    stderr="",
                )

            with patch("webapp.specificites_variables.subprocess.run",
                       side_effect=execution_simulee), patch(
                "webapp.specificites_variables.runtime.resolve_rscript",
                return_value="Rscript",
            ), patch(
                "webapp.specificites_variables.runtime.build_command_env",
                return_value={},
            ):
                resultat = calculer_specificites_variables(
                    str(source), "*source", "hypergeo"
                )
            self.assertTrue(resultat["success"])
            self.assertEqual(len(resultat["rows"]), 1000)
            self.assertEqual(sum(row[1] == "original" for row in resultat["rows"]), 500)
            self.assertEqual(sum(row[1] == "ia" for row in resultat["rows"]), 500)
            self.assertIn("source,ia,resume599", resultat["csv"])

    def test_parametres_invalides_refuses(self) -> None:
        """Un mauvais nom de variable ne doit pas déclencher R."""
        with self.assertRaisesRegex(ValueError, "variable étoilée"):
            calculer_specificites_variables("/inexistant", "source", "hypergeo")
        with self.assertRaisesRegex(ValueError, "Indice"):
            calculer_specificites_variables("/inexistant", "*source", "autre")


if __name__ == "__main__":
    unittest.main()
