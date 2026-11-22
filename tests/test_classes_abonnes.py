"""Non-régression des six modalités d'audience et de leur export IRaMuTeQ."""
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
from tempfile import TemporaryDirectory

from collecte.classes_abonnes import classer_nombre_abonnes
from webapp import StartRequest, Job, execute_job, text_export
from corpus.construction import lignes_engagement
from collecte.researchapi import _fiche


class TestsClassesAbonnes(unittest.TestCase):
    def test_seuils_et_valeurs_manquantes(self):
        valeurs = {
            0: "abonnes_moins_1k",
            999: "abonnes_moins_1k",
            1000: "abonnes_1k_10k",
            9999: "abonnes_1k_10k",
            10000: "abonnes_10k_100k",
            99999: "abonnes_10k_100k",
            100000: "abonnes_100k_1m",
            999999: "abonnes_100k_1m",
            1000000: "abonnes_plus_1m",
            3000000: "abonnes_plus_1m",
            None: "abonnes_indetermine",
            -1: "abonnes_indetermine",
            True: "abonnes_indetermine",
            "inconnu": "abonnes_indetermine",
            "12345": "abonnes_10k_100k",
        }
        for valeur, attendu in valeurs.items():
            with self.subTest(valeur=valeur):
                self.assertEqual(classer_nombre_abonnes(valeur), attendu)

    def test_en_tete_de_chacune_des_six_modalites(self):
        exemples = (
            (99, "*abonnes_moins_1k"),
            (1000, "*abonnes_1k_10k"),
            (12345, "*abonnes_10k_100k"),
            (100000, "*abonnes_100k_1m"),
            (1000000, "*abonnes_plus_1m"),
            (None, "*abonnes_indetermine"),
        )
        for nombre, variable in exemples:
            with self.subTest(nombre=nombre):
                texte = text_export(
                    [{"id": "123", "author": "chercheur", "description": "Corpus",
                      "follower_count": nombre}],
                    False, variables_txt=["id"],
                    abonnes_classe_illustratif=True)
                self.assertEqual(texte, f"{variable} *id_123\nCorpus\n")
                self.assertNotIn("*follower_count_", texte)

    def test_options_independantes_et_compatibilite_brut(self):
        r = StartRequest(
            hashtag="manifestation", hashtag_moteur="research",
            research_client_key="cle", research_client_secret="secret",
            collecter_follower_count=True, abonnes_classe_illustratif=True)
        self.assertTrue(r.abonnes_classe_illustratif)
        self.assertFalse(r.follower_count_illustratif)
        self.assertTrue(r.model_dump()["abonnes_classe_illustratif"])
        autre = StartRequest(hashtag="manifestation",
                             collecter_follower_count=True,
                             abonnes_classe_illustratif=True)
        self.assertFalse(autre.collecter_follower_count)
        self.assertFalse(autre.abonnes_classe_illustratif)
        seul = StartRequest(
            hashtag="manifestation", hashtag_moteur="research",
            research_client_key="cle", research_client_secret="secret",
            abonnes_classe_illustratif=True)
        self.assertFalse(seul.abonnes_classe_illustratif)
        v = [{"id": "123", "description": "Corpus", "follower_count": 12345}]
        self.assertEqual(text_export(v, False, variables_txt=[],
                                     follower_count_illustratif=True),
                         "*follower_count_12345\nCorpus\n")
        self.assertEqual(text_export(
            v, False, variables_txt=[], abonnes_classe_illustratif=True,
            follower_count_illustratif=True),
            "*abonnes_10k_100k *follower_count_12345\nCorpus\n")

    def test_export_avec_texte_ia_et_sans_variables_precedentes(self):
        item = {"id": "123", "author": "compte", "description": "Texte",
                "follower_count": 5000, "resume_ia_tiktok": "Résumé"}
        resultat = text_export(
            [item], False, variables_txt=[],
            inclure_texte_genere_ia=True, abonnes_classe_illustratif=True)
        self.assertEqual(resultat.count("*abonnes_1k_10k"), 2)
        self.assertIn("**** *source_original", resultat)
        self.assertIn("**** *source_ia", resultat)
        texte_simple = text_export(
            [item], False, variables_txt=[],
            abonnes_classe_illustratif=False)
        self.assertEqual(texte_simple, "Texte\n")

    def test_export_csv_conserve_la_valeur_brute(self):
        enregistrements = [{"id": "12", "author": "compte", "description": "Texte",
                            "follower_count": 12345, "follower_count_statut": "ok",
                            "classe_abonnes": "abonnes_10k_100k", "engagement": {}}]
        lignes = lignes_engagement(enregistrements)
        self.assertEqual(lignes[0]["follower_count"], 12345)
        self.assertEqual(lignes[0]["classe_abonnes"], "abonnes_10k_100k")

    def test_collecte_research_stocke_classe_avec_cache_par_auteur(self):
        videos = [
            _fiche({"id": identifiant, "username": "lemondefr",
                    "video_description": "Manifestation #manifestation",
                    "create_time": 1760000000,
                    "hashtag_names": ["manifestation"]}, "lemondefr")
            for identifiant in ("7702367667616746785", "7702367667616746786")
        ]
        def simuler_recherche(compte, limite, rapport, **kwargs):
            rapport.update(
                discovered_urls=[v["url"] for v in videos],
                metadonnees_api={v["id"]: v for v in videos},
                candidats_examines=2, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [v["url"] for v in videos]
        navigateur = Mock(side_effect=AssertionError("Chrome ne doit pas démarrer"))
        with TemporaryDirectory() as dossier:
            travail = Job("m" * 64, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=3, variables_txt=["id"],
                collecter_follower_count=True, abonnes_classe_illustratif=True,
                research_client_key="cle_test", research_client_secret="secret_test"),
                Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=simuler_recherche), patch(
                           "collecte.researchapi.collecter_abonnes_research",
                           return_value=12345) as profils:
                execute_job(travail, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(profils.call_count, 1)
            self.assertEqual([v["classe_abonnes"] for v in travail.records],
                             ["abonnes_10k_100k", "abonnes_10k_100k"])
            self.assertEqual(travail.texte_a_exporter().count("*abonnes_10k_100k"), 2)
            self.assertNotIn("*follower_count_", travail.texte_a_exporter())
            self.assertTrue(travail.snapshot()["abonnes_classe_illustratif"])


if __name__ == "__main__":
    unittest.main()
