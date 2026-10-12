"""Scénarios locaux du profil paginé, sans accès réseau ni navigateur réel."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import scraptiktok as moteur
from collecte.profil_selenium import collecter_grille_profil, LIENS_PROFIL_JS, ONGLET_PUBLICATIONS_JS
from collecte.reseau_profils import extraire_page_publications


class PaginationProfils(unittest.TestCase):
    def test_page_suivante_et_auteur_exact(self):
        page = extraire_page_publications({"statusCode": 0, "cursor": "1234", "hasMore": True,
            "itemList": [{"id": "123", "desc": "Texte", "author": {"uniqueId": "lemondefr"}, "video": {"id": "123"}},
                         {"id": "456", "desc": "Autre auteur", "author": {"uniqueId": "autre"}, "video": {"id": "456"}}]}, "lemondefr")
        self.assertEqual(page["liens"], ["https://www.tiktok.com/@lemondefr/video/123"])
        self.assertTrue(page["suite"])
        self.assertEqual(page["curseur"], "1234")

    def test_absence_de_suite_reste_indeterminee(self):
        self.assertIsNone(extraire_page_publications({"itemList": []}, "media")["suite"])
        self.assertFalse(extraire_page_publications({"itemList": [], "hasMore": 0}, "media")["suite"])
        erreur = extraire_page_publications({"statusCode": 10201, "itemList": [], "hasMore": False}, "media")
        self.assertFalse(erreur["liste_valide"])
        self.assertIsNone(erreur["suite"])

    def test_reponse_etrangere_ne_termine_pas_le_profil(self):
        page = extraire_page_publications({"itemList": [{"id": "456", "desc": "Autre", "video": {"id": "456"},
            "author": {"uniqueId": "autre"}}], "hasMore": False, "cursor": "123"}, "media")
        self.assertEqual(page["liens"], [])
        self.assertIsNone(page["suite"])
        self.assertIsNone(page["curseur"])

    def test_depasse_six_vignettes_avec_la_reponse_suivante(self):
        urls = [f"https://www.tiktok.com/@media/video/{i}" for i in range(100, 112)]
        pilote = Mock()
        pilote.execute_script.side_effect = lambda code, *a: urls[:6] if code == LIENS_PROFIL_JS else [] if code == moteur.DONNEES_PUBLICATIONS_JS else None
        arguments = SimpleNamespace(limit=12, timeout=.01, delay=0, max_scrolls=3, idle_rounds=2, interactive=True)
        rapport = {"compte_attendu": "media", "hashtag_url": "https://www.tiktok.com/@media"}
        with patch("collecte.profil_selenium.ObservationProfil") as classe, \
             patch.object(moteur, "open_page"), patch.object(moteur, "type_intervention_tiktok", return_value=""), \
             patch.object(moteur, "fermer_invitation_connexion"), \
             patch("collecte.profil_selenium.defiler_grille_profil", return_value={"avant": {}, "apres": {}}):
            classe.return_value.lire.side_effect = [[], urls[6:]]
            resultat = collecter_grille_profil(pilote, arguments, rapport, interact=Mock())
            self.assertEqual(resultat, urls)
            self.assertEqual(rapport["discovery_stop"], "limit")
            classe.return_value.fermer.assert_called_once()

    def test_connexion_conserve_six_liens_sans_imposer_authentification(self):
        urls = [f"https://www.tiktok.com/@media/video/{i}" for i in range(100, 106)]
        pilote = Mock()
        pilote.execute_script.side_effect = lambda code, *a: urls if code == LIENS_PROFIL_JS else [] if code == moteur.DONNEES_PUBLICATIONS_JS else None
        arguments = SimpleNamespace(limit=20, timeout=.001, delay=0, max_scrolls=1, idle_rounds=1, interactive=True)
        rapport = {"compte_attendu": "media", "hashtag_url": "https://www.tiktok.com/@media"}
        intervention = Mock()
        with patch("collecte.profil_selenium.ObservationProfil") as classe, \
             patch.object(moteur, "open_page"), patch.object(moteur, "type_intervention_tiktok", return_value="connexion"), \
             patch.object(moteur, "fermer_invitation_connexion"):
            classe.return_value.lire.return_value = []
            resultat = collecter_grille_profil(pilote, arguments, rapport, interact=intervention)
            self.assertEqual(resultat, urls)
            self.assertEqual(rapport["discovery_stop"], "connexion_apres_resultats")
            intervention.assert_called_once()
            self.assertIn("pagination_bloquee", rapport["interventions_automatiques"])
            classe.return_value.fermer.assert_called_once()

    def test_page_vide_ouvre_la_fenetre_et_relit_sans_navigation(self):
        url = "https://www.tiktok.com/@media/video/123"
        visibles = []
        pilote = Mock()
        pilote.execute_script.side_effect = lambda code, *a: list(visibles) if code == LIENS_PROFIL_JS else [] if code == moteur.DONNEES_PUBLICATIONS_JS else None
        arguments = SimpleNamespace(limit=1, timeout=.01, delay=0, max_scrolls=1, idle_rounds=1, interactive=True)
        rapport = {"compte_attendu": "media", "hashtag_url": "https://www.tiktok.com/@media"}
        intervention = Mock(side_effect=lambda message: visibles.append(url))
        with patch("collecte.profil_selenium.ObservationProfil") as classe, \
             patch.object(moteur, "open_page") as ouvrir, \
             patch.object(moteur, "type_intervention_tiktok", return_value=""), \
             patch.object(moteur, "fermer_invitation_connexion"), \
             patch("collecte.profil_selenium.WebDriverWait") as attente:
            classe.return_value.lire.return_value = []
            def patienter(scanner):
                if not scanner(pilote):
                    raise moteur.TimeoutException()
                return True
            attente.return_value.until.side_effect = patienter
            self.assertEqual(collecter_grille_profil(pilote, arguments, rapport, interact=intervention), [url])
            intervention.assert_called_once()
            ouvrir.assert_called_once()
            self.assertEqual(rapport["interventions_automatiques"], ["profil_sans_liens"])

    def test_page_toujours_vide_ne_boucle_pas_sur_la_fenetre(self):
        pilote = Mock()
        pilote.execute_script.return_value = None
        arguments = SimpleNamespace(limit=1, timeout=.01, delay=0, max_scrolls=1, idle_rounds=1, interactive=True)
        rapport = {"compte_attendu": "media", "hashtag_url": "https://www.tiktok.com/@media"}
        intervention = Mock()
        with patch("collecte.profil_selenium.ObservationProfil") as classe, \
             patch.object(moteur, "open_page"), \
             patch.object(moteur, "type_intervention_tiktok", return_value=""), \
             patch.object(moteur, "fermer_invitation_connexion"), \
             patch("collecte.profil_selenium.WebDriverWait") as attente:
            attente.return_value.until.side_effect = moteur.TimeoutException()
            with self.assertRaises(RuntimeError):
                collecter_grille_profil(pilote, arguments, rapport, interact=intervention)
            intervention.assert_called_once()
            self.assertEqual(attente.return_value.until.call_count, 2)
            classe.return_value.fermer.assert_called_once()

    def test_onglet_apparu_apres_navigation_est_selectionne(self):
        url = "https://www.tiktok.com/@media/video/123"
        bouton = Mock()
        pilote = Mock()
        appels_onglet = 0
        def executer(code, *args):
            nonlocal appels_onglet
            if code == ONGLET_PUBLICATIONS_JS:
                appels_onglet += 1
                return bouton if appels_onglet > 1 else None
            if code == LIENS_PROFIL_JS:
                return [url] if bouton.click.called else []
            return [] if code == moteur.DONNEES_PUBLICATIONS_JS else None
        pilote.execute_script.side_effect = executer
        arguments = SimpleNamespace(limit=1, timeout=.01, delay=0, max_scrolls=1, idle_rounds=1, interactive=True)
        rapport = {"compte_attendu": "media", "hashtag_url": "https://www.tiktok.com/@media"}
        intervention = Mock()
        with patch("collecte.profil_selenium.ObservationProfil") as classe, \
             patch.object(moteur, "open_page"), \
             patch.object(moteur, "type_intervention_tiktok", return_value=""), \
             patch.object(moteur, "fermer_invitation_connexion"), \
             patch("collecte.profil_selenium.WebDriverWait") as attente:
            classe.return_value.lire.return_value = []
            def patienter(scanner):
                self.assertFalse(scanner(pilote))
                self.assertTrue(scanner(pilote))
            attente.return_value.until.side_effect = patienter
            self.assertEqual(collecter_grille_profil(pilote, arguments, rapport, interact=intervention), [url])
            bouton.click.assert_called_once()
            intervention.assert_not_called()
