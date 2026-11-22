"""Tester les destinations indépendantes TXT et CSV de ScrapTikTok."""

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from collecte.selection_variables_csv import (
    VARIABLES_CSV, colonnes_csv_selectionnees,
)
from corpus.publications_csv import COLONNES_PUBLICATIONS_CSV
from corpus.construction import COLONNES_ENGAGEMENT
from webapp import StartRequest, entete_publication


RACINE = Path(__file__).resolve().parents[1]


def demander_parametres(source="comptes", **options):
    """Instancier une requête sans accès TikTok ni base PostgreSQL."""
    donnees = {
        "source_collecte": source,
        "hashtags_saisis": ["manifestation"],
        "profil_moteur": "navigateur",
        "hashtag_moteur": "navigateur",
        "comptes": ["microbalade"] if source == "comptes" else [],
        **options,
    }
    return StartRequest.model_validate(donnees)


class TestDestinationsTxtCsv(unittest.TestCase):
    def test_ancien_schema_csv_reste_entier(self):
        """Les anciens paramètres None conservent les colonnes historiques."""
        self.assertEqual(
            colonnes_csv_selectionnees(COLONNES_PUBLICATIONS_CSV, None),
            list(COLONNES_PUBLICATIONS_CSV))
        self.assertIsNone(demander_parametres().variables_csv)

    def test_csv_brut_et_classe_independants(self):
        """Une case CSV de classe ne force pas la colonne numérique."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["vues_classe", "ville_etude"])
        self.assertIn("publication_id", colonnes)
        self.assertIn("vues_classe", colonnes)
        self.assertIn("ville_etude", colonnes)
        self.assertNotIn("vues", colonnes)
        self.assertNotIn("vues_brut", colonnes)
        self.assertNotIn("classe_abonnes", colonnes)
        self.assertNotIn("region_code", colonnes)
        self.assertNotIn("id", colonnes)

    def test_csv_brut_sans_classe(self):
        """La sélection brute n'inclut pas la classe."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_ENGAGEMENT, ["likes", "profil"])
        self.assertIn("likes", colonnes)
        self.assertIn("likes_brut", colonnes)
        self.assertIn("auteur", colonnes)
        self.assertNotIn("likes_classe", colonnes)
        self.assertNotIn("partages", colonnes)

    def test_csv_sans_option_conserve_la_jointure_technique(self):
        """Même une sélection vide préserve publication_id, pas id visible."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, [])
        self.assertIn("publication_id", colonnes)
        self.assertNotIn("id", colonnes)
        self.assertNotIn("author", colonnes)
        self.assertNotIn("create_time", colonnes)
        self.assertNotIn("presse_nationale", colonnes)
        self.assertNotIn("ville_etude", colonnes)

    def test_options_csv_sont_validees(self):
        """Refuser les noms arbitraires et les doublons."""
        self.assertIn("categorie_compte", VARIABLES_CSV)
        self.assertIn("ville_etude", VARIABLES_CSV)
        valide = demander_parametres(variables_csv=["date", "vues_classe"])
        self.assertEqual(valide.variables_csv, ["date", "vues_classe"])
        with self.assertRaises(ValueError):
            demander_parametres(variables_csv=["option_inconnue"])
        with self.assertRaises(ValueError):
            demander_parametres(variables_csv=["date", "date"])

    def test_ville_txt_et_csv_independants(self):
        """La ville peut figurer dans le CSV sans figurer dans le TXT."""
        requete = demander_parametres(
            ville_etude="Toulouse", ville_etude_txt=False,
            variables_txt=["id"], variables_csv=["ville_etude"])
        self.assertEqual(requete.ville_etude, "toulouse")
        self.assertFalse(requete.ville_etude_txt)
        self.assertEqual(requete.variables_csv, ["ville_etude"])
        video = {
            "id": "12345", "author": "microbalade", "engagement": {},
            "ville_etude": requete.ville_etude,
            "inclure_ville_etude_txt": requete.ville_etude_txt,
        }
        self.assertNotIn("*ville_", entete_publication(video, ["id"]))
        video["inclure_ville_etude_txt"] = True
        self.assertIn("*ville_toulouse", entete_publication(video, ["id"]))

    def test_presse_txt_independante_de_la_presence_en_csv(self):
        """La catégorie presse ne dépend pas de la variable profil."""
        video = {
            "id": "12345", "author": "mediatest", "engagement": {},
            "inclure_categorie_compte_txt": False,
        }
        with patch("collecte.presse.code_presse_publication",
                   return_value="presse_nationale"):
            self.assertNotIn(
                "*presse_nationale", entete_publication(video, []))
            video["inclure_categorie_compte_txt"] = True
            self.assertIn(
                "*presse_nationale", entete_publication(video, []))
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["categorie_compte"])
        self.assertIn("presse_nationale", colonnes)
        self.assertIn("presse_regio_dpt", colonnes)

    def test_interface_trois_modes_et_deux_cases_par_ligne(self):
        """Chaque variable dispose d'un choix TXT/CSV, même en mode presse."""
        interface = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(interface)
        self.assertIn('def ligne_variable(libelle, cle_txt, cle_csv', interface)
        self.assertIn('"TXT", key=cle_txt', interface)
        self.assertIn('"CSV", key=cle_csv', interface)
        for cle in (
            "txt_date", "csv_date", "txt_profil", "csv_profil",
            "txt_collecter_follower_count", "csv_recuperer_abonnes",
            "follower_count_illustratif", "csv_follower_count",
            "abonnes_classe_illustratif", "csv_abonnes_classe",
            "txt_id", "csv_id", "txt_region_code", "csv_region_code",
            "txt_is_verified", "csv_is_verified",
            "txt_categorie_compte", "csv_categorie_compte",
            "txt_ville_etude", "csv_ville_etude",
            "txt_taux_engagement_brut", "csv_taux_engagement",
            "txt_taux_engagement_classe", "csv_classe_taux_engagement",
        ):
            self.assertIn('"' + cle + '"', interface)
        self.assertIn('valeurs["variables_csv"] = [', interface)
        self.assertIn('valeurs["ville_etude"] = (', interface)

    def test_research_programmee_respecte_les_destinations_csv(self):
        """Le second export des programmes doit utiliser le même filtre."""
        import csv
        import io
        from stockage.collectes_research import texte_csv

        publications = [
            {"id": "12345", "author": "microbalade",
             "ville_etude": "toulouse", "description": "Manifestation",
             "engagement": {"vues": {"valeur": 2500, "brut": "2500"}},
             "retenue": True}
        ]
        lignes = texte_csv(
            publications, [], "publications",
            variables_csv=["ville_etude", "vues_classe"])
        tableau = csv.DictReader(io.StringIO(lignes))
        self.assertIn("publication_id", tableau.fieldnames)
        self.assertIn("ville_etude", tableau.fieldnames)
        self.assertIn("vues_classe", tableau.fieldnames)
        self.assertNotIn("vues", tableau.fieldnames)
        self.assertNotIn("author", tableau.fieldnames)
        premiere = next(tableau)
        self.assertEqual(premiere["ville_etude"], "toulouse")

    def test_commentaires_programmes_conservent_la_ville_du_corpus(self):
        """Les commentaires gardent leur lien vidéo sans inventer une ville."""
        import csv
        import io
        from stockage.collectes_research import texte_csv

        videos = [{"id": "12345", "ville_etude": "toulouse"}]
        commentaires = [{
            "id": "999", "publication_id": "12345",
            "texte": "Solidarité", "parent_id": "",
            "est_reponse": False, "auteur": "",
        }]
        resultat = texte_csv(
            videos, commentaires, "commentaires",
            variables_csv=["ville_etude"])
        lignes = list(csv.DictReader(io.StringIO(resultat)))
        self.assertEqual(lignes[0]["ville_etude"], "toulouse")
        self.assertEqual(lignes[0]["publication_id"], "12345")
        ancien = texte_csv(videos, commentaires, "commentaires")
        self.assertNotIn("ville_etude", ancien.splitlines()[0])

    def test_export_applique_reellement_les_colonnes(self):
        """Les deux tableaux principaux doivent invoquer le filtre CSV."""
        construction = (RACINE / "corpus" / "construction.py").read_text(
            encoding="utf-8")
        moteur = (RACINE / "webapp.py").read_text(encoding="utf-8")
        ast.parse(construction)
        ast.parse(moteur)
        self.assertIn(
            'colonnes_csv_selectionnees(COLONNES_PUBLICATIONS_CSV, choix_csv)',
            construction)
        self.assertIn(
            'colonnes_csv_selectionnees(COLONNES_ENGAGEMENT, choix_csv)',
            construction)
        self.assertIn(
            'and (selection is None or "id" in selection)', moteur)
        self.assertIn('"variables_csv": self.settings.variables_csv', moteur)


if __name__ == "__main__":
    unittest.main()
