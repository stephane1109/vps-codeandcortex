"""Contrôler l'absence de doublons dans les CSV sans altérer les données brutes."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, compte_reposteur_pour_csv,
    ligne_publication_csv,
)
from corpus.construction import COLONNES_ENGAGEMENT, lignes_engagement
from corpus.export_csv import serialiser_csv
from analyse_desordre.corpus_fusion import construire_tableau_complet


class TestsColonnesCsvSimplifiees(unittest.TestCase):
    def publication(self, **options):
        """Construire une vidéo avec deux comptes reposteurs et un résumé IA absent."""
        p = {
            "id": "7012345678901234567",
            "author": "lemondefr",
            "url": "https://www.tiktok.com/@lemondefr/video/7012345678901234567",
            "description": "Manifestation",
            "created_at": "2026-10-25T12:00:00+00:00",
            "engagement": {"vues": {"valeur": 20, "brut": "20"}},
            "statut_resume_ia": "non_trouve",
            "contenu_genere_ia": True,
            "comptes_reposteurs": ["blast_officiel", "basta_media"],
            "groupe_visuel": "visuel_01",
            "reemploi_visuel": "oui",
        }
        p.update(options)
        return p

    def test_colonnes_presse_et_engagement(self):
        """Exporter le statut du résumé IA et un seul champ de reposteurs."""
        p = self.publication()
        original = json.dumps(p, sort_keys=True)
        for colonnes, ligne in (
            (COLONNES_PUBLICATIONS_CSV, ligne_publication_csv(p)),
            (COLONNES_ENGAGEMENT, lignes_engagement([p])[0]),
        ):
            with self.subTest(fichier=colonnes[:2]):
                self.assertEqual(ligne["compte_reposteur"],
                                 "basta_media, blast_officiel")
                self.assertEqual(ligne["statut_resume_ia"], "non_trouve")
                self.assertEqual(ligne["groupe_visuel"], "visuel_01")
                self.assertEqual(ligne["reemploi_visuel"], "oui")
                for champ in ("comptes_reposteurs", "contenu_genere_ia"):
                    self.assertNotIn(champ, colonnes)
                    self.assertNotIn(champ, ligne)
                contenu = serialiser_csv([ligne], colonnes)
                ligne_csv = next(csv.DictReader(
                    io.StringIO(contenu.lstrip("\ufeff")), delimiter=";"))
                self.assertEqual(ligne_csv["compte_reposteur"],
                                 "basta_media, blast_officiel")
                self.assertEqual(ligne_csv["statut_resume_ia"], "non_trouve")
        # Le JSON/les archives ne perdent aucune donnée d'analyse.
        self.assertEqual(json.dumps(p, sort_keys=True), original)
        self.assertTrue(p["contenu_genere_ia"])
        self.assertEqual(len(p["comptes_reposteurs"]), 2)

    def test_compatibilite_donnees_anciennes_et_une_seule_republication(self):
        """Conserver le compte unique ou décoder les anciens formats en liste."""
        for valeur, attendu in (
            (["basta_media", "blast_officiel"], "basta_media, blast_officiel"),
            ('["blast_officiel", "basta_media"]', "basta_media, blast_officiel"),
            ("blast_officiel, basta_media", "basta_media, blast_officiel"),
            ([], ""),
        ):
            with self.subTest(valeur=valeur):
                p = self.publication(comptes_reposteurs=valeur,
                                     compte_reposteur=None)
                self.assertEqual(compte_reposteur_pour_csv(p), attendu)
        video_republiee = self.publication(
            compte_reposteur="blast_officiel", comptes_reposteurs=[])
        self.assertEqual(compte_reposteur_pour_csv(video_republiee),
                         "blast_officiel")

    def test_fusion_visuelle_donnees_anciennes(self):
        """Supprimer les anciennes colonnes du tableau d'analyse fusionné."""
        p = self.publication()
        with tempfile.TemporaryDirectory() as racine:
            session = Path(racine) / ("a" * 32)
            session.mkdir()
            dossier = session / "desordre_0123456789abcdef"
            dossier.mkdir()
            (dossier / "indicateurs_engagement.csv").write_text(
                "publication_id;url;comptes_reposteurs;contenu_genere_ia;"
                "groupe_visuel;reemploi_visuel\n"
                + p["id"] + ";" + p["url"]
                + ';["blast_officiel", "basta_media"];true;visuel_01;oui\n',
                encoding="utf-8")
            with patch("analyse_desordre.annotation.lire_annotations",
                       return_value={}), patch(
                       "analyse_desordre.codages_personnalises.lire",
                       return_value={"variables": [], "valeurs": {}}), patch(
                       "analyse_desordre.sources.lire_publications",
                       return_value=[p]):
                texte = construire_tableau_complet(session, dossier)
            lignes = list(csv.DictReader(
                io.StringIO(texte.lstrip("\ufeff")), delimiter=";"))
            self.assertEqual(len(lignes), 1)
            ligne = lignes[0]
            self.assertEqual(ligne["compte_reposteur"],
                             "basta_media, blast_officiel")
            self.assertEqual(ligne["statut_resume_ia"], "non_trouve")
            self.assertEqual(ligne["groupe_visuel"], "visuel_01")
            self.assertEqual(ligne["reemploi_visuel"], "oui")
            self.assertNotIn("comptes_reposteurs", ligne)
            self.assertNotIn("contenu_genere_ia", ligne)


if __name__ == "__main__":
    unittest.main()
