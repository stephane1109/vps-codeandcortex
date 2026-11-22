"""Suppression sûre d'une seule collecte PostgreSQL, sans base réelle."""
import unittest
from unittest.mock import patch

from stockage.postgres_consultation import supprimer_collecte_postgres, empreinte


class CurseurFictif:
    """Conserver les requêtes SQL et simuler un propriétaire autorisé."""

    def __init__(self, nom="sauvegarde_test_3"):
        self.nom = nom
        self.instructions = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, instruction, parametres=None):
        self.instructions.append((instruction, parametres))

    def fetchone(self):
        if self.nom is None:
            return None
        return (self.nom,)


class ConnexionFictive:
    """Simuler une transaction valide sans toucher aux données réelles."""

    def __init__(self, nom="sauvegarde_test_3"):
        self.curseur_fictif = CurseurFictif(nom)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.curseur_fictif


class TestsSuppressionPostgres(unittest.TestCase):
    def test_supprime_uniquement_la_collecte_confirmee(self):
        """Une ligne par identifiant : aucune commande DROP TABLE."""
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            resultat = supprimer_collecte_postgres(
                "cookie_prive", "collecte", "a" * 32, "sauvegarde_test_3")
        self.assertEqual(resultat["statut"], "supprime")
        self.assertEqual(resultat["nom"], "sauvegarde_test_3")
        instructions = connexion.curseur_fictif.instructions
        self.assertEqual(len(instructions), 2)
        self.assertIn("FOR UPDATE", instructions[0][0])
        self.assertIn(
            "DELETE FROM scraptiktok_collectes WHERE collecte_id=%s",
            instructions[1][0])
        self.assertIn("proprietaire_hash=%s", instructions[1][0])
        self.assertNotIn("DROP", instructions[1][0])
        self.assertEqual(instructions[1][1], (
            "a" * 32, empreinte("cookie_prive")))

    def test_refuse_nom_inexact_et_ne_supprime_rien(self):
        """Une saisie ressemblante n'autorise pas la suppression."""
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            with self.assertRaisesRegex(ValueError, "confirmation"):
                supprimer_collecte_postgres(
                    "cookie_prive", "collecte", "a" * 32, "sauvegarde_test")
        self.assertEqual(len(connexion.curseur_fictif.instructions), 1)

    def test_refuse_collecte_non_autorisee(self):
        """Une collecte inaccessible n'est jamais supprimée."""
        connexion = ConnexionFictive(nom=None)
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            with self.assertRaises(ValueError):
                supprimer_collecte_postgres(
                    "cookie_prive", "collecte", "a" * 32, "sauvegarde_test_3")
        self.assertEqual(len(connexion.curseur_fictif.instructions), 1)

    def test_refuse_identifiants_et_types_inconnus(self):
        """La table SQL ne peut pas être choisie librement dans la requête."""
        for type_ in ("publications", "research; DROP TABLE x", ""):
            with self.assertRaises(ValueError):
                supprimer_collecte_postgres(
                    "cookie_prive", type_, "a" * 32, "sauvegarde_test_3")
        with self.assertRaises(ValueError):
            supprimer_collecte_postgres(
                "cookie_prive", "collecte", "id-non-valide", "sauvegarde_test_3")

    def test_supprimer_research_utilise_une_table_autorisee(self):
        """Research conserve son propre schéma et une vérification préalable."""
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion), patch(
                       "stockage.postgres_consultation.tables_disponibles",
                       return_value=True):
            resultat = supprimer_collecte_postgres(
                "cookie_prive", "research", "a" * 32, "sauvegarde_test_3")
        self.assertEqual(resultat["type"], "research")
        self.assertIn(
            "DELETE FROM research_plans WHERE plan_id=%s",
            connexion.curseur_fictif.instructions[-1][0])

    def test_interface_simple_et_suppression_confirmee(self):
        """La consultation et la migration anciennes ne sont plus affichées."""
        from pathlib import Path
        from webapp import app
        page = (Path(__file__).resolve().parents[1]
                / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertNotIn('"Table à consulter"', page)
        self.assertNotIn('"Rechercher dans les auteurs, identifiants et textes"', page)
        self.assertNotIn("Opération exceptionnelle : recopier", page)
        self.assertIn('"Télécharger tous les résultats (ZIP)"', page)
        self.assertIn('"Supprimer définitivement cette collecte"', page)
        self.assertIn('disabled=nom_confirmation != sauvegarde_bdd["nom"]', page)
        self.assertIn(
            "/api/base-donnees/{type_sauvegarde}/{identifiant}/supprimer",
            {getattr(route, "path", "") for route in app.routes})


if __name__ == "__main__":
    unittest.main()
