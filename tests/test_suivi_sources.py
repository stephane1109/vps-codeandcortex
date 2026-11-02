"""Tests du bilan des médias et de la sélection de reprise du lendemain."""
import unittest

from collecte.suivi_sources import (
    etablir_bilan_medias, exporter_bilan_medias_csv,
    importer_bilan_medias_csv, medias_a_reprendre,
)


class TestsSuiviSourcesMedias(unittest.TestCase):

    def setUp(self):
        self.sources = [
            {"id": "media_1", "nom": "Premier", "compte": "premier"},
            {"id": "media_2", "nom": "Deuxième", "compte": "deuxieme"},
            {"id": "media_3", "nom": "Troisième", "compte": "troisieme"},
            {"id": "media_4", "nom": "Quatrième", "compte": "quatrieme"},
        ]

    def test_quota_apres_deux_sources(self):
        journal = [
            {"source": "@premier", "rapport": {
                "media_id": "media_1", "discovered_urls": ["url1"]},
             "statut_source": "traitee", "message": "Recherche terminée."},
            {"source": "@deuxieme", "rapport": {
                "media_id": "media_2", "discovered_urls": ["url2"]},
             "statut_source": "interrompue", "message": "Quota Research atteint."},
        ]
        bilan = etablir_bilan_medias(
            self.sources, journal, source_en_cours="media_2", termine=True)
        self.assertEqual([ligne["etat"] for ligne in bilan], [
            "traitee", "interrompue", "non_commencee", "non_commencee"])
        self.assertEqual(medias_a_reprendre(bilan), [
            "media_2", "media_3", "media_4"])

    def test_source_en_cours_au_moment_de_l_arret(self):
        journal = [{"source": "@premier", "rapport": {
            "media_id": "media_1", "discovered_urls": []},
            "statut_source": "en_cours"}]
        bilan = etablir_bilan_medias(
            self.sources, journal, source_en_cours="media_1", termine=True)
        self.assertEqual(bilan[0]["etat"], "interrompue")
        self.assertEqual(bilan[1]["etat"], "non_commencee")

    def test_aucune_video_n_implique_pas_une_absence_de_recherche(self):
        journal = [{"source": "@premier", "rapport": {
            "media_id": "media_1", "discovered_urls": []},
            "statut_source": "traitee"}]
        bilan = etablir_bilan_medias(self.sources, journal, termine=True)
        self.assertEqual(bilan[0]["etat"], "traitee")
        self.assertEqual(bilan[0]["liens"], 0)

    def test_ancien_journal_sans_etat(self):
        journal = [{"source": "@premier", "rapport": {
            "discovered_urls": ["url1"]}},
            {"source": "@deuxieme", "statut": "inaccessible",
             "rapport": {"discovered_urls": []}}]
        bilan = etablir_bilan_medias(self.sources, journal, termine=True)
        self.assertEqual([r["etat"] for r in bilan[:2]],
                         ["traitee", "echec"])

    def test_export_import_reconstitue_selection_dans_l_ordre(self):
        journal = [{"source": "@premier", "statut_source": "traitee",
                    "rapport": {"media_id": "media_1"}}]
        bilan = etablir_bilan_medias(self.sources, journal, termine=True)
        fichier = exporter_bilan_medias_csv(bilan)
        self.assertTrue(fichier.startswith(b"\xef\xbb\xbf"))
        selection, absents = importer_bilan_medias_csv(
            fichier, {s["id"]: s for s in self.sources})
        self.assertEqual(selection, ["media_2", "media_3", "media_4"])
        self.assertEqual(absents, [])

    def test_media_supprime_du_catalogue_est_signale(self):
        bilan = etablir_bilan_medias(self.sources, [], termine=True)
        selection, absents = importer_bilan_medias_csv(
            exporter_bilan_medias_csv(bilan), {"media_1": self.sources[0]})
        self.assertEqual(selection, ["media_1"])
        self.assertEqual(absents, ["media_2", "media_3", "media_4"])

    def test_fichier_invalide_refuse(self):
        with self.assertRaisesRegex(ValueError, "pas un bilan"):
            importer_bilan_medias_csv(b"id;etat\nmedia_1;traitee",
                                     {"media_1": self.sources[0]})
        with self.assertRaisesRegex(ValueError, "invalide"):
            importer_bilan_medias_csv(b"media_id;etat\nmedia_1;pirate",
                                     {"media_1": self.sources[0]})


if __name__ == "__main__":
    unittest.main()
