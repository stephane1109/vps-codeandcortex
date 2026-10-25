"""Régressions du moteur TikWM : aucune connexion réelle au prestataire."""
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from collecte.presse_tikwm import (
    _fiche, _obtenir, _page, TikwmErreur, TikwmRefus429,
    collecter_videos_presse_tikwm,
)
from connect_presse import ConnexionPresse
from webapp import StartRequest, Job, execute_job


def video(numero, compte="lemondefr", **autres):
    fiche = {
        "id": str(7000000000000000000 + numero),
        "author": {"unique_id": compte},
        "title": "Manifestation #France",
        "create_time": 1770000000,
        "play": "https://cdn.example/placeholder.mp4",
        "play_count": 0, "digg_count": 20,
        "comment_count": 8, "share_count": 3,
    }
    fiche.update(autres)
    return fiche


def page(videos, cursor="0", has_more=False):
    return json.dumps({
        "code": 0, "data": {
            "videos": videos, "cursor": cursor, "hasMore": has_more,
        },
    }).encode()


class TestsTikwm(unittest.TestCase):
    def test_pagination_par_compte_sans_secuid_et_metadonnees(self):
        demandes = []
        reponses = iter([
            page([video(1), video(2, compte="autremedia")], "100", True),
            page([video(1), video(3)], "200", False),
        ])

        def obtenir(url):
            demandes.append(url)
            return next(reponses)

        rapport = {}
        progression = []
        urls = collecter_videos_presse_tikwm(
            "lemondefr", 50, rapport, obtenir=obtenir,
            pause=lambda _: None, progress=progression.append,
        )
        self.assertEqual(len(urls), 2)
        self.assertEqual(rapport["pages_tikwm"], 2)
        self.assertEqual(rapport["candidats_examines"], 4)
        self.assertEqual(rapport["auteurs_ecartes"], 1)
        self.assertEqual(progression, [1, 2])
        self.assertEqual(rapport["discovery_stop"], "fin_signalee_par_tikwm")
        self.assertTrue(rapport["collecte_partielle"])
        premier = rapport["metadonnees_api"][str(7000000000000000001)]
        self.assertEqual(premier["source"], "tikwm_tiers")
        self.assertEqual(premier["created_at"][:4], "2026")
        self.assertEqual(premier["engagement"]["vues"]["valeur"], 0)
        self.assertEqual(premier["engagement"]["likes"]["valeur"], 20)
        self.assertEqual(premier["hashtags"], ["France"])
        self.assertEqual(parse_qs(urlparse(demandes[0]).query)["unique_id"], ["lemondefr"])
        self.assertEqual(parse_qs(urlparse(demandes[1]).query)["cursor"], ["100"])
        self.assertTrue(all(urlparse(url).netloc == "tikwm.com" for url in demandes))
        self.assertFalse(any("secUid" in url or "tiktok.com" in url for url in demandes))

    def test_arret_exact_au_nombre_demande(self):
        rapport = {}
        appels = []
        def obtenir(url):
            appels.append(url)
            return page([video(i) for i in range(1, 5)], "50", True)
        liens = collecter_videos_presse_tikwm("lemondefr", 2, rapport,
                                              obtenir=obtenir, pause=lambda _: None)
        self.assertEqual(len(liens), 2)
        self.assertEqual(len(appels), 1)
        self.assertEqual(rapport["discovery_stop"], "limit")
        self.assertFalse(rapport["collecte_partielle"])

    def test_ne_pas_inventer_auteur_ou_metriques(self):
        self.assertIsNone(_fiche({"id": "7000000000000000001"}, "lemondefr"))
        self.assertIsNone(_fiche(video(1, "autremedia"), "lemondefr"))
        self.assertIsNone(_fiche(video(1, images=["https://example/img"], play=""), "lemondefr"))
        fiche = _fiche(video(1, play_count=None, digg_count="0",
                             comment_count=-1, share_count=True), "lemondefr")
        self.assertNotIn("vues", fiche["engagement"])
        self.assertNotIn("commentaires", fiche["engagement"])
        self.assertNotIn("partages", fiche["engagement"])
        self.assertEqual(fiche["engagement"]["likes"]["valeur"], 0)

    def test_429_deuxieme_page_conserve_donnees_premiere_page(self):
        appels = []
        def obtenir(url):
            appels.append(url)
            if len(appels) == 1:
                return page([video(1)], "100", True)
            raise TikwmRefus429("TikWM HTTP 429")
        rapport = {}
        with self.assertRaises(TikwmRefus429):
            collecter_videos_presse_tikwm("lemondefr", 50, rapport,
                                         obtenir=obtenir, pause=lambda _: None)
        self.assertEqual(len(appels), 2)
        self.assertEqual(rapport["pages_tikwm"], 1)
        self.assertEqual(rapport["discovery_stop"], "tikwm_http_429")
        self.assertEqual(len(rapport["discovered_urls"]), 1)
        self.assertEqual(len(rapport["metadonnees_api"]), 1)

    def test_pages_incorrectes_et_codes_refuses(self):
        for contenu in (b"{invalid", b"[]", b'{"code":0,"data":{}}',
                        b'{"code":404,"data":{"videos":[]}}'):
            with self.subTest(contenu=contenu):
                with self.assertRaises(TikwmErreur):
                    _page(contenu)
        with self.assertRaises(TikwmRefus429):
            _page(b'{"code":429}')

    def test_curseur_identique_ne_cree_pas_de_boucle(self):
        appels = []
        def obtenir(url):
            appels.append(url)
            return page([video(1)], "0", True)
        rapport = {}
        collecter_videos_presse_tikwm("lemondefr", 50, rapport, obtenir=obtenir,
                                     pause=lambda _: None)
        self.assertEqual(len(appels), 1)
        self.assertEqual(rapport["discovery_stop"], "curseur_tikwm_repetitif")

    def test_http_429_provient_de_tikwm_pas_de_tiktok(self):
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        with patch("collecte.presse_tikwm.urlopen", side_effect=HTTPError(
            "https://tikwm.com/api/user/posts", 429, "Too Many Requests", {}, None,
        )):
            with self.assertRaises(TikwmRefus429) as erreur:
                _obtenir("https://tikwm.com/api/user/posts?unique_id=lemondefr")
        self.assertIn("TikWM HTTP 429", str(erreur.exception))

    def test_connecteur_sans_navigateur_sauf_commentaires(self):
        for commentaires in (False, True):
            with self.subTest(commentaires=commentaires):
                fabrique = Mock(return_value=Mock())
                options = StartRequest(
                    source_collecte="presse", medias=["lemonde"],
                    presse_moteur="tikwm", collecter_commentaires=commentaires,
                )
                session = ConnexionPresse(Mock(limit=3), fabrique=fabrique)
                session.preparer_sources(options)
                navigateur = session.ouvrir()
                if commentaires:
                    fabrique.assert_called_once()
                    self.assertIsNotNone(navigateur)
                else:
                    fabrique.assert_not_called()
                    self.assertIsNone(navigateur)
                session.fermer()

    def test_worker_presse_utilise_les_metadonnees_sans_chrome(self):
        # Le moteur TikWM doit pouvoir créer le corpus sans navigateur.
        with tempfile.TemporaryDirectory() as repertoire:
            job = Job("a" * 64, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="tikwm", limit=3,
            ), Path(repertoire))
            navigateur = Mock(side_effect=AssertionError("Chrome ne doit pas être ouvert"))
            with patch("collecte.presse_tikwm._obtenir",
                       return_value=page([video(1)], "0", False)), \
                 patch.object(job, "sauvegarder_historique"):
                execute_job(job, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(job.processed, 1)
            self.assertEqual(len(job.records), 1)
            self.assertEqual(job.records[0]["source"], "tikwm_tiers")
            self.assertEqual(job.records[0]["engagement"]["likes"]["valeur"], 20)
            self.assertEqual(job.status, "partial")
            self.assertTrue(job.archive_prete)

    def test_compte_presse_oriente_uniquement_vers_tikwm(self):
        from collecte.comptes import collecter_compte
        fake = Mock(return_value=[])
        with patch("collecte.presse_tikwm.collecter_videos_presse_tikwm", fake), \
             patch("collecte.presse_api.collecter_videos_presse_api") as ancienne, \
             patch("collecte.profil_selenium.collecter_grille_profil") as selenium:
            collecter_compte(None, Mock(limit=3), "lemondefr", {},
                            presse_videos_uniquement=True, presse_moteur="tikwm")
        fake.assert_called_once()
        ancienne.assert_not_called()
        selenium.assert_not_called()


if __name__ == "__main__":
    unittest.main()
