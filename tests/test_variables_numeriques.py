"""Tests des classes numériques et du taux d'engagement dans le pipeline."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from webapp import StartRequest, Job, text_export, execute_job
from collecte.variables_numeriques import (
    classer_compteur, calculer_taux_engagement, classer_taux_engagement,
    indicateurs_numeriques, modalite_taux_brut)
from corpus.construction import lignes_engagement, COLONNES_ENGAGEMENT


def publication(vues=2000, likes=100, commentaires=20, partages=10, favoris=10,
                video_duration=45):
    return {
        "id": "7702367667616746785", "author": "lemondefr",
        "description": "Mobilisation étudiante",
        "engagement": {
            nom: {"valeur": valeur} for nom, valeur in (
                ("vues", vues), ("likes", likes), ("commentaires", commentaires),
                ("partages", partages), ("favoris", favoris))
        },
        "video_duration": video_duration,
    }


class TestsVariablesNumeriques(unittest.TestCase):
    def test_calcul_taux_et_inconnues(self):
        self.assertEqual(calculer_taux_engagement(publication()), 7)
        self.assertEqual(calculer_taux_engagement(publication(vues=0)), None)
        self.assertEqual(calculer_taux_engagement(publication(vues=None)), None)
        self.assertEqual(calculer_taux_engagement(publication(favoris=None)), None)
        self.assertEqual(calculer_taux_engagement(publication(likes=0, commentaires=0, partages=0, favoris=0)), 0)
        self.assertEqual(calculer_taux_engagement(publication(vues=10, likes=20, commentaires=1, partages=0, favoris=0)), 210)
        self.assertEqual(calculer_taux_engagement(publication(vues="inconnu")), None)

    def test_classes_taux_bornes(self):
        for taux, nom in (
            (0, "engagement_moins_1pct"),
            (0.99, "engagement_moins_1pct"),
            (1, "engagement_1_3pct"),
            (2.99, "engagement_1_3pct"),
            (3, "engagement_3_5pct"),
            (4.99, "engagement_3_5pct"),
            (5, "engagement_5_10pct"),
            (9.99, "engagement_5_10pct"),
            (10, "engagement_plus_10pct"),
            (120, "engagement_plus_10pct"),
            (None, "engagement_indetermine"),
        ):
            with self.subTest(taux=taux):
                self.assertEqual(classer_taux_engagement(taux), nom)

    def test_classes_compteurs_et_duree(self):
        for nom, valeur, attendu in (
            ("vues", 999, "vues_classe_moins_1k"),
            ("vues", 1000, "vues_classe_1k_10k"),
            ("vues", 10000, "vues_classe_10k_100k"),
            ("vues", 100000, "vues_classe_100k_1m"),
            ("vues", 1000000, "vues_classe_plus_1m"),
            ("likes", 0, "likes_classe_zero"),
            ("commentaires", 9, "commentaires_classe_1_9"),
            ("partages", 10, "partages_classe_10_99"),
            ("favoris", 100, "favoris_classe_100_999"),
            ("likes", 1, "likes_classe_1_9"),
            ("likes", 9, "likes_classe_1_9"),
            ("likes", 10, "likes_classe_10_99"),
            ("likes", 99, "likes_classe_10_99"),
            ("likes", 100, "likes_classe_100_999"),
            ("likes", 999, "likes_classe_100_999"),
            ("likes", 1000, "likes_classe_1000_9999"),
            ("likes", 9999, "likes_classe_1000_9999"),
            ("likes", 10000, "likes_classe_plus_10000"),
            ("likes", 10001, "likes_classe_plus_10000"),
            ("duree", 14, "duree_classe_moins_15s"),
            ("duree", 15, "duree_classe_15_59s"),
            ("duree", 60, "duree_classe_60_179s"),
            ("duree", 180, "duree_classe_plus_180s"),
            ("duree", None, "duree_classe_indetermine"),
            ("vues", None, "vues_classe_indetermine"),
            ("likes", True, "likes_classe_indetermine"),
        ):
            with self.subTest(nom=nom, valeur=valeur):
                self.assertEqual(classer_compteur(nom, valeur), attendu)

    def test_export_txt_choix_utilisateur(self):
        exemple = publication()
        aucun = text_export([exemple], False, variables_txt=[])
        self.assertEqual(aucun, "Mobilisation étudiante\n")
        classes = text_export([exemple], False, variables_txt=["id"],
            variables_classes_txt=["vues", "likes", "duree"],
            taux_engagement_txt="classes")
        self.assertTrue(classes.startswith(
            "*vues_classe_1k_10k *likes_classe_100_999 "
            "*duree_classe_15_59s *engagement_5_10pct *id_7702367667616746785\n"))
        brut = text_export([exemple], False, variables_txt=[],
                           taux_engagement_txt="brut")
        self.assertEqual(brut,
                         "*taux_engagement_7p00pct\nMobilisation étudiante\n")
        indetermine = text_export([publication(vues=0)], False, variables_txt=[],
                                  taux_engagement_txt="classes")
        self.assertTrue(indetermine.startswith("*engagement_indetermine\n"))
        # Les variables brutes déjà présentes restent fonctionnelles.
        ancien = text_export([exemple], False, variables_txt=["vues", "likes"])
        self.assertTrue(ancien.startswith("*vues_2000 *likes_100\n"))
        double = text_export([exemple], False, variables_txt=["vues"],
                             variables_classes_txt=["vues"])
        self.assertTrue(double.startswith("*vues_classe_1k_10k *vues_2000\n"))

    def test_taux_engagement_valeur_et_recodage_simultanes(self):
        """Le TXT conserve la valeur numérique et sa classe distincte."""
        exemple = publication()
        texte = text_export(
            [exemple], False, variables_txt=["vues", "likes"],
            variables_classes_txt=["vues", "likes", "duree"],
            taux_engagement_txt="brut_et_classes")
        self.assertIn("*vues_2000", texte)
        self.assertIn("*vues_classe_1k_10k", texte)
        self.assertIn("*likes_100", texte)
        self.assertIn("*likes_classe_100_999", texte)
        self.assertIn("*taux_engagement_7p00pct", texte)
        self.assertIn("*engagement_5_10pct", texte)
        self.assertEqual(texte.count("*taux_engagement_7p00pct"), 1)
        self.assertEqual(texte.count("*engagement_5_10pct"), 1)
        options = StartRequest(hashtag="mobilisation",
                               taux_engagement_txt="brut_et_classes")
        self.assertEqual(options.taux_engagement_txt, "brut_et_classes")

    def test_taux_absent_conserve_deux_modalites_indeterminees(self):
        """Des compteurs absents ne sont jamais convertis en zéro."""
        texte = text_export(
            [publication(vues=0)], False, variables_txt=[],
            taux_engagement_txt="brut_et_classes")
        self.assertIn("*taux_engagement_indetermine", texte)
        self.assertIn("*engagement_indetermine", texte)

    def test_ia_et_abonnes_compatibilite(self):
        exemple = {**publication(), "follower_count": 12345, "resume_ia_tiktok": "Analyse"}
        texte = text_export([exemple], False, variables_txt=["id"],
            inclure_texte_genere_ia=True, abonnes_classe_illustratif=True,
            variables_classes_txt=["commentaires"], taux_engagement_txt="classes")
        self.assertEqual(texte.count("*engagement_5_10pct"), 2)
        self.assertEqual(texte.count("*abonnes_10k_100k"), 2)
        self.assertIn("*commentaires_classe_10_99", texte)

    def test_export_csv_garde_taux_exact_et_modalites(self):
        p = publication(vues=3, likes=1, commentaires=0, partages=0, favoris=0)
        indicateurs = indicateurs_numeriques(p)
        self.assertAlmostEqual(indicateurs["taux_engagement"], 100 / 3)
        self.assertEqual(indicateurs["classe_taux_engagement"], "engagement_plus_10pct")
        self.assertEqual(modalite_taux_brut(indicateurs["taux_engagement"]),
                         "taux_engagement_33p33pct")
        ligne = lignes_engagement([p])[0]
        self.assertAlmostEqual(ligne["taux_engagement"], 100 / 3)
        self.assertEqual(ligne["vues"], 3)
        for nom in ("taux_engagement", "classe_taux_engagement", "video_duration",
                    "vues_classe", "likes_classe", "commentaires_classe",
                    "partages_classe", "favoris_classe", "duree_classe"):
            self.assertIn(nom, COLONNES_ENGAGEMENT)

    def test_configuration_api_validation(self):
        x = StartRequest(hashtag="mobilisation", variables_classes_txt=["vues", "vues", "likes"],
                         taux_engagement_txt="classes")
        self.assertEqual(x.variables_classes_txt, ["vues", "likes"])
        self.assertEqual(x.taux_engagement_txt, "classes")
        with self.assertRaises(ValueError):
            StartRequest(hashtag="mobilisation", taux_engagement_txt="invalide")
        with self.assertRaises(ValueError):
            StartRequest(hashtag="mobilisation", variables_classes_txt=["inconnu"])

    def test_pipeline_research_sans_navigation_et_compteurs_absents(self):
        from collecte.researchapi import _fiche
        video = {
            "id": "7702367667616746785", "username": "lemondefr",
            "video_description": "Mobilisation #mobilisation",
            "create_time": 1760000000,
            "view_count": 2000, "like_count": 100, "comment_count": 20,
            "share_count": 10, "favorites_count": 10,
            "video_duration": 45, "hashtag_names": ["mobilisation"],
        }
        fiche = _fiche(video, "lemondefr")
        def recherche(compte, limite, rapport, **kwargs):
            rapport.update(
                discovered_urls=[fiche["url"]],
                metadonnees_api={fiche["id"]: fiche},
                candidats_examines=1, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [fiche["url"]]
        with tempfile.TemporaryDirectory() as dossier:
            job = Job("t" * 64, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=2,
                variables_txt=["id"], variables_classes_txt=["duree", "vues"],
                taux_engagement_txt="classes",
                research_client_key="CLE_TEST", research_client_secret="SECRET_TEST"
            ), Path(dossier))
            navigateur = Mock(side_effect=AssertionError("Chrome interdit"))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=recherche):
                execute_job(job, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(job.records[0]["taux_engagement"], 7)
            self.assertEqual(job.records[0]["classe_taux_engagement"],
                             "engagement_5_10pct")
            self.assertEqual(job.publications[0]["taux_engagement"], 7)
            self.assertIn("*duree_classe_15_59s", job.texte_a_exporter())
            self.assertIn("*engagement_5_10pct", job.texte_a_exporter())
            self.assertEqual(job.snapshot()["taux_engagement_txt"], "classes")
            self.assertEqual(job.snapshot()["variables_classes_txt"], ["duree", "vues"])


if __name__ == "__main__":
    unittest.main()
