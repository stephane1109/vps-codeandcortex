"""Tests de reprise Research sur le même identifiant et le même corpus."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from collecte.reprise_collecte import (
    initialiser_donnees_reprise,
    preparer_reprise_medias,
)


class TestsReprendreCollecte(unittest.TestCase):

    def setUp(self):
        self.medias = [
            {"id": "media_1", "compte": "journal1", "nom": "Journal 1"},
            {"id": "media_2", "compte": "journal2", "nom": "Journal 2"},
            {"id": "media_3", "compte": "journal3", "nom": "Journal 3"},
        ]
        self.journal = [
            {"source": "@journal1", "statut_source": "traitee",
             "rapport": {"media_id": "media_1", "discovered_urls": []}},
            {"source": "@journal2", "statut": "inaccessible",
             "rapport": {"media_id": "media_2", "discovered_urls": []},
             "message": "Research API HTTP 500."},
        ]

    def test_reprendre_uniquement_media_en_echec_et_non_commence(self):
        choix, bilan = preparer_reprise_medias(self.medias, self.journal)
        self.assertEqual(choix, ["media_2", "media_3"])
        self.assertEqual([ligne["etat"] for ligne in bilan],
                         ["traitee", "echec", "non_commencee"])

    def test_refuser_media_deja_traite(self):
        with self.assertRaisesRegex(ValueError, "uniquement les médias inachevés"):
            preparer_reprise_medias(self.medias, self.journal, ["media_1"])

    def test_accepter_sous_ensemble_sans_alterer_ordre(self):
        choix, _ = preparer_reprise_medias(
            self.medias, self.journal, ["media_3", "media_2"])
        self.assertEqual(choix, ["media_3", "media_2"])

    def test_refuser_selection_en_double(self):
        with self.assertRaisesRegex(ValueError, "plusieurs fois"):
            preparer_reprise_medias(self.medias, self.journal,
                                   ["media_2", "media_2"])

    def test_journal_remplace_ancien_echec_par_succes(self):
        nouveau = self.journal + [{
            "source": "@journal2", "statut_source": "traitee",
            "rapport": {"media_id": "media_2", "discovered_urls": []}
        }]
        choix, bilan = preparer_reprise_medias(self.medias, nouveau)
        self.assertEqual(choix, ["media_3"])
        self.assertEqual(bilan[1]["etat"], "traitee")

    def test_restaurer_publications_commentaires_et_compteur(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = Path(temporaire)
            publications = [
                {"id": "1111111111", "url": "https://www.tiktok.com/@journal1/video/1111111111",
                 "retenue": True, "description": "Texte précédent"},
                {"id": "2222222222", "url": "https://www.tiktok.com/@journal1/video/2222222222",
                 "retenue": False, "description": "Texte filtré"},
            ]
            commentaires = [{"id": "c1", "publication_id": "1111111111", "texte": "Avis"}]
            (dossier / "publications.json").write_text(
                json.dumps(publications), encoding="utf-8")
            (dossier / "commentaires.json").write_text(
                json.dumps(commentaires), encoding="utf-8")
            (dossier / "journal.json").write_text(
                json.dumps({"evenements": self.journal}), encoding="utf-8")
            job = SimpleNamespace()
            compte = initialiser_donnees_reprise(
                job, dossier, {"traites": 5, "source_en_cours_id": "media_2"},
                ["media_2", "media_3"])
            self.assertEqual(compte, 2)
            self.assertEqual(job.processed, 2)
            self.assertEqual(job.reprise_decalage, 3)
            self.assertEqual(len(job.publications), 2)
            self.assertEqual(len(job.records), 1)
            self.assertEqual(len(job.commentaires), 1)
            self.assertEqual(len(job.journal), 2)
            self.assertEqual(job.medias_reprise, ["media_2", "media_3"])
            self.assertEqual(job.source_en_cours_id, "media_2")
            self.assertEqual(job._pg_publications, 2)
            self.assertTrue(job._pg_initialise)
            self.assertFalse(job.archive_prete)

    def test_refuser_journal_absent_pour_ne_pas_perdre_l_historique(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = Path(temporaire)
            (dossier / "publications.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "journal.json"):
                initialiser_donnees_reprise(
                    SimpleNamespace(), dossier, {"traites": 0}, ["media_2"])


if __name__ == "__main__":
    unittest.main()
