"""Valider les republications Research sans connexion réseau ni compte TikTok."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from collecte.republications_research import (
    collecter_republications_research, rapprocher_republications,
    url_republications,
)
from collecte.researchapi import _fiche, ResearchAccesRefuse
from webapp import Job, StartRequest, execute_job
from corpus.publications_csv import ligne_publication_csv


def video(numero, auteur="autrecreateur", texte="Manifestation #lyceens"):
    """Créer une réponse Research avec auteur original indépendant du reposteur."""
    return {
        "id": str(7000000000000000000 + numero),
        "username": auteur,
        "video_description": texte,
        "create_time": 1760000000,
        "view_count": 100, "like_count": 8,
        "comment_count": 2, "share_count": 5,
        "favorites_count": 1, "hashtag_names": ["lyceens"],
    }


class TestsRepublicationsResearch(unittest.TestCase):
    def test_validation_des_options_et_compatibilite(self):
        """L'option est opt-in et disponible seulement en presse Research."""
        ancien = StartRequest(source_collecte="presse", medias=["lemonde"])
        self.assertFalse(ancien.collecter_republications_research)
        with self.assertRaisesRegex(ValueError, "Research API"):
            StartRequest(source_collecte="presse", medias=["lemonde"],
                presse_moteur="api", collecter_republications_research=True)
        with self.assertRaisesRegex(ValueError, "Research API"):
            StartRequest(source_collecte="hashtags", hashtag="manifestation",
                collecter_republications_research=True)
        with self.assertRaises(ValueError):
            StartRequest(source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", collecter_republications_research=True,
                maximum_republications_par_compte=1001)

    def test_programmation_research_refuse_une_option_non_executee(self):
        """Ne jamais programmer silencieusement un lot sans ses republications."""
        from datetime import date
        from fastapi import HTTPException
        from webapp import Manager

        parametres = StartRequest(
            source_collecte="presse", medias=["lemonde"],
            nom_sauvegarde="Test republications",
            presse_moteur="research",
            collecter_republications_research=True,
            date_debut="2026-10-01", date_fin="2026-10-15",
        )
        manager = object.__new__(Manager)
        with patch("collecte.researchapi.identifiants_disponibles",
                   return_value=True):
            with self.assertRaises(HTTPException) as erreur:
                manager.programmer_research(
                    "proprietaire", parametres,
                    date(2026, 10, 1), date(2026, 10, 15))
        self.assertEqual(erreur.exception.status_code, 422)
        self.assertIn("ponctuelles", erreur.exception.detail)

    def test_pagination_avec_deux_noms_de_champs_et_auteur_original(self):
        """Les versions documentées de la liste et le curseur fonctionnent."""
        appels = []
        def api(url, *, data, headers):
            appels.append((url, json.loads(data), headers))
            if len(appels) == 1:
                return {"data": {
                    "user_reposted_videos": [video(1), video(2)],
                    "cursor": 2, "has_more": True}}
            return {"data": {
                "reposted_videos": [video(2), video(3)],
                "cursor": 3, "has_more": False}}
        diagnostic = {}
        lignes = collecter_republications_research(
            "@lemondefr", 10, jeton="token_de_test", requete=api,
            rapport=diagnostic, pause=lambda _:None)
        self.assertEqual(len(lignes), 3)
        self.assertEqual(len(appels), 2)
        self.assertTrue(all(u == url_republications() for u,_,_ in appels))
        self.assertEqual(appels[0][1]["username"], "lemondefr")
        self.assertEqual(appels[0][1]["max_count"], 10)
        self.assertEqual(appels[1][1]["cursor"], 2)
        self.assertEqual(diagnostic["doublons"], 1)
        self.assertTrue(diagnostic["pagination_terminee"])
        self.assertFalse(diagnostic["exhaustif"])
        # Pagination achevée ne signifie pas recensement intégral sur TikTok.
        self.assertEqual(lignes[0]["author"], "autrecreateur")
        self.assertEqual(lignes[0]["compte_reposteur"], "lemondefr")
        self.assertEqual(lignes[0]["auteur_original"], "autrecreateur")
        self.assertEqual(lignes[0]["id_video_originale"], lignes[0]["id"])
        self.assertIsNone(lignes[0]["date_republication"])
        self.assertEqual(lignes[0]["republication_confirmee"], 1)
        self.assertEqual(ligne_publication_csv(lignes[0])["republication_confirmee"], 1)

    def test_filtre_corpus_et_pagination_invalide(self):
        """La période concerne la création, les hashtags sont filtrés localement."""
        diagnostic = {}
        resultats = collecter_republications_research(
            "brutofficiel", 20, jeton="test", pause=lambda _:None,
            debut="2025-10-01", fin="2025-10-31",
            accepter=lambda f: "lyceens" in f["hashtags"],
            requete=lambda url, **kwargs: {"data": {
                "reposted_videos": [video(1), {**video(2, texte="Sans hashtag"), "hashtag_names": []}],
                "has_more": True, "cursor": 0}},
            rapport=diagnostic)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(diagnostic["statut"], "pagination_invalide")
        self.assertFalse(diagnostic["exhaustif"])

    def test_rapprochement_multi_comptes_et_absence_inconnue(self):
        """Une même vidéo peut être republiée par plusieurs comptes."""
        fiches = [{"id": "701", "author": "a"},
                  {"id": "702", "author": "b"}]
        relations = [
            {"id": "701", "compte_reposteur": "lemondefr"},
            {"id": "701", "compte_reposteur": "brutofficiel"},
            {"id": "701", "compte_reposteur": "lemondefr"},
        ]
        self.assertEqual(rapprocher_republications(fiches, relations), 1)
        self.assertEqual(fiches[0]["comptes_reposteurs"],
                         ["brutofficiel", "lemondefr"])
        self.assertEqual(fiches[0]["republication_confirmee"], 1)
        self.assertIsNone(fiches[1]["republication_confirmee"])
        self.assertEqual(fiches[1]["type_publication"], "publication_du_createur")
        self.assertEqual(fiches[0]["id_video_originale"], "701")

    def test_collecte_presse_exporte_les_deux_populations_sans_chrome(self):
        """Les vidéos d'autres créateurs ne contaminent pas le corpus Presse."""
        from collecte.presse_research import _fiche as fiche_api
        video_originale = video(15, auteur="lemondefr")
        fiche = fiche_api(video_originale, "lemondefr")
        repub_identique = _fiche(video_originale, None)
        repub_externe = _fiche(video(18, auteur="autreauteur"), None)

        def decouvrir(compte, limite, rapport, **kwargs):
            rapport.update(
                discovered_urls=[fiche["url"]],
                metadonnees_api={fiche["id"]: fiche},
                candidats_examines=1, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [fiche["url"]]

        def republications(compte, limite, **kwargs):
            self.assertEqual(compte, "lemondefr")
            self.assertEqual(limite, 100)
            self.assertEqual(kwargs["credentiels"], ("cle_test", "secret_test"))
            lignes = []
            for publication in (repub_identique, repub_externe):
                lignes.append({**publication,
                    "compte_reposteur": compte,
                    "auteur_original": publication["author"],
                    "id_video_originale": publication["id"],
                    "type_publication": "republication_par_compte",
                    "republication_confirmee": 1,
                    "date_republication": None})
            kwargs["rapport"].update(pages=1, statut="termine", retenues=2)
            return lignes

        with tempfile.TemporaryDirectory() as dossier:
            options = StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=5, french_only=False,
                collecter_republications_research=True,
                research_client_key="cle_test", research_client_secret="secret_test")
            job = Job("a" * 64, options, Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=decouvrir), patch(
                       "collecte.republications_research.collecter_republications_research",
                       side_effect=republications):
                execute_job(job, driver_factory=Mock(
                    side_effect=AssertionError("Ne pas lancer Selenium")))
            self.assertEqual(len(job.records), 1, job.message)
            self.assertEqual(len(job.publications), 1, job.message)
            self.assertEqual(len(job.republications), 2, job.message)
            self.assertEqual(job.records[0]["republication_confirmee"], 1)
            self.assertEqual(job.records[0]["comptes_reposteurs"], ["lemondefr"])
            self.assertEqual(job.republications[1]["auteur_original"], "autreauteur")
            self.assertFalse(job.republications[1]["inclure_hashtags_csv"])
            self.assertTrue(job.archive_prete, job.message)
            with ZipFile(job.directory / "archive.zip") as archive:
                self.assertIn("republications.csv", archive.namelist())
                self.assertIn("republications.json", archive.namelist())
                self.assertIn("publications.csv", archive.namelist())
                texte = archive.read("republications.csv").decode("utf-8")
                self.assertIn("autreauteur", texte)
                self.assertIn("lemondefr", texte)
                self.assertNotIn("secret_test", texte)
                # L'option « Htag dans le csv » vaut aussi pour les republications.
                import csv
                import io
                lignes_csv = list(csv.DictReader(io.StringIO(texte), delimiter=";"))
                self.assertTrue(lignes_csv)
                self.assertTrue(all(ligne["hashtags"] == "" for ligne in lignes_csv))
                corpus = archive.read("publications.csv").decode("utf-8")
                self.assertNotIn("autreauteur", corpus)
                self.assertIn("republication_confirmee", corpus)


if __name__ == "__main__":
    unittest.main()
