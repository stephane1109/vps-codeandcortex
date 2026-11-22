"""Vérifier la collecte facultative des abonnés via l'API Research officielle."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from collecte.researchapi import (
    ResearchAccesRefuse, ResearchErreur, URL_PROFIL,
    collecter_abonnes_research, _fiche,
)
from webapp import StartRequest, Job, execute_job, text_export


class TestsNombreAbonnesResearch(unittest.TestCase):
    def test_profil_officiel_et_compteur_nul(self):
        appels = []
        def simuler(url, *, data, headers):
            appels.append((url, json.loads(data), headers))
            return {"data": {"follower_count": 0}, "error": {"code": "ok"}}
        nombre = collecter_abonnes_research(
            "@lemondefr", jeton="JETON_TEST", requete=simuler)
        self.assertEqual(nombre, 0)
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][1], {"username": "lemondefr"})
        self.assertEqual(appels[0][0],
                         URL_PROFIL + "?fields=follower_count")
        self.assertEqual(appels[0][2]["Authorization"], "Bearer JETON_TEST")

    def test_valeur_absente_et_refus_ne_deviennent_pas_zero(self):
        with self.assertRaises(ResearchErreur):
            collecter_abonnes_research(
                "lemondefr", jeton="TEST",
                requete=lambda *a, **k: {"data": {}})
        with self.assertRaises(ResearchErreur):
            collecter_abonnes_research(
                "lemondefr", jeton="TEST",
                requete=lambda *a, **k: {"data": {"follower_count": -2}})

    def test_option_restreinte_au_moteur_research(self):
        par_defaut = StartRequest(hashtag="manifestation")
        self.assertFalse(par_defaut.collecter_follower_count)
        normal = StartRequest(
            hashtag="manifestation", collecter_follower_count=True,
            follower_count_illustratif=True)
        self.assertFalse(normal.collecter_follower_count)
        self.assertFalse(normal.follower_count_illustratif)
        recherche = StartRequest(
            hashtag="manifestation", hashtag_moteur="research",
            research_client_key="TEST_KEY", research_client_secret="TEST_SECRET",
            collecter_follower_count=True, follower_count_illustratif=True)
        self.assertTrue(recherche.collecter_follower_count)
        self.assertTrue(recherche.follower_count_illustratif)
        self.assertEqual(recherche.model_dump()["collecter_follower_count"], True)
        self.assertNotIn("TEST_SECRET", json.dumps(recherche.model_dump()))

    def test_entete_illustratif_et_valeur_manquante(self):
        texte = [{"id": "123", "author": "lemondefr",
                  "description": "Manifestation observée",
                  "follower_count": 25000}]
        sortie = text_export(
            texte, False, variables_txt=["profil", "id"],
            follower_count_illustratif=True)
        self.assertTrue(sortie.startswith(
            "*follower_count_25000 *profil_@lemondefr *id_123"))
        # Le codage de catégorie des médias est un champ illustratif
        # indépendant, ajouté automatiquement depuis l'inventaire.
        self.assertIn("*presse_nationale", sortie.splitlines()[0])
        sans = text_export(texte, False, variables_txt=["profil", "id"])
        self.assertNotIn("follower_count", sans)
        texte[0]["follower_count"] = None
        inconnu = text_export(
            texte, False, variables_txt=[],
            follower_count_illustratif=True)
        self.assertIn("*follower_count_indetermine", inconnu.splitlines()[0])
        self.assertIn("*presse_nationale", inconnu.splitlines()[0])
        self.assertTrue(inconnu.endswith("Manifestation observée\n"))
        texte[0]["follower_count"] = 0
        zero = text_export(
            texte, False, variables_txt=[],
            follower_count_illustratif=True)
        self.assertIn("*follower_count_0", zero.splitlines()[0])
        self.assertIn("*presse_nationale", zero.splitlines()[0])
        ia = text_export(
            texte, False, variables_txt=["id"], inclure_texte_genere_ia=True,
            follower_count_illustratif=True)
        self.assertIn("**** *source_original", ia)
        self.assertIn("*follower_count_0", ia.splitlines()[0])

    def test_une_requete_par_auteur_et_export_structures(self):
        videos = []
        for identifiant in ("7702367667616746785", "7702367667616746786"):
            videos.append(_fiche({
                "id": identifiant, "username": "lemondefr",
                "video_description": "Manifestation #manifestation",
                "create_time": 1760000000,
                "hashtag_names": ["manifestation"],
            }, "lemondefr"))
        def recherche(compte, limite, rapport, **kwargs):
            rapport.update(
                discovered_urls=[v["url"] for v in videos],
                metadonnees_api={v["id"]: v for v in videos},
                candidats_examines=2, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [v["url"] for v in videos]
        navigateur = Mock(side_effect=AssertionError(
            "Aucun navigateur ne doit être ouvert."))
        with tempfile.TemporaryDirectory() as dossier:
            travail = Job("test" * 16, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=3,
                variables_txt=["id", "profil"], collecter_follower_count=True,
                follower_count_illustratif=True,
                research_client_key="CLE_TEST", research_client_secret="SECRET_TEST",
            ), Path(dossier))
            with patch(
                "collecte.presse_research.collecter_videos_presse_research",
                side_effect=recherche
            ), patch(
                "collecte.researchapi.collecter_abonnes_research",
                return_value=12345
            ) as lire_abonnes:
                execute_job(travail, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(lire_abonnes.call_count, 1)
            self.assertEqual(len(travail.records), 2)
            self.assertEqual([v["follower_count"] for v in travail.records],
                             [12345, 12345])
            self.assertEqual([v["follower_count"] for v in travail.publications],
                             [12345, 12345])
            self.assertEqual(travail.texte_a_exporter().count(
                "*follower_count_12345"), 2)
            self.assertTrue(travail.snapshot()["collecter_follower_count"])
            self.assertTrue(travail.snapshot()["follower_count_illustratif"])
            chemin = Path(dossier)
            self.assertNotIn(b"SECRET_TEST", b"".join(
                p.read_bytes() for p in chemin.rglob("*")
                if p.is_file() and p.suffix in {".txt", ".json", ".csv"}))

    def test_refus_est_memoise_et_illustre_comme_inconnu(self):
        element = {"id": "123456789", "author": "lemondefr",
                   "description": "Manifestation", "follower_count": None}
        self.assertIn("*follower_count_indetermine",
                      text_export([element], False, variables_txt=["id"],
                                  follower_count_illustratif=True))
        def refuser(*args, **kwargs):
            raise ResearchAccesRefuse("HTTP 403")
        with self.assertRaises(ResearchAccesRefuse):
            collecter_abonnes_research("lemondefr", jeton="TEST",
                                      requete=refuser)


if __name__ == "__main__":
    unittest.main()
