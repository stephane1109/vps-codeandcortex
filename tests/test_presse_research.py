"""Tests sans accès réseau de la Research API officielle et du moteur secUid."""
import json
import os
import unittest
from datetime import date
from unittest.mock import patch, Mock
from urllib.parse import parse_qs
from collecte.presse_research import (
    _dates, _fiche, _jeton, _cache_token, collecter_videos_presse_research,
    ResearchErreur, ResearchAccesRefuse, URL_TOKEN, URL_VIDEOS,
)


def v(numero, compte="lemondefr"):
    return {"id": str(7000000000000000000 + numero), "username": compte,
            "video_description": "Manifestation #France",
            "create_time": 1760000000, "view_count": 0, "like_count": 12,
            "share_count": 3, "comment_count": 2, "hashtag_names": ["France"]}


class TestsResearch(unittest.TestCase):
    def test_fenetres_trente_jours_incluses(self):
        fenetres = list(_dates("2026-07-01", "2026-09-01",
                              aujourd_hui=date(2026, 10, 25)))
        self.assertEqual(fenetres, [
            ("20260803", "20260901"),
            ("20260704", "20260802"),
            ("20260701", "20260703"),
        ])
        self.assertEqual(list(_dates(None, None, aujourd_hui=date(2026, 10, 25))),
                         [("20260926", "20261025")])

    def test_manque_cle_ne_contacte_pas_le_serveur(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ResearchAccesRefuse):
                collecter_videos_presse_research(
                    "lemondefr", 10, {}, requete=Mock(),
                    aujourd_hui=date(2026, 10, 25))

    def test_authentification_secrete_et_token_reutilisable(self):
        _cache_token.update(valeur=None, expire=0.0, identite=None)
        appels = []
        def serveur(url, *, data, headers):
            appels.append((url, parse_qs(data.decode()), headers))
            return {"access_token": "jeton_test", "expires_in": 7200}
        with patch.dict(os.environ, {"TIKTOK_RESEARCH_CLIENT_KEY": "test_cle",
                                     "TIKTOK_RESEARCH_CLIENT_SECRET": "test_secret"}):
            self.assertEqual(_jeton(requete=serveur, maintenant=lambda:100.), "jeton_test")
            self.assertEqual(_jeton(requete=serveur, maintenant=lambda:110.), "jeton_test")
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][0], URL_TOKEN)
        self.assertEqual(appels[0][1]["grant_type"], ["client_credentials"])
        self.assertEqual(appels[0][1]["client_secret"], ["test_secret"])

    def test_pagination_authenticite_et_metadonnees(self):
        appels = []
        def api(url, *, data, headers):
            requete = json.loads(data)
            appels.append((url, requete, headers))
            if len(appels) == 1:
                return {"data":{"videos":[v(1),v(9,"unautreauteur")],
                                "cursor":2,"search_id":"recherche1","has_more":True},
                        "error":{"code":"ok"}}
            return {"data":{"videos":[v(2)], "cursor":3,
                            "search_id":"recherche1","has_more":False},
                    "error":{"code":"ok"}}
        rapport = {}
        urls = collecter_videos_presse_research(
            "lemondefr", 2, rapport, requete=api, jeton="test_token",
            debut="2026-10-01", fin="2026-10-25",
            aujourd_hui=date(2026, 10, 25), pause=lambda _:None)
        self.assertEqual(len(urls), 2)
        self.assertEqual(len(appels), 2)
        self.assertTrue(all(u.startswith(URL_VIDEOS) for u,_,_ in appels))
        self.assertEqual(appels[0][1]["query"]["and"][0]["field_values"], ["lemondefr"])
        self.assertEqual(appels[1][1]["cursor"], 2)
        self.assertEqual(appels[1][1]["search_id"], "recherche1")
        self.assertEqual(rapport["auteurs_ecartes"], 1)
        self.assertEqual(rapport["pages_research"], 2)
        self.assertEqual(rapport["metadonnees_api"][str(7000000000000000001)]
                         ["engagement"]["vues"]["valeur"], 0)
        self.assertEqual(rapport["discovery_stop"], "limit")

    def test_erreur_quota_conserve_pages_precedentes(self):
        numero = 0
        def api(url, *, data, headers):
            nonlocal numero
            numero += 1
            if numero == 1:
                return {"data":{"videos":[v(1)],"has_more":True,
                                "cursor":1,"search_id":"test"}}
            raise ResearchAccesRefuse("Research API HTTP 429")
        rapport = {}
        with self.assertRaises(ResearchAccesRefuse):
            collecter_videos_presse_research(
                "lemondefr", 20, rapport, requete=api, jeton="test",
                aujourd_hui=date(2026,10,25), pause=lambda _:None)
        self.assertEqual(rapport["pages_research"], 1)
        self.assertEqual(len(rapport["discovered_urls"]), 1)
        self.assertEqual(rapport["discovery_stop"], "research_refus_ou_erreur")

    def test_absence_description_ne_necessite_pas_chrome(self):
        fiche = _fiche({**v(1), "video_description":None}, "lemondefr")
        self.assertEqual(fiche["description"], "")
        self.assertEqual(fiche["source"], "research_api_officielle")
        self.assertEqual(fiche["status"], "empty_caption")

    def test_rejet_autres_auteurs(self):
        self.assertIsNone(_fiche(v(1, "autre"), "lemondefr"))


    def test_worker_presse_research_sans_chrome_et_export_txt(self):
        """Les résultats Research utilisent le même pipeline et ne lancent pas Chrome."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from webapp import Job, StartRequest, execute_job
        from connect_presse import ConnexionPresse
        publication = v(1)
        fiche = _fiche(publication, "lemondefr")
        def collecte(compte, limite, rapport, **kwargs):
            self.assertEqual(compte, "lemondefr")
            rapport.update(discovered_urls=[fiche["url"]],
                           metadonnees_api={fiche["id"]:fiche},
                           candidats_examines=1, pages_research=1,
                           navigation_publications="research_officielle",
                           discovery_stop="fin_des_periodes")
            if kwargs.get("progress"):
                kwargs["progress"](1)
            return [fiche["url"]]
        navigateur = Mock(side_effect=AssertionError("Chrome ne doit pas démarrer"))
        with TemporaryDirectory() as dossier:
            job = Job("a" * 64, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=5,
            ), Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecte):
                execute_job(job, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(job.processed, 1)
            self.assertEqual(len(job.records), 1)
            self.assertEqual(job.records[0]["source"], "research_api_officielle")
            self.assertIn("Manifestation", job.path.read_text(encoding="utf-8"))

    def test_research_cle_secrete_non_presente_en_sortie_health(self):
        from tempfile import TemporaryDirectory
        from fastapi.testclient import TestClient
        from webapp import create_app, Manager
        with TemporaryDirectory() as dossier, \
             patch.dict(os.environ, {"TIKTOK_RESEARCH_CLIENT_KEY": "cle_test",
                                     "TIKTOK_RESEARCH_CLIENT_SECRET": "secret_test"}), \
             patch("urllib.request.urlopen") as controle:
            controle.return_value.__enter__.return_value = Mock()
            with TestClient(create_app(Manager(data_dir=dossier))) as client:
                rep = client.get("/healthz")
        self.assertEqual(rep.status_code, 200)
        self.assertTrue(rep.json()["research_configuree"])
        self.assertNotIn("secret_test", rep.text)
        self.assertNotIn("cle_test", rep.text)


if __name__ == "__main__":
    unittest.main()
