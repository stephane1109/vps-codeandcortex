"""Vérifier les exclusions NOT, le filtrage local et les exports."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from collecte.exclusion_hashtags import hashtags_a_exclure
from collecte.researchapi import collecter_videos_presse_research, _fiche
from webapp import StartRequest, Job, execute_job


class TestsExclusionHashtags(unittest.TestCase):
    def test_correspondance_exacte_insensible_a_la_casse(self):
        publication = {"description": "Annonce #Publicite #été autre publicité",
                       "hashtags": ["#MANIFESTATION"]}
        self.assertEqual(
            hashtags_a_exclure(publication, ["publicite", "manifestation"]),
            ["publicite", "manifestation"])
        self.assertFalse(hashtags_a_exclure(
            {"description": "publicite et #publicitaire"}, ["publicite"]))
        self.assertFalse(hashtags_a_exclure(
            {"description": "publication sans tag"}, ["publicite"]))
        self.assertEqual(hashtags_a_exclure(
            {"hashtags": ["#humour"], "description": ""}, ["humour"]), ["humour"])

    def test_validation_et_conflits_avec_recherche(self):
        p = StartRequest(
            source_collecte="hashtags", hashtags_saisis=["manifestation"],
            hashtags_exclus=["#Publicite", "publicite", "#HUMOUR"])
        self.assertEqual(p.hashtags_exclus, ["Publicite", "HUMOUR"])
        self.assertEqual(p.model_dump()["hashtags_exclus"], ["Publicite", "HUMOUR"])
        with self.assertRaisesRegex(ValueError, "maximum 10"):
            StartRequest(hashtag="manifestation",
                         hashtags_exclus=[f"exclu{i}" for i in range(11)])
        with self.assertRaisesRegex(ValueError, "recherché et exclu"):
            StartRequest(hashtag="manifestation",
                         hashtags_exclus=["#MANIFESTATION"])
        with self.assertRaisesRegex(ValueError, "recherché et exclu"):
            StartRequest(source_collecte="presse", medias=["lemonde"],
                         croiser_hashtag_presse=True,
                         hashtag_presse="publicite",
                         hashtags_exclus=["#PUBLICITE"])
        StartRequest(source_collecte="presse", medias=["lemonde"],
                     hashtags_exclus=["#publicite"])

    def test_research_not_in_et_verification_locales(self):
        appels = []
        def serveur(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            def video(numero, hashtags):
                return {"id": str(7000000000000000000+numero),
                        "username": "lemondefr", "video_description": "Légende",
                        "create_time": 1760000000, "hashtag_names": hashtags}
            return {"data": {"videos": [
                video(1, ["manifestation", "publicite"]),
                video(2, ["manifestation"]),
                video(3, ["manifestation", "humour"])
            ], "has_more": False}}
        rapport = {}
        urls = collecter_videos_presse_research(
            "lemondefr", 10, rapport, requete=serveur, jeton="test",
            exclusions=["publicite", "humour"],
            aujourd_hui=__import__("datetime").date(2026, 10, 25),
            pause=lambda _: None)
        self.assertEqual(appels[0]["query"]["not"], [
            {"field_name": "hashtag_name", "operation": "IN",
             "field_values": ["publicite", "humour"]}])
        self.assertEqual(len(urls), 1)
        self.assertEqual(rapport["exclus_hashtags_api"], 2)
        self.assertEqual(len(rapport["metadonnees_api"]), 1)

    def test_compatibilite_api_sans_exclusions(self):
        def serveur(url, *, data, headers):
            corps = json.loads(data)
            self.assertNotIn("not", corps["query"])
            return {"data": {"videos": [], "has_more": False}}
        collecter_videos_presse_research(
            "lemondefr", 10, {}, requete=serveur, jeton="test",
            aujourd_hui=__import__("datetime").date(2026, 10, 25))

    def test_worker_research_pas_de_commentaires_des_videos_exclues(self):
        def video(numero, description, hashtags):
            return _fiche({
                "id": str(7000000000000000000+numero),
                "username": "lemondefr",
                "video_description": description,
                "create_time": 1760000000,
                "hashtag_names": hashtags,
            }, "lemondefr")
        fiches = [
            video(1, "Annonce sponsorisée #publicite", ["publicite"]),
            video(2, "Manifestation lycéenne #manifestation", ["manifestation"]),
        ]
        def collecte(compte, limite, rapport, **kwargs):
            rapport.update(
                discovered_urls=[v["url"] for v in fiches],
                metadonnees_api={v["id"]: v for v in fiches},
                candidats_examines=2, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [v["url"] for v in fiches]
        def commentaires(pub, limite=None, reponses=False, **kwargs):
            self.assertIsNone(limite)
            return {"commentaires": [{
                "id": "99", "publication_id": pub["id"], "texte": "Avis",
            }], "statut": "complet", "recuperes": 1,
                "exhaustif": True, "bloquer_requetes": False}
        navigateur = Mock(side_effect=AssertionError("Chrome non nécessaire"))
        with tempfile.TemporaryDirectory() as dossier:
            job = Job("x"*64, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=3,
                research_client_key="cle", research_client_secret="secret",
                hashtags_exclus=["publicite"], collecter_commentaires=True
            ), Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecte), patch(
                       "collecte.researchapi.collecter_commentaires_research",
                       side_effect=commentaires) as mock_comments:
                execute_job(job, driver_factory=navigateur)
            navigateur.assert_not_called()
            mock_comments.assert_called_once()
            self.assertEqual(job.exclus_hashtags, 1)
            self.assertEqual(job.processed, 2)
            self.assertEqual(len(job.records), 1)
            self.assertEqual(len(job.publications), 1)
            self.assertEqual(len(job.commentaires), 1)
            self.assertNotIn("sponsorisée", job.texte_a_exporter())
            self.assertIn("lycéenne", job.texte_a_exporter())
            self.assertEqual(job.snapshot()["exclus_hashtags"], 1)
            self.assertEqual(job.snapshot()["hashtags_exclus"], ["publicite"])


if __name__ == "__main__":
    unittest.main()
