"""Tests des trois réseaux et des formats sociométriques, sans collecte réelle."""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient

from analyse_sociometrique.reseaux import (
    construire_reseau, exporter, construire_dot, apercu)

VIDEOS = [{"id": "100"}, {"id": "200"}, {"id": "300"}]
COMMENTAIRES = [
    {"id": "a", "publication_id": "100", "source": "page_visible",
     "auteur": "compte_a"},
    {"id": "b", "publication_id": "100", "source": "page_visible",
     "auteur": "compte_a"},
    {"id": "c", "publication_id": "200", "source": "page_visible",
     "auteur": "compte_a", "parent_id": "d"},
    {"id": "d", "publication_id": "200", "source": "research_api_officielle",
     "auteur": None},
    {"id": "e", "publication_id": "200", "source": "page_visible",
     "auteur": "compte_b"},
    {"id": "f", "publication_id": "100", "source": "page_visible",
     "auteur": "compte_b"},
    {"id": "g", "publication_id": "300", "source": "research_api_officielle",
     "auteur": "affichage", "parent_id": "inconnu"},
    {"id": "h", "publication_id": "100", "source": "research_api_officielle",
     "auteur": "affichage"},
]


class TestsSociometrie(unittest.TestCase):
    def test_reseau_auteurs_et_identites_non_deduites(self):
        reseau = construire_reseau(COMMENTAIRES, VIDEOS, "auteurs_videos", "lot")
        self.assertEqual(reseau["statistiques"]["auteurs_distincts"], 2)
        self.assertEqual(reseau["statistiques"]["commentaires_sans_auteur_fiable"], 3)
        self.assertEqual(len(reseau["liens"]), 4)
        self.assertEqual(sorted(l["poids"] for l in reseau["liens"]), [1, 1, 1, 2])
        self.assertNotIn("compte_a", str(reseau))
        self.assertNotIn("affichage", str(reseau))

    def test_projection_audiences_communes(self):
        reseau = construire_reseau(COMMENTAIRES, VIDEOS, "videos_communes", "lot")
        self.assertEqual(len(reseau["liens"]), 1)
        self.assertEqual(reseau["liens"][0]["poids"], 2)
        self.assertFalse(construire_reseau(
            COMMENTAIRES, VIDEOS, "videos_communes", "lot", seuil=3)["liens"])

    def test_reponses_sans_identification_research(self):
        reseau = construire_reseau(COMMENTAIRES, VIDEOS, "reponses", "lot")
        self.assertTrue(reseau["oriente"])
        self.assertEqual(len(reseau["liens"]), 2)
        self.assertTrue(any(n["type"] == "parent_non_collecte"
                            for n in reseau["noeuds"]))

    def test_exports_csv_graphml_gexf(self):
        reseau = construire_reseau(COMMENTAIRES, VIDEOS, "auteurs_videos", "lot")
        for nom in ("noeuds.csv", "liens.csv", "matrice.csv"):
            self.assertTrue(exporter(reseau, nom).startswith(b"\xef\xbb\xbf"))
        for nom in ("graphml", "gexf"):
            ET.fromstring(exporter(reseau, nom))
        self.assertIn("graph R", construire_dot(apercu(reseau)))
        with self.assertRaises(ValueError):
            exporter(reseau, "html")

    def test_api_privee_et_formats(self):
        from webapp import Manager, create_app
        with tempfile.TemporaryDirectory() as dossier:
            gestion = Manager(data_dir=dossier, runner=lambda travail: None)
            appli = create_app(gestion)
            with TestClient(appli) as client:
                client.get("/")
                demande = client.post(
                    "/api/jobs", headers={"X-ScrapTikTok": "1"},
                    json={"hashtag": "lyceens", "limit": 1})
                self.assertEqual(demande.status_code, 202)
                identifiant = demande.json()["id"]
                job = gestion.jobs[identifiant]
                with job.lock:
                    job.records = VIDEOS
                    job.commentaires = COMMENTAIRES
                base = f"/api/jobs/{identifiant}/sociometrie"
                self.assertEqual(client.get(base).json()["statistiques"]["liens"], 4)
                self.assertTrue(client.get(base + "/export/graphml").content.startswith(b"<?xml"))
                self.assertEqual(client.get(base + "?mode=inconnu").status_code, 422)
                with TestClient(appli) as etranger:
                    etranger.get("/")
                    self.assertEqual(etranger.get(base).status_code, 404)


if __name__ == "__main__":
    unittest.main()
