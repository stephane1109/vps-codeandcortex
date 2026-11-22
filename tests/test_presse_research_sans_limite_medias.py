"""Vérifier l'absence de plafond local de 29 médias dans Research API.

Les autres moteurs conservent leurs protections déjà existantes.
"""
import threading
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from collecte.presse import charger_inventaire
from webapp import Manager, StartRequest


class TestsSourcesPresseSansPlafondResearch(unittest.TestCase):

    def test_tous_les_comptes_de_l_inventaire_sont_acceptes(self):
        """Accepter une sélection entière sans réduire son cardinal."""
        comptes = [media["id"] for media in charger_inventaire()]
        self.assertGreater(len(comptes), 29)
        options = StartRequest(
            source_collecte="presse", medias=comptes, presse_moteur="research",
            nom_sauvegarde="Tous les médias",
            research_client_key="cle_test", research_client_secret="secret_test",
            collecte_research_complete=True,
        )
        self.assertEqual(options.medias, comptes)
        self.assertEqual(len(options.sources), len(comptes))
        self.assertTrue(options.collecte_research_complete)

    def test_lancement_research_n_est_pas_bloque_par_max_sources(self):
        """La garde locale historique n'est pas utilisée avec Research."""
        comptes = [m["id"] for m in charger_inventaire()]
        options = StartRequest(
            source_collecte="presse", medias=comptes, presse_moteur="research",
            research_client_key="cle_test", research_client_secret="secret_test",
            nom_sauvegarde="Collecte totale",
            collecte_research_complete=True,
        )
        manager = object.__new__(Manager)
        manager.lock = threading.RLock()
        manager.jobs = {}
        manager.max_jobs = 1
        manager.idle_timeout = 3600
        manager.max_duration = 86400
        manager.data_dir = Path(tempfile.gettempdir())
        manager.runner = lambda job: None
        appel = SimpleNamespace(
            id="job_tous_medias", busy=True, video_busy=False)
        with patch("collecte.quotas_exploitation.max_sources", return_value=1), \
                patch("stockage.postgres_consultation.adresse_configuree",
                      return_value=False), \
                patch("webapp.Job", return_value=appel), \
                patch("webapp.threading.Thread.start", return_value=None):
            recu = manager.start("proprietaire", options)
        self.assertIs(recu, appel)
        self.assertIs(manager.jobs[appel.id], appel)

    def test_autres_moteurs_conservent_leurs_gardes(self):
        """Éviter les régressions sur l'API web et Selenium."""
        comptes = [m["id"] for m in charger_inventaire()]
        options = StartRequest(
            source_collecte="presse", medias=comptes,
            presse_moteur="api", nom_sauvegarde="Contrôle API web",
        )
        manager = object.__new__(Manager)
        with patch("collecte.quotas_exploitation.max_sources", return_value=1):
            with self.assertRaises(HTTPException) as erreur:
                manager.start("proprietaire", options)
        self.assertEqual(erreur.exception.status_code, 422)

    def test_interface_n_affiche_pas_de_plafond_research(self):
        """Le bouton et le compteur tiennent compte du moteur sélectionné."""
        interface = (
            Path(__file__).resolve().parents[1] / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'if st.session_state.get("presse_moteur") == "research":',
            interface)
        self.assertIn(
            '"Research API : aucune limite locale sur le nombre de médias ; "',
            interface)
        self.assertIn(
            '(source == "presse" and moteur_formulaire != "research"',
            interface)


if __name__ == "__main__":
    unittest.main()
