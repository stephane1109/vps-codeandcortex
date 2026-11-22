"""Vérifier le téléchargement unique des résultats ScrapTikTok."""
import csv
import io
import json
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
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

    def test_bouton_streamlit_produit_le_bilan_enrichi_et_non_un_csv_obsolete(self):
        """Le bouton fournit le contenu CSV calculé, sans ancien lien HTTP."""
        from collecte.suivi_hashtags import (
            COLONNES_HISTORIQUES, COLONNES_PAGINATION,
            exporter_bilan_hashtags_csv,
        )
        source = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        interface = source.read_text(encoding="utf-8")
        self.assertIn("contenu_bilan = exporter_bilan_hashtags_csv(bilan_sources)",
                      interface)
        self.assertIn("data=contenu_bilan", interface)
        self.assertIn('key="telecharger_bilan_hashtags_" + actuel["id"]',
                      interface)
        self.assertNotIn(
            'f"/api/jobs/{actuel[\'id\']}/bilan-hashtags.csv"',
            interface)
        self.assertIn(
            "set(COLONNES_PAGINATION).issubset(entete_bilan)", interface)
        # Exemple réel du format ancien : deux hashtags signalés terminés
        # malgré des nombres de liens très différents. Le nouveau fichier
        # garde les observations et complète systématiquement son en-tête.
        bilan = exporter_bilan_hashtags_csv([
            {"collecte_id": "a" * 32, "hashtag": "manifestation",
             "etat": "traitee", "liens": 1393,
             "motif": "Recherche terminée."},
            {"collecte_id": "a" * 32, "hashtag": "lyceen",
             "etat": "traitee", "liens": 0,
             "motif": "Recherche conjointe ET déjà effectuée."},
        ])
        lignes = list(csv.DictReader(
            io.StringIO(bilan.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(lignes), 2)
        self.assertTrue(
            set(COLONNES_HISTORIQUES + COLONNES_PAGINATION).issubset(lignes[0]))
        self.assertEqual(lignes[0]["liens"], "1393")
        self.assertEqual(lignes[1]["liens"], "0")
        self.assertEqual(lignes[0]["cursor"], "")
        self.assertEqual(lignes[0]["search_id"], "")
        self.assertEqual(lignes[0]["positions_research_json"], "")

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

    def test_bilan_hashtags_http_et_zip_conservent_les_colonnes_de_pagination(self):
        """La réponse téléchargée, y compris dans un ancien ZIP, garde le curseur."""
        from fastapi.testclient import TestClient
        from webapp import Job, Manager, create_app, COOKIE
        with tempfile.TemporaryDirectory() as dossier:
            manager = Manager(data_dir=dossier)
            with TestClient(create_app(manager)) as client:
                client.get("/")
                proprietaire = client.cookies[COOKIE]
                options = StartRequest(
                    nom_sauvegarde="Bilan Research avec curseur",
                    source_collecte="hashtags",
                    hashtag_moteur="research",
                    hashtags_saisis=["manifestation", "lyceen"],
                    date_debut="2026-10-01",
                    date_fin="2026-10-31",
                    research_client_key="cle_test",
                    research_client_secret="secret_test",
                )
                job = Job(proprietaire, options, Path(dossier))
                job.journal = [{
                    "source": "#manifestation",
                    "statut_source": "partielle",
                    "message": "Research API HTTP 401",
                    "rapport": {
                        "collecte_partielle": True,
                        "discovery_stop": "research_refus_ou_erreur",
                        "pages_research": 1,
                        "requetes_tentees": 2,
                        "candidats_examines": 150,
                        "discovered_urls": [
                            "https://www.tiktok.com/@exemple/video/7000000000000000001"],
                        "reprise_pagination_research": {
                            "indice_periode": 0,
                            "debut_periode": "20261001",
                            "fin_periode": "20261031",
                            "cursor": 150,
                            "search_id": "recherche_sauvegardee",
                        },
                    },
                }]
                job.status = "partial"
                job.busy = False
                job.archive_prete = True
                with ZipFile(job.directory / "archive.zip", "w") as archive:
                    archive.writestr(
                        "bilan_hashtags.csv",
                        "collecte_id;hashtag;etat;liens;motif\\n")
                    archive.writestr("textes.txt", "Corpus existant")
                manager.jobs[job.id] = job

                reponse = client.get(
                    f"/api/jobs/{job.id}/bilan-hashtags.csv")
                self.assertEqual(reponse.status_code, 200, reponse.text)
                self.assertIn("no-store", reponse.headers["cache-control"])
                self.assertIn("bilan_hashtags", reponse.headers[
                    "content-disposition"])
                lignes = list(csv.DictReader(
                    io.StringIO(reponse.content.decode("utf-8-sig")),
                    delimiter=";"))
                self.assertEqual(len(lignes), 2)
                self.assertEqual(lignes[0]["cursor"], "150")
                self.assertEqual(
                    lignes[0]["search_id"], "recherche_sauvegardee")
                self.assertEqual(lignes[0]["date_debut"], "2026-10-01")
                self.assertEqual(lignes[0]["date_fin"], "2026-10-31")
                self.assertEqual(
                    lignes[0]["arret_research"], "research_refus_ou_erreur")
                self.assertEqual(lignes[0]["pages_research"], "1")
                self.assertEqual(lignes[0]["requetes_tentees"], "2")
                self.assertEqual(lignes[0]["candidats_examines"], "150")
                self.assertIn(
                    "#manifestation", lignes[0]["positions_research_json"])
                self.assertEqual(lignes[1]["hashtag"], "lyceen")
                self.assertEqual(lignes[1]["cursor"], "")

                reponse_zip = client.get(f"/api/jobs/{job.id}/archive")
                self.assertEqual(
                    reponse_zip.status_code, 200, reponse_zip.text)
                with ZipFile(io.BytesIO(reponse_zip.content)) as archive:
                    noms = archive.namelist()
                    self.assertEqual(noms.count("bilan_hashtags.csv"), 1)
                    bilan_zip = archive.read("bilan_hashtags.csv")
                    lignes_zip = list(csv.DictReader(
                        io.StringIO(bilan_zip.decode("utf-8-sig")),
                        delimiter=";"))
                    # Les deux téléchargements reçoivent un horodatage
                    # d'export distinct, mais leur pagination est identique.
                    for ligne_zip, ligne_http in zip(lignes_zip, lignes):
                        for champ in ("collecte_id", "hashtag", "etat",
                                      "date_debut", "date_fin", "cursor",
                                      "search_id", "positions_research_json",
                                      "arret_research", "pages_research",
                                      "requetes_tentees", "candidats_examines"):
                            self.assertEqual(
                                ligne_zip[champ], ligne_http[champ])

    def test_arret_research_inscrit_cause_et_garde_curseur_csv(self):
        """Un arrêt après 150 vidéos reste explicite et reprenable."""
        from webapp import Job, signaler_arret_source_research
        from collecte.suivi_hashtags import (
            etablir_bilan_hashtags, exporter_bilan_hashtags_csv)
        with tempfile.TemporaryDirectory() as dossier:
            options = StartRequest(
                nom_sauvegarde="Arret pendant collecte Research",
                source_collecte="hashtags",
                hashtag_moteur="research",
                hashtags_saisis=["manifestation", "lyceen"],
                date_debut="2026-10-01", date_fin="2026-10-31",
                research_client_key="cle_test",
                research_client_secret="secret_test",
            )
            job = Job("proprietaire_test", options, Path(dossier))
            job.source_en_cours_id = "#manifestation"
            job.journal = [{
                "source": "#manifestation",
                "statut_source": "en_cours",
                "message": "Recherche Research en cours",
                "rapport": {
                    "collecte_partielle": True,
                    "discovered_urls": [
                        "https://www.tiktok.com/@x/video/7000000000000000001"],
                    "reprise_pagination_research": {
                        "indice_periode": 0, "debut_periode": "20261001",
                        "fin_periode": "20261031",
                        "cursor": 150, "search_id": "recherche_active",
                    },
                },
            }]
            job.demander_arret("duree_maximale")
            signaler_arret_source_research(job)
            bilan = etablir_bilan_hashtags(
                options.hashtags, False, job.journal,
                source_en_cours=job.source_en_cours_id,
                termine=True, collecte_id=job.id,
                date_debut=options.date_debut, date_fin=options.date_fin)
            lignes = list(csv.DictReader(io.StringIO(
                exporter_bilan_hashtags_csv(bilan).decode("utf-8-sig")),
                delimiter=";"))
            self.assertEqual(lignes[0]["etat"], "interrompue")
            self.assertIn("Durée maximale", lignes[0]["motif"])
            self.assertEqual(lignes[0]["cursor"], "150")
            self.assertEqual(lignes[0]["search_id"], "recherche_active")
            self.assertEqual(
                lignes[0]["arret_research"], "arret_duree_maximale")
            self.assertEqual(
                job.journal[0]["rapport"]["discovery_stop"],
                "arret_duree_maximale")
            self.assertEqual(lignes[1]["etat"], "non_commencee")

    def test_watchdog_research_ignore_absence_de_polling_streamlit(self):
        """Une collecte Research ne doit pas s'arrêter après 5 ou 30 min."""
        from webapp import Job, Manager
        with tempfile.TemporaryDirectory() as dossier:
            manager = Manager(data_dir=dossier)
            manager.idle_timeout = 300
            manager.max_duration = 1800
            options = StartRequest(
                nom_sauvegarde="Research longue",
                source_collecte="hashtags",
                hashtag_moteur="research",
                hashtags_saisis=["manifestation"],
                research_client_key="cle_test",
                research_client_secret="secret_test",
            )
            job = Job("proprietaire_test", options, Path(dossier))
            job.created = time.monotonic() - 3600
            job.last_seen = time.monotonic() - 1200
            manager.jobs[job.id] = job
            with patch(
                    "ticket_gate.verifier_session_active",
                    return_value=True):
                manager.cleanup()
            self.assertFalse(job.stop.is_set())
            self.assertIsNone(job.cause_arret)
            self.assertIsNone(
                job.limites_debug["inactivite_max_s"])
            self.assertGreaterEqual(
                job.limites_debug["duree_max_s"], 86400)

    def test_watchdog_navigateur_conserve_son_delai_inactivite(self):
        """Ne pas modifier les contrôles des moteurs navigateur existants."""
        from webapp import Job, Manager
        with tempfile.TemporaryDirectory() as dossier:
            manager = Manager(data_dir=dossier)
            manager.idle_timeout = 300
            manager.max_duration = 1800
            options = StartRequest(
                nom_sauvegarde="Navigateur court",
                source_collecte="hashtags",
                hashtag_moteur="navigateur",
                hashtags_saisis=["manifestation"],
                limit=50,
            )
            job = Job("proprietaire_test", options, Path(dossier))
            job.created = time.monotonic() - 400
            job.last_seen = time.monotonic() - 350
            manager.jobs[job.id] = job
            with patch(
                    "ticket_gate.verifier_session_active",
                    return_value=True):
                manager.cleanup()
            self.assertTrue(job.stop.is_set())
            self.assertEqual(
                job.cause_arret["code"], "inactivite")

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
