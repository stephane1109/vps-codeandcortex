"""Tests de découverte territoriale, pagination et transmission des @comptes."""
import csv
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from collecte.decouverte_territoriale import (
    creer_inventaire, charger, exporter_csv, exporter_txt, lister_inventaires,
    poursuivre_inventaire, correspond_territoire, correspond_hashtags,
    requete_territoriale, extraire_reference_lieu,
    preuve_localisation_video,
    hashtags_publication, hashtags_correspondants,
    lancer_recherche, arreter_recherche, recherche_active,
    recherche_arret_demande, recherche_en_cours,
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

    def test_arret_et_redemarrage_de_la_meme_collecte(self):
        """Le bouton d'arrêt libère le worker et autorise la reprise."""
        demarre = threading.Event()
        libere = threading.Event()
        appels = []

        def simuler_collecte(racine, proprietaire, identifiant, *,
                            nombre_pages, arret, credentiels):
            appels.append(identifiant)
            demarre.set()
            if not libere.wait(3):
                raise RuntimeError("Le test n'a pas libéré le travail.")
            if arret.is_set():
                etat = charger(racine, proprietaire, identifiant)
                from collecte.decouverte_territoriale import (
                    chemin_inventaire, sauvegarder)
                etat["etat"] = "interrompue"
                sauvegarder(
                    chemin_inventaire(racine, proprietaire, identifiant),
                    etat)
            return {}

        with patch("collecte.decouverte_territoriale.poursuivre_inventaire",
                   side_effect=simuler_collecte):
            self.assertTrue(lancer_recherche(
                self.racine, PROPRIETAIRE, self.inventaire["id"]))
            self.assertTrue(demarre.wait(2))
            self.assertTrue(recherche_active(self.inventaire["id"]))
            self.assertTrue(recherche_en_cours())
            inventaires = lister_inventaires(self.racine, PROPRIETAIRE)
            self.assertEqual(inventaires[0]["etat"], "en_cours")
            self.assertFalse(inventaires[0]["arret_demande"])
            self.assertTrue(arreter_recherche(self.inventaire["id"]))
            self.assertTrue(recherche_arret_demande(self.inventaire["id"]))
            self.assertTrue(lister_inventaires(
                self.racine, PROPRIETAIRE)[0]["arret_demande"])
            self.assertTrue(arreter_recherche(self.inventaire["id"]))
            libere.set()
            for entree in list(__import__(
                    "collecte.decouverte_territoriale",
                    fromlist=["_TRAVAUX"])._TRAVAUX.values()):
                entree["thread"].join(timeout=3)
            self.assertFalse(recherche_en_cours())
            self.assertFalse(recherche_active(self.inventaire["id"]))
            self.assertEqual(lister_inventaires(
                self.racine, PROPRIETAIRE)[0]["etat"], "interrompue")
            demarre.clear()
            self.assertTrue(lancer_recherche(
                self.racine, PROPRIETAIRE, self.inventaire["id"]))
            self.assertTrue(demarre.wait(2))
            self.assertEqual(len(appels), 2)
            libere.set()
            for entree in list(__import__(
                    "collecte.decouverte_territoriale",
                    fromlist=["_TRAVAUX"])._TRAVAUX.values()):
                entree["thread"].join(timeout=3)

    def test_arret_preserve_le_curseur_et_les_comptes(self):
        """Une page enregistrée doit rester disponible après un arrêt."""
        arret = threading.Event()
        corps = []

        def lire_page(url, *, data, headers):
            import json
            requete = json.loads(data)
            corps.append(requete)
            if len(corps) == 1:
                arret.set()
                return {"data": {
                    "videos": [{
                        "id": "1234567890", "username": "media31",
                        "video_description": "Manifestation à Toulouse",
                        "hashtag_names": ["manifestation"]}],
                    "has_more": True, "cursor": 100,
                    "search_id": "toulouse"}}
            return {"data": {"videos": [{
                "id": "1234567891", "username": "media31",
                "video_description": "Toulouse #lyceen",
                "hashtag_names": ["lyceen"]}], "has_more": False}}

        with patch("collecte.decouverte_territoriale._jeton",
                   return_value="jeton"):
            premier = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=lire_page, arret=arret)
            self.assertEqual(premier["etat"], "interrompue")
            self.assertEqual(premier["nombre_comptes"], 1)
            self.assertEqual(premier["pages"], 1)
            arret.clear()
            second = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=lire_page)
        self.assertTrue(second["terminee"])
        self.assertEqual(second["comptes"][0]["videos_trouvees"], 2)
        self.assertEqual(corps[1]["cursor"], 100)
        self.assertEqual(corps[1]["search_id"], "toulouse")

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
        self.assertEqual(lignes[0]["url_compte"],
                         "https://www.tiktok.com/@toulouse.media")
        self.assertEqual(lignes[1]["url_compte"],
                         "https://www.tiktok.com/@media31")
        self.assertEqual(
            exporter_txt(fichier).decode("utf-8"),
            "@toulouse.media\n@media31\n")

    def test_url_tiktok_place_sans_filtrage_place_id(self):
        """Le Place ID est documenté, jamais inventé comme filtre Research."""
        url = "https://www.tiktok.com/place/Toulouse-22535796483363264"
        reference = extraire_reference_lieu(url)
        self.assertEqual(reference["place_id"], "22535796483363264")
        self.assertEqual(reference["nom_lieu"], "Toulouse")
        bilan_initial = creer_inventaire(
            self.racine, PROPRIETAIRE, "",
            ["manifestation", "lyceen"], "2026-10-01", "2026-10-15",
            mode_territoire="place_reference", reference_lieu=url)
        self.assertEqual(bilan_initial["mode_territoire"], "place_reference")
        self.assertEqual(bilan_initial["place_id"], "22535796483363264")
        appels = []

        def renvoyer_page(adresse, *, data, headers):
            import json
            corps = json.loads(data)
            appels.append(corps)
            return {"data": {"videos": [
                {"id": "1234567891", "username": "toulouse.media",
                 "video_description": "Manifestation à Toulouse",
                 "hashtag_names": ["manifestation"]},
                {"id": "1234567892", "username": "hors.territoire",
                 "video_description": "Manifestation à Nantes",
                 "hashtag_names": ["manifestation"]},
            ], "has_more": False}}

        with patch("collecte.decouverte_territoriale._jeton",
                   return_value="jeton"):
            bilan = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, bilan_initial["id"],
                requete=renvoyer_page, nombre_pages=1)
        self.assertEqual(bilan["nombre_comptes"], 1)
        self.assertEqual(bilan["comptes"][0]["username"], "@toulouse.media")
        self.assertEqual(bilan["statut_localisation"],
                         "non_verifiee_recherche_textuelle")
        requete = appels[0]
        self.assertNotIn("place_id", str(requete))
        self.assertEqual(
            [c["field_name"] for c in requete["query"]["and"]],
            ["keyword", "hashtag_name"])
        sauvegarde = charger(self.racine, PROPRIETAIRE, bilan_initial["id"])
        export = list(csv.DictReader(
            io.StringIO(exporter_csv(sauvegarde).decode("utf-8-sig")),
            delimiter=";"))
        self.assertEqual(export[0]["place_id_reference"],
                         "22535796483363264")
        self.assertEqual(export[0]["url_compte"],
                         "https://www.tiktok.com/@toulouse.media")
        self.assertEqual(export[0]["statut_localisation"],
                         "non_verifiee_recherche_textuelle")
        self.assertEqual(export[0]["localisation_video_preuve"], "Toulouse")
        self.assertEqual(export[0]["source_localisation_preuve"],
                         "mention_dans_description_place_id_non_verifie")
        self.assertEqual(export[0]["hashtags_correspondants_preuve"],
                         "manifestation")
        self.assertEqual(
            export[0]["url_video_preuve"],
            "https://www.tiktok.com/@toulouse.media/video/1234567891")
        self.assertEqual(exporter_txt(sauvegarde).decode("utf-8"),
                         "@toulouse.media\n")

    def test_place_id_seul_et_validation_domaine(self):
        """L'identifiant seul exige une ville et les domaines externes sont exclus."""
        reference = extraire_reference_lieu("22535796483363264", "Toulouse")
        self.assertEqual(reference["nom_lieu"], "Toulouse")
        with self.assertRaisesRegex(ValueError, "ville"):
            extraire_reference_lieu("22535796483363264")
        with self.assertRaises(ValueError):
            extraire_reference_lieu(
                "https://example.net/place/Toulouse-22535796483363264")
        with self.assertRaises(ValueError):
            extraire_reference_lieu(
                "https://www.tiktok.com/place/Toulouse-invalide")

    def test_video_microbalade_sans_hashtags_demandes_est_exclue(self):
        """Une vidéo #toulouse sans #manifestation ni #lyceen est rejetée."""
        donnees = [
            {
                "id": "7702191252325862176",
                "username": "microbalade",
                "video_description": (
                    "Bienvenue à Toulouse #france #toulouse #microbalade"),
                "hashtag_names": ["france", "toulouse", "microbalade"],
            },
            {
                "id": "7702191252325862177",
                "username": "manifestants31",
                "video_description": "Manifestation des lycéens à Toulouse",
                "hashtag_names": ["manifestation", "lyceen"],
            },
        ]

        def requete(url, *, data, headers):
            import json
            corps = json.loads(data)
            self.assertEqual(
                [critere["field_name"]
                 for critere in corps["query"]["and"]],
                ["keyword", "hashtag_name"])
            self.assertEqual(
                corps["query"]["and"][1]["field_values"],
                ["manifestation", "lyceen"])
            return {"data": {"videos": donnees, "has_more": False}}

        with patch("collecte.decouverte_territoriale._jeton",
                   return_value="jeton"):
            resultat = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=requete, nombre_pages=1)

        self.assertEqual(resultat["nombre_comptes"], 1)
        self.assertEqual(resultat["comptes"][0]["username"], "@manifestants31")
        self.assertEqual(resultat["videos_sans_hashtag"], 1)
        self.assertEqual(resultat["videos_retenues"], 1)
        preuve = resultat["comptes"][0]["video_preuve"]
        self.assertEqual(preuve["hashtags_correspondants"],
                         ["lyceen", "manifestation"])
        self.assertIn("/@manifestants31/video/", preuve["url_video"])
        export = list(csv.DictReader(io.StringIO(exporter_csv(charger(
            self.racine, PROPRIETAIRE, self.inventaire["id"]
        )).decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(export), 1)
        self.assertEqual(export[0]["statut_preuve"],
                         "video_conforme_enregistree")
        self.assertEqual(export[0]["hashtags_correspondants_preuve"],
                         "lyceen, manifestation")
        self.assertEqual(export[0]["localisation_video_preuve"], "Toulouse")
        self.assertEqual(export[0]["source_localisation_preuve"],
                         "mention_dans_description")

    def test_un_compte_est_retenu_par_une_autre_video_conforme(self):
        """L'activité générale du profil ne remplace jamais la preuve vidéo."""
        def requete(url, *, data, headers):
            return {"data": {"videos": [
                {
                    "id": "7702191252325862176",
                    "username": "microbalade",
                    "video_description": (
                        "Bienvenue à Toulouse #france #toulouse #microbalade"),
                    "hashtag_names": ["france", "toulouse", "microbalade"],
                },
                {
                    "id": "7702191252325862178",
                    "username": "microbalade",
                    "video_description": "Toulouse #manifestation",
                    "hashtag_names": ["toulouse", "manifestation"],
                },
            ], "has_more": False}}

        with patch("collecte.decouverte_territoriale._jeton",
                   return_value="jeton"):
            resultat = poursuivre_inventaire(
                self.racine, PROPRIETAIRE, self.inventaire["id"],
                requete=requete, nombre_pages=1)
        self.assertEqual(resultat["comptes"][0]["username"], "@microbalade")
        self.assertEqual(resultat["comptes"][0]["videos_trouvees"], 1)
        self.assertEqual(resultat["videos_ecartees"], 1)
        self.assertEqual(
            resultat["comptes"][0]["video_preuve"]["url_video"],
            "https://www.tiktok.com/@microbalade/video/7702191252325862178")
        self.assertEqual(
            resultat["comptes"][0]["video_preuve"]["localisation"], "Toulouse")
        self.assertEqual(
            resultat["comptes"][0]["video_preuve"]["source_localisation"],
            "hashtag_territorial")

    def test_preuve_region_code_nest_pas_un_place_id(self):
        """Le Region Code du pays ne doit pas être présenté comme une ville."""
        preuve = preuve_localisation_video(
            {"region_code": "FR", "hashtag_names": ["manifestation"]},
            [], "region_code", "FR", "FR")
        self.assertEqual(preuve, {
            "localisation": "FR",
            "source_localisation": "region_code_pays_du_compte",
        })
        self.assertFalse(preuve_localisation_video(
            {"region_code": "US"}, [], "region_code", "FR", "FR"))

    def test_preuve_place_id_par_hashtag_territorial(self):
        """L'URL Place ne prouve pas la position de la vidéo."""
        preuve = preuve_localisation_video(
            {"hashtag_names": ["toulouse", "manifestation"],
             "video_description": "Une manifestation"},
            ["toulouse"], "place_reference", None, "Toulouse")
        self.assertEqual(preuve["localisation"], "Toulouse")
        self.assertEqual(
            preuve["source_localisation"],
            "hashtag_territorial_place_id_non_verifie")

    def test_export_ancien_inventaire_sans_preuve(self):
        """Un ancien CSV reste exportable sans localisation inventée."""
        ancien = charger(
            self.racine, PROPRIETAIRE, self.inventaire["id"])
        ancien["comptes"] = {"compte": {
            "username": "@compte",
            "videos_trouvees": 1,
            "identifiants_videos": ["1234567890"],
        }}
        lignes = list(csv.DictReader(
            io.StringIO(exporter_csv(ancien).decode("utf-8-sig")),
            delimiter=";"))
        self.assertEqual(lignes[0]["localisation_video_preuve"], "")
        self.assertEqual(lignes[0]["url_video_preuve"], "")
        self.assertEqual(
            lignes[0]["statut_preuve"],
            "historique_sans_preuve_enregistree")

    def test_seuls_les_hashtags_explicites_sont_retenus(self):
        """Le mot manifestation sans dièse n'est pas un hashtag."""
        message = {
            "video_description": "Manifestation à Toulouse #toulouse",
            "hashtag_names": ["toulouse", "france"],
        }
        self.assertEqual(hashtags_publication(message), {"toulouse", "france"})
        self.assertFalse(correspond_hashtags(
            message, ["manifestation", "lyceen"], "OR"))
        self.assertTrue(correspond_hashtags(
            {"video_description": "Toulouse #manifestation #lyceen"},
            ["manifestation", "lyceen"], "AND"))
        self.assertFalse(hashtags_correspondants(
            {"hashtag_names": ["manifestation"]},
            ["manifestation", "lyceen"], "AND"))

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
