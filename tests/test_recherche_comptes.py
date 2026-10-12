"""Chargements successifs simulés ; aucun navigateur ni accès TikTok nécessaire."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import scraptiktok as moteur
from collecte.recherche_comptes import collecter_recherche_compte
from collecte.recherche_comptes import LIENS_RECHERCHE_JS
from collecte.pagination_recherche import defiler_resultats
from collecte.reseau_recherche import ObservationRecherche, extraire_page_recherche


def lien(numero, auteur="media"):
    return f"https://www.tiktok.com/@{auteur}/video/{numero}"


class AttenteSimulee:
    def __init__(self, navigateur, delai):
        self.navigateur = navigateur

    def until(self, fonction):
        for _ in range(3):
            if resultat := fonction(self.navigateur):
                return resultat
        raise moteur.TimeoutException()


class RechercheProgressive(unittest.TestCase):
    def parcourir(self, pages, limite=18, donnees=None, suite=None):
        etat = {"page": 0, "scans": 0}
        pilote = Mock()
        pilote.current_url = "https://www.tiktok.com/search/video?q=%40media"
        def script(code, *arguments):
            if code == LIENS_RECHERCHE_JS:
                etat["scans"] += 1
                page = pages[min(etat["page"], len(pages)-1)]
                return page(etat["scans"]) if callable(page) else page
            if code == moteur.DONNEES_PUBLICATIONS_JS:
                return [json.dumps(donnees)] if donnees else []
            if code == moteur.TYPE_INTERVENTION_JS:
                return ""
            return False
        pilote.execute_script.side_effect = script
        bas = {"position": 600, "hauteur": 1200, "fenetre": 600, "fin": True}
        def defiler(*args, **options):
            etat["page"] += 1
            etat["scans"] = 0
            return {"avant": dict(bas), "apres": dict(bas), "methode": "simulee"}
        observation = Mock()
        observation.lire.return_value = []
        observation.derniere_page = {"suite": suite, "curseur": "10"}
        arguments = SimpleNamespace(limit=limite, timeout=.01, delay=0, max_scrolls=2,
                                    idle_rounds=1, interactive=False)
        rapport, progression = {"compte_attendu": "media"}, []
        with patch("collecte.recherche_comptes.ObservationRecherche", return_value=observation), \
             patch("collecte.recherche_comptes.WebDriverWait", AttenteSimulee), \
             patch("collecte.recherche_comptes.defiler_resultats", side_effect=defiler), \
             patch("collecte.recherche_comptes.etat_resultats", return_value=bas):
            resultat = collecter_recherche_compte(pilote, arguments, rapport, progress=progression.append)
        pilote.get.assert_called_once_with("https://www.tiktok.com/search/video?q=%40media")
        observation.fermer.assert_called_once()
        return resultat, rapport, etat, progression

    def test_six_puis_deux_chargements_vides_puis_dix_huit(self):
        six = [lien(i) for i in range(100,106)]
        douze = [lien(i) for i in range(100,112)]
        dix_huit = [lien(i) for i in range(100,118)]
        resultat, rapport, etat, progression = self.parcourir([six, six, six, douze, dix_huit])
        self.assertEqual(resultat, dix_huit)
        self.assertEqual(etat["page"], 4)
        self.assertIn(6, progression)
        self.assertIn(12, progression)
        self.assertEqual(rapport["discovery_stop"], "limit")
        self.assertFalse(rapport["exhaustif"])
        self.assertFalse(rapport["collecte_partielle"])

    def test_autres_auteurs_doublons_et_remplacement_des_cartes(self):
        debut = [lien(i, "autre") for i in range(100,106)]
        milieu = [lien(200), lien(201), lien(200)+"?lang=fr", lien(202, "media2")]
        fin = [lien(201), lien(203), lien(204)]
        resultat, rapport, _, _ = self.parcourir([debut, milieu, fin], limite=4)
        self.assertEqual(resultat, [lien(200), lien(201), lien(203), lien(204)])
        self.assertEqual(rapport["candidats_examines"], 11)
        self.assertEqual(rapport["auteurs_ecartes"], 7)

    def test_chargement_asynchrone_pendant_attente(self):
        six = [lien(i) for i in range(100,106)]
        suite = six + [lien(106)]
        resultat, _, _, _ = self.parcourir([six, lambda lecture: suite if lecture >= 3 else six], limite=7)
        self.assertEqual(resultat, suite)

    def test_fin_annoncee_reste_partielle_apres_plusieurs_essais(self):
        six = [lien(i) for i in range(100,106)]
        resultat, rapport, etat, _ = self.parcourir([six], suite=False)
        self.assertEqual(resultat, six)
        self.assertGreaterEqual(etat["page"], 3)
        self.assertEqual(rapport["discovery_stop"], "fin_recherche_signalee")
        self.assertTrue(rapport["collecte_partielle"])
        self.assertIn("partielle", rapport["bilan_recherche"])

    def test_auteur_des_donnees_prime_sur_un_lien_contradictoire(self):
        donnee = {"id":"100", "author":{"uniqueId":"autre"}, "desc":"Texte", "video":{"duration":2}}
        resultat, rapport, _, _ = self.parcourir([[lien(100), lien(101)]], limite=2, donnees=donnee)
        self.assertEqual(resultat, [lien(101)])
        self.assertEqual(rapport["auteurs_ecartes"], 1)

    def test_comptes_seulement_etrangers_n_est_pas_un_profil_vide(self):
        resultat, rapport, _, _ = self.parcourir([[lien(100, "autre")]])
        self.assertEqual(resultat, [])
        self.assertEqual(rapport["candidats_examines"], 1)
        self.assertTrue(rapport["collecte_partielle"])

    def test_reponse_reseau_auteur_et_pagination(self):
        page = extraire_page_recherche({"status_code":0, "has_more":1, "cursor":12, "data":[
            {"item":{"id":"123", "author":{"uniqueId":"autre"}, "desc":"#media", "video":{"id":"123"}}}]})
        self.assertEqual(page["liens"], [lien(123, "autre")])
        self.assertTrue(page["suite"])
        self.assertEqual(page["curseur"], "12")
        observation = ObservationRecherche(Mock(), "media", {})
        self.assertTrue(observation.accepter_reponse(urlsplit("https://www.tiktok.com/api/search/item/full/?keyword=%40media")))
        self.assertFalse(observation.accepter_reponse(urlsplit("https://www.tiktok.com/api/search/item/full/?keyword=%40autre")))
        self.assertFalse(observation.accepter_reponse(urlsplit("https://www.tiktok.com/api/post/item_list/")))
        self.assertIsNone(extraire_page_recherche({"item_list":[]})["suite"])

    def test_page_suivante_utilise_le_bouton_disponible(self):
        pilote, bouton = Mock(), Mock()
        etat = {"position":600, "hauteur":1200, "fenetre":600, "fin":True}
        pilote.execute_script.side_effect = [etat, bouton, etat]
        with patch("collecte.pagination_recherche.ActionChains") as gestes:
            resultat = defiler_resultats(pilote, reprendre=True)
        bouton.click.assert_called_once()
        gestes.assert_not_called()
        self.assertEqual(resultat["methode"], "page_suivante")

    def test_hashtag_conserve_son_parcours(self):
        args = SimpleNamespace(limit=1, timeout=.01, delay=0, max_scrolls=2, idle_rounds=1, interactive=False)
        pilote = Mock()
        pilote.execute_script.side_effect = lambda code: [lien(100)] if code == moteur.DISCOVER_JS else False
        with patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            resultat = moteur.collect_links(pilote, args, {"hashtag_url":"https://www.tiktok.com/tag/test"})
        self.assertEqual(resultat, [lien(100)])
        recherche.assert_not_called()
        pilote.get.assert_called_once_with("https://www.tiktok.com/tag/test")

    def test_redirection_vers_profil_ne_decouvre_aucune_video(self):
        args = SimpleNamespace(limit=1, timeout=.01, delay=0, max_scrolls=2, idle_rounds=1, interactive=False)
        pilote = Mock()
        pilote.current_url = "https://www.tiktok.com/@media"
        pilote.execute_script.side_effect = lambda code, *a: [lien(100)] if code == LIENS_RECHERCHE_JS else False
        rapport = {"compte_attendu": "media"}
        with patch("collecte.recherche_comptes.ObservationRecherche") as observation, \
             patch("collecte.recherche_comptes.WebDriverWait", AttenteSimulee):
            with self.assertRaises(RuntimeError):
                collecter_recherche_compte(pilote, args, rapport)
        pilote.get.assert_called_once_with("https://www.tiktok.com/search/video?q=%40media")
        observation.return_value.lire.assert_not_called()
        self.assertFalse(any(c.args[0] == LIENS_RECHERCHE_JS for c in pilote.execute_script.call_args_list))
        self.assertEqual(rapport["diagnostic"]["code"], "recherche_redirigee")
