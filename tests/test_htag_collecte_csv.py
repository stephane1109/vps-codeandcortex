"""Vérifier l'intitulé htag_collecte et le contenu réel des exports CSV."""
import csv
import io
import json
import unittest

from corpus.construction import COLONNES_ENGAGEMENT, lignes_engagement
from corpus.export_csv import serialiser_csv
from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, ligne_publication_csv,
    hashtags_collecte_pour_csv,
)


def publication(**ajouts):
    """Construire un enregistrement de test indépendant des API TikTok."""
    valeurs = {
        "id": "7012345678901234567",
        "author": "lemondefr",
        "description": "Manifestation #lyceens",
        "hashtags": ["lyceens"],
        "engagement": {},
    }
    valeurs.update(ajouts)
    return valeurs


class TestsHashtagCollecteCSV(unittest.TestCase):
    def test_distinction_hashtag_present_et_critere_de_collecte(self):
        """Le hashtag d'une légende n'est pas nécessairement recherché."""
        medias_sans_croisement = publication(hashtags_recherches=[])
        self.assertEqual(hashtags_collecte_pour_csv(medias_sans_croisement), "")
        self.assertEqual(
            ligne_publication_csv(medias_sans_croisement)["htag_collecte"], "")
        self.assertEqual(
            lignes_engagement([medias_sans_croisement])[0]["htag_collecte"], "")
        self.assertNotIn(
            "hashtags_recherches", COLONNES_PUBLICATIONS_CSV)
        self.assertNotIn(
            "hashtags_recherches", COLONNES_ENGAGEMENT)

    def test_liste_et_chaine_ancienne_forme(self):
        """Les anciennes collectes restent lisibles sans exporter [] ni #."""
        cas = [
            ([], ""),
            ("[]", ""),
            (None, ""),
            (["#manifestation", "#blocage", "manifestation"],
             "manifestation, blocage"),
            ('["manifestation", "blocage"]', "manifestation, blocage"),
            ("manifestation, blocage", "manifestation, blocage"),
        ]
        for ancienne, attendu in cas:
            with self.subTest(valeur=ancienne):
                fiche = publication(hashtags_recherches=ancienne)
                self.assertEqual(hashtags_collecte_pour_csv(fiche), attendu)
                self.assertEqual(
                    ligne_publication_csv(fiche)["htag_collecte"], attendu)
                self.assertEqual(
                    lignes_engagement([fiche])[0]["htag_collecte"], attendu)
        fiche = publication(hashtags_recherches=["ancien"],
                            htag_collecte=["nouveau"])
        self.assertEqual(hashtags_collecte_pour_csv(fiche), "nouveau")

    def test_csv_harmonises_et_colonne_sans_diese(self):
        """Tous les fichiers CSV exposent la même colonne renseignée."""
        fiche = publication(hashtags_recherches=["#manifestation", "#blocage"])
        for ligne, colonnes in (
            (ligne_publication_csv(fiche), COLONNES_PUBLICATIONS_CSV),
            (lignes_engagement([fiche])[0], COLONNES_ENGAGEMENT),
        ):
            with self.subTest(colonnes=colonnes[:3]):
                texte = serialiser_csv([ligne], colonnes)
                source = next(csv.DictReader(
                    io.StringIO(texte.lstrip("\ufeff")), delimiter=";"))
                self.assertEqual(source["htag_collecte"], "manifestation, blocage")
                self.assertNotIn("hashtags_recherches", source)

    def test_hashtags_et_profils_stockent_les_criteres(self):
        """Les filtres saisis sont conservés en mode hashtag et en mode profils."""
        from pathlib import Path
        from unittest.mock import Mock, patch
        from tempfile import TemporaryDirectory
        import webapp as web

        id_video = "7012345678901234567"
        url = f"https://www.tiktok.com/@lemondefr/video/{id_video}"
        fiche = publication(id=id_video, url=url,
                            created_at="2026-10-25T12:00:00+00:00")
        params = web.StartRequest(
            source_collecte="hashtags", hashtag="manifestation",
            hashtags_saisis=["#manifestation", "#blocage"],
            hashtag_moteur="navigateur", limit=5,
            enrichir=True, french_only=False)
        with TemporaryDirectory() as racine:
            job = web.Job("test-htag-collecte", params, Path(racine))
            job.base = None
            with patch.object(web.scraper, "collect_links", return_value=[url]), \
                    patch.object(web.scraper, "read_post", return_value=dict(fiche)), \
                    patch.object(job, "pause"):
                web.execute_job(job, driver_factory=lambda args: Mock())
            self.assertTrue(job.publications, job.message)
            self.assertEqual(job.publications[0]["hashtags_recherches"],
                             ["manifestation", "blocage"])
            self.assertEqual(
                ligne_publication_csv(job.publications[0])["htag_collecte"],
                "manifestation, blocage")


if __name__ == "__main__":
    unittest.main()
