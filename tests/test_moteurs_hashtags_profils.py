"""Tests des moteurs Hashtags et Profils, sans appels externes facturables."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from webapp import StartRequest
from connect_profil import ConnexionProfil
from connect_htag import ConnexionHashtag
from collecte.presse_research import collecter_videos_presse_research


class TestsMoteursHashtagsProfils(unittest.TestCase):
    def test_choix_independants_et_compatibilite(self):
        configuration = StartRequest(
            source_collecte="comptes", comptes=["lemondefr"],
            hashtag="manifestation", profil_moteur="gallerydl",
            hashtag_moteur="navigateur", presse_moteur="api")
        self.assertEqual(configuration.moteur_actif, "gallerydl")
        self.assertEqual(configuration.hashtag_moteur, "navigateur")
        ancien = StartRequest(source_collecte="hashtags", hashtag="manifestation")
        self.assertEqual(ancien.moteur_actif, "navigateur")
        self.assertEqual(StartRequest(
            source_collecte="presse", medias=["lemonde"]).moteur_actif, "api")

    def test_tikhub_exige_la_cle_sur_un_profil(self):
        with patch.dict("os.environ", {"TIKHUB_API_KEY": ""}):
            with self.assertRaisesRegex(Exception, "TikHub"):
                StartRequest(source_collecte="comptes", comptes=["lemondefr"],
                             hashtag="manifestation", profil_moteur="tikhub")
        requete = StartRequest(source_collecte="hashtags",
                               hashtag="manifestation", hashtag_moteur="tikhub",
                               tikhub_api_key="JETON_TEST")
        self.assertNotIn("JETON_TEST", str(requete))
        self.assertNotIn("tikhub_api_key", requete.model_dump())

    def test_profil_tikhub_ne_change_pas_le_compte_selectionne(self):
        parametres = StartRequest(source_collecte="comptes", comptes=["lemondefr"],
                                  hashtag="manifestation", profil_moteur="tikhub",
                                  tikhub_api_key="JETON_TEST")
        connexion = ConnexionProfil(SimpleNamespace(limit=2), fabrique=Mock())
        comptes = connexion.preparer_sources(parametres)
        connexion.tikhub_client = Mock()
        retour = ["https://www.tiktok.com/@lemondefr/video/7702367667616746785"]
        connexion.tikhub_client.decouvrir.return_value = retour
        rapport = {}
        self.assertEqual(connexion.decouvrir(comptes[0], rapport), retour)
        connexion.tikhub_client.decouvrir.assert_called_once()
        self.assertEqual(rapport["connexion"]["api"], "TikHub")
        with self.assertRaises(ValueError):
            connexion.decouvrir({"compte": "autrecompte"}, {})
        connexion.fermer()

    def test_research_recherche_vraiment_hashtag_et_auteur_reel(self):
        corps = []
        def demander(url, *, data, headers):
            corps.append(json.loads(data))
            return {"data": {"videos": [{
                "id": "7702367667616746785", "username": "lemondefr",
                "video_description": "Manifestation #manifestation",
                "hashtag_names": ["manifestation"],
                "create_time": 1750000000,
                "view_count": 1234,
            }], "has_more": False}}
        rapport = {}
        liens = collecter_videos_presse_research(
            None, 2, rapport, hashtag="manifestation", jeton="JETON_SIMULE",
            requete=demander, pause=lambda _: None)
        self.assertEqual(len(corps), 1)
        self.assertEqual(corps[0]["query"]["and"][0]["field_name"], "hashtag_name")
        self.assertEqual(liens, [
            "https://www.tiktok.com/@lemondefr/video/7702367667616746785"])
        self.assertEqual(rapport["metadonnees_api"]["7702367667616746785"]["author"], "lemondefr")

    def test_hashtags_hybrides_conservent_l_origine(self):
        parametres = StartRequest(source_collecte="hashtags",
                                  hashtag="manifestation", hashtag_moteur="gallerydl")
        connexion = ConnexionHashtag(SimpleNamespace(limit=2), fabrique=Mock())
        sources = connexion.preparer_sources(parametres)
        self.assertEqual(len(sources), 1)
        connexion.gallerydl_client = Mock()
        identifiant = "7702367667616746785"
        url = f"https://www.tiktok.com/@lemondefr/video/{identifiant}"
        def decouvrir(compte, rapport):
            rapport["metadonnees_api"] = {identifiant: {
                "id": identifiant, "url": url, "author": compte,
                "description": "#manifestation", "source": "gallerydl_createur"}}
        connexion.gallerydl_client.decouvrir.side_effect = decouvrir
        fiche = connexion.lire_publication(url)
        self.assertEqual(fiche["source"], "gallerydl_createur")
        self.assertEqual(connexion._cache_profils, {"lemondefr"})
        connexion.gallerydl_client.decouvrir.assert_called_once()
        connexion.fermer()


if __name__ == "__main__":
    unittest.main()
