"""Isolation des méthodes Presse et preuve de version côté serveur."""
import unittest
import tempfile
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient

from webapp import StartRequest,Manager,create_app
from collecte.presse_api import VERSION_PRESSE
from connect_presse import ConnexionPresse


class TestIsolationPresse(unittest.TestCase):
    def test_version_serveur_est_exposee_sur_healthz(self):
        with tempfile.TemporaryDirectory() as dossier, \
             patch("urllib.request.urlopen") as controle:
            controle.return_value.__enter__.return_value = Mock()
            with TestClient(create_app(Manager(data_dir=dossier))) as client:
                response = client.get("/healthz")
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["version_presse"],VERSION_PRESSE)

    def test_une_seule_methode_est_selectionnee_par_collecte(self):
        for moteur in ("api","navigateur"):
            with self.subTest(moteur=moteur):
                requete=StartRequest(source_collecte="presse",
                                     medias=["lemonde"],presse_moteur=moteur)
                connecteur=ConnexionPresse(Mock())
                connecteur.preparer_sources(requete)
                self.assertEqual(connecteur.moteur_collecte,moteur)
                self.assertEqual(requete.presse_moteur,moteur)
        with self.assertRaises(ValueError):
            StartRequest(source_collecte="presse",medias=["lemonde"],
                         presse_moteur="api_puis_navigateur")

    def test_methode_api_par_defaut_et_numero_version_explicite(self):
        requete=StartRequest(source_collecte="presse",medias=["lemonde"])
        self.assertEqual(requete.presse_moteur,"api")
        self.assertEqual(VERSION_PRESSE,"presse-metadonnees-identites-20261024-v9")
        from pathlib import Path
        code=Path(__file__).resolve().parents[1].joinpath(
            "collecte/presse_api.py").read_text(encoding="utf-8")
        self.assertNotIn("secUid du média introuvable ou invalide",code)


if __name__=="__main__":
    unittest.main()
