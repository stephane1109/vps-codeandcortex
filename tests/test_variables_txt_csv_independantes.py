"""Tester la sélection indépendante TXT et CSV des variables TikTok."""

import ast
import unittest
from pathlib import Path

from collecte.selection_variables_csv import (
    VARIABLES_CSV, colonnes_csv_selectionnees)
from corpus.publications_csv import COLONNES_PUBLICATIONS_CSV
from corpus.construction import COLONNES_ENGAGEMENT
from webapp import entete_publication, StartRequest


RACINE = Path(__file__).resolve().parents[1]


class TestVariablesTxtCsvIndependantes(unittest.TestCase):
    def test_toutes_les_variables_possedent_une_destination_csv(self):
        """Vérifier les variables brutes, les classes et la ville."""
        attentes = {
            "date", "profil", "recuperer_abonnes", "follower_count",
            "abonnes_classe", "id", "categorie_compte", "region_code",
            "is_verified", "vues", "vues_classe", "likes", "likes_classe",
            "commentaires", "commentaires_classe", "partages",
            "partages_classe", "favoris", "favoris_classe", "duree",
            "duree_classe", "taux_engagement", "classe_taux_engagement",
            "ville_etude",
        }
        self.assertEqual(set(VARIABLES_CSV), attentes)

    def test_csv_classe_seule_sans_valeur_brute(self):
        """Conserver les classes choisies et l'ID technique de jointure."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["vues_classe"])
        self.assertIn("vues_classe", colonnes)
        self.assertNotIn("vues", colonnes)
        self.assertIn("publication_id", colonnes)
        self.assertNotIn("likes_classe", colonnes)

    def test_csv_recuperation_abonnes_sans_valeur_numerique(self):
        """Ne pas imposer une colonne décrochée par une autre option."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["recuperer_abonnes"])
        self.assertIn("follower_count_statut", colonnes)
        self.assertNotIn("follower_count", colonnes)
        self.assertNotIn("classe_abonnes", colonnes)

    def test_csv_ville_et_categorie_independantes(self):
        """La ville et la catégorie se sélectionnent chacune explicitement."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["ville_etude"])
        self.assertIn("ville_etude", colonnes)
        self.assertNotIn("categorie_media", colonnes)
        self.assertNotIn("presse_nationale", colonnes)
        autres = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["categorie_compte"])
        self.assertNotIn("ville_etude", autres)
        self.assertIn("presse_nationale", autres)

    def test_engagement_csv_meme_choix_que_publications_csv(self):
        """Le filtrage s'applique aux deux tableaux de publications."""
        colonnes = colonnes_csv_selectionnees(
            COLONNES_ENGAGEMENT, ["partages_classe"])
        self.assertIn("partages_classe", colonnes)
        self.assertNotIn("partages", colonnes)
        self.assertIn("publication_id", colonnes)

    def test_txt_et_csv_ne_dependant_pas_l_un_de_l_autre(self):
        """Un champ TXT peut être absent alors que le CSV le conserve."""
        video = {
            "id": "123", "author": "compte",
            "created_at": "2026-11-05T12:00:00Z",
            "engagement": {"vues": {"valeur": 1500}},
            "ville_etude": "toulouse",
            "inclure_ville_etude_txt": False,
        }
        entete = entete_publication(video, ["id"])
        self.assertNotIn("*vues_", entete)
        self.assertNotIn("*ville_toulouse", entete)
        donnees = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, ["vues", "ville_etude"])
        self.assertIn("vues", donnees)
        self.assertIn("ville_etude", donnees)

    def test_options_restent_facultatives_pour_les_anciennes_collectes(self):
        """Les anciennes requêtes conservent les schémas historiques."""
        self.assertIsNone(StartRequest.model_fields["variables_csv"].default)
        colonnes = colonnes_csv_selectionnees(
            COLONNES_PUBLICATIONS_CSV, None)
        self.assertEqual(colonnes, list(COLONNES_PUBLICATIONS_CSV))

    def test_interface_une_ligne_deux_cases(self):
        """Les trois modes utilisent le même composant compact."""
        source = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("def ligne_variable(libelle, cle_txt, cle_csv", source)
        self.assertIn("colonne_libelle, colonne_txt, colonne_csv = st.columns(", source)
        self.assertIn('"TXT", key=cle_txt', source)
        self.assertIn('"CSV", key=cle_csv', source)
        self.assertIn('if source == "comptes":', source)
        self.assertIn('"txt_ville_etude", "csv_ville_etude"', source)
        self.assertIn('valeurs["variables_csv"] = [', source)
        self.assertIn('valeurs["variables_txt"] = [', source)


if __name__ == "__main__":
    unittest.main()
