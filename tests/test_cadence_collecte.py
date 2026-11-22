"""Cadence des hashtags : aucune attente IA implicite, ni pause cumulée inutile."""
import argparse
import json
import unittest
from unittest.mock import Mock, patch

import scraptiktok as moteur
from webapp import attendre_intervalle_lecture

URL = 'https://www.tiktok.com/@test/video/1234567890'


class Horloge:
    def __init__(self):
        self.temps = 0.0

    def maintenant(self):
        return self.temps

    def attendre(self, duree):
        self.temps += duree


class TestsCadenceCollecte(unittest.TestCase):
    def test_legende_json_lue_sans_plus_ni_attente_ia(self):
        navigateur = Mock()
        page = {'url': URL, 'payloads': [json.dumps({'id': '1234567890', 'desc': 'Texte complet #test'})]}
        navigateur.execute_script.return_value = page
        with patch.object(moteur, 'open_page'), patch.object(moteur, 'fermer_invitation_connexion'), \
             patch.object(moteur, 'captcha_present', return_value=False), \
             patch.object(moteur, 'completer_resume_ia') as ia, patch.object(moteur.time, 'sleep') as attente:
            publication = moteur.read_post(navigateur, URL, argparse.Namespace(timeout=20, interactive=False))
        self.assertEqual(publication['description'], 'Texte complet #test')
        navigateur.execute_script.assert_called_once_with(moteur.PAGE_JS, '1234567890', False)
        attente.assert_not_called()
        ia.assert_not_called()

    def test_repli_dom_conserve_le_depliage_de_la_legende(self):
        navigateur = Mock()
        lectures = []
        def executer(script, *_):
            if script == moteur.DEPLIER_LEGENDE_JS:
                return len(lectures) == 1
            lectures.append(True)
            return {'url': URL, 'description': 'Texte tronqué' if len(lectures) == 1 else 'Texte complet après Plus'}
        navigateur.execute_script.side_effect = executer
        with patch.object(moteur, 'open_page'), patch.object(moteur, 'fermer_invitation_connexion'), \
             patch.object(moteur, 'captcha_present', return_value=False), patch.object(moteur.time, 'sleep'):
            publication = moteur.read_post(navigateur, URL, argparse.Namespace(timeout=20, interactive=False))
        self.assertEqual(publication['description'], 'Texte complet après Plus')

    def test_lecture_lente_compte_dans_intervalle_rapide_reste_limitee(self):
        horloge = Horloge()
        pause = Mock(side_effect=horloge.attendre)
        with patch('webapp.time.monotonic', side_effect=horloge.maintenant):
            debut = attendre_intervalle_lecture(None, 3, pause)
            pause.assert_not_called()
            horloge.attendre(1)
            debut = attendre_intervalle_lecture(debut, 3, pause)
            pause.assert_called_once_with(2)
            self.assertEqual(debut, 3)
            horloge.attendre(8)
            self.assertEqual(attendre_intervalle_lecture(debut, 3, pause), 11)
            self.assertEqual(pause.call_count, 1)

    def simuler_decouverte(self, arrivee_tardive=None):
        horloge = Horloge()
        navigateur = Mock()
        def executer(script):
            if script == moteur.DISCOVER_JS:
                return [URL] + ([URL.replace('1234567890', '9999999999')]
                    if arrivee_tardive is not None and horloge.temps >= arrivee_tardive else [])
            return False
        navigateur.execute_script.side_effect = executer
        class Attente:
            def __init__(self, navigateur, delai):
                self.navigateur, self.delai = navigateur, delai
            def until(self, condition):
                fin = horloge.temps + self.delai
                while True:
                    if condition(self.navigateur): return True
                    if horloge.temps >= fin: raise moteur.TimeoutException()
                    horloge.attendre(min(0.5, fin - horloge.temps))
        args = moteur.parse_args(['test', '--limit', '2'])
        rapport = {'hashtag_url': 'https://www.tiktok.com/tag/test'}
        with patch.object(moteur, 'WebDriverWait', Attente), \
             patch.object(moteur.time, 'monotonic', side_effect=horloge.maintenant), \
             patch.object(moteur.time, 'sleep', side_effect=horloge.attendre):
            liens = moteur.collect_links(navigateur, args, rapport)
        return liens, rapport, horloge.temps

    def test_fin_de_liste_confirmee_en_un_delai_complet(self):
        liens, rapport, duree = self.simuler_decouverte()
        self.assertEqual(liens, [URL])
        self.assertEqual(rapport['discovery_stop'], 'no_new_links')
        self.assertEqual(rapport['defilements_effectues'], 3)
        self.assertEqual(duree, 20)

    def test_lot_tardif_apres_trois_defilements_est_conserve(self):
        liens, rapport, duree = self.simuler_decouverte(arrivee_tardive=18)
        self.assertEqual(len(liens), 2)
        self.assertEqual(rapport['discovery_stop'], 'limit')
        self.assertEqual(duree, 18)


if __name__ == '__main__':
    unittest.main()
