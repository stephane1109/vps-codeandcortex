"""Tests sans accès réseau : six hashtags en OU et traçabilité des exports."""
import json
import unittest
from types import SimpleNamespace

from collecte.parametres_collecte import generer_parametres_collecte
from collecte.researchapi import collecter_videos_presse_research
from connect_profil import ConnexionProfil


class TestHashtagsProfilsEtParametres(unittest.TestCase):
    def setUp(self):
        self.hashtags = [
            "manifestation", "lyceen", "mobilisation",
            "violence", "education", "protestation",
        ]

    def test_six_hashtags_transmis_au_connecteur_profils(self):
        connexion = ConnexionProfil.__new__(ConnexionProfil)
        connexion.configurer_moteur = lambda _parametres, moteur: setattr(
            connexion, "moteur_collecte", moteur)
        parametres = SimpleNamespace(
            hashtags=self.hashtags, comptes=["compte1", "compte2"],
            profil_moteur="research", operator="OR")
        sources = connexion.preparer_sources(parametres)
        self.assertEqual([s["compte"] for s in sources], ["compte1", "compte2"])
        self.assertEqual(connexion.research_hashtags, self.hashtags)
        self.assertEqual(connexion.research_operateur, "OR")

    def test_recherche_officielle_ou_transmet_six_valeurs(self):
        requetes = []

        def reponse_simulee(_url, *, data, headers):
            requetes.append(json.loads(data))
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
            return {
                "data": {
                    "videos": [{
                        "id": "1234567890123456789",
                        "username": "compte1",
                        "video_description": "Message #protestation",
                        "hashtag_names": ["protestation"],
                        "create_time": 1790899200,
                    }],
                    "has_more": False,
                }
            }

        bilan = {}
        trouves = collecter_videos_presse_research(
            "compte1", None, bilan, debut="2026-10-01",
            fin="2026-10-02", jeton="jeton_fictif",
            requete=reponse_simulee, pause=lambda _duree: None,
            hashtags=self.hashtags, operateur="OR")
        self.assertEqual(len(requetes), 1)
        conditions = requetes[0]["query"]["and"]
        self.assertIn({
            "field_name": "username", "operation": "EQ",
            "field_values": ["compte1"]}, conditions)
        self.assertIn({
            "field_name": "hashtag_name", "operation": "IN",
            "field_values": self.hashtags}, conditions)
        self.assertEqual(len(trouves), 1)
        self.assertEqual(bilan["hashtags_recherches"], self.hashtags)
        self.assertEqual(bilan["operateur_hashtags"], "OR")

    def test_fichier_parametres_contient_options_sans_secrets(self):
        contenu = generer_parametres_collecte({
            "source_collecte": "comptes",
            "nom_sauvegarde": "Essai profils",
            "profil_moteur": "research",
            "comptes": ["compte1", "compte2"],
            "hashtags_saisis": self.hashtags,
            "operator": "OR",
            "date_debut": "2026-10-01",
            "date_fin": "2026-10-31",
            "variables_txt": ["date", "profil", "likes"],
            "variables_csv": ["likes", "vues"],
            "collecter_commentaires": False,
            "research_client_key": "CLE_INTERDITE",
            "research_client_secret": "SECRET_INTERDIT",
            "cookies_tiktok": "COOKIE_INTERDIT",
        }, identifiant="test123", statut="completed")
        self.assertIn("Nombre de hashtags recherchés : 6", contenu)
        self.assertIn("Opérateur : OR", contenu)
        self.assertIn("hashtag_name IN", contenu)
        self.assertIn("protestation", contenu)
        self.assertIn("2026-10-01", contenu)
        self.assertIn("Variables sélectionnées dans le TXT", contenu)
        self.assertIn("Collecter les commentaires [collecter_commentaires] : non", contenu)
        for secret in ("CLE_INTERDITE", "SECRET_INTERDIT", "COOKIE_INTERDIT"):
            self.assertNotIn(secret, contenu)


if __name__ == "__main__":
    unittest.main()
