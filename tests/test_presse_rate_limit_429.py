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
        self.assertEqual(rapport["urls_embed_non_verifiees"], 3)
        self.assertEqual(rapport["discovered_urls"], [])

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

    def test_urls_embed_non_verifiees_ecartees_sans_nouvel_appel_429(self):
        """Aucun faux résultat sauvegardé, aucun appel de repli TikTok."""
        adresse = "https://www.tiktok.com/@lemondefr/video/7000000000000000001"
        rapport = {}

        def simuler_collecte(compte, limite, etat, **options):
            etat["discovered_urls"] = [adresse]
            etat["urls_embed_non_verifiees"] = 1
            etat["etape_api"] = "identification_video"
            etat["requetes_tentees"] = 2
            raise PresseRateLimitError()

        with (
            patch("collecte.presse_api.collecter_videos_presse_api",
                  side_effect=simuler_collecte),
            patch("collecte.profil_selenium.collecter_grille_profil") as grille,
        ):
            with self.assertRaises(PresseRateLimitError):
                collecter_compte(
                    Mock(), SimpleNamespace(limit=50), "lemondefr", rapport,
                    presse_videos_uniquement=True, presse_moteur="api",
                )
        grille.assert_not_called()
        self.assertEqual(rapport["discovered_urls"], [])
        self.assertEqual(rapport["recherches_compte"][0]["discovered_urls"], [])
        self.assertEqual(rapport["recherches_compte"][0]["urls_embed_non_verifiees"], 1)
        self.assertEqual(
            rapport["recherches_compte"][0]["diagnostic"]["code"],
            "tiktok_limitation_429",
        )

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
        self.assertIn("Accès API Presse refusé par TikTok (HTTP 429)",
                      job.snapshot()["bilan_sources"][0]["message"])
        self.assertNotIn("Aucun lien de publication lisible",
                         job.snapshot()["bilan_sources"][0]["message"])


    def test_plusieurs_medias_compte_requetes_par_source(self):
        """Deux appels sur le deuxième média ne signifient pas deux au total."""
        medias = charger_inventaire()[:2]
        comptes = [m["compte"] for m in medias]

        class ConnexionDeuxMedias:
            def __init__(self, *args, **kwargs):
                pass

            def preparer_sources(self, settings):
                return [{"id": m["id"], "compte": m["compte"]} for m in medias]

            def ouvrir(self):
                return Mock()

            def decouvrir(self, source, rapport, *, contexte="", progression=None):
                if source["compte"] == comptes[0]:
                    rapport["recherches_compte"] = [{
                        "compte_attendu": comptes[0],
                        "requetes_tentees": 21,
                        "pages_api": 19,
                        "discovered_urls": [],
                    }]
                    return []
                rapport["recherches_compte"] = [{
                    "compte_attendu": comptes[1],
                    "requetes_tentees": 2,
                    "pages_api": 0,
                    "diagnostic": {
                        "code": "tiktok_limitation_429",
                        "etape_api": "identification_video",
                        "requetes_tentees": 2,
                        "pages_api": 0,
                    },
                }]
                raise PresseRateLimitError()

            def fermer(self):
                pass

        with tempfile.TemporaryDirectory() as repertoire:
            job = Job(
                "a" * 64,
                StartRequest(source_collecte="presse", medias=[m["id"] for m in medias]),
                Path(repertoire),
            )
            job.base = None
            with (
                patch("connect_presse.ConnexionPresse", ConnexionDeuxMedias),
                patch.object(job, "save"),
                patch.object(job, "sauvegarder_historique"),
            ):
                execute_job(job)
            donnees = job.snapshot()["bilan_sources"]
            self.assertEqual(len(donnees), 2)
            self.assertEqual(donnees[0]["recherches"][0]["requetes_tentees"], 21)
            self.assertEqual(donnees[1]["recherches"][0]["requetes_tentees"], 2)
            self.assertEqual(sum(
                r["requetes_tentees"]
                for source in donnees for r in source["recherches"]
            ), 23)
            self.assertIn("HTTP 429", job.message)

    def test_429_ne_sauvegarde_pas_les_urls_incompletes_en_archive_vide(self):
        """Une collecte refusée ne crée ni faux corpus ni archive vide."""
        from analyse_desordre.sources import inventaire_sources, lire_publications

        media = charger_inventaire()[0]
        adresses = [
            f'https://www.tiktok.com/@{media["compte"]}/video/{7000000000000000000+i}'
            for i in range(1, 11)
        ]
        class Connexion429Partielle:
            def __init__(self, *args, **kwargs):
                pass

            def preparer_sources(self, settings):
                return [{"id": media["id"], "compte": media["compte"]}]

            def ouvrir(self):
                return Mock()

            def decouvrir(self, source, rapport, *, contexte="", progression=None):
                rapport["discovered_urls"] = list(adresses)
                rapport["recherches_compte"] = [{
                    "requete_recherche": "liste vidéos du média",
                    "compte_attendu": media["compte"],
                    "navigation_publications": "api_liste_createur",
                    "discovered_urls": list(adresses),
                    "urls_embed_non_verifiees": 10,
                    "pages_api": 0,
                    "candidats_examines": 0,
                    "diagnostic": {
                        "code": "tiktok_limitation_429",
                        "etape_api": "identification_video",
                        "requetes_tentees": 2,
                        "pages_api": 0,
                    },
                }]
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
            self.assertEqual(job.status, "failed")
            self.assertFalse(job.archive_prete, job.message)
            self.assertFalse((job.directory / "archive.zip").exists())
            self.assertFalse((job.directory / "sources_visuelles.json").exists())
            self.assertFalse((job.directory / "publications.json").exists())
            self.assertFalse(job.path.exists())
            self.assertEqual(lire_publications(job.directory), [])
            self.assertEqual(inventaire_sources(job.directory)["mp4_telechargeables"], 0)
            self.assertEqual(len(job.records), 0)
            bilan = job.snapshot()["bilan_sources"][0]["recherches"][0]
            self.assertEqual(bilan["urls_embed_non_verifiees"], 10)
            self.assertNotIn("urls_embed_references", bilan)
            self.assertEqual(bilan["liens"], 0)
            self.assertEqual(bilan["pages_api"], 0)
            self.assertEqual(bilan["candidats_examines"], 0)
            self.assertFalse(job.busy)


    def test_429_apres_media_complet_archive_uniquement_donnees_validees(self):
        """Un média terminé reste exporté, le média interrompu est exclu."""
        from analyse_desordre.sources import inventaire_sources, lire_publications

        medias = charger_inventaire()[:2]
        premier, bloque = medias[0]["compte"], medias[1]["compte"]
        identifiant = "7000000000000000001"
        url_valide = f"https://www.tiktok.com/@{premier}/video/{identifiant}"
        url_refusee = f"https://www.tiktok.com/@{bloque}/video/7000000000000000002"
        appels = []

        class ConnexionDeuxMedias:
            def __init__(self, *args, **kwargs):
                pass

            def preparer_sources(self, settings):
                return [{"id":m["id"],"compte":m["compte"]} for m in medias]

            def ouvrir(self):
                return Mock()

            def decouvrir(self, source, rapport, *, contexte="", progression=None):
                compte = source["compte"]
                appels.append(compte)
                if compte == premier:
                    rapport["discovered_urls"] = [url_valide]
                    rapport["metadonnees_api"] = {
                        identifiant: {
                            "id":identifiant,"url":url_valide,"author":premier,
                            "description":"Manifestation", "hashtags":[],
                            "created_at":"2026-01-01T10:00:00+00:00",
                            "engagement":{"likes":{"valeur":8,"brut":"8"}},
                        }
                    }
                    return [url_valide]
                rapport["discovered_urls"] = [url_refusee]
                rapport["recherches_compte"] = [{
                    "discovered_urls":[url_refusee],
                    "urls_embed_non_verifiees":1,
                    "diagnostic":{"code":"tiktok_limitation_429"}
                }]
                raise PresseRateLimitError()

            def lire_publication(self, url):
                raise AssertionError("Aucun accès Selenium après découverte")

            def fermer(self):
                pass

        with tempfile.TemporaryDirectory() as dossier:
            job = Job("a"*64,StartRequest(
                source_collecte="presse",medias=[m["id"] for m in medias],
                limit=1,
            ),Path(dossier))
            with (patch("connect_presse.ConnexionPresse",ConnexionDeuxMedias),
                  patch.object(job,"pause",return_value=None)):
                execute_job(job)
            self.assertEqual(appels,[premier,bloque])
            self.assertEqual(job.status,"partial",job.message)
            self.assertTrue(job.archive_prete,job.message)
            self.assertEqual([p["url"] for p in job.publications],[url_valide])
            self.assertEqual([p["url"] for p in lire_publications(job.directory)],
                             [url_valide])
            self.assertEqual(inventaire_sources(job.directory)["publications_collectees"],1)
            self.assertEqual(job.records[0]["engagement"]["likes"]["valeur"],8)
            self.assertTrue((job.directory/"archive.zip").exists())
            self.assertFalse((job.directory/"sources_visuelles.json").exists())
            self.assertNotIn(url_refusee, (job.directory/"journal.json").read_text())
            bilan=job.snapshot()["bilan_sources"]
            self.assertEqual(bilan[1]["liens"],0)
            self.assertEqual(bilan[1]["recherches"][0]["liens"],0)

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
