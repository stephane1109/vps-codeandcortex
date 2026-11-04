"""Tests de restauration des historiques manquants sans réinitialisation."""
import base64
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient

import webapp as web
from collecte.suivi_hashtags import exporter_bilan_hashtags_csv
from interface.reprise_hashtags_ui import reprendre_depuis_bilans_csv
from stockage.historique_analyses import retrouver
from stockage.recuperation_hashtags import (
    reconstruire_historique, restaurer_depuis_zip,
    retrouver_ou_reconstruire,
)


class TestsRecuperationHashtags(unittest.TestCase):
    def setUp(self):
        self.identifiant = "a" * 32
        self.nom = "Corpus original de 521 publications"
        self.publications = [
            {"id": str(7000000000000000000 + i),
             "url": "https://www.tiktok.com/@exemple/video/"
                    + str(7000000000000000000 + i),
             "description": "#17octobre", "author": "exemple",
             "retenue": True, "engagement": {}}
            for i in range(521)
        ]
        options = web.StartRequest(
            nom_sauvegarde=self.nom,
            source_collecte="hashtags",
            hashtag_moteur="research",
            hashtags_saisis=["17octobre", "24octobre"],
            date_debut="2026-10-01", date_fin="2026-10-31",
            research_client_key="cle_initiale",
            research_client_secret="secret_initial",
        )
        parametres = options.model_dump(mode="json")
        parametres["research_client_key"] = None
        parametres["research_client_secret"] = None
        self.journal = {
            "session": self.identifiant, "statut": "partial",
            "parametres": parametres,
            "compteurs_collecte": {"traitees": 521},
            "evenements": [{
                "source": "#17octobre",
                "statut_source": "partielle",
                "rapport": {
                    "collecte_partielle": True,
                    "reprise_pagination_research": {
                        "indice_periode": 0,
                        "debut_periode": "20261001",
                        "fin_periode": "20261031",
                        "cursor": 600,
                        "search_id": "page_suivante",
                    },
                },
            }],
        }
        tampon = BytesIO()
        with ZipFile(tampon, "w") as archive:
            archive.writestr(
                "publications.json",
                json.dumps(self.publications, ensure_ascii=False))
            archive.writestr(
                "journal.json",
                json.dumps(self.journal, ensure_ascii=False))
            archive.writestr("commentaires.json", "[]")
            archive.writestr("bilan_hashtags.csv", "collecte_id;hashtag;etat;liens;motif\n")
        self.zip = tampon.getvalue()
        self.cookie = "cookie_historique_prive_test"

    def test_restaurer_depuis_zip_sans_perdre_521_publications(self):
        """Recréer l'index local, le journal et le corpus original."""
        with tempfile.TemporaryDirectory() as dossier:
            with patch(
                "stockage.recuperation_hashtags.verifier_propriete_postgres",
                return_value=(self.nom, 521)):
                identifiant = restaurer_depuis_zip(
                    dossier, self.identifiant, self.cookie,
                    base64.b64encode(self.zip).decode("ascii"))
                archive = retrouver(dossier, identifiant, self.cookie)
            self.assertIsNotNone(archive)
            _, emplacement, manifeste = archive
            self.assertEqual(manifeste["id"], self.identifiant)
            self.assertEqual(manifeste["publications"], 521)
            self.assertEqual(
                len(json.loads((emplacement / "publications.json").read_text())),
                521)
            recuperation = json.loads((emplacement / "journal.json").read_text())
            self.assertEqual(
                recuperation["evenements"][0]["rapport"][
                    "reprise_pagination_research"]["cursor"], 600)

    def test_retrouver_archive_locale_si_index_absent(self):
        """Retrouver une collecte dans sessions/id même sans index SQLite."""
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "sessions" / self.identifiant
            source.mkdir(parents=True)
            (source / "publications.json").write_text(
                json.dumps(self.publications), encoding="utf-8")
            (source / "journal.json").write_text(
                json.dumps(self.journal), encoding="utf-8")
            with patch(
                "stockage.recuperation_hashtags.verifier_propriete_postgres",
                return_value=(self.nom, 521)):
                archive = retrouver_ou_reconstruire(
                    dossier, self.identifiant, self.cookie)
            self.assertIsNotNone(archive)
            self.assertEqual(archive[2]["publications"], 521)

    def test_restaurer_depuis_postgres_si_journal_durable_disponible(self):
        """La perte des fichiers historiques ne force plus le redémarrage."""
        sauvegarde = {
            "id": self.identifiant, "nom": self.nom,
            "statut": "partial", "traitees": 521,
            "parametres": self.journal["parametres"],
            "journal": self.journal["evenements"],
            "source_en_cours_id": "#17octobre",
            "publications": self.publications,
            "commentaires": [], "republications": [],
        }
        with tempfile.TemporaryDirectory() as dossier:
            with (
                patch("stockage.postgres_consultation.adresse_configuree",
                      return_value=True),
                patch("stockage.postgres_consultation.lire_archive_reprise_hashtags",
                      return_value=sauvegarde),
                patch(
                    "stockage.recuperation_hashtags.verifier_propriete_postgres",
                    return_value=(self.nom, 521)),
            ):
                archive = retrouver_ou_reconstruire(
                    dossier, self.identifiant, self.cookie)
            self.assertIsNotNone(archive)
            self.assertEqual(archive[2]["publications"], 521)
            journal = json.loads(
                (archive[1] / "journal.json").read_text(encoding="utf-8"))
            self.assertEqual(journal["evenements"][0]["rapport"][
                "reprise_pagination_research"]["cursor"], 600)
            self.assertEqual(archive[2]["source_en_cours_id"], "#17octobre")

    def test_postgres_sans_journal_exige_zip_original(self):
        """Le nombre de publications n'est pas un curseur de pagination."""
        with tempfile.TemporaryDirectory() as dossier:
            with (
                patch("stockage.postgres_consultation.adresse_configuree",
                      return_value=True),
                patch("stockage.postgres_consultation.lire_archive_reprise_hashtags",
                      return_value=None),
            ):
                archive = retrouver_ou_reconstruire(
                    dossier, self.identifiant, self.cookie)
            self.assertIsNone(archive)

    def test_csv_manifestation_521_lyceen_zero_reprise_sans_zip(self):
        """La structure réelle du CSV restaure le corpus sans curseur."""
        parametres = web.StartRequest(
            nom_sauvegarde=self.nom,
            source_collecte="hashtags", hashtag_moteur="research",
            hashtags_saisis=["manifestation", "lyceen"],
            date_debut="2026-10-01", date_fin="2026-10-31",
            research_client_key="cle_simulee",
            research_client_secret="secret_simule",
        ).model_dump(mode="json")
        bilans = [
            exporter_bilan_hashtags_csv([
                {"collecte_id": self.identifiant, "hashtag": "manifestation",
                 "etat": "partielle", "liens": 521,
                 "motif": "Research API officielle : Research API HTTP 401 "
                          ": autorisation, droits ou quota officiel à vérifier."},
            ]),
            exporter_bilan_hashtags_csv([
                {"collecte_id": self.identifiant, "hashtag": "lyceen",
                 "etat": "non_commencee", "liens": 0, "motif": ""},
            ]),
        ]
        sauvegarde = {
            "id": self.identifiant, "nom": self.nom,
            "statut": "partial", "traitees": 521,
            "parametres": parametres, "journal": [],
            "source_en_cours_id": None,
            "cree_le": datetime(2026, 10, 25, tzinfo=timezone.utc),
            "publications": self.publications,
            "commentaires": [], "republications": [],
        }
        termine = threading.Event()
        resultat = {}

        def sans_tiktok(job):
            resultat.update(
                id=job.id, publications=len(job.publications),
                traitees=job.processed,
                hashtags=job.hashtags_reprise,
                sources=job.sources_reprise_hashtags,
                positions=job.positions_reprise_research,
                reexploration=job.reprise_sans_curseur,
                journal_mode=json.loads(
                    (job.directory / "journal.json").read_text(
                        encoding="utf-8")).get("reprise_sans_curseur"),
                evenements_mode=[
                    e.get("rapport", {}).get("reprise_sans_curseur")
                    for e in job.journal if isinstance(e, dict)
                ],
            )
            job.update(status="partial", busy=False)
            termine.set()

        with tempfile.TemporaryDirectory() as dossier:
            manager = web.Manager(data_dir=dossier, runner=sans_tiktok)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                appels = []
                def api(chemin, donnees):
                    appels.append(chemin)
                    reponse = client.post(
                        chemin, json=donnees, headers={"X-ScrapTikTok": "1"})
                    if reponse.status_code >= 400:
                        raise RuntimeError(reponse.json().get("detail", "Erreur"))
                    if chemin.endswith("/restaurer-bilans") or chemin.endswith("/ouvrir"):
                        chemin_journal = (
                            Path(dossier) / "historique_analyses" /
                            self.identifiant / "journal.json")
                        if chemin_journal.is_file():
                            document = json.loads(
                                chemin_journal.read_text(encoding="utf-8"))
                            resultat["etape_" + chemin.rsplit("/", 1)[-1]] = {
                                "mode": document.get("reprise_sans_curseur"),
                                "sources": [
                                    e.get("source") for e in
                                    document.get("evenements", [])
                                    if isinstance(e, dict)],
                            }
                    return reponse.json()

                with (
                    patch("stockage.postgres_consultation.adresse_configuree",
                          return_value=True),
                    patch("stockage.postgres_consultation.verifier_disponibilite"),
                    patch("stockage.postgres_consultation.lire_archive_reprise_hashtags",
                          return_value=sauvegarde),
                    patch("stockage.postgres_consultation.obtenir_nom_collecte",
                          return_value=self.nom),
                    patch("stockage.postgres_consultation.compter_publications_collecte",
                          return_value=521),
                    patch("ticket_gate.verifier_session_active", return_value=True),
                ):
                    reprise, selection = reprendre_depuis_bilans_csv(
                        api, bilans, cle="cle_reprise", secret="secret_reprise")
                self.assertTrue(termine.wait(5))
                self.assertEqual(selection, ["manifestation", "lyceen"])
                self.assertEqual(resultat["id"], self.identifiant)
                self.assertEqual(resultat["publications"], 521)
                self.assertEqual(resultat["traitees"], 521)
                self.assertEqual(resultat["positions"], {})
                self.assertTrue(resultat["reexploration"], str({
                    "journal_mode": resultat["journal_mode"],
                    "evenements_mode": resultat["evenements_mode"],
                    "apres_restaurer": resultat.get("etape_restaurer-bilans"),
                    "apres_ouvrir": resultat.get("etape_ouvrir")}))
                self.assertEqual(
                    resultat["sources"], ["manifestation", "lyceen"])
                self.assertTrue(
                    any(chemin.endswith("/restaurer-bilans")
                        for chemin in appels))
                self.assertTrue(
                    all(chemin != "/api/jobs" for chemin in appels))
                self.assertEqual(reprise["id"], self.identifiant)
                self.assertTrue(reprise["reprise_sans_curseur"])

    def test_csv_bloque_si_postgres_vides_malgre_521_liens(self):
        """Ne pas annoncer une reprise si aucune publication n'est sauvée."""
        from stockage.recuperation_hashtags import restaurer_depuis_bilans_csv
        bilan = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "manifestation",
             "etat": "partielle", "liens": 521, "motif": "HTTP 401"},
            {"collecte_id": self.identifiant, "hashtag": "lyceen",
             "etat": "non_commencee", "liens": 0, "motif": ""},
        ])
        parametres = web.StartRequest(
            nom_sauvegarde=self.nom, source_collecte="hashtags",
            hashtag_moteur="research",
            hashtags_saisis=["manifestation", "lyceen"],
            date_debut="2026-10-01", date_fin="2026-10-31",
            research_client_key="cle_simulee",
            research_client_secret="secret_simule",
        ).model_dump(mode="json")
        sauvegarde = {
            "nom": self.nom, "traitees": 0,
            "parametres": parametres, "journal": [],
            "cree_le": datetime(2026, 10, 25, tzinfo=timezone.utc),
            "publications": [], "commentaires": [],
            "republications": [],
        }
        with tempfile.TemporaryDirectory() as dossier:
            with patch(
                    "stockage.postgres_consultation.lire_archive_reprise_hashtags",
                    return_value=sauvegarde):
                with self.assertRaisesRegex(ValueError, "aucune publication"):
                    restaurer_depuis_bilans_csv(
                        dossier, self.identifiant, self.cookie, [bilan])
            self.assertIsNone(retrouver(dossier, self.identifiant, self.cookie))

    def test_zip_incomplet_ou_corpus_different_refuse(self):
        """Ne jamais reconstruire la pagination avec un simple bilan CSV."""
        with tempfile.TemporaryDirectory() as dossier:
            with patch(
                "stockage.recuperation_hashtags.verifier_propriete_postgres",
                return_value=(self.nom, 521)):
                tampon = BytesIO()
                with ZipFile(tampon, "w") as archive:
                    archive.writestr("bilan_hashtags.csv", "fichier seul")
                with self.assertRaisesRegex(ValueError, "obligatoires"):
                    restaurer_depuis_zip(
                        dossier, self.identifiant, self.cookie,
                        base64.b64encode(tampon.getvalue()).decode("ascii"))
            with patch(
                "stockage.recuperation_hashtags.verifier_propriete_postgres",
                return_value=(self.nom, 522)):
                with self.assertRaisesRegex(ValueError, "PostgreSQL"):
                    restaurer_depuis_zip(
                        dossier, self.identifiant, self.cookie,
                        base64.b64encode(self.zip).decode("ascii"))
            with patch(
                "stockage.recuperation_hashtags.verifier_propriete_postgres",
                side_effect=ValueError("Cookie privé non autorisé")):
                with self.assertRaisesRegex(ValueError, "Cookie privé"):
                    restaurer_depuis_zip(
                        dossier, self.identifiant, self.cookie,
                        base64.b64encode(self.zip).decode("ascii"))
            self.assertIsNone(retrouver(dossier, self.identifiant, self.cookie))

    def test_api_reprise_depuis_zip_garde_le_curseur_et_l_identifiant(self):
        """Parcours HTTP ZIP → historique → reprise, avec 521 publications."""
        termine = threading.Event()
        resultats = {}

        def executer_sans_tiktok(job):
            resultats["id"] = job.id
            resultats["publications"] = len(job.publications)
            resultats["cursor"] = job.positions_reprise_research[
                "#17octobre"]["cursor"]
            job.update(status="partial", busy=False)
            termine.set()

        with tempfile.TemporaryDirectory() as dossier:
            manager = web.Manager(data_dir=dossier, runner=executer_sans_tiktok)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                cookie = client.cookies[web.HISTORIQUE_COOKIE]
                self.assertIsNone(retrouver(dossier, self.identifiant, cookie))
                with (
                    patch(
                        "stockage.recuperation_hashtags.verifier_propriete_postgres",
                        return_value=(self.nom, 521)),
                    patch(
                        "stockage.postgres_consultation.adresse_configuree",
                        return_value=True),
                    patch(
                        "stockage.postgres_consultation.verifier_disponibilite"),
                    patch(
                        "stockage.postgres_consultation.obtenir_nom_collecte",
                        return_value=self.nom),
                    patch(
                        "stockage.postgres_consultation.compter_publications_collecte",
                        return_value=521),
                    patch("ticket_gate.verifier_session_active",
                          return_value=True),
                ):
                    charge = client.post(
                        f"/api/historique/{self.identifiant}/restaurer-zip",
                        json={"archive_base64": base64.b64encode(
                            self.zip).decode("ascii")},
                        headers={"X-ScrapTikTok": "1"})
                    self.assertEqual(charge.status_code, 200, charge.text)
                    ouvert = client.post(
                        f"/api/historique/{self.identifiant}/ouvrir",
                        json={}, headers={"X-ScrapTikTok": "1"})
                    self.assertEqual(ouvert.status_code, 200, ouvert.text)
                    self.assertEqual(ouvert.json()["id"], self.identifiant)
                    reprise = client.post(
                        f"/api/historique/{self.identifiant}/reprendre-hashtags",
                        json={
                            "hashtags": ["17octobre", "24octobre"],
                            "research_client_key": "cle_reprise",
                            "research_client_secret": "secret_reprise",
                        }, headers={"X-ScrapTikTok": "1"})
                self.assertEqual(reprise.status_code, 202, reprise.text)
                self.assertTrue(termine.wait(5))
                self.assertEqual(resultats, {
                    "id": self.identifiant,
                    "publications": 521,
                    "cursor": 600,
                })


if __name__ == "__main__":
    unittest.main()
