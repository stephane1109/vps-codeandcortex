"""Vérification manuelle : cadres imbriqués, priorité CAPTCHA et reprise de collecte."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import scraptiktok as moteur
from collecte.comptes import collecter_compte


class NavigateurSimule:
    def __init__(self, cadres):
        self.cadres = cadres
        self.chemin = ["page"]
        self.current_url = "https://www.tiktok.com/search/video?q=%40media%20%23test"
        self.fermeture = Mock()
        self.get = Mock(side_effect=lambda url: setattr(self, "current_url", url))
        self.execute_script = Mock(side_effect=self.executer)
        self.switch_to = SimpleNamespace(
            frame=Mock(side_effect=self.entrer), parent_frame=Mock(side_effect=self.sortir),
            default_content=Mock(side_effect=lambda: self.chemin.__setitem__(slice(None), ["page"])))

    def entrer(self, cadre):
        if cadre not in self.cadres:
            raise moteur.WebDriverException("Cadre supprimé")
        self.chemin.append(cadre)

    def sortir(self):
        self.chemin.pop()

    def executer(self, code):
        etat = self.cadres[self.chemin[-1]]
        if code == moteur.TYPE_INTERVENTION_JS:
            return etat.get("nature", "")
        if code == moteur.CADRES_VISIBLES_JS:
            return etat.get("enfants", [])
        if code == moteur.FERMETURE_CONNEXION_JS:
            return self.fermeture
        if code == moteur.DIAGNOSTIC_JS:
            return {}
        if code == moteur.DISCOVER_JS:
            if self.chemin != ["page"]:
                raise AssertionError("Les liens doivent être lus dans la page principale.")
            return ["https://www.tiktok.com/@media/video/123"]
        return False


class VerificationTikTok(unittest.TestCase):
    def avec_puzzle(self):
        return NavigateurSimule({"page": {"nature": "connexion", "enfants": ["fenetre"]},
            "fenetre": {"nature": "connexion", "enfants": ["puzzle"]},
            "puzzle": {"nature": "captcha"}})

    def test_captcha_imbrique_prioritaire_sur_connexion_et_retour_fenetre_complete(self):
        navigateur = self.avec_puzzle()
        self.assertEqual(moteur.type_intervention_tiktok(navigateur), "captcha")
        self.assertEqual(navigateur.chemin, ["page"])
        self.assertEqual(navigateur.switch_to.parent_frame.call_count, 2)
        navigateur.switch_to.default_content.assert_called_once()

    def test_cadre_disparu_ne_masque_pas_le_captcha_suivant(self):
        navigateur = self.avec_puzzle()
        navigateur.cadres["page"]["enfants"].insert(0, "disparu")
        self.assertEqual(moteur.type_intervention_tiktok(navigateur), "captcha")
        self.assertEqual(navigateur.chemin, ["page"])

    def test_aucune_fermeture_automatique_du_puzzle_dans_une_fenetre_de_connexion(self):
        navigateur = self.avec_puzzle()
        moteur.fermer_invitation_connexion(navigateur)
        navigateur.fermeture.click.assert_not_called()
        self.assertFalse(any(c.args[0] == moteur.FERMETURE_CONNEXION_JS
                             for c in navigateur.execute_script.call_args_list))

    def test_invitation_simple_ne_devient_pas_un_captcha(self):
        navigateur = NavigateurSimule({"page": {"nature": "connexion"}})
        self.assertEqual(moteur.type_intervention_tiktok(navigateur), "connexion")
        self.assertFalse(moteur.captcha_present(navigateur))
        self.assertEqual(moteur.diagnostiquer_page(navigateur, {})["code"], "invitation_connexion")
        moteur.fermer_invitation_connexion(navigateur)
        navigateur.fermeture.click.assert_called_once()

    def test_session_perdue_n_est_pas_presentee_comme_absence_de_verification(self):
        navigateur = self.avec_puzzle()
        navigateur.execute_script.side_effect = moteur.InvalidSessionIdException("Session perdue")
        with self.assertRaises(moteur.InvalidSessionIdException):
            moteur.type_intervention_tiktok(navigateur)

    def test_erreur_dans_un_cadre_restaure_la_page_principale(self):
        navigateur = self.avec_puzzle()
        def executer(code):
            if navigateur.chemin[-1] == "puzzle":
                raise moteur.WebDriverException("Cadre en cours de remplacement")
            return navigateur.executer(code)
        navigateur.execute_script.side_effect = executer
        self.assertEqual(moteur.type_intervention_tiktok(navigateur), "")
        self.assertEqual(navigateur.chemin, ["page"])
        moteur.fermer_invitation_connexion(navigateur)
        navigateur.fermeture.click.assert_not_called()

    def test_hashtag_et_compte_attendent_le_meme_captcha_avant_de_lire(self):
        for mode in ("hashtag", "compte"):
            with self.subTest(mode=mode):
                navigateur = self.avec_puzzle()
                arguments = SimpleNamespace(limit=1, timeout=.01, max_scrolls=2,
                                             delay=0, idle_rounds=3, interactive=True)
                def terminer(message):
                    self.assertIn("CAPTCHA", message)
                    self.assertEqual(navigateur.chemin, ["page"])
                    self.assertFalse(any(c.args[0] == moteur.DISCOVER_JS
                                         for c in navigateur.execute_script.call_args_list))
                    for etat in navigateur.cadres.values():
                        etat["nature"] = ""
                intervention = Mock(side_effect=terminer)
                if mode == "compte":
                    liens = collecter_compte(navigateur, arguments, "media", hashtags=["test"],
                        interact=intervention, validation_initiale=False)
                else:
                    liens = moteur.collect_links(navigateur, arguments,
                        {"hashtag_url": "https://www.tiktok.com/tag/test"},
                        interact=intervention, validation_initiale=False)
                self.assertEqual(liens, ["https://www.tiktok.com/@media/video/123"])
                intervention.assert_called_once()
                navigateur.get.assert_called_once()
                self.assertEqual(navigateur.chemin, ["page"])
