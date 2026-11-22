"""Tester region_code et is_verified : API officielle, TXT et exports."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from collecte.researchapi import (
    ResearchErreur, _fiche, URL_PROFIL,
    collecter_profil_research, collecter_verification_research)
from collecte.variables_profil import normaliser_region, modalite_verification
from corpus.construction import lignes_engagement, COLONNES_ENGAGEMENT
from webapp import StartRequest, Job, execute_job, text_export


def fiche(identifiant, region="FR"):
    return _fiche({
        "id": identifiant, "username": "lemondefr",
        "video_description": "Manifestation lycéenne #manifestation",
        "create_time": 1760000000, "region_code": region,
        "hashtag_names": ["manifestation"],
    }, "lemondefr")


def decouvrir_deux(compte, limite, rapport, **kwargs):
    videos = [
        fiche("7702367667616746785"),
        fiche("7702367667616746786", "BE"),
    ]
    rapport.update(
        discovered_urls=[v["url"] for v in videos],
        metadonnees_api={v["id"]: v for v in videos},
        candidats_examines=2, pages_research=1,
        navigation_publications="research_officielle",
        discovery_stop="fin_des_periodes")
    return [v["url"] for v in videos]


class TestsVariablesProfil(TestCase):
    def test_region_forme_et_inconnues(self):
        self.assertEqual(normaliser_region(" fr "), "FR")
        self.assertIsNone(normaliser_region("France"))
        self.assertIsNone(normaliser_region(None))
        self.assertIsNone(normaliser_region("F-"))
        self.assertEqual(fiche("7702367667616746785", "fr")["region_code"], "FR")

    def test_verification_vrai_faux_indetermine(self):
        self.assertEqual(modalite_verification(True), "oui")
        self.assertEqual(modalite_verification(False), "non")
        self.assertEqual(modalite_verification(None), "indetermine")
        self.assertEqual(modalite_verification(0), "indetermine")
        for verifie, attendu in (
            (True, "*is_verified_oui"),
            (False, "*is_verified_non"),
            (None, "*is_verified_indetermine"),
        ):
            with self.subTest(verifie=verifie):
                publication = {
                    "id": "123", "author": "lemondefr", "description": "Essai",
                    "region_code": "fr", "is_verified": verifie}
                texte = text_export([publication], False,
                                    variables_txt=["region_code", "is_verified"])
                self.assertEqual(texte, f"*region_FR {attendu}\nEssai\n")
        texte = text_export(
            [{"id": "123", "description": "Essai"}], False,
            variables_txt=["region_code", "is_verified"])
        self.assertEqual(
            texte, "*region_indetermine *is_verified_indetermine\nEssai\n")

    def test_requete_officielle_mutualisee(self):
        appels = []
        def simuler(url, *, data, headers):
            appels.append((url, json.loads(data), headers))
            return {"data": {"follower_count": 0, "is_verified": False},
                    "error": {"code": "ok"}}
        result = collecter_profil_research(
            "lemondefr", jeton="JETON", requete=simuler)
        self.assertEqual(result, {"follower_count": 0, "is_verified": False})
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][0],
                         URL_PROFIL + "?fields=follower_count,is_verified")
        self.assertEqual(appels[0][1], {"username": "lemondefr"})
        self.assertEqual(appels[0][2]["Authorization"], "Bearer JETON")
        self.assertFalse(collecter_verification_research(
            "lemondefr", jeton="JETON", requete=simuler))
        self.assertEqual(appels[-1][0], URL_PROFIL + "?fields=is_verified")

    def test_verification_manquante_ne_devient_pas_non(self):
        donnees = collecter_profil_research(
            "lemondefr", jeton="TEST",
            requete=lambda *a, **k: {"data": {"follower_count": 13}})
        self.assertEqual(donnees["follower_count"], 13)
        self.assertIsNone(donnees["is_verified"])
        with self.assertRaises(ResearchErreur):
            collecter_verification_research(
                "lemondefr", jeton="TEST",
                requete=lambda *a, **k: {"data": {}})

    def test_options_research_et_exports(self):
        r = StartRequest(
            hashtag="manifestation", hashtag_moteur="research",
            research_client_key="TEST", research_client_secret="SECRET",
            variables_txt=["region_code", "is_verified"],
        )
        self.assertTrue(r.collecter_is_verified)
        self.assertFalse(r.collecter_follower_count)
        self.assertNotIn("SECRET", json.dumps(r.model_dump()))
        r = StartRequest(hashtag="manifestation", collecter_is_verified=True)
        self.assertFalse(r.collecter_is_verified)
        publication = {
            "id": "12", "author": "lemondefr", "description": "Essai",
            "region_code": "FR", "is_verified": False,
            "is_verified_statut": "ok", "engagement": {}}
        ligne = lignes_engagement([publication])[0]
        self.assertIs(ligne["is_verified"], False)
        self.assertEqual(ligne["region_code"], "FR")
        self.assertEqual(ligne["is_verified_statut"], "ok")
        for nom in ("region_code", "is_verified", "is_verified_statut"):
            self.assertIn(nom, COLONNES_ENGAGEMENT)

    def test_worker_collecte_et_cache_par_auteur(self):
        with TemporaryDirectory() as dossier:
            options = StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=3,
                variables_txt=["id", "region_code", "is_verified"],
                collecter_follower_count=True,
                research_client_key="CLE", research_client_secret="SECRET")
            travail = Job("w" * 64, options, Path(dossier))
            navigateur = mock.Mock(side_effect=AssertionError("Chrome interdit"))
            with mock.patch(
                    "collecte.presse_research.collecter_videos_presse_research",
                    side_effect=decouvrir_deux), mock.patch(
                    "collecte.researchapi.collecter_profil_research",
                    return_value={"follower_count": 12345, "is_verified": False}
                    ) as profil:
                execute_job(travail, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(profil.call_count, 1)
            self.assertEqual(len(travail.records), 2)
            self.assertEqual([r["region_code"] for r in travail.records], ["FR", "BE"])
            self.assertTrue(all(r["is_verified"] is False for r in travail.records))
            self.assertTrue(all(r["is_verified_statut"] == "ok" for r in travail.records))
            self.assertTrue(all(r["follower_count"] == 12345 for r in travail.records))
            self.assertIn("*region_FR", travail.texte_a_exporter())
            self.assertEqual(travail.texte_a_exporter().count("*is_verified_non"), 2)
            self.assertTrue(travail.snapshot()["collecter_is_verified"])
            self.assertNotIn(b"SECRET", b"".join(p.read_bytes()
                for p in Path(dossier).rglob("*")
                if p.is_file() and p.suffix in (".csv", ".json", ".txt")))

    def test_worker_profil_verification_indisponible(self):
        with TemporaryDirectory() as dossier:
            options = StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=2,
                variables_txt=["id", "is_verified"],
                research_client_key="CLE", research_client_secret="SECRET")
            travail = Job("q" * 64, options, Path(dossier))
            with mock.patch(
                    "collecte.presse_research.collecter_videos_presse_research",
                    side_effect=decouvrir_deux), mock.patch(
                    "collecte.researchapi.collecter_verification_research",
                    side_effect=ResearchErreur("Donnée indisponible")) as verification:
                execute_job(travail, driver_factory=mock.Mock(
                    side_effect=AssertionError("Chrome interdit")))
            self.assertEqual(verification.call_count, 1)
            self.assertTrue(all(p["is_verified"] is None for p in travail.records))
            self.assertEqual(travail.texte_a_exporter().count(
                "*is_verified_indetermine"), 2)
