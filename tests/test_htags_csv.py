"""Vérifier le choix « Htag dans le csv » sans altérer le corpus TXT."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import webapp as application
from corpus.construction import COLONNES_ENGAGEMENT, lignes_engagement
from corpus.export_csv import serialiser_csv
from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, hashtags_pour_csv, ligne_publication_csv,
)


def exemple_publication(identifiant="7701005447410552077"):
    """Représenter un résultat TikTok comportant des hashtags hétérogènes."""
    return {
        "id": identifiant, "author": "lemondefr",
        "url": f"https://www.tiktok.com/@lemondefr/video/{identifiant}",
        "description": ("Des #lycéens participent à une #manifestation. "
                        "https://exemple.fr/#ignorertag"),
        "hashtags": ["#manifestation", " #Lycéens ", "#Blocage", "blocage"],
        "created_at": "2026-10-25T12:00:00+00:00",
        "engagement": {}, "status": "ok",
    }


class TestsHashtagsCSV(unittest.TestCase):
    def test_case_activee_sans_diese_avec_dedoublonnage_et_accents(self):
        publication = exemple_publication()
        publication["inclure_hashtags_csv"] = True
        attendu = "manifestation, Lycéens, Blocage"
        self.assertEqual(hashtags_pour_csv(publication), attendu)
        self.assertEqual(ligne_publication_csv(publication)["hashtags"], attendu)
        self.assertEqual(lignes_engagement([publication])[0]["hashtags"], attendu)
        for ligne, colonnes in (
            (ligne_publication_csv(publication), COLONNES_PUBLICATIONS_CSV),
            (lignes_engagement([publication])[0], COLONNES_ENGAGEMENT),
        ):
            contenu = serialiser_csv([ligne], colonnes)
            export = next(csv.DictReader(io.StringIO(contenu), delimiter=";"))
            self.assertEqual(export["hashtags"], attendu)
            self.assertNotIn("#", export["hashtags"])

    def test_case_desactivee_colonne_vide_donnees_brutes_preservees(self):
        publication = exemple_publication()
        brutes = list(publication["hashtags"])
        publication["inclure_hashtags_csv"] = False
        self.assertEqual(hashtags_pour_csv(publication), "")
        self.assertEqual(ligne_publication_csv(publication)["hashtags"], "")
        self.assertEqual(lignes_engagement([publication])[0]["hashtags"], "")
        self.assertEqual(publication["hashtags"], brutes)

    def test_repli_sur_la_legende_et_exclusion_des_urls(self):
        publication = exemple_publication()
        publication.update(
            hashtags=[], description="Aujourd'hui #manifestation #lycéens "
                                     "https://exemple.fr/#ne_pas_inclure")
        publication["inclure_hashtags_csv"] = True
        self.assertEqual(hashtags_pour_csv(publication), "manifestation, lycéens")
        publication["description"] = "Publication sans hashtag"
        self.assertEqual(hashtags_pour_csv(publication), "")

    def test_anciens_exports_et_txt_ne_sont_pas_alteres(self):
        publication = exemple_publication()
        self.assertEqual(hashtags_pour_csv(publication), publication["hashtags"])
        texte = application.text_export(
            [publication], True, variables_txt=["profil", "id"])
        self.assertIn(publication["description"], texte)
        texte_ancien = application.text_export(
            [publication], True, variables_txt=["profil", "hashtags"])
        self.assertIn("#manifestation", texte_ancien)
        self.assertIn("#lycéens", texte_ancien)
        self.assertNotEqual(texte, texte_ancien)

    def test_collecte_transmet_le_choix_jusqu_aux_csv(self):
        """Tester le chemin de collecte et les deux états de la nouvelle case."""
        for cocher in (False, True):
            with self.subTest(cocher=cocher), tempfile.TemporaryDirectory() as dossier:
                publication = exemple_publication()
                parametres = application.StartRequest(
                    source_collecte="presse", medias=["lemonde"],
                    presse_moteur="api", limit=10, french_only=False,
                    enrichir=True, variables_txt=["profil"],
                    inclure_hashtags_csv=cocher)
                travail = application.Job("test-htag-csv", parametres, Path(dossier))
                travail.base = None

                def decouvrir(source, rapport, **options):
                    return [publication["url"]]

                with patch("connect_presse.ConnexionPresse.decouvrir",
                           side_effect=decouvrir), patch.object(
                           application.scraper, "read_post",
                           return_value=dict(publication)), patch.object(travail, "pause"):
                    application.execute_job(
                        travail, driver_factory=lambda arguments: Mock())
                self.assertEqual(len(travail.publications), 1, travail.message)
                fiche = travail.publications[0]
                self.assertEqual(fiche["inclure_hashtags_csv"], cocher)
                attendu = "manifestation, Lycéens, Blocage" if cocher else ""
                self.assertEqual(ligne_publication_csv(fiche)["hashtags"], attendu)
                self.assertEqual(lignes_engagement([fiche])[0]["hashtags"], attendu)
                self.assertIn(publication["description"], travail.texte_a_exporter())
                self.assertEqual(travail.snapshot()["inclure_hashtags_csv"], cocher)

    def test_libelle_et_transmission_streamlit(self):
        """La nouvelle case n'agit plus sur les variables du texte IRaMuTeQ."""
        source = (Path(__file__).resolve().parents[1] /
                  "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('"hashtags": "Htag dans le csv"', source)
        self.assertIn('key="csv_hashtags"', source)
        self.assertIn('valeurs["inclure_hashtags_csv"]', source)
        self.assertIn('if v != "hashtags" and st.session_state["txt_" + v]', source)
        self.assertNotIn('"Hashtags sous le texte"', source)


if __name__ == "__main__":
    unittest.main()
