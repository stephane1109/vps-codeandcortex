"""Ciblage compte + hashtag et défilement simulé, sans navigateur réel."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import scraptiktok as moteur
from collecte.comptes import collecter_compte
from collecte.recherche_comptes import adresse_recherche


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


class CiblageComptes(unittest.TestCase):
    def pilote(self, pages, erreur=False, redirection=False):
        navigateur = Mock()
        etat = {"requete": "", "page": 0}
        def ouvrir(url):
            etat.update(requete=parse_qs(urlsplit(url).query)["q"][0], page=0)
            navigateur.current_url = "https://www.tiktok.com/tag/manifestation" if redirection else url
        def script(code, *arguments):
            if code == moteur.DISCOVER_JS:
                serie = pages.get(etat["requete"], [[]])
                return serie[min(etat["page"], len(serie)-1)]
            if code == moteur.DEFILER_PUBLICATIONS_JS:
                etat["page"] += 1
            if code == moteur.DIAGNOSTIC_JS:
                return {"erreur_tiktok": erreur}
            if code == moteur.TYPE_INTERVENTION_JS:
                return ""
            return False
        navigateur.get.side_effect = ouvrir
        navigateur.execute_script.side_effect = script
        return navigateur

    def arguments(self, limite=10):
        return SimpleNamespace(limit=limite, max_scrolls=40, idle_rounds=3,
                               timeout=.01, delay=0, interactive=False)

    def test_requete_contient_compte_et_hashtag_normalises(self):
        self.assertEqual(adresse_recherche("@LeMondeFR", "#lycéen"),
                         "https://www.tiktok.com/search/video?q=lyc%C3%A9en%20lemondefr")

    def test_compte_cible_plus_de_six_videos_apres_deux_chargements_sans_nouveaute(self):
        six = [lien(i) for i in range(100,106)]
        douze = [lien(i) for i in range(100,112)]
        autres = [lien(i, "autre") for i in range(200,206)]
        pilote = self.pilote({"manifestation lemondefr": [autres, six, six, six, douze]})
        rapport, progressions = {}, []
        with patch.object(moteur, "WebDriverWait", AttenteSimulee), patch.object(moteur.time, "sleep"):
            resultat = collecter_compte(pilote, self.arguments(), "lemondefr", rapport,
                hashtags=["manifestation"], progress=lambda nombre: progressions.append((nombre, rapport.get("requete_recherche"))))
        pilote.get.assert_called_once_with(adresse_recherche("lemondefr", "manifestation"))
        self.assertEqual(resultat, douze[:10])
        self.assertEqual(rapport["candidats_examines"], 18)
        self.assertEqual(rapport["auteurs_ecartes"], 6)
        self.assertEqual(rapport["auteurs_dans_liens"], {"autre": 6, "lemondefr": 12})
        self.assertEqual(rapport["defilements_effectues"], 4)
        self.assertIn((6, "manifestation lemondefr"), progressions)
        self.assertFalse(rapport["collecte_partielle"])

    def test_deux_hashtags_meme_compte_meme_session_et_quota_cumule(self):
        pilote = self.pilote({
            "manifestation lemondefr": [[lien(100), lien(101)]],
            "lycéen lemondefr": [[lien(100), lien(102), lien(103), lien(200, "autre")]],
        })
        rapport = {}
        with patch.object(moteur, "WebDriverWait", AttenteSimulee), patch.object(moteur.time, "sleep"):
            resultat = collecter_compte(pilote, self.arguments(3), "@lemondefr", rapport,
                                       hashtags=["manifestation", "lycéen"])
        self.assertEqual(resultat, [lien(100), lien(101), lien(102)])
        self.assertEqual([c.args[0] for c in pilote.get.call_args_list],
                         [adresse_recherche("lemondefr", h) for h in ("manifestation", "lycéen")])
        self.assertEqual([r["requete_recherche"] for r in rapport["recherches_hashtags"]],
                         ["manifestation lemondefr", "lycéen lemondefr"])
        self.assertEqual(rapport["retenues_par_compte"], {"lemondefr": 3})

    def test_erreur_tiktok_recharge_seulement_la_requete_ciblee(self):
        pilote, rapport = self.pilote({}, erreur=True), {}
        with patch.object(moteur, "WebDriverWait", AttenteSimulee):
            with self.assertRaises(RuntimeError):
                collecter_compte(pilote, self.arguments(), "lemondefr", rapport, hashtags=["manifestation"])
        self.assertEqual([c.args[0] for c in pilote.get.call_args_list],
                         [adresse_recherche("lemondefr", "manifestation")] * 2)
        self.assertEqual(rapport["diagnostic"]["code"], "erreur_tiktok")
        self.assertEqual(rapport["recherches_en_echec"], 1)

    def test_redirection_ne_transforme_pas_la_recherche_en_hashtag_general(self):
        pilote = self.pilote({"manifestation lemondefr": [[lien(100)]]}, redirection=True)
        rapport = {}
        with patch.object(moteur, "WebDriverWait", AttenteSimulee):
            with self.assertRaises(RuntimeError):
                collecter_compte(pilote, self.arguments(), "lemondefr", rapport, hashtags=["manifestation"])
        self.assertFalse(any(c.args[0] == moteur.DISCOVER_JS for c in pilote.execute_script.call_args_list))
        self.assertEqual(rapport["diagnostic"]["code"], "recherche_redirigee")

    def test_un_hashtag_en_echec_conserve_les_resultats_de_l_autre(self):
        rapport = {}
        def decouvrir(navigateur, arguments, courant, **options):
            if courant["hashtag_recherche"] == "manifestation":
                courant["diagnostic"] = {"code": "erreur_tiktok"}
                raise RuntimeError("Erreur TikTok")
            courant.update(candidats_ids=["100"], discovered_urls=[lien(100)])
            return [lien(100)]
        with patch.object(moteur, "collect_links", side_effect=decouvrir):
            resultat = collecter_compte(Mock(), self.arguments(), "lemondefr", rapport,
                                       hashtags=["manifestation", "lycéen"])
        self.assertEqual(resultat, [lien(100)])
        self.assertEqual(rapport["recherches_en_echec"], 1)
        self.assertTrue(rapport["collecte_partielle"])
        self.assertEqual(rapport["recherches_hashtags"][0]["diagnostic"]["code"], "erreur_tiktok")

    def test_erreur_tardive_conserve_les_liens_deja_decouverts_du_compte(self):
        rapport = {}
        def decouvrir(navigateur, arguments, courant, **options):
            courant.update(discovered_urls=[lien(100), lien(200, "autre")],
                           candidats_ids=["100", "200"], diagnostic={"code": "erreur_tiktok"})
            raise RuntimeError("Chargement interrompu")
        with patch.object(moteur, "collect_links", side_effect=decouvrir):
            resultat = collecter_compte(Mock(), self.arguments(), "lemondefr", rapport,
                                       hashtags=["manifestation"])
        self.assertEqual(resultat, [lien(100)])
        self.assertEqual(rapport["discovered_urls"], [lien(100)])
        self.assertEqual(rapport["recherches_en_echec"], 1)
        self.assertTrue(rapport["collecte_partielle"])

    def test_aucun_media_dans_les_liens_signale_les_auteurs_effectivement_recus(self):
        pilote = self.pilote({"manifestation lemondefr": [[lien(100, "autre"), lien(101, "autre")]]})
        rapport = {}
        with patch.object(moteur, "WebDriverWait", AttenteSimulee), patch.object(moteur.time, "sleep"):
            resultat = collecter_compte(pilote, self.arguments(), "lemondefr", rapport,
                                       hashtags=["manifestation"])
        self.assertEqual(resultat, [])
        self.assertEqual(rapport["auteurs_dans_liens"], {"autre": 2})
        self.assertEqual(rapport["candidats_examines"], 2)
        self.assertEqual(rapport["discovery_stop"], "no_new_links")
        self.assertEqual(rapport["defilements_effectues"], 3)

    def test_requete_reproduit_le_cas_fourni_par_l_utilisateur(self):
        exemple = "https://www.tiktok.com/@lemondefr/video/7691745512910900513?q=manifestation%20lemondefr&t=1791820038871"
        recherche = adresse_recherche("@lemondefr", "#manifestation")
        self.assertEqual(parse_qs(urlsplit(recherche).query)["q"],
                         parse_qs(urlsplit(exemple).query)["q"])
        self.assertEqual(moteur.canonical_post(exemple),
                         ("7691745512910900513", "https://www.tiktok.com/@lemondefr/video/7691745512910900513", "lemondefr"))
