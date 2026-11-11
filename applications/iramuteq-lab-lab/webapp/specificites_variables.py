"""Calcul indépendant des spécificités lexicales selon les variables étoilées.

Ce module n'intervient pas dans le calcul historique d'un terme par modalité.
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from . import runtime


def calculer_specificites_variables(source_rds: str, variable: str, indice: str) -> dict:
    """Calculer et exporter toutes les formes, sans modifier les analyses existantes."""
    if not isinstance(variable, str) or not variable.startswith("*") or len(variable) > 120:
        raise ValueError("Sélectionnez une variable étoilée valide.")
    if indice not in {"hypergeo", "chi2"}:
        raise ValueError("Indice de spécificité inconnu.")
    chemin_source = Path(source_rds).resolve()
    if not chemin_source.is_file():
        raise FileNotFoundError("La matrice lexicale conservée par la CHD est introuvable.")

    with TemporaryDirectory(prefix="specificites-variables-") as repertoire:
        commande = [
            runtime.resolve_rscript(),
            "--vanilla",
            str(runtime.PROJECT_ROOT / "backend" / "r" / "run_specificites_variables.R"),
            str(chemin_source),
            variable,
            indice,
            repertoire,
        ]
        try:
            processus = subprocess.run(
                commande,
                cwd=runtime.PROJECT_ROOT,
                env=runtime.build_command_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
                check=False,
            )
        except subprocess.TimeoutExpired as erreur:
            raise RuntimeError("Le calcul des spécificités par variable a dépassé le délai autorisé.") from erreur

        if processus.returncode != 0:
            raise RuntimeError(
                (processus.stderr or processus.stdout or "Échec du calcul R.")[-1800:]
            )
        try:
            resume = json.loads(processus.stdout)
        except json.JSONDecodeError as erreur:
            raise RuntimeError("Le moteur R n'a pas renvoyé de résumé valide.") from erreur

        csv_path = Path(repertoire) / "specificites_formes_variables.csv"
        if not csv_path.is_file():
            raise RuntimeError("Le moteur R n'a pas produit le tableau des spécificités.")
        texte_csv = csv_path.read_text(encoding="utf-8")
        lecteur = csv.reader(io.StringIO(texte_csv))
        en_tetes = next(lecteur, [])
        if "modalite" not in en_tetes:
            raise RuntimeError("La colonne des modalités manque dans le résultat statistique.")
        indice_modalite = en_tetes.index("modalite")
        nombre_modalites = max(1, int(resume.get("n_modalities", 1)))
        limite_par_modalite = max(50, 1000 // nombre_modalites)
        compteurs = {}
        apercu = []
        for ligne in lecteur:
            modalite = ligne[indice_modalite]
            nombre = compteurs.get(modalite, 0)
            if nombre < limite_par_modalite:
                apercu.append(ligne)
                compteurs[modalite] = nombre + 1
        return {
            "success": True,
            "summary": resume,
            "headers": en_tetes,
            "rows": apercu,
            "csv": texte_csv,
            "preview_limit": 1000,
        }
