import tempfile
import csv
import io
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import webapp as web


RECORD = {"id": "123", "url": "https://www.tiktok.com/@test/video/123",
          "author": "test", "description": "Café 🍋\n#été"}
HEADERS = {"X-ScrapTikTok": "1"}


def waiting_runner(job):
    job.update(status="attention", frame=b"fake-png")
    job.stop.wait(5)
    job.update(status="stopped", busy=False, finished=time.monotonic())


class WebTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.manager = web.Manager(data_dir=self.directory.name, runner=waiting_runner, max_jobs=1)
        self.app = web.create_app(self.manager)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.client.get("/")

    def start(self, client=None):
        response = (client or self.client).post("/api/jobs", headers=HEADERS,
                                               json={"hashtag": "#été", "limit": 2})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()["id"]

    def test_french_filter_settings_persist_and_download_filename(self):
        response = self.client.post("/api/jobs", headers=HEADERS, json={"hashtag": "été", "french_only": True})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["french_only"])
        snapshot = self.client.get("/api/session").json()["job"]
        self.assertTrue(snapshot["french_only"])
        job = self.manager.jobs[snapshot["id"]]
        job.records.append(RECORD)
        job.save()
        response = self.client.get(f"/api/jobs/{job.id}/download")
        self.assertIn("_fr.txt", response.headers["content-disposition"])

    def test_option_entete_transmise_reprise_et_telechargee(self):
        response = self.client.post('/api/jobs', headers=HEADERS,
            json={'hashtag':'été', 'inclure_metadonnees_txt':True, 'include_sources':False})
        self.assertEqual(response.status_code, 202)
        reprise = self.client.get('/api/session').json()['job']
        self.assertTrue(reprise['inclure_metadonnees_txt'])
        job = self.manager.jobs[reprise['id']]
        job.records.append(dict(RECORD, created_at='2026-10-09T12:00:00+00:00'))
        job.save()
        fichier = self.client.get(f'/api/jobs/{job.id}/download')
        self.assertEqual(fichier.status_code, 200)
        self.assertIn('*date 2026-10-09T12:00:00+00:00\n*profil @test\n*urlvidéo '+RECORD['url'], fichier.text)
        self.assertIn(RECORD['description'], fichier.text)

    def test_validation_and_csrf_guard(self):
        self.assertEqual(self.client.post("/api/jobs", json={"hashtag": "test"}).status_code, 403)
        for payload in ({"hashtag": "test", "second_hashtag": "deux mots"}, {"hashtag": "test", "operator": "XOR"}, {"hashtag": "deux mots"}, {"hashtag": "test", "limit": 0}, {"hashtag": "test", "limit": 301}):
            response = self.client.post("/api/jobs", headers=HEADERS, json=payload)
            self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.manager.jobs), 0)

    def test_other_session_cannot_see_control_or_download(self):
        job_id = self.start()
        stranger = TestClient(self.app)
        self.addCleanup(stranger.close)
        stranger.get("/")
        self.assertIsNone(stranger.get("/api/session").json()["job"])
        for suffix in ("", "/frame", "/download"):
            self.assertEqual(stranger.get(f"/api/jobs/{job_id}{suffix}").status_code, 404)
        for suffix in ("stop", "continue"):
            self.assertEqual(stranger.post(f"/api/jobs/{job_id}/{suffix}", json={}, headers=HEADERS).status_code, 404)
        response = stranger.post(f"/api/jobs/{job_id}/action", headers=HEADERS,
                                 json={"kind": "click", "points": [{"x": 0.5, "y": 0.5}]})
        self.assertEqual(response.status_code, 404)

    def test_concurrency_limit_and_existing_job_survive_refresh(self):
        job_id = self.start()
        self.assertEqual(self.client.get("/api/session").json()["job"]["id"], job_id)
        self.assertEqual(self.client.post("/api/jobs", headers=HEADERS, json={"hashtag": "test"}).status_code, 409)
        stranger = TestClient(self.app)
        self.addCleanup(stranger.close)
        stranger.get("/")
        self.assertEqual(stranger.post("/api/jobs", headers=HEADERS, json={"hashtag": "test"}).status_code, 429)

    def test_utf8_text_download_and_stop_preserve_corpus(self):
        job_id = self.start()
        job = self.manager.jobs[job_id]
        with job.lock:
            job.records.append(RECORD)
        job.save()
        response = self.client.get(f"/api/jobs/{job_id}/download")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertIn("tiktok_%C3%A9t%C3%A9.txt", response.headers["content-disposition"])
        self.assertIn(RECORD["description"], response.content.decode("utf-8"))
        self.client.post(f"/api/jobs/{job_id}/stop", json={}, headers=HEADERS)
        job.thread.join(1)
        self.assertFalse(job.busy)
        self.assertEqual(self.client.get(f"/api/jobs/{job_id}/download").content, response.content)

    def test_browser_commands_require_attention_and_valid_coordinates(self):
        job_id = self.start()
        job = self.manager.jobs[job_id]
        self.assertEqual(self.client.post(f"/api/jobs/{job_id}/action", headers=HEADERS,
                         json={"kind": "click", "points": [{"x": 2, "y": 0}]}).status_code, 422)
        for kind in ("pointer_down", "pointer_move", "pointer_up"):
            self.assertEqual(self.client.post(f"/api/jobs/{job_id}/action", headers=HEADERS,
                             json={"kind": kind}).status_code, 422)
        job.update(status="collecting")
        self.assertEqual(self.client.post(f"/api/jobs/{job_id}/continue", headers=HEADERS, json={}).status_code, 409)

    def test_exports_compteurs_et_commentaires_prives_sans_perdre_zero_ou_inconnues(self):
        from collecte.engagement import extraire_engagement
        identifiant = self.start()
        job = self.manager.jobs[identifiant]
        publication = dict(RECORD, retenue=True, langue_detection='unknown',
            engagement=extraire_engagement({'stats': {'diggCount': 0, 'commentCount': 12, 'shareCount': '1.2K'}}))
        job.records.append(publication)
        job.commentaires.extend([
            {'publication_id': '123', 'auteur': 'lecteur', 'texte': 'Très bien !'},
            {'publication_id': '999', 'auteur': 'autre', 'texte': 'Commentaire hors sélection'},
        ])
        r = self.client.get(f'/api/jobs/{identifiant}/engagement.csv')
        self.assertEqual(r.status_code, 200)
        ligne = list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))[0]
        self.assertEqual(ligne['likes'], '0')
        self.assertEqual(ligne['vues'], '')
        self.assertEqual(ligne['commentaires'], '12')
        self.assertEqual(ligne['partages'], '1200')
        self.assertEqual(ligne['partages_brut'], '1.2K')
        self.assertEqual(ligne['partages_estime'], 'True')
        self.assertEqual(ligne['langue_detection'], 'unknown')
        self.assertEqual(ligne['legende'], RECORD['description'])
        self.assertEqual(job.snapshot()['apercu_engagement'][0]['engagement']['likes']['valeur'], 0)
        commentaires = self.client.get(f'/api/jobs/{identifiant}/commentaires.txt')
        self.assertEqual(commentaires.status_code, 200)
        self.assertIn('Très bien !', commentaires.text)
        self.assertNotIn('hors sélection', commentaires.text)
        with TestClient(self.app) as autre:
            autre.get('/')
            for fichier in ('engagement.csv', 'commentaires.txt'):
                self.assertEqual(autre.get(f'/api/jobs/{identifiant}/{fichier}').status_code, 404)

    def test_expiration_stops_abandoned_job_and_removes_finished_files(self):
        job_id = self.start()
        job = self.manager.jobs[job_id]
        job.last_seen -= self.manager.idle_timeout + 1
        self.manager.cleanup()
        job.thread.join(1)
        self.assertTrue(job.stop.is_set())
        job.finished -= self.manager.retention + 1
        self.manager.cleanup()
        self.assertNotIn(job_id, self.manager.jobs)
        self.assertFalse(job.directory.exists())

    def test_optional_access_password_protects_page_and_not_healthcheck(self):
        with patch.dict(web.os.environ, {"APP_ACCESS_PASSWORD": "test-password", "APP_ACCESS_USER": "test"}):
            self.assertEqual(self.client.get("/").status_code, 401)
            self.assertEqual(self.client.get("/healthz").status_code, 200)
            self.assertEqual(self.client.get("/", auth=("test", "test-password")).status_code, 200)
            self.assertEqual(self.client.get("/", headers={"Authorization": "Basic ??"}).status_code, 401)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.job = web.Job("test", web.StartRequest(hashtag="été", limit=2), Path(directory.name))

    def test_plain_text_has_no_sources_when_unchecked(self):
        self.assertEqual(web.text_export([RECORD], False), "Café 🍋\n#été\n")

    def test_entete_facultatif_par_post_sans_modifier_les_legendes(self):
        date = '2026-10-09T12:00:00+00:00'
        premiere = dict(RECORD, created_at=date)
        seconde = dict(RECORD, id='456', author='autre', url='https://www.tiktok.com/@autre/video/456', description='Oui !')
        attendu = (f"*date {date}\n*profil @test\n*urlvidéo {RECORD['url']}\n{RECORD['description']}\n\n"
                   f"*date indéterminée\n*profil @autre\n*urlvidéo {seconde['url']}\nOui !\n")
        for sources in (False, True):
            self.assertEqual(web.text_export([premiere, seconde], sources, True), attendu)
        self.assertEqual(web.text_export([premiere], True), f"@test\n{RECORD['url']}\n{RECORD['description']}\n")
        self.assertEqual(web.text_export([dict(premiere, description='')], True, True), '')

    def test_worker_exports_and_quits_browser(self):
        driver = Mock()
        with patch.object(web.scraper, "collect_links", return_value=[RECORD["url"]]), \
             patch.object(web.scraper, "read_post", return_value=RECORD), patch.object(self.job, "pause"):
            web.execute_job(self.job, driver_factory=lambda args: driver)
        self.assertEqual(self.job.status, "completed")
        self.assertIn("Café 🍋", self.job.path.read_text())
        driver.quit.assert_called_once()

    def test_cancellation_closes_browser_and_keeps_existing_text(self):
        self.job.records.append(RECORD)
        driver = Mock()
        with patch.object(web.scraper, "collect_links", side_effect=web.Stopped):
            web.execute_job(self.job, driver_factory=lambda args: driver)
        self.assertEqual(self.job.status, "stopped")
        self.assertIn(RECORD["description"], self.job.path.read_text())
        driver.quit.assert_called_once()

    def test_two_hashtags_filter_exact_words_unicode_and_case(self):
        settings = web.StartRequest(hashtag="#GRÈVE", second_hashtag="#école")
        self.assertTrue(web.matches_hashtags("#GRÈVE #école", settings))
        self.assertFalse(web.matches_hashtags("#grève #écolerie", settings))
        self.assertFalse(web.matches_hashtags("#grève et école", settings))
        settings.operator = "OR"
        self.assertTrue(web.matches_hashtags("#ÉCOLE", settings))
        self.assertFalse(web.matches_hashtags("#gréviste", settings))
        self.assertEqual(settings.filename, "tiktok_GRÈVE_OU_école.txt")

    def test_two_searches_deduplicate_and_export_only_matching_descriptions(self):
        urls = [f"https://www.tiktok.com/@test/video/{i}" for i in (111, 222, 333)]
        records = {url: dict(RECORD, id=str(i), url=url, description=caption) for i, url, caption in zip(
            (111, 222, 333), urls, ("#été #voyage", "#été", "#voyage"))}
        for operator, expected in (("AND", 1), ("OR", 3)):
            job = web.Job("test", web.StartRequest(hashtag="été", second_hashtag="voyage", operator=operator), self.job.directory)
            driver = Mock()
            with patch.object(web.scraper, "collect_links", side_effect=[urls[:2], urls[1:]]) as discover, \
                 patch.object(web.scraper, "read_post", side_effect=lambda d, url, *a, **k: records[url]) as read, \
                 patch.object(job, "pause"):
                web.execute_job(job, driver_factory=lambda args: driver)
            self.assertEqual(discover.call_count, 2)
            self.assertEqual(read.call_count, 3)
            self.assertEqual(len(job.records), expected)
            self.assertEqual(job.filtered, 3 - expected)
            self.assertEqual(job.processed, 3)
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.path.read_text().count("#été #voyage"), 1)

    def test_one_inaccessible_hashtag_preserves_partial_results(self):
        self.job.settings = web.StartRequest(hashtag="été", second_hashtag="voyage", operator="OR")
        with patch.object(web.scraper, "collect_links", side_effect=[RuntimeError("blocked"), [RECORD["url"]]]), \
             patch.object(web.scraper, "read_post", return_value=RECORD), patch.object(self.job, "pause"):
            web.execute_job(self.job, driver_factory=lambda args: Mock())
        self.assertEqual(self.job.status, "partial")
        self.assertEqual(self.job.search_errors, 1)
        self.assertEqual(len(self.job.records), 1)

    def test_une_validation_partagee_entre_sources(self):
        for reglages in (web.StartRequest(hashtag='été', second_hashtag='voyage'),
                        web.StartRequest(source_collecte='presse', medias=['lemonde','franceinfo'])):
            job = web.Job('test', reglages, self.job.directory)
            pilote = Mock()
            validations = []
            def decouvrir(navigateur, arguments, rapport, **options):
                self.assertIs(navigateur, pilote)
                validations.append(options['validation_initiale'])
                if options['validation_initiale']: options['interact']('Première vérification')
                return [RECORD['url']]
            with patch.object(web.scraper, 'collect_links', side_effect=decouvrir), \
                 patch.object(web, 'wait_for_user') as intervention, \
                 patch('collecte.verification_comptes.observer_profil', return_value={}), \
                 patch.object(web.scraper, 'read_post', return_value=RECORD), patch.object(job, 'pause'):
                web.execute_job(job, driver_factory=lambda args: pilote)
            if reglages.source_collecte == 'hashtags':
                self.assertEqual(validations, [True,False])
                intervention.assert_called_once()
            else:
                self.assertEqual(validations, [False,False])
                intervention.assert_not_called()

    def test_identical_hashtags_and_blank_second_input(self):
        self.assertEqual(len(web.StartRequest(hashtag="été", second_hashtag="#ÉTÉ").hashtags), 1)
        self.assertEqual(web.StartRequest(hashtag="été", second_hashtag="  ").second_hashtag, "")

    def test_language_filter_combines_with_and_or_and_keeps_original_text(self):
        captions = [
            "Les manifestants demandent une augmentation des salaires et de meilleures conditions de travail. 🍋 #été #voyage",
            "Today we are visiting the city and sharing our favorite places with friends. #été #voyage",
            "#été #voyage 😀",
            "Nous sommes réunis pour défendre nos droits et améliorer nos conditions de travail. #été",
        ]
        urls = [f"https://www.tiktok.com/@test/video/{i}" for i in (111,222,333,444)]
        records = {url: dict(RECORD, url=url, description=text) for url, text in zip(urls, captions)}
        for operator, expected in (("AND", 2), ("OR", 3)):
            job = web.Job("test", web.StartRequest(hashtag="été", second_hashtag="voyage", operator=operator, french_only=True), self.job.directory)
            with patch.object(web.scraper, "collect_links", return_value=urls), \
                 patch.object(web.scraper, "read_post", side_effect=lambda d, url, *a, **k: records[url]), patch.object(job, "pause"):
                web.execute_job(job, driver_factory=lambda args: Mock())
            self.assertEqual(len(job.records), expected)
            self.assertEqual((job.non_french, job.language_unknown), (1, 1))
            self.assertEqual(job.filtered, 3 - expected)
            self.assertIn(captions[0], job.path.read_text())
            self.assertNotIn(captions[1], job.path.read_text())
            self.assertIn(captions[2], job.path.read_text())
            self.assertEqual(next(r for r in job.records if r['description']==captions[2])['langue_detection'], 'unknown')
            self.assertTrue(job.settings.filename.endswith("_fr.txt"))

    def test_disabled_language_filter_does_not_discard_short_text(self):
        with patch.object(web.scraper, "collect_links", return_value=[RECORD["url"]]), \
             patch.object(web.scraper, "read_post", return_value=RECORD), patch.object(self.job, "pause"), \
             patch.object(web, "classify_description") as detect:
            web.execute_job(self.job, driver_factory=lambda args: Mock())
        detect.assert_not_called()
        self.assertEqual(len(self.job.records), 1)

    def test_filtre_francais_conserve_les_textes_courts_indetermines(self):
        self.job.settings.french_only = True
        with patch.object(web.scraper, "collect_links", return_value=[RECORD["url"]]), \
             patch.object(web.scraper, "read_post", return_value=RECORD), patch.object(self.job, "pause"):
            web.execute_job(self.job, driver_factory=lambda args: Mock())
        self.assertEqual(self.job.language_unknown, 1)
        self.assertTrue(self.job.snapshot()["can_download"])
        self.assertIn(RECORD['description'], self.job.path.read_text())
        self.assertIn("langue indéterminée conservés", self.job.message)
        self.assertEqual(self.job.status, "completed")

    def test_live_action_acknowledged_after_execution_and_reports_failure(self):
        for failure in (False, True):
            driver = Mock()
            driver.execute_script.return_value = False
            driver.get_screenshot_as_png.return_value = b"png"
            command = web.LiveAction(web.BrowserAction(kind="pointer_down", points=[web.Point(x=.2, y=.3)]))
            self.job.commands.put(command)
            self.job.commands.put("continue")
            def perform(*args):
                self.assertFalse(command.done.is_set())
                if failure:
                    raise web.scraper.WebDriverException("unavailable")
            with patch.object(web, "perform_action", side_effect=perform), patch.object(web, "release_pointer") as release:
                web.wait_for_user(driver, self.job, "Vérifiez TikTok")
            self.assertTrue(command.done.is_set())
            self.assertEqual(bool(command.error), failure)
            release.assert_called_once_with(driver)

    def test_attention_loop_processes_actions_before_continuing(self):
        driver = Mock()
        driver.execute_script.return_value = False
        driver.get_screenshot_as_png.return_value = b"png"
        self.job.commands.put(web.BrowserAction(kind="key", key="Enter"))
        self.job.commands.put("continue")
        with patch.object(web, "perform_action") as action:
            web.wait_for_user(driver, self.job, "Vérifiez TikTok")
        action.assert_called_once()
        self.assertEqual(self.job.frame, b"")
        self.assertEqual(self.job.status, "starting")


if __name__ == "__main__":
    unittest.main()
