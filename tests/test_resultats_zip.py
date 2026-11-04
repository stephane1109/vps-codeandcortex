"""Vérifier le téléchargement unique des résultats ScrapTikTok."""
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from corpus.export_zip import archive_avec_texte
from stockage.collectes_research import creer_plan, enregistrer_partiel, exporter
from webapp import StartRequest


class TestsZipResultats(unittest.TestCase):
    def test_zip_ponctuel_conserve_les_fichiers_et_ajoute_les_complements(self):
        """Le bouton unique ne perd aucun ancien CSV ou JSON."""
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "archive.zip"
            with ZipFile(chemin, "w") as archive:
                archive.writestr("engagement.csv", "vues;likes\n100;1\n")
                archive.writestr("publications.csv", "id;vues\n123;100\n")
                archive.writestr("publications.json", '[{"id":"123"}]')
                archive.writestr("commentaires.csv", "id;texte\n")
                archive.writestr("textes.txt", "Ancien texte")
            flux = archive_avec_texte(
                chemin, b"Texte actualis\xc3\xa9",
                {
                    "commentaires.txt": b"*id_123\n@auteur\nCommentaire\n",
                    "diagnostic_collecte.json": b'{"statut":"completed"}',
                },
            )
            with flux, ZipFile(flux) as resultat:
                noms = resultat.namelist()
                self.assertEqual(len(noms), len(set(noms)))
                self.assertTrue({
                    "engagement.csv", "publications.csv", "publications.json",
                    "commentaires.csv", "textes.txt", "corpus_iramuteq.txt",
                    "commentaires.txt", "diagnostic_collecte.json",
                }.issubset(noms))
                self.assertEqual(resultat.read("engagement.csv"), b"vues;likes\n100;1\n")
                self.assertEqual(resultat.read("textes.txt"), b"Texte actualis\xc3\xa9")
                self.assertEqual(resultat.read("commentaires.txt"),
                                 b"*id_123\n@auteur\nCommentaire\n")

    def test_ancienne_collecte_zip_reconstruit_bilan_hashtags_sans_csv_existant(self):
        """Une ancienne archive sans bilan doit rester réimportable."""
        from fastapi.testclient import TestClient
        from webapp import Job, Manager, create_app, COOKIE
        with tempfile.TemporaryDirectory() as dossier:
            manager = Manager(data_dir=dossier)
            with TestClient(create_app(manager)) as client:
                client.get("/")
                proprietaire = client.cookies[COOKIE]
                options = StartRequest(
                    nom_sauvegarde="Collecte historique deux hashtags",
                    source_collecte="hashtags",
                    hashtag_moteur="research",
                    hashtags_saisis=["17octobre", "24octobre"],
                    research_client_key="cle_test",
                    research_client_secret="secret_test",
                )
                job = Job(proprietaire, options, Path(dossier))
                job.journal = [{
                    "source": "#17octobre",
                    "statut_source": "partielle",
                    "rapport": {"collecte_partielle": True,
                                "discovered_urls": [
                                    "https://www.tiktok.com/@exemple/video/7000000000000000123"
                                ]},
                }]
                job.busy = False
                job.status = "partial"
                job.archive_prete = True
                job.source_en_cours_id = "#17octobre"
                with ZipFile(job.directory / "archive.zip", "w") as archive:
                    archive.writestr("textes.txt", "Texte ancien")
                    archive.writestr("publications.csv", "id;texte\\n123;ancien\\n")
                manager.jobs[job.id] = job
                reponse = client.get(f"/api/jobs/{job.id}/archive")
                self.assertEqual(reponse.status_code, 200, reponse.text)
                with ZipFile(io.BytesIO(reponse.content)) as archive:
                    noms = archive.namelist()
                    self.assertIn("bilan_hashtags.csv", noms)
                    self.assertEqual(noms.count("bilan_hashtags.csv"), 1)
                    bilan = archive.read("bilan_hashtags.csv").decode("utf-8-sig")
                    self.assertIn("17octobre", bilan)
                    self.assertIn("24octobre", bilan)
                    self.assertIn(job.id, bilan)
                    self.assertEqual(
                        archive.read("publications.csv"),
                        b"id;texte\\n123;ancien\\n")

    def test_zip_research_contient_la_base_sqlite_et_les_autres_formats(self):
        """Le ZIP programmé intègre les six anciens téléchargements."""
        with tempfile.TemporaryDirectory() as dossier:
            options = {
                "nom_sauvegarde": "Manifestations lycéennes 2026",
                "source_collecte": "presse",
                "medias": ["lemonde"],
                "date_debut": "2026-10-01",
                "date_fin": "2026-10-31",
                "variables_txt": ["date", "profil", "id", "region_code",
                                  "is_verified", "vues", "hashtags"],
                "include_sources": True,
            }
            identifiant = creer_plan(
                dossier, "proprietaire", options,
                "2026-11-01", "2026-11-10")
            enregistrer_partiel(dossier, identifiant, {
                "id": "123", "url": "https://www.tiktok.com/@exemple/video/123",
                "author": "exemple", "description": "Manifestation lycéenne",
                "created_at": "2026-10-30T15:00:00+00:00",
                "region_code": "FR", "is_verified": False,
                "engagement": {
                    "vues": {"valeur": 100, "brut": "100"},
                    "likes": {"valeur": 5, "brut": "5"},
                },
                "retenue": True,
            }, [])
            contenu = exporter(dossier, identifiant, "proprietaire", "zip")
            with ZipFile(io.BytesIO(contenu)) as archive:
                attendus = {
                    "publications.csv", "commentaires.csv",
                    "collecte.json", "textes.txt", "corpus.sqlite3",
                    "journal_research.json",
                }
                self.assertTrue(attendus.issubset(archive.namelist()))
                self.assertEqual(
                    archive.read("publications.csv"),
                    exporter(dossier, identifiant, "proprietaire", "csv"))
                self.assertEqual(
                    archive.read("textes.txt"),
                    exporter(dossier, identifiant, "proprietaire", "txt"))
                self.assertEqual(
                    json.loads(archive.read("collecte.json"))["publications"][0]["id"],
                    "123")
                base = archive.read("corpus.sqlite3")
                self.assertTrue(base.startswith(b"SQLite format 3\x00"))
                self.assertIn(b"123", base)

    def test_nom_du_fichier_provient_du_champ_de_collecte(self):
        """Le nom existant est utilisé sans création d'un autre champ."""
        parametres = StartRequest(
            nom_sauvegarde=" Manifestations lycéennes 2026 ",
            hashtag="manifestation")
        self.assertEqual(parametres.filename, "Manifestations_lycéennes_2026.txt")
        interface = (Path(__file__).resolve().parents[1]
                     / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('"Nom de la collecte *", key="nom_sauvegarde"', interface)
        self.assertEqual(interface.count('"Télécharger les résultats"'), 1)
        self.assertNotIn('"Télécharger l’archive ZIP"', interface)


if __name__ == "__main__":
    unittest.main()
