"""Régressions simulées : aucun accès TikTok, aucun véritable navigateur."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from selenium.common.exceptions import InvalidSessionIdException

import webapp as web
import webapp as serveur
from collecte.authentification import CONNEXION_OUVERTE_JS, detruire_session
from collecte.comptes import collecter_compte
from collecte.recherche_comptes import LIENS_RECHERCHE_JS


class Authentification(unittest.TestCase):
    def creer_job(self, **options):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        valeurs = dict(source_collecte="comptes", comptes=["media"], se_connecter_tiktok=True)
        valeurs.update(options)
        return web.Job("proprietaire", web.StartRequest(**valeurs), Path(dossier.name))

    def test_anonyme_par_defaut_et_hashtags_jamais_connectes(self):
        self.assertFalse(web.StartRequest(source_collecte="comptes", comptes=["media"]).se_connecter_tiktok)
        self.assertFalse(web.StartRequest(hashtag="test", se_connecter_tiktok=True).se_connecter_tiktok)
        for valeur in (True, False):
            with patch.object(web.scraper, "collect_links", return_value=[]) as collecte:
                collecter_compte(Mock(), Mock(), "media", sans_connexion=valeur)
            self.assertIs(collecte.call_args.kwargs["sans_connexion"], valeur)

    def test_meme_navigateur_pour_connexion_comptes_videos_et_commentaires(self):
        job = self.creer_job(comptes=["media", "presse"], collecter_commentaires=True, limit=7)
        navigateur = Mock()
        navigateur.get_cookies.return_value = [{"value": "SECRET_INTERDIT_EXPORT"}]
        profils, navigateurs = [], []
        def creer(arguments):
            profils.append(arguments.profile_dir)
            self.assertTrue(arguments.profile_dir.is_dir())
            self.assertNotIn(job.directory, arguments.profile_dir.parents)
            return navigateur
        def decouvrir(pilote, arguments, compte, rapport, **options):
            navigateurs.append(pilote)
            self.assertFalse(options["sans_connexion"])
            urls = [f"https://www.tiktok.com/@{compte}/video/{(100 if compte == 'media' else 200)+i}" for i in range(7)]
            rapport.update(discovered_urls=urls, collecte_partielle=False, objectif_atteint=True)
            return urls
        def lire(pilote, url, arguments, **options):
            navigateurs.append(pilote)
            self.assertTrue(options["authentification"])
            self.assertFalse(options["sans_connexion"])
            identifiant, canonique, auteur = web.scraper.canonical_post(url)
            return {"id": identifiant, "url": canonique, "author": auteur, "description": "Texte conservé",
                    "engagement": {"likes": {"valeur": 12}}}
        def commentaires(pilote, *args, **options):
            navigateurs.append(pilote)
            return {"commentaires": [], "statut": "partiel", "exhaustif": False}
        with patch("collecte.comptes.collecter_compte", side_effect=decouvrir), \
             patch.object(web.scraper, "read_post", side_effect=lire), patch.object(job, "pause"), \
             patch("collecte.commentaires.collecter_commentaires", side_effect=commentaires), \
             patch.object(web, "wait_for_user") as intervention:
            fabrique = Mock(side_effect=creer)
            web.execute_job(job, driver_factory=fabrique)
        fabrique.assert_called_once()
        intervention.assert_called_once()
        navigateur.get.assert_called_once_with("https://www.tiktok.com/login")
        navigateur.quit.assert_called_once()
        navigateur.get_cookies.assert_not_called()
        self.assertTrue(all(pilote is navigateur for pilote in navigateurs))
        self.assertFalse(profils[0].exists())
        self.assertEqual(job.etat_connexion, "fermee")
        self.assertEqual(job.exportees, 14)
        self.assertTrue(job.archive_prete)
        with ZipFile(job.directory / "archive.zip") as archive:
            for nom in archive.namelist():
                self.assertNotIn("cookie", nom.lower())
                self.assertNotIn(b"SECRET_INTERDIT_EXPORT", archive.read(nom))
        self.assertNotIn("SECRET_INTERDIT_EXPORT", json.dumps(job.snapshot()))

    def test_arret_pendant_connexion_detruit_la_session(self):
        job, navigateur = self.creer_job(), Mock()
        def arreter(*arguments):
            job.deconnexion_demandee.set()
            job.stop.set()
            job.check()
        with patch.object(web, "wait_for_user", side_effect=arreter), \
             patch("collecte.comptes.collecter_compte") as collecte:
            web.execute_job(job, driver_factory=lambda arguments: navigateur)
        collecte.assert_not_called()
        navigateur.quit.assert_called_once()
        self.assertEqual(job.status, "stopped")
        self.assertEqual(job.etat_connexion, "fermee")

    def test_erreur_ouverture_nettoie_le_profil_sans_journaliser_erreur_brute(self):
        job, profils = self.creer_job(), []
        def echouer(arguments):
            profils.append(arguments.profile_dir)
            raise InvalidSessionIdException("SECRET_INTERDIT_EXPORT")
        web.execute_job(job, driver_factory=echouer)
        self.assertFalse(profils[0].exists())
        self.assertIn({"code": "erreur_session", "exception": "InvalidSessionIdException"}, job.diagnostics)
        self.assertNotIn("SECRET_INTERDIT_EXPORT", json.dumps(job.snapshot()))

    def test_connexion_ne_se_ferme_pas_au_clic_continuer(self):
        job, navigateur = self.creer_job(), Mock()
        navigateur.get_screenshot_as_png.return_value = b"qr-temporaire"
        ouvert = {"valeur": True}
        def script(code):
            if code == CONNEXION_OUVERTE_JS: return ouvert["valeur"]
            return False
        navigateur.execute_script.side_effect = script
        job.commands.put("continue")
        job.commands.put(web.BrowserAction(kind="key", key="Tab"))
        job.commands.put("continue")
        def confirmer(*arguments):
            self.assertEqual(job.type_intervention, "connexion")
            self.assertIn("connexion", job.action_error)
            ouvert["valeur"] = False
        with patch.object(web, "perform_action", side_effect=confirmer), patch.object(web, "release_pointer"), \
             patch.object(web.scraper, "fermer_invitation_connexion") as fermer:
            web.wait_for_user(navigateur, job, "Connexion demandée")
        fermer.assert_not_called()
        self.assertEqual(job.etat_connexion, "confirmee_utilisateur")
        self.assertEqual(job.frame, b"")
        self.assertTrue(job.commands.empty())

    def test_nettoyage_continue_meme_si_cookies_et_fermeture_echouent(self):
        navigateur, profil = Mock(), Mock()
        navigateur.execute_cdp_cmd.side_effect = web.scraper.WebDriverException()
        navigateur.delete_all_cookies.side_effect = web.scraper.WebDriverException()
        navigateur.quit.side_effect = web.scraper.WebDriverException()
        self.assertFalse(detruire_session(navigateur, profil))
        profil.cleanup.assert_called_once()

    def test_navigateur_prive_et_fermeture_si_configuration_echoue(self):
        arguments = SimpleNamespace(driver=None, headless=True, profile_dir=None, chrome_binary=None,
                                    timeout=20, se_connecter_tiktok=True)
        navigateur = Mock()
        navigateur.set_page_load_timeout.side_effect = web.scraper.WebDriverException()
        with patch.object(web.scraper.webdriver, "Chrome", return_value=navigateur) as chrome:
            with self.assertRaises(web.scraper.WebDriverException):
                web.scraper.create_driver(arguments)
        options = chrome.call_args.kwargs["options"]
        self.assertIn("--incognito", options.arguments)
        self.assertFalse(options.experimental_options["prefs"]["profile.password_manager_enabled"])
        navigateur.quit.assert_called_once()

    def test_captcha_puis_connexion_et_plus_de_six_videos(self):
        navigateur = Mock()
        etat = {"captcha": True, "connexion": True, "page": 0}
        navigateur.current_url = "https://www.tiktok.com/search/video?q=%40media"
        def script(code, *arguments):
            if code == web.scraper.TYPE_INTERVENTION_JS: return "captcha" if etat["captcha"] else ""
            if code == CONNEXION_OUVERTE_JS: return etat["connexion"]
            if code == LIENS_RECHERCHE_JS:
                return [f"https://www.tiktok.com/@media/video/{i}" for i in range(100, 106 + 6 * etat["page"])]
            if code == web.scraper.DONNEES_PUBLICATIONS_JS: return []
            return False
        navigateur.execute_script.side_effect = script
        interventions = []
        def intervenir(message):
            interventions.append(message)
            if etat["captcha"]: etat["captcha"] = False
            else: etat["connexion"] = False
        def defiler(*arguments, **options):
            etat["page"] += 1
            return {"avant": {}, "apres": {}}
        observation = Mock()
        observation.lire.return_value = []
        arguments = SimpleNamespace(limit=12, timeout=.01, delay=0, max_scrolls=4, idle_rounds=3, interactive=True)
        rapport = {}
        with patch("collecte.recherche_comptes.ObservationRecherche", return_value=observation), \
             patch("collecte.recherche_comptes.defiler_resultats", side_effect=defiler), \
             patch.object(web.scraper, "fermer_invitation_connexion") as fermer:
            liens = collecter_compte(navigateur, arguments, "media", rapport, sans_connexion=False, interact=intervenir)
        self.assertEqual(len(liens), 12)
        self.assertEqual(len(interventions), 2)
        fermer.assert_not_called()
        self.assertFalse(rapport["exhaustif"])
        observation.fermer.assert_called_once()

    def test_session_perdue_et_erreur_extraction_distinguees(self):
        for erreur, code in [(InvalidSessionIdException("perdue"), "erreur_session"),
                             (web.scraper.TimeoutException("légende absente"), "erreur_extraction_video")]:
            job, navigateur = self.creer_job(), Mock()
            with patch.object(web, "wait_for_user"), patch.object(job, "pause"), \
                 patch("collecte.comptes.collecter_compte", return_value=["https://www.tiktok.com/@media/video/123"]), \
                 patch.object(web.scraper, "read_post", side_effect=erreur):
                web.execute_job(job, driver_factory=lambda arguments: navigateur)
            self.assertIn(code, [d["code"] for d in job.diagnostics])
            self.assertEqual(job.etat_connexion, "fermee")
            navigateur.quit.assert_called_once()

    def test_reconnexion_pendant_lecture_reprend_la_video_dans_le_meme_navigateur(self):
        navigateur, ouverte = Mock(), {"valeur": True}
        url = "https://www.tiktok.com/@media/video/123"
        def ouvrir(adresse): navigateur.current_url = adresse
        navigateur.get.side_effect = ouvrir
        navigateur.execute_script.side_effect = lambda code: ouverte["valeur"] if code == CONNEXION_OUVERTE_JS else False
        def confirmer(message):
            ouverte["valeur"] = False
            navigateur.current_url = "https://www.tiktok.com/"
        arguments = SimpleNamespace(timeout=.01, interactive=True)
        with patch.object(web.scraper, "extract_record", return_value={"id": "123"}), \
             patch.object(web.scraper, "fermer_invitation_connexion") as fermer:
            resultat = web.scraper.read_post(navigateur, url, arguments, authentification=True, interact=confirmer)
        self.assertEqual(resultat["id"], "123")
        self.assertEqual([appel.args[0] for appel in navigateur.get.call_args_list], [url, url])
        fermer.assert_not_called()


class RoutesAuthentification(unittest.TestCase):
    def test_refus_saisie_secrete_et_deconnexion_reservee_au_proprietaire(self):
        def attendre(job):
            job.update(status="attention")
            job.stop.wait(5)
            job.update(status="stopped", busy=False, finished=time.monotonic())
        with tempfile.TemporaryDirectory() as dossier:
            manager = web.Manager(data_dir=dossier, runner=attendre, max_jobs=1)
            application = serveur.create_app(manager)
            with TestClient(application) as client:
                client.get("/")
                reponse = client.post("/api/jobs", headers={"X-ScrapTikTok": "1"}, json={
                    "source_collecte": "comptes", "comptes": ["media"], "se_connecter_tiktok": True})
                self.assertEqual(reponse.status_code, 202)
                identifiant = reponse.json()["id"]
                url = "/api/jobs/" + identifiant
                reponse = client.post(url+"/action", headers={"X-ScrapTikTok": "1"},
                                      json={"kind": "text", "text": "SECRET_INTERDIT_EXPORT"})
                self.assertEqual(reponse.status_code, 422)
                self.assertNotIn("SECRET_INTERDIT_EXPORT", reponse.text)
                self.assertTrue(manager.jobs[identifiant].commands.empty())
                autre = TestClient(application)
                autre.get("/")
                self.assertEqual(autre.post(url+"/deconnexion", headers={"X-ScrapTikTok": "1"}).status_code, 404)
                autre.close()
                self.assertEqual(client.post(url+"/deconnexion", headers={"X-ScrapTikTok": "1"}).status_code, 202)
                self.assertTrue(manager.jobs[identifiant].stop.is_set())
                self.assertTrue(manager.jobs[identifiant].deconnexion_demandee.is_set())
