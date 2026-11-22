"""Parcours des hashtags filtré par comptes, sans navigateur réel."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import scraptiktok as moteur
from collecte.comptes import collecter_comptes_par_hashtag


def lien(numero, auteur="lemondefr"):
    return f"https://www.tiktok.com/@{auteur}/video/{numero}"


class AttenteSimulee:
    def __init__(self, navigateur, delai):
        self.navigateur = navigateur

    def until(self, fonction):
        for _ in range(3):
            if resultat := fonction(self.navigateur):
                return resultat
        raise moteur.TimeoutException()


class PresseParHashtags(unittest.TestCase):
    def parcourir(self, pages, comptes=("lemondefr", "franceinfo"), limite=8, precedents=()):
        etat = {"page": 0, "lectures": 0}
        navigateur = Mock()

        def executer(script, *arguments):
            if script == moteur.DISCOVER_JS:
                etat["lectures"] += 1
                page = pages[min(etat["page"], len(pages)-1)]
                return page(etat["lectures"]) if callable(page) else page
            if script == moteur.DEFILER_PUBLICATIONS_JS:
                etat["page"] += 1
                etat["lectures"] = 0
            if script == moteur.TYPE_INTERVENTION_JS:
                return ""
            return False

        navigateur.execute_script.side_effect = executer
        arguments = SimpleNamespace(limit=limite, timeout=.01, delay=0, max_scrolls=20,
                                    idle_rounds=3, interactive=False)
        rapport = {}
        with patch.object(moteur, "WebDriverWait", AttenteSimulee), patch.object(moteur.time, "sleep"), \
             patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            resultat = collecter_comptes_par_hashtag(navigateur, arguments, comptes,
                "#actualité", rapport, liens_precedents=precedents)
        recherche.assert_not_called()
        if rapport["candidats_examines"]:
            navigateur.get.assert_called_once_with("https://www.tiktok.com/tag/actualit%C3%A9")
        return resultat, rapport, navigateur, etat

    def test_autres_auteurs_et_deux_attentes_sans_nouveaute_avant_plus_de_six(self):
        autres = [lien(i, "autre") for i in range(100,106)]
        six = [lien(i) for i in range(200,206)]
        douze = [lien(i) for i in range(200,212)]
        franceinfo = [lien(i, "franceinfo") for i in range(300,308)]
        resultat, rapport, _, etat = self.parcourir(
            [autres, six, six, six, douze, douze + franceinfo])
        self.assertEqual(resultat, douze[:8] + franceinfo)
        self.assertEqual(etat["page"], 5)
        self.assertEqual(rapport["candidats_examines"], 26)
        self.assertEqual(rapport["retenues_par_compte"], {"franceinfo": 8, "lemondefr": 8})
        self.assertEqual(rapport["discovery_stop"], "limit")
        self.assertFalse(rapport["collecte_partielle"])
        self.assertFalse(rapport["exhaustif"])

    def test_limite_par_compte_et_doublons_entre_hashtags(self):
        precedents = [lien(100), lien(101), lien(200, "franceinfo")]
        page = precedents + [lien(100)+"?lang=fr", lien(102), lien(103),
                            lien(201, "franceinfo"), lien(202, "franceinfo"),
                            lien(300, "lemondefr_voisin")]
        resultat, rapport, _, _ = self.parcourir([page], limite=3, precedents=precedents)
        self.assertEqual(resultat, [lien(102), lien(201, "franceinfo"), lien(202, "franceinfo")])
        self.assertEqual(rapport["retenues_par_compte"], {"franceinfo": 3, "lemondefr": 3})

    def test_chargement_differe_pendant_la_meme_attente(self):
        six = [lien(i) for i in range(100,106)]
        suite = six + [lien(106)]
        resultat, _, _, _ = self.parcourir(
            [six, lambda lecture: suite if lecture >= 3 else six], comptes=["lemondefr"], limite=7)
        self.assertEqual(resultat, suite)

    def test_absence_de_medias_dans_le_hashtag_reste_partielle(self):
        resultat, rapport, _, etat = self.parcourir([[lien(100, "autre")]])
        self.assertEqual(resultat, [])
        self.assertGreaterEqual(etat["page"], 3)
        self.assertEqual(rapport["candidats_examines"], 1)
        self.assertTrue(rapport["collecte_partielle"])
        self.assertIn("partielle", rapport["bilan_recherche"])

    def test_second_hashtag_non_rouvert_si_les_limites_sont_deja_atteintes(self):
        precedents = [lien(100), lien(200, "franceinfo")]
        resultat, rapport, navigateur, _ = self.parcourir([[]], limite=1, precedents=precedents)
        self.assertEqual(resultat, [])
        self.assertTrue(rapport["objectif_atteint"])
        navigateur.get.assert_not_called()

    def test_mode_hashtag_general_conserve_les_autres_auteurs_et_sa_limite(self):
        navigateur = Mock()
        urls = [lien(100, "autre"), lien(101, "franceinfo"), lien(102)]
        navigateur.execute_script.side_effect = lambda script: urls if script == moteur.DISCOVER_JS else False
        arguments = SimpleNamespace(limit=2, timeout=.01, delay=0, max_scrolls=2,
                                    idle_rounds=3, interactive=False)
        with patch.object(moteur, "WebDriverWait", AttenteSimulee):
            resultat = moteur.collect_links(navigateur, arguments,
                {"hashtag_url": "https://www.tiktok.com/tag/actualite"})
        self.assertEqual(resultat, urls[:2])
