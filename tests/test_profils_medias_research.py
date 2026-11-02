"""Tests des métriques agrégées des médias, sans appel réseau à TikTok."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from collecte.profils_medias import (
    VARIABLES_PROFILS_MEDIAS, colonnes_profils_medias, ligne_profil_media,
    segmenter_profil_media,
)
from collecte.researchapi import (
    ResearchErreur, collecter_metriques_profil_media_research, URL_PROFIL,
)
from webapp import StartRequest, Job, execute_job


class TestsProfilsMediasResearch(unittest.TestCase):
    def test_valeurs_exactes_et_seuils_des_quatre_segmentations(self):
        """Vérifier les bornes et le zéro distinct de l'absence."""
        valeurs = {
            "following_count": [(0, "0"), (9, "1_9"), (10, "10_99"),
                                (999, "100_999"), (1000, "plus_1000")],
            "follower_count": [(999, "moins_1k"), (1000, "1k_10k"),
                               (97900, "10k_100k"), (1000000, "plus_1m")],
            "likes_count": [(0, "0"), (9999, "1_9999"),
                            (10000, "10k_100k"), (1900000, "1m_10m"),
                            (10000000, "plus_10m")],
            "video_count": [(0, "0"), (9, "1_9"), (56, "10_99"),
                            (1000, "plus_1000")],
        }
        self.assertEqual(len(VARIABLES_PROFILS_MEDIAS), 4)
        for champ, exemples in valeurs.items():
            for nombre, classe in exemples:
                with self.subTest(champ=champ, valeur=nombre):
                    self.assertEqual(segmenter_profil_media(champ, nombre), classe)
            self.assertEqual(segmenter_profil_media(champ, None), "indetermine")
            self.assertEqual(segmenter_profil_media(champ, -1), "indetermine")
            self.assertEqual(segmenter_profil_media(champ, True), "indetermine")

    def test_requete_officielle_unique_champs_choisis_et_valeurs_absentes(self):
        """L'API publique est interrogée une fois, sans confusion avec les vidéos."""
        appels = []
        def simuler(url, *, data, headers):
            appels.append((url, json.loads(data), headers))
            return {"data": {"following_count": 0, "follower_count": 97900,
                             "likes_count": 1900000, "video_count": 56}}
        valeurs = collecter_metriques_profil_media_research(
            "@actulyon", VARIABLES_PROFILS_MEDIAS,
            jeton="jeton_de_test", requete=simuler)
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][0], URL_PROFIL +
                         "?fields=following_count,follower_count,likes_count,video_count")
        self.assertEqual(appels[0][1], {"username": "actulyon"})
        self.assertEqual(valeurs["follower_count"], 97900)
        self.assertEqual(valeurs["likes_count"], 1900000)
        self.assertEqual(valeurs["following_count"], 0)
        self.assertEqual(valeurs["video_count"], 56)
        self.assertEqual(appels[0][2]["Authorization"], "Bearer jeton_de_test")
        incomplet = collecter_metriques_profil_media_research(
            "actulyon", ["video_count", "following_count"], jeton="test",
            requete=lambda *a, **k: {"data": {"following_count": 0}})
        self.assertEqual(incomplet, {"video_count": None, "following_count": 0})
        with self.assertRaises(ValueError):
            collecter_metriques_profil_media_research(
                "actulyon", ["comment_count"], jeton="test", requete=simuler)
        with self.assertRaises(ResearchErreur):
            collecter_metriques_profil_media_research(
                "actulyon", ["video_count"], jeton="test",
                requete=lambda *a, **k: {"data": None})

    def test_colonnes_independantes_et_donnees_manquantes(self):
        """Chaque segment est facultatif et la source garde une ligne sans vidéo."""
        media = {
            "compte": "actulyon", "nom": "Actu Lyon",
            "categorie": "presse_regionale",
            "url": "https://www.tiktok.com/@actulyon"}
        ligne = ligne_profil_media(
            media, ["follower_count", "video_count"], ["follower_count"],
            donnees={"follower_count": 97900, "video_count": 0}, statut="ok",
            date_collecte="2026-11-02T12:00:00Z")
        self.assertEqual(ligne["follower_count"], 97900)
        self.assertEqual(ligne["classe_follower_count"], "10k_100k")
        self.assertEqual(ligne["video_count"], 0)
        self.assertNotIn("classe_video_count", ligne)
        self.assertNotIn("likes_count", ligne)
        self.assertEqual(ligne["categorie_media"], "presse_regionale")
        colonnes = colonnes_profils_medias(
            ["follower_count", "video_count"], ["follower_count"])
        self.assertEqual(colonnes[-3:],
                         ["follower_count", "classe_follower_count", "video_count"])
        absent = ligne_profil_media(
            media, ["follower_count"], ["follower_count"],
            donnees={}, statut="acces_refuse")
        self.assertIsNone(absent["follower_count"])
        self.assertEqual(absent["classe_follower_count"], "indetermine")
        self.assertEqual(absent["statut_profil"], "acces_refuse")

    def test_validation_du_formulaire_research_uniquement(self):
        """Le moteur et la segmentation sont validés côté serveur."""
        options = StartRequest(
            source_collecte="presse", medias=["actulyon"],
            presse_moteur="research",
            research_client_key="cle_test", research_client_secret="secret_test",
            profils_medias_variables=list(VARIABLES_PROFILS_MEDIAS),
            profils_medias_classes=["follower_count", "likes_count"])
        self.assertEqual(len(options.profils_medias_variables), 4)
        self.assertNotIn("secret_test", json.dumps(options.model_dump()))
        for valeurs in (
            {"source_collecte": "presse", "medias": ["actulyon"],
             "presse_moteur": "api",
             "profils_medias_variables": ["likes_count"]},
            {"source_collecte": "presse", "medias": ["actulyon"],
             "presse_moteur": "research",
             "research_client_key": "cle_test",
             "research_client_secret": "secret_test",
             "profils_medias_variables": ["likes_count"],
             "profils_medias_classes": ["video_count"]},
        ):
            with self.subTest(valeurs=valeurs), self.assertRaises(ValueError):
                StartRequest(**valeurs)

    def test_deux_comptes_dont_un_inaccessible_sans_video_retendue(self):
        """Archiver chaque média indépendamment des publications découvertes."""
        def collecter(compte, variables, **options):
            if compte == "actulyon":
                return {"following_count": 0, "follower_count": 97900,
                        "likes_count": 1900000, "video_count": 56}
            raise ResearchErreur("Profil inaccessible")
        def videos(compte, limite, rapport, **options):
            rapport.update(discovered_urls=[], metadonnees_api={},
                           discovery_stop="fin_des_periodes")
            return []
        with tempfile.TemporaryDirectory() as racine:
            job = Job("a" * 64, StartRequest(
                source_collecte="presse",
                medias=["actulyon", "complementdenquete_off"],
                presse_moteur="research", nom_sauvegarde="Profils des médias",
                research_client_key="cle_de_test",
                research_client_secret="secret_de_test",
                profils_medias_variables=list(VARIABLES_PROFILS_MEDIAS),
                profils_medias_classes=["following_count", "follower_count",
                                       "likes_count", "video_count"],
            ), Path(racine))
            with patch(
                    "collecte.researchapi.collecter_metriques_profil_media_research",
                    side_effect=collecter) as api, patch(
                    "collecte.presse_research.collecter_videos_presse_research",
                    side_effect=videos):
                execute_job(job, driver_factory=Mock(
                    side_effect=AssertionError("Aucun Selenium nécessaire")))
            self.assertEqual(api.call_count, 2)
            self.assertEqual(len(job.profils_medias), 2, job.message)
            self.assertEqual(len(job.records), 0)
            self.assertEqual(job.profils_medias[0]["compte"], "actulyon")
            self.assertEqual(job.profils_medias[0]["likes_count"], 1900000)
            self.assertEqual(job.profils_medias[1]["statut_profil"], "indisponible")
            self.assertEqual(job.profils_medias[1]["classe_video_count"], "indetermine")
            self.assertTrue(job.archive_prete, job.message)
            self.assertEqual(job.status, "partial")
            self.assertIn("Profils médias : 1/2", job.message)
            self.assertTrue(job.snapshot()["can_download"])
            self.assertEqual(job.snapshot()["nombre_profils_medias"], 2)
            zipfile = job.directory / "archive.zip"
            with ZipFile(zipfile) as archive:
                self.assertIn("profils_medias.csv", archive.namelist())
                self.assertIn("profils_medias.json", archive.namelist())
                self.assertIn("publications.csv", archive.namelist())
                texte = archive.read("profils_medias.csv").decode("utf-8-sig")
                tableau = list(csv.DictReader(texte.splitlines(), delimiter=";"))
                self.assertEqual(len(tableau), 2)
                self.assertEqual(tableau[0]["follower_count"], "97900")
                self.assertEqual(tableau[0]["classe_likes_count"], "1m_10m")
                self.assertEqual(tableau[1]["likes_count"], "")
                self.assertEqual(tableau[1]["classe_likes_count"], "indetermine")
                self.assertNotIn("secret_de_test", texte)
            self.assertNotIn(
                "secret_de_test", (job.directory / "profils_medias.json").read_text())

    def test_cases_deux_colonnes_sous_profil_et_export(self):
        """Vérifier la position et la propagation des huit cases Streamlit."""
        page = (Path(__file__).resolve().parents[1] /
                "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('if nom == "profil" and source == "presse":', page)
        self.assertIn('colonne_nombre.checkbox(', page)
        self.assertIn('colonne_classe.checkbox(', page)
        self.assertIn('key=cle_brute', page)
        self.assertIn('key=cle_classe', page)
        self.assertIn('valeurs["profils_medias_variables"] = [', page)
        self.assertIn('valeurs["profils_medias_classes"] = [', page)


if __name__ == "__main__":
    unittest.main()
