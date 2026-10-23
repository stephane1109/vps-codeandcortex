"""Régressions : ne pas confondre l'aperçu (six vidéos) et la rubrique Publications."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import scraptiktok as moteur
from collecte.profil_selenium import (
    ONGLET_PUBLICATIONS_JS, LIENS_PROFIL_JS, collecter_grille_profil,
)
from collecte.reseau_profils import ObservationProfil, extraire_page_publications


class NavigationVideosPresse(unittest.TestCase):
    def test_ouvrir_rubrique_complete_avant_de_lire_ses_videos(self):
        videos = [f"https://www.tiktok.com/@lemondefr/video/{i}" for i in range(100, 112)]
        bouton = Mock()
        navigateur = Mock()
        navigateur.current_url = "https://www.tiktok.com/@lemondefr?tab=videos"

        def script(code, *args):
            if code == ONGLET_PUBLICATIONS_JS:
                self.assertEqual(args, ("lemondefr",))
                return bouton
            if code == LIENS_PROFIL_JS:
                # Avant clic = aperçu ; après clic = publications du média.
                return videos if bouton.click.called else videos[:6]
            if code == moteur.DONNEES_PUBLICATIONS_JS:
                return []
            return None

        navigateur.execute_script.side_effect = script
        arguments = SimpleNamespace(limit=12, timeout=.01, delay=0,
                                    max_scrolls=2, idle_rounds=1, interactive=True)
        rapport = {"compte_attendu":"lemondefr",
                   "hashtag_url":"https://www.tiktok.com/@lemondefr"}
        with patch("collecte.profil_selenium.ObservationProfil") as observateur, \
             patch.object(moteur, "open_page"), \
             patch.object(moteur, "type_intervention_tiktok", return_value=""), \
             patch.object(moteur, "fermer_invitation_connexion"):
            observateur.return_value.lire.return_value = []
            resultat = collecter_grille_profil(
                navigateur, arguments, rapport, interact=Mock()
            )
        self.assertEqual(resultat, videos)
        self.assertEqual(rapport["discovery_stop"],"limit")
        self.assertEqual(rapport["navigation_publications"],"rubrique_selectionnee")
        self.assertEqual(rapport["url_rubrique_publications"],
                         "https://www.tiktok.com/@lemondefr")
        bouton.click.assert_called_once()

    def test_observe_la_liste_createur_en_plus_de_la_liste_classique(self):
        observation = ObservationProfil(Mock(), "lemondefr", {})
        self.assertTrue(observation.accepter_reponse(
            urlsplit("https://www.tiktok.com/api/creator/item_list/?cursor=0")
        ))
        self.assertTrue(observation.accepter_reponse(
            urlsplit("https://www.tiktok.com/api/post/item_list/?cursor=0")
        ))
        self.assertFalse(observation.accepter_reponse(
            urlsplit("https://www.tiktok.com/api/comment/list/?cursor=0")
        ))
        self.assertFalse(observation.accepter_reponse(
            urlsplit("https://example.org/api/creator/item_list/")
        ))

    def test_creators_pages_enchainees_sont_filtres_sur_le_bon_media(self):
        page = extraire_page_publications({
            "statusCode":0,"cursor":"1234","hasMore":True,
            "itemList":[
                {"id":"101","author":{"uniqueId":"lemondefr"},"video":{"id":"101"}},
                {"id":"102","author":{"uniqueId":"autremedia"},"video":{"id":"102"}},
            ],
        }, "lemondefr")
        self.assertEqual(page["liens"],["https://www.tiktok.com/@lemondefr/video/101"])
        self.assertEqual(page["curseur"],"1234")
        self.assertTrue(page["suite"])


if __name__ == "__main__":
    unittest.main()
