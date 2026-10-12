"""Retrait de la connexion facultative et des commandes d'ouverture manuelle."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import webapp as web
import webapp as serveur
from collecte.comptes import collecter_compte


class CollecteAnonyme(unittest.TestCase):
    def test_ancienne_option_ignoree_sans_ouvrir_de_page_de_connexion(self):
        with tempfile.TemporaryDirectory() as dossier:
            parametres = web.StartRequest(source_collecte="comptes", comptes=["media", "presse"], se_connecter_tiktok=True)
            self.assertNotIn("se_connecter_tiktok", parametres.model_dump())
            job = web.Job("test", parametres, Path(dossier))
            navigateur, pilotes = Mock(), []
            def decouvrir(pilote, arguments, compte, rapport, **options):
                pilotes.append(pilote)
                self.assertTrue(options["sans_connexion"])
                return []
            with patch("collecte.comptes.collecter_compte", side_effect=decouvrir), patch.object(web, "wait_for_user") as pause:
                fabrique = Mock(return_value=navigateur)
                web.execute_job(job, driver_factory=fabrique)
            fabrique.assert_called_once()
            pause.assert_not_called()
            navigateur.get.assert_not_called()
            navigateur.quit.assert_called_once()
            self.assertEqual(pilotes, [navigateur, navigateur])
            self.assertNotIn("etat_connexion", job.snapshot())
            self.assertNotIn("navigateur_disponible", job.snapshot())

    def test_comptes_ne_peuvent_pas_reactiver_un_mode_connecte(self):
        with patch.object(web.scraper, "collect_links", return_value=[]) as liens:
            collecter_compte(Mock(), Mock(), "media", sans_connexion=False)
        self.assertTrue(liens.call_args.kwargs["sans_connexion"])

    def test_aucun_profil_chrome_persistant_reutilise(self):
        arguments = SimpleNamespace(driver=None, headless=True, profile_dir=Path("ancien-profil"), chrome_binary=None, timeout=20)
        navigateur = Mock()
        with patch.object(web.scraper.webdriver, "Chrome", return_value=navigateur) as chrome:
            web.scraper.create_driver(arguments)
        self.assertFalse(any(argument.startswith("--user-data-dir") for argument in chrome.call_args.kwargs["options"].arguments))

    def test_routes_connexion_et_ouverture_manuelle_supprimees(self):
        with tempfile.TemporaryDirectory() as dossier:
            manager = web.Manager(data_dir=dossier)
            try:
                routes = {route.path for route in serveur.create_app(manager).routes}
                self.assertNotIn("/api/jobs/{job_id}/deconnexion", routes)
                self.assertNotIn("/api/jobs/{job_id}/navigateur", routes)
                self.assertIn("/controle", routes)
                self.assertIn("/api/jobs/{job_id}/continue", routes)
            finally:
                manager.shutdown()
