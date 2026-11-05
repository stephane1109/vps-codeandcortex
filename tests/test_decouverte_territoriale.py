"""Tests de découverte territoriale, pagination et transmission des @comptes."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collecte.decouverte_territoriale import (
    creer_inventaire, charger, exporter_csv, exporter_txt, lister_inventaires,
    poursuivre_inventaire, correspond_territoire, requete_territoriale,
)

PROPRIETAIRE = "a" * 64


class TestDecouverteTerritoriale(unittest.TestCase):
    def setUp(self):
        self.temporaire = tempfile.TemporaryDirectory()
        self.racine = Path(self.temporaire.name)
        self.inventaire = creer_inventaire(
            self.racine, PROPRIETAIRE, "Toulouse",
            ["toulousain", "toulousaine"], "2026-10-01", "2026-10-15")

    def tearDown(self):
        self.temporaire.cleanup()

    def test_liste_privee(self):
        """Les recherches appartiennent exclusivement à leur historique."""
        self.assertEqual(len(lister_inventaires(self.racine, PROPRIETAIRE)), 1)
        self.assertEqual(len(lister_inventaires(self.racine, "b"*64)), 0)

    def test_pagination_dedoublonnage_et_export(self):
        """La deuxième séquence utilise bien le curseur de la première."""
        corps_envoyes = []

        def fausse_requete(url, *, data, headers):
            import json
            corps = json.loads(data)
            corps_envoyes.append(corps)
            if len(corps_envoyes) == 1:
                return {"data": {
                    "videos": [
                        {"id": "1234567890", "username": "toulouse.media",
                         "video_description": "Manifestation lycéenne à Toulouse"},
                        {"id": "1234567890", "username": "toulouse.media",
                            "video_description": "Toulouse"}],
                    "has_more": True, "cursor": 100, "search_id": "recherche1",
                }}
            return {"data": {
                "videos": [
                    {"id": "1234567890", "username": "toulouse.media"},
                    {"id": "1234567891", "username": "toulouse.media",
                     "video_description": "Rassemblement à Toulouse"},
                    {"id": "1234567892", "username": "media31",
                     "hashtag_names": ["toulouse"]}],
                "has_more": False,
            }}

        with patch("collecte.decouverte_territoriale._jeton", return_value="token"):
            premier = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=fausse_requete, nombre_pages=1)
            self.assertEqual(premier["nombre_comptes"], 1)
            self.assertFalse(premier["terminee"])
            second = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=fausse_requete, nombre_pages=1)
        self.assertTrue(second["terminee"])
        self.assertEqual(second["nombre_comptes"], 2)
        self.assertEqual(second["comptes"][0]["videos_trouvees"], 2)
        self.assertEqual(corps_envoyes[1]["cursor"], 100)
        self.assertEqual(corps_envoyes[1]["search_id"], "recherche1")
        self.assertIn("hashtag_name", str(corps_envoyes[0]))
        self.assertIn("keyword", str(corps_envoyes[0]))
        fichier = charger(self.racine, PROPRIETAIRE, self.inventaire["id"])
        lignes = list(csv.DictReader(
            io.StringIO(exporter_csv(fichier).decode("utf-8-sig")),
            delimiter=";"))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["username"], "@toulouse.media")
        self.assertEqual(
            exporter_txt(fichier).decode("utf-8"),
            "@toulouse.media\\n@media31\\n")

    def test_pas_de_residence_inventee(self):
        """L'inventaire ne contient aucune attribution de résidence."""
        self.assertNotIn("residence", self.inventaire)
        self.assertEqual(self.inventaire["hashtags"][0], "toulouse")

    def test_recherche_description_sans_hashtag_de_ville(self):
        """Repérer Toulouse avec les seuls hashtags manifestation et lycéen."""
        video = {
            "id": "1234567890", "username": "lyceen.tlse",
            "hashtag_names": ["manifestation", "lyceen"],
            "video_description": "Manifestation des lycéens de Toulouse",
        }
        self.assertTrue(correspond_territoire(video, ["toulouse"]))
        self.assertFalse(correspond_territoire(
            {**video, "video_description": "Manifestation à Bordeaux"},
            ["toulouse"]))
        requete = requete_territoriale(["toulouse"], "20261001", "20261015")
        self.assertIn("keyword", {
            c["field_name"] for c in requete["query"]["or"]})
        self.assertEqual(requete["max_count"], 100)

    def test_protection_contre_curseur_invalide(self):
        """Un curseur manquant interrompt sans recommencer à la première page."""
        def reponse_invalide(url, *, data, headers):
            return {"data": {
                "videos": [{"id": "1234567890", "username": "toulouse.media"}],
                "has_more": True}}
        with patch("collecte.decouverte_territoriale._jeton", return_value="token"):
            resultat = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=reponse_invalide, nombre_pages=1)
        self.assertIn("curseur", resultat["erreur"])
        self.assertEqual(resultat["nombre_comptes"], 1)


if __name__ == "__main__":
    unittest.main()
