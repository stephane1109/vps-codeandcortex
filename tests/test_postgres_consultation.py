"""Tests du stockage privé PostgreSQL, sans connexion réseau."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from threading import RLock
from unittest.mock import patch

from stockage.postgres_consultation import (
    IDENTIFIANT, adresse_configuree, empreinte, valeur_colonne,
    archiver_collecte, importer_historique,
)


class CurseurFictif:
    def __init__(self):
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        return False

    def execute(self, instruction, parametres=None):
        self.executions.append((instruction, parametres))


class ConnexionFictive:
    def __init__(self):
        self.curseur = CurseurFictif()

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        return False

    def cursor(self):
        return self.curseur


class ParametresFictifs:
    nom_sauvegarde = "Test 24 octobre"
    libelle = "Autre libellé"
    source_collecte = "presse"
    moteur_actif = "research"

    def model_dump(self):
        return {"nom_sauvegarde": self.nom_sauvegarde,
                "research_client_key": "cle_interdite",
                "research_client_secret": "secret_interdit"}


class TestsPostgresConsultation(unittest.TestCase):
    def test_id_et_cookie_proteges(self):
        self.assertTrue(IDENTIFIANT.fullmatch("a" * 32))
        self.assertFalse(IDENTIFIANT.fullmatch("a" * 31))
        self.assertFalse(IDENTIFIANT.fullmatch("a" * 32 + "_"))
        self.assertEqual(len(empreinte("cookie_prive")), 64)

    def test_extraction_compteurs_exacte(self):
        self.assertEqual(valeur_colonne(
            {"engagement": {"vues": {"valeur": 0}}}, "vues"), "0")
        self.assertEqual(valeur_colonne(
            {"engagement": {"vues": {"valeur": None}}}, "vues"), "")

    def test_archiver_test_sans_texte_retenu_et_sans_secrets(self):
        """Les vidéos rejetées sont archivées, même si le TXT est vide."""
        identifiant = "b" * 32
        travail = SimpleNamespace(
            lock=RLock(), id=identifiant, owner_historique="cookie_prive",
            settings=ParametresFictifs(), status="completed", processed=1,
            publications=[{"id": "123", "author": "brutofficiel",
                           "description": "#actu", "retenue": False}],
            records=[], commentaires=[])
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            bilan = archiver_collecte(travail)
        self.assertEqual(bilan["publications"], 1)
        self.assertEqual(bilan["commentaires"], 0)
        textes = " ".join(str(entree) for entree in connexion.curseur.executions)
        self.assertIn("scraptiktok_publications", textes)
        self.assertIn("Test 24 octobre", textes)
        self.assertNotIn("cle_interdite", textes)
        self.assertNotIn("secret_interdit", textes)
        self.assertNotIn("cookie_prive", textes)
        self.assertIn(empreinte("cookie_prive"), textes)

    def test_import_historique_autorise_par_cookie(self):
        """L'import reprend la sauvegarde possédée par le même navigateur."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            (racine / "publications.json").write_text(
                json.dumps([{"id": "123", "description": "Légende"}]),
                encoding="utf-8")
            (racine / "commentaires.json").write_text("[]", encoding="utf-8")
            entree = {"id": "c" * 32, "titre": "Ancienne recherche",
                      "statut": "completed"}
            manifeste = {"parametres": {"source_collecte": "presse",
                                        "presse_moteur": "research"},
                         "traites": 1}
            with patch("stockage.historique_analyses.lister",
                       return_value=[entree]), patch(
                           "stockage.historique_analyses.retrouver",
                           return_value=(entree, racine, manifeste)), patch(
                           "stockage.postgres_consultation.archiver_collecte",
                           return_value={"publications": 1, "commentaires": 0}
                           ) as enregistrer:
                bilan = importer_historique(dossier, "cookie_original")
            self.assertEqual(bilan["imports"], 1)
            self.assertEqual(bilan["publications"], 1)
            self.assertEqual(bilan["erreurs"], 0)
            travail = enregistrer.call_args.args[0]
            self.assertEqual(travail.owner_historique, "cookie_original")
            self.assertEqual(travail.settings.nom_sauvegarde,
                             "Ancienne recherche")


if __name__ == "__main__":
    unittest.main()
