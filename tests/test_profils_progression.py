"""Régressions de la transition entre découverte de profil et lecture des vidéos."""
import argparse
import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException

import scraptiktok as moteur
from collecte.comptes import collecter_profil_public, collecter_compte


class AttenteSimulee:
    """Ne pas attendre réellement pendant une simulation de grille immobile."""
    def __init__(self, navigateur, temps, **kwargs):
        self.navigateur = navigateur

    def until(self, condition):
        if condition(self.navigateur):
            return True
        raise TimeoutException("Pas de publication supplémentaire")


class TestCollecteProfil(unittest.TestCase):
    def test_douze_videos_et_fin_de_grille_lancent_la_lecture(self):
        compte = "lemondefr"
        urls = [
            f"https://www.tiktok.com/@{compte}/video/{100000 + i}"
            for i in range(12)
        ]
        navigateur = Mock()
        navigateur.current_url = f"https://www.tiktok.com/@{compte}"
        navigateur.execute_script.side_effect = (
            lambda script: list(urls) + ["https://www.tiktok.com/@autre/video/999999"]
            if script == moteur.DISCOVER_JS else []
        )
        arguments = argparse.Namespace(
            limit=50, max_scrolls=40, idle_rounds=3,
            timeout=20.0, delay=3.0, interactive=True,
        )
        rapport, progression = {}, Mock()
        page_fin = {
            "avant": {"fin": True, "position": 100},
            "apres": {"fin": True, "position": 100},
        }

        with patch("collecte.reseau_profils.ObservationProfil") as observation, \
             patch("collecte.pagination_profils.defiler_grille_profil",
                   return_value=page_fin) as defilement, \
             patch("scraptiktok.open_page"), \
             patch("scraptiktok.diagnostiquer_page", return_value={"code": "ok"}), \
             patch("scraptiktok.type_intervention_tiktok", return_value=""), \
             patch("selenium.webdriver.support.ui.WebDriverWait", AttenteSimulee), \
             patch("time.sleep"):
            observation.return_value.lire.return_value = []
            trouves = collecter_profil_public(
                navigateur, arguments, compte, rapport,
                interact=Mock(), progress=progression,
            )

        self.assertEqual(trouves, urls)
        self.assertEqual(rapport["discovery_stop"], "pagination_epuisee")
        self.assertEqual(rapport["auteurs_ecartes"], 1)
        self.assertEqual(rapport["candidats_examines"], 13)
        self.assertEqual(defilement.call_count, 1)
        self.assertEqual(progression.call_args.args[0], 12)
        observation.return_value.fermer.assert_called_once()

    def test_recherche_generale_ignoree_si_profil_a_des_liens(self):
        urls = ["https://www.tiktok.com/@lemondefr/video/12345"]
        args = argparse.Namespace(limit=50)
        with patch("collecte.comptes.collecter_profil_public",
                   return_value=urls) as profil, \
             patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            rapport = {}
            resultat = collecter_compte(
                Mock(), args, "lemondefr", rapport,
                hashtags=["17octobre"], interact=Mock(), check=Mock(),
            )
        self.assertEqual(resultat, urls)
        self.assertEqual(rapport["retenues_par_compte"], {"lemondefr": 1})
        profil.assert_called_once()
        recherche.assert_not_called()


if __name__ == "__main__":
    unittest.main()
