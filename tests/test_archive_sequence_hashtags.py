"""Vérifier le ZIP réellement créé à la fin d'une séquence hashtags Research."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from webapp import Job, StartRequest, execute_job
from collecte.researchapi import _fiche


class TestsArchiveSequenceHashtags(unittest.TestCase):
    def test_sequence_partielle_genere_zip_txt_csv_avant_reprise(self):
        """Une séquence terminée produit les fichiers sans attendre la suivante."""
        video = {
            "id": "7000000000000000123",
            "username": "exemple",
            "video_description": "Manifestation #17octobre",
            "hashtag_names": ["17octobre"],
            "region_code": "FR",
            "create_time": 1791633600,
            "view_count": 100,
            "like_count": 12,
            "comment_count": 3,
            "share_count": 2,
            "favorites_count": 1,
        }
        fiche = _fiche(video, None)
        self.assertIsNotNone(fiche)

        def collecter(compte, limite, rapport, **options):
            self.assertIsNone(compte)
            self.assertIsNone(limite)
            self.assertEqual(options["maximum_candidats"], 1000)
            self.assertEqual(options["maximum_requetes"], 10)
            rapport.update({
                "discovered_urls": [fiche["url"]],
                "liens_page_research": [fiche["url"]],
                "metadonnees_api": {fiche["id"]: fiche},
                "candidats_examines": 1000,
                "requetes_tentees": 10,
                "pages_research": 10,
                "collecte_partielle": True,
                "discovery_stop": "lot_termine",
                "reprise_pagination_research": {
                    "indice_periode": 0,
                    "debut_periode": "20261001",
                    "fin_periode": "20261025",
                    "cursor": 1000,
                    "search_id": "recherche_test",
                },
            })
            options["progress"](1)
            return [fiche["url"]]

        with tempfile.TemporaryDirectory() as dossier:
            options = StartRequest(
                nom_sauvegarde="Manifestations octobre",
                source_collecte="hashtags",
                hashtag_moteur="research",
                hashtags_saisis=["17octobre"],
                date_debut="2026-10-01",
                date_fin="2026-10-25",
                variables_txt=["date", "profil", "id", "vues", "region_code"],
                research_client_key="cle_test",
                research_client_secret="secret_test",
            )
            job = Job("a" * 64, options, Path(dossier))
            with patch(
                "collecte.presse_research.collecter_videos_presse_research",
                side_effect=collecter
            ):
                execute_job(
                    job, driver_factory=Mock(
                        side_effect=AssertionError("Chrome ne doit pas démarrer")
                    )
                )

            self.assertFalse(job.busy)
            self.assertEqual(job.status, "partial", job.message)
            self.assertTrue(job.archive_prete, job.message)
            self.assertEqual(len(job.records), 1)
            chemin = job.directory / "archive.zip"
            self.assertTrue(chemin.is_file())
            with ZipFile(chemin) as archive:
                noms = set(archive.namelist())
                attendus = {
                    "textes.txt", "corpus_iramuteq.txt",
                    "publications.csv", "engagement.csv",
                    "ratios_engagement.csv", "commentaires.csv",
                    "bilan_hashtags.csv", "publications.json",
                    "journal.json",
                }
                self.assertTrue(attendus.issubset(noms), attendus - noms)
                texte = archive.read("textes.txt")
                self.assertIn(b"Manifestation", texte)
                self.assertEqual(archive.read("corpus_iramuteq.txt"), texte)
                self.assertIn(b"publication_id", archive.read("publications.csv"))
                self.assertIn(b"7000000000000000123", archive.read("engagement.csv"))
                self.assertIn(b"17octobre", archive.read("bilan_hashtags.csv"))

            # Le téléchargement utilise une copie du ZIP original dont les TXT
            # peuvent être actualisés sans modifier les autres exports.
            from corpus.export_zip import archive_avec_texte
            with archive_avec_texte(chemin, job.texte_a_exporter().encode("utf-8")) as flux:
                with ZipFile(flux) as resultat:
                    self.assertTrue(attendus.issubset(set(resultat.namelist())))
                    self.assertEqual(
                        resultat.read("corpus_iramuteq.txt"),
                        resultat.read("textes.txt")
                    )


    def test_deux_hashtags_enchainent_les_sequences_jusqu_au_zip_final(self):
        """Deux hashtags dépassent dix pages sans clic ni perte de max_count."""
        import json
        from collecte.researchapi import collecter_videos_presse_research

        demandes = []
        erreurs_api = []
        def api_tiktok(url, *, data, headers):
            corps = json.loads(data)
            conditions = corps["query"]["and"]
            tags = [
                valeur for condition in conditions
                if condition["field_name"] == "hashtag_name"
                for valeur in condition["field_values"]
            ]
            try:
                self.assertEqual(len(tags), 1)
                hashtag = tags[0]
                self.assertIn(hashtag, {"17octobre", "24octobre"})
                compteur = sum(1 for nom, _ in demandes if nom == hashtag) + 1
                demandes.append((hashtag, corps))
                self.assertEqual(corps["max_count"], 100)
                self.assertEqual(corps.get("cursor"), None if compteur == 1
                                 else compteur - 1)
            except AssertionError as erreur:
                erreurs_api.append(str(erreur) + " / requête=" + repr(corps))
                raise
            total = 12 if hashtag == "17octobre" else 3
            identifiant = 7000000000000000000 + (
                compteur if hashtag == "17octobre" else 100 + compteur)
            video = {
                "id": str(identifiant),
                "username": "exemple",
                "video_description": f"Manifestation #{hashtag}",
                "hashtag_names": [hashtag],
                "region_code": "FR",
                "create_time": 1792497600,
                "view_count": 100,
                "like_count": 10,
                "comment_count": 0,
                "share_count": 1,
                "favorites_count": 1,
            }
            return {"data": {
                "videos": [video],
                "has_more": compteur < total,
                "cursor": compteur,
                "search_id": "recherche_" + hashtag,
            }}

        def collecter(compte, limite, rapport, **options):
            return collecter_videos_presse_research(
                compte, limite, rapport, requete=api_tiktok,
                jeton="jeton_simule", pause=lambda _: None, **options)

        with tempfile.TemporaryDirectory() as dossier:
            options = StartRequest(
                nom_sauvegarde="Corpus deux hashtags",
                source_collecte="hashtags",
                hashtag_moteur="research",
                hashtags_saisis=["17octobre", "24octobre"],
                operator="OR",
                date_debut="2026-10-15",
                date_fin="2026-10-31",
                french_only=False,
                collecter_commentaires=False,
                collecter_follower_count=False,
                variables_txt=["date", "profil", "id", "vues"],
                research_client_key="cle_test",
                research_client_secret="secret_test",
            )
            job = Job("a" * 64, options, Path(dossier))
            with patch(
                "collecte.presse_research.collecter_videos_presse_research",
                side_effect=collecter
            ):
                execute_job(job, driver_factory=Mock(
                    side_effect=AssertionError("Chrome ne doit pas démarrer")))

            self.assertEqual(job.status, "completed",
                             (job.message, job.diagnostics, erreurs_api))
            self.assertFalse(job.busy)
            self.assertTrue(job.archive_prete, job.message)
            self.assertEqual(len(demandes), 15)
            self.assertEqual(len(job.records), 15)
            self.assertEqual(job.requetes_research_lot, 15)
            self.assertEqual(
                [x["statut_source"] for x in job.journal
                 if "source" in x], ["traitee", "traitee"])
            with ZipFile(job.directory / "archive.zip") as archive:
                self.assertIn("corpus_iramuteq.txt", archive.namelist())
                self.assertIn("publications.csv", archive.namelist())
                self.assertIn("engagement.csv", archive.namelist())
                self.assertIn("bilan_hashtags.csv", archive.namelist())
                self.assertIn(
                    b"7000000000000000103",
                    archive.read("publications.csv"))


if __name__ == "__main__":
    unittest.main()
