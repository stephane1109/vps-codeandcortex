"""Tests des commentaires TikTok Research sans réseau ni navigateur."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from collecte.researchapi import (
    URL_COMMENTAIRES, ResearchAccesRefuse, collecter_commentaires_research,
    normaliser_commentaire_research,
)


class TestResearchCommentaires(unittest.TestCase):
    def setUp(self):
        self.publication = {
            "id": "7702367667616746785",
            "engagement": {"commentaires": {"valeur": 25}},
        }

    def test_commentaires_officiels_et_champs_demandes(self):
        requetes = []

        def simuler(url, *, data, headers):
            requetes.append((url, json.loads(data), headers))
            return {"data": {"comments": [
                {"id": 123456789, "video_id": 7702367667616746785,
                 "text": "Premier commentaire", "like_count": 0,
                 "reply_count": 0, "parent_comment_id": 7702367667616746785,
                 "create_time": 1760000000},
                {"id": 123456790, "video_id": 7702367667616746785,
                 "text": "Deuxième commentaire", "like_count": 12,
                 "reply_count": 0, "create_time": 1760000010},
                {"id": 123456791, "video_id": 999, "text": "Autre vidéo"},
            ], "cursor": 3, "has_more": False}}
        resultat = collecter_commentaires_research(
            self.publication, limite=10, requete=simuler,
            jeton="JETON_SIMULE", pause=lambda _: None)
        self.assertEqual([c["id"] for c in resultat["commentaires"]],
                         ["123456789", "123456790"])
        self.assertEqual(resultat["commentaires"][0]["likes"]["valeur"], 0)
        self.assertFalse(resultat["commentaires"][0]["est_reponse"])
        self.assertEqual(resultat["commentaires"][0]["source"], "research_api_officielle")
        self.assertEqual(resultat["annonces"], 25)
        self.assertEqual(resultat["statut"], "complet")
        self.assertTrue(resultat["exhaustif"])
        self.assertTrue(requetes[0][0].startswith(URL_COMMENTAIRES))
        self.assertIn("parent_comment_id", requetes[0][0])
        self.assertEqual(requetes[0][1]["video_id"], 7702367667616746785)
        self.assertNotIn("comment_id", requetes[0][1])
        self.assertEqual(requetes[0][2]["Authorization"], "Bearer JETON_SIMULE")
        self.assertFalse(resultat["diagnostic"]["repli_selenium"])

    def test_reponses_sont_demandees_par_comment_id_et_rattachees(self):
        appels = []

        def simuler(url, *, data, headers):
            payload = json.loads(data)
            appels.append(payload)
            if "video_id" in payload:
                return {"data": {"comments": [
                    {"id": 100, "video_id": 7702367667616746785,
                     "text": "Parent", "reply_count": 2},
                ], "has_more": False, "cursor": 1}}
            self.assertEqual(payload["comment_id"], 100)
            self.assertNotIn("video_id", payload)
            return {"data": {"comments": [
                {"id": 101, "parent_comment_id": 100,
                 "text": "Une réponse", "like_count": 4},
                {"id": 102, "parent_comment_id": 999,
                 "text": "Réponse d'un autre parent"},
            ], "has_more": False, "cursor": 2}}
        resultat = collecter_commentaires_research(
            self.publication, limite=5, reponses=True,
            jeton="JETON_SIMULE", requete=simuler, pause=lambda _: None)
        self.assertEqual([c["id"] for c in resultat["commentaires"]], ["100", "101"])
        self.assertEqual(resultat["commentaires"][1]["parent_id"], "100")
        self.assertTrue(resultat["commentaires"][1]["parent_collecte"])
        self.assertEqual(len(appels), 2)
        self.assertFalse(resultat["exhaustif"])

    def test_refus_research_suspend_la_collecte_sans_repli(self):
        appels = []

        def simuler(url, *, data, headers):
            appels.append(url)
            raise ResearchAccesRefuse("quota refuse")
        resultat = collecter_commentaires_research(
            self.publication, limite=30, jeton="SIMULE",
            requete=simuler, pause=lambda _: None)
        self.assertEqual(len(appels), 1)
        self.assertEqual(resultat["statut"], "acces_refuse")
        self.assertTrue(resultat["bloquer_requetes"])
        self.assertEqual(resultat["commentaires"], [])
        self.assertNotIn("SIMULE", json.dumps(resultat))

    def test_pagination_sans_repetition(self):
        appels = []

        def simuler(url, *, data, headers):
            requete = json.loads(data)
            appels.append(requete)
            if len(appels) == 1:
                return {"data": {"comments": [
                    {"id": 100, "text": "Un"},
                ], "has_more": True, "cursor": 1}}
            return {"data": {"comments": [
                {"id": 100, "text": "Un"},
                {"id": 101, "text": "Deux"},
            ], "has_more": False, "cursor": 3}}
        resultat = collecter_commentaires_research(
            self.publication, limite=4, jeton="SIMULE",
            requete=simuler, pause=lambda _: None)
        self.assertEqual(len(resultat["commentaires"]), 2)
        self.assertEqual(appels[1]["cursor"], 1)
        self.assertEqual(resultat["statut"], "complet")

    def test_pagination_automatique_collecte_plus_de_500_commentaires(self):
        appels = []

        def simuler(url, *, data, headers):
            requete = json.loads(data)
            curseur = requete["cursor"]
            appels.append(requete)
            commentaires = [
                {"id": 100000 + i, "video_id": int(self.publication["id"]),
                 "text": f"Commentaire numéro {i}"}
                for i in range(curseur, min(curseur + 100, 600))
            ]
            return {"data": {"comments": commentaires,
                             "has_more": curseur + 100 < 600,
                             "cursor": curseur + len(commentaires)}}

        resultat = collecter_commentaires_research(
            self.publication, jeton="SIMULE", requete=simuler,
            pause=lambda _: None)
        self.assertEqual(len(resultat["commentaires"]), 600)
        self.assertEqual(len(appels), 6)
        self.assertEqual(resultat["statut"], "complet")
        self.assertTrue(resultat["exhaustif"])
        self.assertTrue(resultat["diagnostic"]["pagination_automatique"])

    def test_pagination_automatique_respecte_la_borne_de_pages(self):
        appels = []

        def simuler(url, *, data, headers):
            requete = json.loads(data)
            appels.append(requete)
            curseur = requete["cursor"]
            return {"data": {"comments": [
                {"id": 200000 + curseur + i,
                 "video_id": int(self.publication["id"]), "text": str(i)}
                for i in range(100)], "cursor": curseur + 100,
                "has_more": True}}

        with patch("collecte.researchapi.MAX_PAGES", 3):
            resultat = collecter_commentaires_research(
                self.publication, jeton="SIMULE", requete=simuler,
                pause=lambda _: None)
        self.assertEqual(len(appels), 3)
        self.assertEqual(len(resultat["commentaires"]), 300)
        self.assertEqual(resultat["statut"], "pagination_incomplete")
        self.assertFalse(resultat["exhaustif"])

    def test_rejet_identifiant_externe(self):
        self.assertIsNone(normaliser_commentaire_research(
            {"id": "10", "video_id": "123", "text": "Autre vidéo"},
            self.publication["id"]))

    def test_worker_presse_research_collecte_commentaires_sans_chrome(self):
        from webapp import Job, StartRequest, execute_job
        from collecte.researchapi import _fiche

        video = {
            "id": self.publication["id"], "username": "lemondefr",
            "video_description": "Publication #manifestation",
            "create_time": 1760000000, "hashtag_names": ["manifestation"],
        }
        fiche = _fiche(video, "lemondefr")
        def simuler_videos(compte, limite, rapport, **kwargs):
            rapport.update(
                discovered_urls=[fiche["url"]],
                metadonnees_api={fiche["id"]: fiche},
                candidats_examines=1, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [fiche["url"]]
        def simuler_commentaires(publication, limite=None, reponses=False, **kwargs):
            self.assertIsNone(limite)
            self.assertEqual(publication["id"], fiche["id"])
            self.assertEqual(kwargs["credentiels"], ("test_key", "test_secret"))
            self.assertTrue(reponses)
            return {"commentaires": [{
                "id": "101", "publication_id": fiche["id"],
                "texte": "Commentaire Research", "parent_id": None,
                "est_reponse": False, "source": "research_api_officielle",
            }], "statut": "complet", "recuperes": 1,
                "exhaustif": False, "bloquer_requetes": False,
                "source": "research_api_officielle"}
        navigateur = Mock(side_effect=AssertionError("Le navigateur est interdit"))
        with tempfile.TemporaryDirectory() as dossier:
            travail = Job("test" * 16, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=5,
                collecter_commentaires=True, collecter_reponses=True,
                research_client_key="test_key", research_client_secret="test_secret",
            ), Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=simuler_videos), patch(
                       "collecte.researchapi.collecter_commentaires_research",
                       side_effect=simuler_commentaires) as recueillir:
                execute_job(travail, driver_factory=navigateur)
        navigateur.assert_not_called()
        recueillir.assert_called_once()
        self.assertEqual(len(travail.commentaires), 1)
        self.assertEqual(travail.records[0]["collecte_commentaires"]["source"],
                         "research_api_officielle")
        self.assertIsNone(travail.settings.research_client_key)


if __name__ == "__main__":
    unittest.main()
