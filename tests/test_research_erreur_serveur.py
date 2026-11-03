"""Tests de distinction HTTP 5xx, quota et poursuite des médias Research."""
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from collecte.researchapi import (
    ResearchErreur, ResearchErreurServeur, ResearchAccesRefuse,
    _requete, _url_videos, poursuivre_apres_erreur_serveur,
)


class TestsErreursServeurResearch(unittest.TestCase):

    def envoyer_erreur_http(self, statut):
        """Simuler une réponse TikTok sans effectuer d'appel externe."""
        url = _url_videos()
        erreur = HTTPError(url, statut, "Réponse du serveur TikTok", {}, None)
        with patch("stockage.collectes_research.reserver_requete",
                   return_value=True), patch(
                "collecte.researchapi.urlopen", side_effect=erreur):
            return _requete(
                url, data=b"{}", headers={"Authorization": "Bearer test"})

    def test_500_est_une_erreur_serveur_et_non_un_refus_de_quota(self):
        for statut in (500, 502, 503, 504):
            with self.subTest(statut=statut):
                with self.assertRaises(ResearchErreurServeur) as capture:
                    self.envoyer_erreur_http(statut)
                self.assertEqual(capture.exception.statut_http, statut)
                self.assertNotIsInstance(capture.exception, ResearchAccesRefuse)

    def test_401_403_429_stoppent_la_collecte(self):
        for statut in (401, 403, 429):
            with self.subTest(statut=statut):
                with self.assertRaises(ResearchAccesRefuse) as capture:
                    self.envoyer_erreur_http(statut)
                self.assertNotIsInstance(capture.exception, ResearchErreurServeur)

    def test_400_ne_doit_pas_devenir_une_erreur_transitoire(self):
        with self.assertRaises(ResearchErreur) as capture:
            self.envoyer_erreur_http(400)
        self.assertNotIsInstance(capture.exception, ResearchErreurServeur)

    def test_un_seul_500_n_interrompt_pas_les_medias_suivants(self):
        erreur = ResearchErreurServeur(500)
        for nombre in (1, 2):
            self.assertTrue(poursuivre_apres_erreur_serveur(
                erreur, source_collecte="presse", moteur_actif="research",
                echecs_consecutifs=nombre))
        self.assertFalse(poursuivre_apres_erreur_serveur(
            erreur, source_collecte="presse", moteur_actif="research",
            echecs_consecutifs=3))

    def test_pas_de_poursuite_pour_refus_ni_autres_collectes(self):
        erreur = ResearchErreurServeur(500)
        for source, moteur in (
            ("hashtags", "research"), ("comptes", "research"),
            ("presse", "api"), ("presse", "selenium")
        ):
            with self.subTest(source=source, moteur=moteur):
                self.assertFalse(poursuivre_apres_erreur_serveur(
                    erreur, source_collecte=source, moteur_actif=moteur,
                    echecs_consecutifs=1))
        self.assertFalse(poursuivre_apres_erreur_serveur(
            ResearchAccesRefuse("Research API HTTP 429"),
            source_collecte="presse", moteur_actif="research",
            echecs_consecutifs=1))

    def test_moteur_garde_la_source_en_echec_et_passe_a_la_suivante(self):
        """Contrôler l'intégration de la politique dans la boucle de collecte."""
        code = (Path(__file__).resolve().parents[1] /
                "webapp.py").read_text(encoding="utf-8")
        self.assertIn("echecs_serveur_research_consecutifs = 0", code)
        self.assertIn("poursuivre = poursuivre_apres_erreur_serveur(", code)
        self.assertIn('"poursuite_autorisee": poursuivre', code)
        self.assertIn('job.pause(2.0)\n                            continue', code)
        self.assertIn("if isinstance(erreur, ResearchErreurServeur):", code)
        self.assertIn("limitation_research = True", code)


if __name__ == "__main__":
    unittest.main()
