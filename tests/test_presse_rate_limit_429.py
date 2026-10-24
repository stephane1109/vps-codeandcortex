"""429 TikTok : arrêter sans réessayer les embeds ni les autres médias du lot."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from collecte.presse_api import (
    PresseRateLimitError, _obtenir, collecter_videos_presse_api,
)
from collecte.comptes import collecter_compte
from collecte.presse import charger_inventaire
from webapp import Job, StartRequest, execute_job


class Reponse:
    def __init__(self, value):
        self.value=value
    def read(self, n):
        return self.value[:n]
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def profil_sans_secuid():
    import json
    page={"source":{"data":{"/embed/@lemondefr":{
        "userInfo":{"uniqueId":"lemondefr","privateAccount":False},
        "videoList":[{"id":"7000000000000000001"},
                     {"id":"7000000000000000002"},
                     {"id":"7000000000000000003"}],
    }}}}
    return ('<script id="__FRONTITY_CONNECT_STATE__">'
            +json.dumps(page)+'</script>').encode()


class LimitationPresseTests(unittest.TestCase):
    def test_429_traduit_en_limitation_avec_retry_after(self):
        client=Mock()
        client.open.side_effect=HTTPError("https://www.tiktok.com/embed/v2/1",
                  429,"Too Many Requests",{"Retry-After":"180"},None)
        with self.assertRaises(PresseRateLimitError) as resultat:
            _obtenir(client,"https://www.tiktok.com/embed/v2/1")
        self.assertIn("HTTP 429",str(resultat.exception))
        self.assertEqual(resultat.exception.retry_after,180)
        self.assertNotIn("secUid introuvable",str(resultat.exception))
        self.assertIsNone(PresseRateLimitError("invalid").retry_after)

    def test_arret_des_le_premier_embed_video_en_429(self):
        client=Mock()
        demandes=[]
        def demander(request,timeout=20):
            demandes.append(request.full_url)
            if "/embed/@" in request.full_url:
                return Reponse(profil_sans_secuid())
            raise HTTPError(request.full_url,429,"Too Many",
                            {"Retry-After":"120"},None)
        client.open.side_effect=demander
        rapport={}
        with self.assertRaises(PresseRateLimitError) as resultat:
            collecter_videos_presse_api("lemondefr",50,rapport,
                                        client=client,pause=lambda _:None)
        self.assertEqual(resultat.exception.retry_after,120)
        self.assertEqual(rapport["tentatives_embed_video"],1)
        self.assertEqual(len(demandes),2)
        self.assertTrue(demandes[1].endswith("/embed/v2/7000000000000000001"))
        self.assertEqual(rapport["pages_api"],0)
        self.assertEqual(rapport["etape_api"],"identification_video")
        self.assertEqual(rapport["requetes_tentees"],2)

    def test_429_sur_la_premiere_requete_identifie_le_blocage_initial(self):
        client = Mock()
        client.open.side_effect = HTTPError(
            "https://www.tiktok.com/embed/@lemondefr",
            429, "Too Many Requests", {}, None,
        )
        rapport = {}
        with self.assertRaises(PresseRateLimitError):
            collecter_videos_presse_api("lemondefr", 300, rapport,
                                       client=client, pause=lambda _: None)
        self.assertEqual(client.open.call_count, 1)
        self.assertEqual(rapport["etape_api"], "identification_media")
        self.assertEqual(rapport["requetes_tentees"], 1)
        self.assertEqual(rapport["pages_api"], 0)
        self.assertEqual(rapport["discovered_urls"], [])

    def test_un_seul_moteur_et_diagnostic_429(self):
        rapport={}
        with patch("collecte.presse_api.collecter_videos_presse_api",
                   side_effect=PresseRateLimitError(50)), \
             patch("collecte.profil_selenium.collecter_grille_profil") as grille:
            with self.assertRaises(PresseRateLimitError):
                collecter_compte(Mock(),SimpleNamespace(limit=50),
                                 "lemondefr",rapport,
                                 presse_videos_uniquement=True,presse_moteur="api")
        self.assertEqual(rapport["recherches_compte"][0]["diagnostic"]["code"],
                         "tiktok_limitation_429")
        self.assertEqual(rapport["recherches_compte"][0]["diagnostic"]["retry_after_seconds"],50)
        self.assertEqual(len(rapport["recherches_compte"]),1)
        grille.assert_not_called()

    def test_le_lot_de_quatre_medias_ne_continue_pas_apres_429(self):
        medias=charger_inventaire()[:4]
        self.assertEqual(len(medias),4)
        appels=[]
        class ConnexionSimulee:
            def __init__(self,*args,**kwargs):
                pass
            def preparer_sources(self,settings):
                return [{"id":m["id"],"compte":m["compte"]} for m in medias]
            def ouvrir(self):
                return Mock()
            def decouvrir(self,source,rapport,*,contexte="",progression=None):
                appels.append(source["compte"])
                rapport.update(recherches_compte=[{
                    "requete_recherche":"api",
                    "diagnostic":{"code":"tiktok_limitation_429",
                                  "detail":"TikTok HTTP 429"}}])
                raise PresseRateLimitError(90)
            def fermer(self):
                pass

        with tempfile.TemporaryDirectory() as repertoire:
            job=Job("a"*64,StartRequest(source_collecte="presse",
                      medias=[m["id"] for m in medias]),
                    Path(repertoire))
            job.base=None
            with patch("connect_presse.ConnexionPresse",ConnexionSimulee), \
                 patch.object(job,"save"), \
                 patch.object(job,"sauvegarder_historique"):
                execute_job(job)
        self.assertEqual(appels,[medias[0]["compte"]])
        self.assertEqual(job.status,"failed")
        self.assertIn("HTTP 429",job.message)
        self.assertIn("autres médias",job.message)
        self.assertEqual(job.search_errors,1)


    def test_429_conserve_les_urls_deja_decouvertes_pour_multimodale(self):
        """Une pagination interrompue ne doit pas perdre les vidéos déjà vues."""
        from analyse_desordre.sources import inventaire_sources, lire_publications

        media = charger_inventaire()[0]
        adresse = f'https://www.tiktok.com/@{media["compte"]}/video/7000000000000000001'

        class Connexion429Partielle:
            def __init__(self, *args, **kwargs):
                pass

            def preparer_sources(self, settings):
                return [{"id": media["id"], "compte": media["compte"]}]

            def ouvrir(self):
                return Mock()

            def decouvrir(self, source, rapport, *, contexte="", progression=None):
                rapport["discovered_urls"] = [adresse]
                raise PresseRateLimitError(180)

            def lire_publication(self, adresse):
                raise AssertionError("Aucune lecture supplémentaire après HTTP 429")

            def fermer(self):
                pass

        with tempfile.TemporaryDirectory() as dossier:
            job = Job("a" * 64, StartRequest(
                source_collecte="presse", medias=[media["id"]],
                telecharger_mp4=True,
            ), Path(dossier))
            with (
                patch("connect_presse.ConnexionPresse", Connexion429Partielle),
                patch("webapp.telecharger_mp4_collecte") as telecharger,
            ):
                execute_job(job)
            telecharger.assert_not_called()
            self.assertEqual(job.status, "partial")
            self.assertTrue(job.archive_prete, job.message)
            self.assertEqual(lire_publications(job.directory)[0]["url"], adresse)
            self.assertEqual(inventaire_sources(job.directory)["mp4_telechargeables"], 1)

    def test_429_interrompt_aussi_les_mp4_pendant_la_finalisation(self):
        """Même si des textes existent, 429 ne doit plus déclencher yt-dlp."""
        media = charger_inventaire()[0]

        class Connexion429:
            def __init__(self, *args, **kwargs):
                pass

            def preparer_sources(self, settings):
                return [{"id": media["id"], "compte": media["compte"]}]

            def ouvrir(self):
                return Mock()

            def decouvrir(self, source, rapport, *, contexte="", progression=None):
                rapport["recherches_compte"] = [{
                    "diagnostic": {"code": "tiktok_limitation_429"}
                }]
                raise PresseRateLimitError(120)

            def fermer(self):
                pass

        with tempfile.TemporaryDirectory() as repertoire:
            job = Job(
                "a" * 64,
                StartRequest(source_collecte="presse", medias=[media["id"]],
                             telecharger_mp4=True),
                Path(repertoire),
            )
            job.base = None
            job.records.append({
                "id": "1234567890123456789",
                "author": media["compte"],
                "url": "https://www.tiktok.com/@compte/video/1234567890123456789",
                "description": "Déjà collecté",
            })
            with (
                patch("connect_presse.ConnexionPresse", Connexion429),
                patch.object(job, "save"),
                patch.object(job, "sauvegarder_historique"),
                patch("webapp.telecharger_mp4_collecte") as telecharger,
            ):
                execute_job(job)
            telecharger.assert_not_called()
            self.assertFalse(job.busy)
            self.assertEqual(job.status, "failed")
            self.assertIn("HTTP 429", job.message)


if __name__=="__main__":
    unittest.main()
