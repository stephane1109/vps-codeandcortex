"""Tests des colonnes complètes dans les fichiers publications.csv."""
import csv
import io
import json
import unittest
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, cellule_csv, ligne_publication_csv,
)
from stockage.collectes_research import (
    creer_plan, enregistrer_partiel, exporter, texte_csv,
)
from stockage.postgres_consultation import CHAMPS_PUBLICATIONS, valeur_colonne


PUBLICATION = {
    "id": "7702544004629531937",
    "url": "https://www.tiktok.com/@compte/video/7702544004629531937",
    "author": "compte", "created_at": "2026-10-30T19:24:42+00:00",
    "collected_at": "2026-11-01T15:23:36+00:00",
    "description": "Manifestation lycéenne #blocus",
    "hashtags": ["blocus", "manifestation"],
    "region_code": "FR", "is_verified": False,
    "is_verified_statut": "ok",
    "follower_count": 12000, "follower_count_statut": "ok",
    "classe_abonnes": "abonnes_10k_100k",
    "video_duration": 28, "duree_classe": "duree_classe_15_59s",
    "engagement": {
        "vues": {"brut": "219", "valeur": 219},
        "likes": {"brut": "5", "valeur": 5},
        "commentaires": {"brut": "1", "valeur": 1},
        "partages": {"brut": "2", "valeur": 2},
        "favoris": {"brut": "2", "valeur": 2},
    },
    "taux_engagement": 4.566210045662101,
    "classe_taux_engagement": "engagement_3_5pct",
    "vues_classe": "vues_classe_moins_1k",
    "likes_classe": "likes_classe_1_9",
    "commentaires_classe": "commentaires_classe_1_9",
    "partages_classe": "partages_classe_1_9",
    "favoris_classe": "favoris_classe_1_9",
    "retenue": True, "contenu_genere_ia": False,
    "statut_resume_ia": "non_trouve", "resume_ia_tiktok": "",
    "collecte_commentaires": {
        "statut": "ok", "recuperes": 1, "annonces": 1, "exhaustif": True
    },
}


class TestsPublicationsCsv(unittest.TestCase):
    def test_colonnes_des_variables_et_recodages_de_l_interface(self):
        """Chaque valeur ou classe cochable a une colonne distincte."""
        attendues = (
            "id", "publication_id", "url", "author", "profil",
            "created_at", "date_publication", "region_code", "is_verified",
            "is_verified_statut", "follower_count", "follower_count_statut",
            "classe_abonnes", "vues", "likes", "commentaires", "partages",
            "favoris", "video_duration", "vues_classe", "likes_classe",
            "commentaires_classe", "partages_classe", "favoris_classe",
            "duree_classe", "taux_engagement", "classe_taux_engagement",
            "hashtags", "description", "resume_ia_tiktok",
            "statut_resume_ia",
            "commentaires_collecte_recuperes",
        )
        self.assertTrue(set(attendues).issubset(COLONNES_PUBLICATIONS_CSV))
        for supprimee in ("comptes_reposteurs", "contenu_genere_ia"):
            self.assertNotIn(supprimee, COLONNES_PUBLICATIONS_CSV)
        self.assertEqual(len(COLONNES_PUBLICATIONS_CSV),
                         len(set(COLONNES_PUBLICATIONS_CSV)))
        self.assertEqual(CHAMPS_PUBLICATIONS, COLONNES_PUBLICATIONS_CSV)

    def test_valeurs_numeriques_classes_et_nulles(self):
        """La classe et la valeur exacte apparaissent simultanément."""
        ligne = ligne_publication_csv(PUBLICATION)
        self.assertEqual(ligne["create_time"], PUBLICATION["created_at"])
        self.assertEqual(ligne["date_publication"], PUBLICATION["created_at"])
        self.assertEqual(ligne["vues"], 219)
        self.assertEqual(ligne["vues_brut"], "219")
        self.assertEqual(ligne["follower_count"], 12000)
        self.assertEqual(ligne["classe_abonnes"], "abonnes_10k_100k")
        self.assertEqual(ligne["taux_engagement"], PUBLICATION["taux_engagement"])
        self.assertEqual(ligne["classe_taux_engagement"], "engagement_3_5pct")
        self.assertEqual(ligne["is_verified"], False)
        self.assertEqual(ligne["commentaires_collecte_recuperes"], 1)
        self.assertEqual(ligne["hashtags"], ["blocus", "manifestation"])
        inconnue = dict(PUBLICATION, follower_count=None, engagement={
            **PUBLICATION["engagement"], "vues": {"valeur": 0, "brut": "0"},
            "likes": {"valeur": None, "brut": None},
        })
        resultat = ligne_publication_csv(inconnue)
        self.assertEqual(resultat["vues"], 0)
        self.assertIsNone(resultat["likes"])
        self.assertIsNone(resultat["follower_count"])
        self.assertEqual(valeur_colonne(resultat, "vues"), "0")
        self.assertEqual(valeur_colonne(resultat, "likes"), "")

    def test_research_csv_conserve_toutes_les_variables(self):
        """L'export CSV et celui du ZIP sont identiques."""
        with TemporaryDirectory() as dossier:
            parametres = {
                "source_collecte": "presse", "medias": ["lemonde"],
                "date_debut": "2026-10-01", "date_fin": "2026-10-31",
                "nom_sauvegarde": "Recherche complète",
                "variables_txt": [
                    "date", "profil", "id", "vues", "likes", "commentaires",
                    "partages", "favoris", "duree", "region_code",
                    "is_verified", "hashtags",
                ],
                "variables_classes_txt": [
                    "vues", "likes", "commentaires", "partages",
                    "favoris", "duree",
                ],
                "collecter_follower_count": True,
                "abonnes_classe_illustratif": True,
                "follower_count_illustratif": True,
                "taux_engagement_txt": "brut_et_classes",
                "collecter_commentaires": True,
            }
            identifiant = creer_plan(
                dossier, "proprietaire", parametres,
                "2026-11-01", "2026-11-10",
            )
            enregistrer_partiel(dossier, identifiant, PUBLICATION, [])
            donnees_csv = exporter(
                dossier, identifiant, "proprietaire", "csv")
            with io.StringIO(donnees_csv.decode("utf-8-sig")) as flux:
                lignes = list(csv.DictReader(flux))
            self.assertEqual(len(lignes), 1)
            ligne = lignes[0]
            self.assertEqual(ligne["follower_count"], "12000")
            self.assertEqual(ligne["video_duration"], "28")
            self.assertEqual(ligne["vues_classe"], "vues_classe_moins_1k")
            self.assertEqual(ligne["classe_taux_engagement"],
                             "engagement_3_5pct")
            self.assertEqual(ligne["hashtags"],
                             json.dumps(PUBLICATION["hashtags"], ensure_ascii=False))
            self.assertEqual(ligne["is_verified"], "False")
            with ZipFile(io.BytesIO(exporter(
                    dossier, identifiant, "proprietaire", "zip"))) as archive:
                self.assertEqual(archive.read("publications.csv"), donnees_csv)

    def test_non_retenu_et_cellules_protegees(self):
        """Ne pas introduire d'injection de formule dans un tableur."""
        self.assertEqual(cellule_csv("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(cellule_csv(0), "0")
        self.assertEqual(cellule_csv(None), "")
        self.assertEqual(cellule_csv(["blocus"]), '["blocus"]')
        texte = texte_csv(
            [dict(PUBLICATION, description="=danger")], [], "publications")
        ligne = list(csv.DictReader(io.StringIO(texte)))[0]
        self.assertEqual(ligne["description"], "'=danger")


if __name__ == "__main__":
    unittest.main()
