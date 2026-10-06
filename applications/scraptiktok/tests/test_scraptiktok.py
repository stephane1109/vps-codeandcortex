import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import scraptiktok as app


URL = "https://www.tiktok.com/@test/video/1234567890"


def snapshot(description="Une recette 🍋 #cuisine #été"):
    return {"url": URL, "payloads": [json.dumps({"__DEFAULT_SCOPE__": {
        "webapp.video-detail": {"itemInfo": {"itemStruct": {
            "id": "1234567890", "desc": description,
            "createTime": "1700000000", "author": {"uniqueId": "test"}
        }}}
    }})]}


class ExtractionTests(unittest.TestCase):
    def test_unicode_hashtag_and_invalid_input(self):
        self.assertEqual(app.normalize_hashtag(" #été "), "été")
        for value in ("#", "deux mots", "../test", "https://tiktok.com/tag/test"):
            with self.assertRaises(app.argparse.ArgumentTypeError):
                app.normalize_hashtag(value)

    def test_canonical_urls_reject_other_hosts_and_preserve_id(self):
        self.assertEqual(app.canonical_post(URL + "?lang=fr")[1], URL)
        self.assertEqual(app.canonical_post(URL.replace("/video/", "/photo/"))[0], "1234567890")
        self.assertIsNone(app.canonical_post(URL.replace("www.tiktok.com", "evil.example")))
        self.assertIsNone(app.canonical_post("https://www.tiktok.com/@test"))

    def test_read_json_and_exclude_recommendations(self):
        page = snapshot()
        page["payloads"].insert(0, '{"id":"999","desc":"Mauvaise vidéo"}')
        record = app.extract_record(page, URL)
        self.assertEqual(record["description"], "Une recette 🍋 #cuisine #été")
        self.assertEqual(record["hashtags"], ["cuisine", "été"])
        self.assertEqual(record["source"], "page_json")
        self.assertTrue(record["created_at"].endswith("+00:00"))

    def test_legacy_state_and_empty_caption(self):
        page = {"payloads": ['{"ItemModule":{"1234567890":{"id":"1234567890","desc":""}}}']}
        self.assertEqual(app.extract_record(page, URL)["status"], "empty_caption")

    def test_dom_fallback_does_not_read_a_different_video(self):
        page = {"url": URL, "canonical": URL, "payloads": ["invalid JSON"], "description": "Texte #test"}
        self.assertEqual(app.extract_record(page, URL)["source"], "page_dom")
        page["url"] = URL.replace("1234567890", "999")
        self.assertIsNone(app.extract_record(page, URL))
        page["url"] = URL
        page["canonical"] = URL.replace("1234567890", "999")
        self.assertIsNone(app.extract_record(page, URL))

    def test_missing_description_is_not_success(self):
        self.assertIsNone(app.extract_record({"url": URL, "payloads": []}, URL))
        self.assertEqual(app.timestamp_iso("invalid"), "")

    def test_export_preserves_unicode_multiline_and_protects_csv(self):
        text = '=test; "cité" 🍋\nDeuxième ligne #été'
        record = app.extract_record(snapshot(text), URL)
        with tempfile.TemporaryDirectory() as folder:
            prefix = Path(folder) / "results"
            app.save_results(prefix, [record], {"run_status": "completed"})
            result = json.loads(prefix.with_suffix(".json").read_text())
            self.assertEqual(result["posts"][0]["description"], text)
            with prefix.with_suffix(".csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter=";"))
            self.assertEqual(rows[0]["description"], "'" + text)
            self.assertIn(text, prefix.with_suffix(".txt").read_text())
            self.assertFalse(list(Path(folder).glob("*.tmp")))

    def test_reject_invalid_limits_and_nonfinite_timeouts(self):
        with self.assertRaises(app.argparse.ArgumentTypeError):
            app.positive_int("0")
        for value in ("0", "-1", "nan", "inf"):
            with self.assertRaises(app.argparse.ArgumentTypeError):
                app.positive_float(value)


class CollectionTests(unittest.TestCase):
    def test_initial_captcha_is_reported_explicitly(self):
        args = app.parse_args(["cuisine"])
        driver = Mock()
        driver.execute_script.return_value = True
        report = {"hashtag_url": "https://www.tiktok.com/tag/cuisine"}
        with patch.object(app, "WebDriverWait") as wait:
            wait.return_value.until.side_effect = app.TimeoutException()
            with self.assertRaisesRegex(RuntimeError, "CAPTCHA"):
                app.collect_links(driver, args, report)
        self.assertEqual(report["discovery_stop"], "blocked")

    def test_discovery_deduplicates_and_honors_limit(self):
        args = app.parse_args(["cuisine", "--limit", "2"])
        driver = Mock()
        driver.execute_script.return_value = [URL, URL + "?tracking=yes", URL.replace("1234567890", "999")]
        report = {"hashtag_url": "https://www.tiktok.com/tag/cuisine"}
        self.assertEqual(len(app.collect_links(driver, args, report)), 2)
        self.assertEqual(report["discovery_stop"], "limit")

    def test_navigation_timeout_is_not_ignored(self):
        driver = Mock()
        driver.get.side_effect = app.TimeoutException()
        with self.assertRaises(app.TimeoutException):
            app.open_page(driver, URL)
        driver.execute_script.assert_called_once_with("window.stop();")

    def exercise_run(self, effects):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        args = app.parse_args(["cuisine", "--output-dir", folder.name])
        driver = Mock()
        with patch.object(app, "create_driver", return_value=driver), \
             patch.object(app, "collect_links", return_value=[URL, URL.replace("1234567890", "999")]), \
             patch.object(app, "read_post", side_effect=effects), patch.object(app.time, "sleep"):
            code = app.run(args)
        driver.quit.assert_called_once()
        report = json.loads(next(Path(folder.name).glob("*.json")).read_text())
        return code, report

    def test_keyboard_interrupt_saves_completed_records_and_closes_browser(self):
        code, report = self.exercise_run([app.extract_record(snapshot(), URL), KeyboardInterrupt()])
        self.assertEqual(code, 130)
        self.assertEqual(report["processed"], 1)
        self.assertEqual(report["run_status"], "interrupted")

    def test_post_error_is_reported_and_other_posts_are_kept(self):
        code, report = self.exercise_run([app.TimeoutException(), app.extract_record(snapshot(), URL)])
        self.assertEqual(code, 2)
        self.assertEqual(report["run_status"], "partial")
        self.assertEqual(report["posts"][0]["status"], "error")
        self.assertEqual(report["captions"], 1)

    def test_browser_start_failure_creates_failure_report(self):
        with tempfile.TemporaryDirectory() as folder:
            args = app.parse_args(["cuisine", "--output-dir", folder])
            with patch.object(app, "create_driver", side_effect=app.WebDriverException("Chrome absent")):
                self.assertEqual(app.run(args), 1)
            report = json.loads(next(Path(folder).glob("*.json")).read_text())
            self.assertEqual(report["run_status"], "failed")
            self.assertEqual(report["processed"], 0)


if __name__ == "__main__":
    unittest.main()
