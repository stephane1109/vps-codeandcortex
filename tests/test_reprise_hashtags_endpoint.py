"""Vérifier le déclenchement HTTP de la reprise et la restauration des 521 vidéos."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import webapp as web
from stockage.historique_analyses import enregistrer


class TestsRepriseHashtagsEndpoint(unittest.TestCase):
    def test_bouton_reprise_reutilise_les_521_publications_et_le_curseur(self):
        """La requête de reprise retourne 202 et conserve le corpus déjà archivé."""
        relancee = threading.Event()
        resultats = {}

        def executer_sans_tiktok(job):
            resultats["id"] = job.id
            resultats["nombre"] = len(job.publications)
            resultats["hashtags"] = job.hashtags_reprise
            resultats["sources"] = job.sources_reprise_hashtags
            resultats["positions"] = job.positions_reprise_research
            job.update(busy=False, status="partial")
            relancee.set()

        with tempfile.TemporaryDirectory() as temporaire:
            manager = web.Manager(data_dir=temporaire, runner=executer_sans_tiktok)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                proprietaire = client.cookies[web.COOKIE]
                cookie_historique = client.cookies[web.HISTORIQUE_COOKIE]
                options = web.StartRequest(
                    nom_sauvegarde="Deux hashtags",
                    source_collecte="hashtags",
                    hashtag_moteur="research",
                    hashtags_saisis=["17octobre", "24octobre"],
                    date_debut="2026-10-01",
                    date_fin="2026-10-31",
                    research_client_key="cle_initiale",
                    research_client_secret="secret_initial",
                )
                ancien = web.Job(
                    proprietaire, options, Path(temporaire),
                    owner_historique=cookie_historique)
                publications = [
                    {
                        "id": str(7000000000000000000 + indice),
                        "url": "https://www.tiktok.com/@exemple/video/"
                               + str(7000000000000000000 + indice),
                        "author": "exemple", "description": "#17octobre",
                        "retenue": True, "engagement": {},
                    }
                    for indice in range(521)
                ]
                ancien.publications = publications
                ancien.records = list(publications)
                ancien.processed = 521
                ancien.busy = False
                ancien.status = "partial"
                ancien.archive_prete = True
                ancien.source_en_cours_id = "#17octobre"
                ancien.journal = [{
                    "source": "#17octobre",
                    "statut_source": "partielle",
                    "rapport": {
                        "collecte_partielle": True,
                        "reprise_pagination_research": {
                            "indice_periode": 0,
                            "debut_periode": "20261001",
                            "fin_periode": "20261031",
                            "cursor": 600,
                            "search_id": "recherche_persistante",
                        },
                    },
                }]
                (ancien.directory / "publications.json").write_text(
                    json.dumps(publications), encoding="utf-8")
                (ancien.directory / "journal.json").write_text(
                    json.dumps({"evenements": ancien.journal}), encoding="utf-8")
                (ancien.directory / "commentaires.json").write_text(
                    "[]", encoding="utf-8")
                enregistrer(ancien, cookie_historique)
                manager.jobs[ancien.id] = ancien
                with (
                    patch(
                        "stockage.postgres_consultation.adresse_configuree",
                        return_value=True),
                    patch(
                        "stockage.postgres_consultation.verifier_disponibilite"),
                    patch(
                        "stockage.postgres_consultation.obtenir_nom_collecte",
                        return_value="Deux hashtags"),
                    patch(
                        "stockage.postgres_consultation.compter_publications_collecte",
                        return_value=521),
                    patch("ticket_gate.verifier_session_active",
                          return_value=True),
                ):
                    reponse = client.post(
                        f"/api/historique/{ancien.id}/reprendre-hashtags",
                        json={
                            "hashtags": ["17octobre", "24octobre"],
                            "research_client_key": "cle_reprise",
                            "research_client_secret": "secret_reprise",
                        },
                        headers={"X-ScrapTikTok": "1"},
                    )
                self.assertEqual(reponse.status_code, 202, reponse.text)
                self.assertTrue(relancee.wait(5))
                self.assertEqual(resultats["id"], ancien.id)
                self.assertEqual(resultats["nombre"], 521)
                self.assertEqual(
                    resultats["hashtags"], ["17octobre", "24octobre"])
                self.assertEqual(
                    resultats["sources"], ["17octobre", "24octobre"])
                self.assertEqual(
                    resultats["positions"]["#17octobre"]["cursor"], 600)
                self.assertEqual(
                    resultats["positions"]["#17octobre"]["search_id"],
                    "recherche_persistante")


if __name__ == "__main__":
    unittest.main()
