"""Tests de l'intégration Apify sans déclencher de collecte payante."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collecte.presse_apify import (
    ACTOR, ErreurApify, PresseApify, construire_entree,
    normaliser_publications,
)
from connect_presse import ConnexionPresse
from webapp import StartRequest, text_export


IDENTIFIANT = "7702367667616746785"


def publication(compte="lemondefr", identifiant=IDENTIFIANT):
    return {
        "id": identifiant,
        "authorMeta": {"name": compte},
        "webVideoUrl": f"https://www.tiktok.com/@{compte}/video/{identifiant}",
        "text": "Manifestation lycéenne en France #manifestation",
        "createTime": 1750000000,
        "playCount": 1250,
        "diggCount": 72,
        "commentCount": 0,
        "shareCount": 11,
        "collectCount": 7,
        "hashtags": [{"name": "manifestation"}],
        "isSlideshow": False,
    }


class ReponseSimulee:
    """Réponse HTTP minimale de l'API Apify."""

    def __init__(self, contenu, statut=200):
        self.contenu = json.dumps(contenu).encode("utf-8")
        self.status = statut

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        return False

    def read(self, longueur):
        return self.contenu[:longueur]


class TestsApify(unittest.TestCase):
    def test_entree_documentee_exclut_telechargements(self):
        entree = construire_entree("@lemondefr", 3)
        self.assertEqual(entree["profiles"], ["lemondefr"])
        self.assertEqual(entree["resultsPerPage"], 3)
        self.assertEqual(entree["profileScrapeSections"], ["videos"])
        self.assertEqual(entree["profileSorting"], "latest")
        self.assertFalse(entree["shouldDownloadVideos"])
        self.assertFalse(entree["shouldDownloadSubtitles"])

    def test_normalisation_rejette_comptes_et_photos(self):
        elements = [
            publication(),
            publication("bfmtv", "7702367667616746786"),
            {**publication(identifiant="7702367667616746787"), "isSlideshow": True},
            {**publication(identifiant="7702367667616746788"),
             "webVideoUrl": "https://www.tiktok.com/@bfmtv/video/7702367667616746788"},
            publication(),
        ]
        donnees = normaliser_publications(elements, "lemondefr", 10)
        self.assertEqual(len(donnees), 1)
        fiche = donnees[IDENTIFIANT]
        self.assertEqual(fiche["author"], "lemondefr")
        self.assertEqual(fiche["description"], publication()["text"])
        self.assertEqual(fiche["engagement"]["vues"]["valeur"], 1250)
        self.assertEqual(fiche["engagement"]["likes"]["valeur"], 72)
        self.assertEqual(fiche["engagement"]["commentaires"]["valeur"], 0)
        self.assertEqual(fiche["engagement"]["partages"]["valeur"], 11)
        self.assertEqual(fiche["engagement"]["favoris"]["valeur"], 7)
        self.assertEqual(fiche["hashtags"], ["manifestation"])
        self.assertEqual(fiche["source"], "apify_profile_scraper")

    def test_correspondance_txt_existing_et_drapeau_ia_non_invente(self):
        fiche = next(iter(normaliser_publications(
            [publication()], "lemondefr", 1).values()))
        self.assertIsNone(fiche.get("contenu_genere_ia"))
        texte = text_export(
            [fiche], False, variables_txt=["profil", "vues", "likes"],
            inclure_texte_genere_ia=False)
        self.assertIn("Manifestation lycéenne en France", texte)
        self.assertIn("lemondefr", texte)
        self.assertIn("1250", texte)

    def test_jeton_secret_ou_variable_coolify(self):
        with patch.dict(os.environ, {"APIFY_API_TOKEN": ""}):
            with self.assertRaisesRegex(Exception, "Apify"):
                StartRequest(
                    source_collecte="presse", presse_moteur="apify",
                    medias=["lemonde"])
        parametres = StartRequest(
            source_collecte="presse", presse_moteur="apify",
            medias=["lemonde"], apify_api_token="JETON_TEST_PRIVE")
        self.assertNotIn("JETON_TEST_PRIVE", str(parametres))
        self.assertNotIn("apify_api_token", parametres.model_dump())
        connexion = ConnexionPresse(Mock())
        connexion.preparer_sources(parametres)
        self.assertEqual(connexion.moteur_collecte, "apify")

    def test_integration_deux_appels_et_export(self):
        appels = []

        def ouvrir(requete, timeout):
            appels.append(requete)
            chemin = requete.full_url
            self.assertEqual(requete.get_header("Authorization"),
                             "Bearer JETON_TEST_PRIVE")
            self.assertNotIn("JETON_TEST_PRIVE", chemin)
            if "/acts/" in chemin:
                self.assertIn(ACTOR, chemin)
                self.assertIn("maxItems=3", chemin)
                self.assertIn("maxTotalChargeUsd=1.0", chemin)
                entree = json.loads(requete.data)
                self.assertEqual(entree["profiles"], ["lemondefr"])
                return ReponseSimulee(
                    {"data": {"id": "abcde12345", "status": "RUNNING"}}, 201)
            if "/actor-runs/" in chemin:
                return ReponseSimulee({"data": {
                    "id": "abcde12345", "status": "SUCCEEDED",
                    "defaultDatasetId": "ds12345678"
                }})
            if "/datasets/" in chemin:
                return ReponseSimulee([publication()])
            raise AssertionError("Requête Apify imprévue")

        with patch.dict(os.environ, {"APIFY_MAX_CHARGE_USD": "1.0"}):
            client = PresseApify(SimpleNamespace(limit=3),
                                cle="JETON_TEST_PRIVE",
                                ouvrir_url=ouvrir, horloge=lambda: 0,
                                pause=lambda _: None)
            rapport = {}
            liens = client.decouvrir("lemondefr", rapport)
            self.assertEqual(len(liens), 1)
            self.assertEqual(len(appels), 3)
            self.assertEqual(rapport["requetes_tentees"], 3)
            self.assertEqual(rapport["metadonnees_api"][IDENTIFIANT]["author"],
                             "lemondefr")
            self.assertTrue(rapport["collecte_partielle"])
            client.fermer()
            self.assertEqual(client._cle, "")
        self.assertEqual(
            liens[0],
            "https://www.tiktok.com/@lemondefr/video/7702367667616746785")

    def test_annulation_arrete_actor_payant(self):
        appels = []
        checks = 0

        def verifier():
            nonlocal checks
            checks += 1
            if checks > 2:
                raise RuntimeError("Annulation utilisateur")

        def ouvrir(requete, timeout):
            appels.append(requete.full_url)
            if requete.full_url.endswith("/abort"):
                return ReponseSimulee({"data": {"status": "ABORTING"}})
            return ReponseSimulee(
                {"data": {"id": "abcde12345", "status": "RUNNING"}}, 201)

        client = PresseApify(SimpleNamespace(limit=3), cle="JETON_TEST_PRIVE",
                            verifier=verifier, ouvrir_url=ouvrir,
                            horloge=lambda: 0, pause=lambda _: None)
        with self.assertRaisesRegex(RuntimeError, "Annulation"):
            client.decouvrir("lemondefr", {})
        self.assertTrue(any(chemin.endswith("/abort") for chemin in appels))
        self.assertIsNone(client.execution_id)

    def test_echec_actor_pas_de_faux_resultat(self):
        appels = []
        def ouvrir(requete, timeout):
            appels.append(requete.full_url)
            if requete.full_url.endswith("/abort"):
                return ReponseSimulee({"data": {"status": "ABORTED"}})
            if "/acts/" in requete.full_url:
                return ReponseSimulee({"data": {
                    "id": "abcde12345", "status": "FAILED"
                }}, 201)
            raise AssertionError("Le dataset ne doit pas être consulté")
        client = PresseApify(SimpleNamespace(limit=3), cle="JETON_TEST_PRIVE",
                            ouvrir_url=ouvrir)
        rapport = {}
        with self.assertRaises(ErreurApify):
            client.decouvrir("lemondefr", rapport)
        self.assertEqual(rapport["diagnostic"]["code"], "apify_execution_echec")
        self.assertFalse(any("/datasets/" in url for url in appels))


    def test_mesures_decimales_et_url_absente(self):
        """Préserver les dates et métriques entières décodées comme flottants."""
        from datetime import datetime, timezone
        element = publication()
        element.update(
            createTime=1750000000.0, playCount=1250.0,
            diggCount=72.0, commentCount=0.0,
            shareCount=11.0, collectCount=7.0,
            webVideoUrl="",
        )
        fiche = normaliser_publications([element], "lemondefr", 5)[IDENTIFIANT]
        self.assertEqual(
            fiche["created_at"],
            datetime.fromtimestamp(1750000000, timezone.utc).isoformat(),
        )
        self.assertEqual(fiche["engagement"]["vues"]["valeur"], 1250)
        self.assertEqual(fiche["engagement"]["favoris"]["valeur"], 7)
        self.assertEqual(
            fiche["url"],
            f"https://www.tiktok.com/@lemondefr/video/{IDENTIFIANT}",
        )

    def test_diaporama_sans_marqueur_explicitement_rejete(self):
        """Ne pas introduire d'images dans le corpus des vidéos."""
        element = publication()
        element.pop("isSlideshow")
        element["slideshowImageLinks"] = [{"tiktokLink": "https://exemple.invalid/photo"}]
        self.assertFalse(normaliser_publications([element], "lemondefr", 5))

    def test_dataset_avec_erreurs_distantes_sans_videos(self):
        """Distinguer un dataset d'erreurs d'un profil simplement vide."""
        appels = []

        def ouvrir(requete, timeout):
            chemin = requete.full_url
            appels.append(chemin)
            if "/acts/" in chemin:
                return ReponseSimulee({"data": {
                    "id": "abcde12345", "status": "SUCCEEDED",
                    "defaultDatasetId": "ds12345678",
                }}, 201)
            if "/datasets/" in chemin:
                return ReponseSimulee([
                    {"error": "TikTok a refusé ce profil", "errorCode": "PROFILE_ERROR"},
                ])
            raise AssertionError("Requête distante inattendue")

        client = PresseApify(SimpleNamespace(limit=3),
                            cle="JETON_TEST_PRIVE", ouvrir_url=ouvrir)
        rapport = {}
        with self.assertRaises(ErreurApify) as contexte:
            client.decouvrir("lemondefr", rapport)
        self.assertEqual(contexte.exception.code, "apify_resultats_erreur")
        self.assertEqual(rapport["diagnostic"]["code"], "apify_resultats_erreur")
        self.assertEqual(rapport["discovered_urls"], [])
        self.assertEqual(len(appels), 2)
        client.fermer()


if __name__ == "__main__":
    unittest.main()
