import tempfile
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

    def test_validation_and_csrf_guard(self):
        self.assertEqual(self.client.post("/api/jobs", json={"hashtag": "test"}).status_code, 403)
        for payload in ({"hashtag": "deux mots"}, {"hashtag": "test", "limit": 0}, {"hashtag": "test", "limit": 301}):
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
        job.update(status="collecting")
        self.assertEqual(self.client.post(f"/api/jobs/{job_id}/continue", headers=HEADERS, json={}).status_code, 409)

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
