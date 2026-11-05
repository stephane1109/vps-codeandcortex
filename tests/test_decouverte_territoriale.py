"""Tests de découverte territoriale, pagination et transmission des @comptes."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collecte.decouverte_territoriale import (
    creer_inventaire, charger, exporter_csv, exporter_txt, lister_inventaires,
    poursuivre_inventaire, correspond_territoire, correspond_hashtags,
    requete_territoriale,
)

PROPRIETAIRE = "a" * 64


class TestDecouverteTerritoriale(unittest.TestCase):
    def setUp(self):
        self.temporaire = tempfile.TemporaryDirectory()
        self.racine = Path(self.temporaire.name)
        self.inventaire = creer_inventaire(
            self.racine, PROPRIETAIRE, "Toulouse",
            ["manifestation", "lyceen"], "2026-10-01", "2026-10-15")

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
                         "video_description": "Manifestation lycéenne à Toulouse",
                         "hashtag_names": ["manifestation", "lyceen"]},
                        {"id": "1234567890", "username": "toulouse.media",
                            "video_description": "Toulouse",
                            "hashtag_names": ["manifestation"]}],
                    "has_more": True, "cursor": 100, "search_id": "recherche1",
                }}
            return {"data": {
                "videos": [
                    {"id": "1234567890", "username": "toulouse.media"},
                    {"id": "1234567891", "username": "toulouse.media",
                     "video_description": "Rassemblement à Toulouse",
                     "hashtag_names": ["lyceen"]},
                    {"id": "1234567892", "username": "media31",
                     "hashtag_names": ["toulouse", "manifestation"]}],
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
        self.assertIn("and", corps_envoyes[0]["query"])
        self.assertNotIn("or", corps_envoyes[0]["query"])
        fichier = charger(self.racine, PROPRIETAIRE, self.inventaire["id"])
        lignes = list(csv.DictReader(
            io.StringIO(exporter_csv(fichier).decode("utf-8-sig")),
            delimiter=";"))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["username"], "@toulouse.media")
        self.assertEqual(
            exporter_txt(fichier).decode("utf-8"),
            "@toulouse.media\n@media31\n")

    def test_pays_region_code_fr_avec_hashtag(self):
        """Ne conserver que les comptes dont region_code vaut FR."""
        inventaire = creer_inventaire(
            self.racine, PROPRIETAIRE, "", ["manifestation", "lyceen"],
            "2026-10-01", "2026-10-15",
            mode_territoire="region_code", region_code="fr")
        reponses = [
            {"id": "1234567891", "username": "profil.fr",
             "region_code": "FR", "hashtag_names": ["manifestation"]},
            {"id": "1234567892", "username": "profil.us",
             "region_code": "US", "hashtag_names": ["manifestation"]},
            {"id": "1234567893", "username": "profil.sans.hashtag",
             "region_code": "FR", "hashtag_names": ["football"]},
        ]
        demandes = []
        def requete(url, *, data, headers):
            import json
            demandes.append(json.loads(data))
            return {"data": {"videos": reponses, "has_more": False}}
        with patch("collecte.decouverte_territoriale._jeton", return_value="token"):
            bilan = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, inventaire["id"],
                requete=requete, nombre_pages=1)
        self.assertTrue(bilan["terminee"])
        self.assertEqual(bilan["nombre_comptes"], 1)
        self.assertEqual(bilan["comptes"][0]["username"], "@profil.fr")
        self.assertEqual(bilan["videos_ecartees"], 2)
        conditions = demandes[0]["query"]["and"]
        self.assertEqual(conditions[0], {
            "field_name": "region_code", "operation": "EQ",
            "field_values": ["FR"]})
        self.assertEqual(conditions[1]["field_name"], "hashtag_name")
        self.assertNotIn("keyword", str(demandes[0]))

    def test_region_code_ne_localise_pas_une_ville(self):
        """Un pays FR ne garantit pas la ville de Toulouse."""
        inventaire = creer_inventaire(
            self.racine, PROPRIETAIRE, "", ["lyceen"],
            "2026-10-01", "2026-10-15",
            mode_territoire="region_code", region_code="FR")
        self.assertEqual(inventaire["mode_territoire"], "region_code")
        self.assertEqual(inventaire["region_code"], "FR")
        self.assertEqual(inventaire["ville"], "FR")

    def test_croisement_et_exige_tous_les_hashtags(self):
        """La ville ET deux hashtags doivent tous être présents."""
        video = {
            "id": "1234567890", "username": "compte.test",
            "video_description": "Toulouse #manifestation #lyceen",
            "hashtag_names": ["manifestation", "lyceen"],
        }
        self.assertTrue(correspond_territoire(video, ["toulouse"]))
        self.assertTrue(correspond_hashtags(
            video, ["manifestation", "lyceen"], "AND"))
        self.assertFalse(correspond_hashtags(
            {**video, "hashtag_names": ["manifestation"],
             "video_description": "Toulouse"},
            ["manifestation", "lyceen"], "AND"))
        requete = requete_territoriale(
            ["toulouse"], "20261001", "20261015",
            hashtags_croises=["manifestation", "lyceen"], operateur="AND")
        self.assertEqual(
            [c["operation"] for c in requete["query"]["and"]],
            ["IN", "EQ", "EQ"])

    def test_saisie_de_hashtags_obligatoire(self):
        """Un inventaire croisé exige au moins un hashtag."""
        with self.assertRaisesRegex(ValueError, "hashtag"):
            creer_inventaire(
                self.racine, PROPRIETAIRE, "Toulouse", [],
                "2026-10-01", "2026-10-15")

    def test_http_500_relance_la_meme_page(self):
        """Un incident 500 ponctuel ne détruit pas la pagination."""
        from collecte.researchapi import ResearchErreurServeur
        essais = []
        def requete_instable(url, *, data, headers):
            essais.append(data)
            if len(essais) == 1:
                raise ResearchErreurServeur(500)
            return {"data": {"videos": [
                {"id": "1234567891", "username": "media.toulouse",
                 "video_description": "Toulouse",
                 "hashtag_names": ["manifestation"]}], "has_more": False}}
        with patch("collecte.decouverte_territoriale._jeton", return_value="jeton"), (
            patch("collecte.decouverte_territoriale.time.sleep", return_value=None)
        ):
            bilan = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=requete_instable, nombre_pages=1)
        self.assertEqual(len(essais), 2)
        self.assertEqual(essais[0], essais[1])
        self.assertEqual(bilan["nombre_comptes"], 1)
        self.assertEqual(bilan["relances_serveur"], 1)
        self.assertEqual(bilan["pages"], 1)

    def test_http_500_repetes_conservent_le_curseur(self):
        """Après quatre échecs, on peut relancer sans effacer l'inventaire."""
        from collecte.researchapi import ResearchErreurServeur
        appels = []
        def erreur(url, *, data, headers):
            appels.append(data)
            raise ResearchErreurServeur(500)
        with patch("collecte.decouverte_territoriale._jeton", return_value="jeton"), (
            patch("collecte.decouverte_territoriale.time.sleep", return_value=None)
        ):
            bilan = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=erreur, nombre_pages=1)
        self.assertEqual(len(appels), 4)
        self.assertEqual(bilan["pages"], 0)
        self.assertEqual(bilan["relances_serveur"], 3)
        self.assertIn("position de reprise", bilan["erreur"])

    def test_pas_de_residence_inventee(self):
        """L'inventaire ne contient aucune attribution de résidence."""
        self.assertNotIn("residence", self.inventaire)
        self.assertEqual(self.inventaire["hashtags"][0], "toulouse")
        self.assertEqual(self.inventaire["hashtags_croises"], ["manifestation", "lyceen"])

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
        requete = requete_territoriale(
            ["toulouse"], "20261001", "20261015",
            hashtags_croises=["manifestation", "lyceen"])
        self.assertIn("keyword", {
            c["field_name"] for c in requete["query"]["and"]})
        self.assertIn("hashtag_name", {
            c["field_name"] for c in requete["query"]["and"]})
        self.assertTrue(correspond_hashtags(video, ["manifestation", "lyceen"]))
        self.assertFalse(correspond_hashtags(video, ["football"]))
        self.assertEqual(requete["max_count"], 100)

    def test_reprise_ancien_inventaire_termine(self):
        """Une recherche hashtag ancienne peut être relancée avec keyword."""
        from collecte.decouverte_territoriale import chemin_inventaire, sauvegarder
        fichier = chemin_inventaire(
            self.racine, PROPRIETAIRE, self.inventaire["id"])
        ancien = charger(self.racine, PROPRIETAIRE, self.inventaire["id"])
        ancien.pop("version_requete", None)
        ancien.pop("hashtags_croises", None)
        ancien["terminee"] = True
        ancien["cursor"] = 100
        ancien["search_id"] = "ancienne_recherche"
        sauvegarder(fichier, ancien)
        appels = []
        def reponse(url, *, data, headers):
            import json
            corps = json.loads(data)
            appels.append(corps)
            return {"data": {"videos": [
                {"id": "1234567890", "username": "compte.tlse",
                 "video_description": "Manifestation à Toulouse",
                 "hashtag_names": ["manifestation", "lyceen"]}],
                 "has_more": False}}
        with patch("collecte.decouverte_territoriale._jeton", return_value="token"):
            resultat = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=reponse, nombre_pages=1)
        self.assertEqual(resultat["nombre_comptes"], 1)
        self.assertNotIn("cursor", appels[0])
        self.assertIn("keyword", str(appels[0]))
        self.assertIn("or", appels[0]["query"])

    def test_protection_contre_curseur_invalide(self):
        """Un curseur manquant interrompt sans recommencer à la première page."""
        def reponse_invalide(url, *, data, headers):
            return {"data": {
                "videos": [{"id": "1234567890", "username": "toulouse.media",
                            "video_description": "Toulouse",
                            "hashtag_names": ["manifestation"]}],
                "has_more": True}}
        with patch("collecte.decouverte_territoriale._jeton", return_value="token"):
            resultat = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=reponse_invalide, nombre_pages=1)
        self.assertIn("curseur", resultat["erreur"])
        self.assertEqual(resultat["nombre_comptes"], 1)


if __name__ == "__main__":
    unittest.main()
