"""Tests multihashtags : validation, compatibilité, filtres et collecte sans réseau."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from collecte.selection_hashtags import (
    MAX_HASHTAGS, normaliser_liste_hashtags, separer_saisie_hashtags,
)
from connect_htag import ConnexionHashtag
from connect_profil import ConnexionProfil
from webapp import Job, StartRequest, matches_hashtags


class TestsHashtagsMultiples(unittest.TestCase):
    def test_saisie_multiligne_et_dedoublonnage(self):
        saisie = "#Manifestation, manifestation; #lycéens\n#mobilisation #LYCÉENS"
        valeurs = normaliser_liste_hashtags(separer_saisie_hashtags(saisie))
        self.assertEqual(valeurs, ["Manifestation", "lycéens", "mobilisation"])
        self.assertEqual(MAX_HASHTAGS, 10)

    def test_liste_dix_hashtags_et_limites(self):
        valeurs = [f"mot{indice}" for indice in range(10)]
        demande = StartRequest(source_collecte="hashtags", hashtags_saisis=valeurs)
        self.assertEqual(demande.hashtags, valeurs)
        with self.assertRaisesRegex(ValueError, "maximum 10"):
            StartRequest(source_collecte="hashtags", hashtags_saisis=valeurs + ["mot10"])
        with self.assertRaisesRegex(ValueError, "hashtag"):
            StartRequest(source_collecte="hashtags", hashtags_saisis=["#valide", "https://exemple.org"])
        with self.assertRaisesRegex(ValueError, "hashtag"):
            StartRequest(source_collecte="hashtags", hashtags_saisis=[])

    def test_ancienne_interface_et_liste_nouvelle(self):
        ancienne = StartRequest(hashtag="#politique", second_hashtag="#société", operator="OR")
        self.assertEqual(ancienne.hashtags, ["politique", "société"])
        demande = StartRequest(
            hashtag="ancien", second_hashtag="autre",
            hashtags_saisis=["#manifestation", "#lycéens", "manifestation", "#mobilisation"])
        self.assertEqual(demande.hashtags, ["manifestation", "lycéens", "mobilisation"])
        self.assertEqual(demande.hashtag, "manifestation")
        self.assertEqual(demande.second_hashtag, "lycéens")
        self.assertEqual(demande.model_dump()["hashtags_saisis"], demande.hashtags)
        presse = StartRequest(source_collecte="presse", medias=["lemonde"],
                              hashtags_saisis=["#horssujet"])
        self.assertEqual(presse.hashtags, [])

    def test_operateurs_et_ou_sur_toute_la_liste(self):
        demande = StartRequest(
            hashtags_saisis=["manifestation", "lycéens", "mobilisation"],
            operator="AND", rechercher_dans_texte=False)
        self.assertFalse(matches_hashtags("#manifestation #lycéens", demande))
        self.assertTrue(matches_hashtags("#manifestation #lycéens #mobilisation", demande))
        demande.operator = "OR"
        self.assertTrue(matches_hashtags("Annonce #lycéens uniquement", demande))
        self.assertFalse(matches_hashtags("Autre publication", demande))
        demande.rechercher_dans_texte = True
        self.assertTrue(matches_hashtags("Mobilisation des élèves", demande))

    def test_sources_hashtags_budget_global_et_profils(self):
        demande = StartRequest(
            source_collecte="hashtags", hashtags_saisis=["premier", "deuxieme", "troisieme"],
            limit=8)
        connexion = ConnexionHashtag(SimpleNamespace(limit=8), fabrique=Mock())
        sources = connexion.preparer_sources(demande)
        self.assertEqual([source["hashtag"] for source in sources],
                         ["premier", "deuxieme", "troisieme"])
        self.assertEqual(connexion._quota_hashtag, {
            "premier": 3, "deuxieme": 3, "troisieme": 2})
        profil = StartRequest(
            source_collecte="comptes", comptes=["lemondefr"],
            hashtags_saisis=["premier", "deuxieme", "troisieme"])
        connexion_profil = ConnexionProfil(SimpleNamespace(limit=8), fabrique=Mock())
        sources_profil = connexion_profil.preparer_sources(profil)
        self.assertEqual(sources_profil[0]["compte"], "lemondefr")
        self.assertEqual(connexion_profil.hashtags, tuple(profil.hashtags))

    def test_restauration_snapshot_et_nom_fichier_borne(self):
        valeurs = [f"hashtagsuperlong{indice}" * 8 for indice in range(10)]
        demande = StartRequest(hashtags_saisis=valeurs)
        self.assertLess(len(demande.filename.encode("utf-8")), 230)
        with tempfile.TemporaryDirectory() as dossier:
            travail = Job("test", demande, Path(dossier))
            self.assertEqual(travail.snapshot()["hashtags_saisis"], demande.hashtags)


if __name__ == "__main__":
    unittest.main()
