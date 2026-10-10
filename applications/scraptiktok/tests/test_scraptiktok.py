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
    def test_erreur_tiktok_recharge_une_fois_puis_recupere_les_liens(self):
        args = app.parse_args(['test', '--limit', '1']); args.interactive = True; args.timeout = .01
        pilote, intervention = Mock(), Mock()
        def executer(code):
            if code == app.BLOCKED_JS: return False
            if code == app.DISCOVER_JS: return [URL] if pilote.get.call_count > 1 else []
            return {'erreur_tiktok': True, 'liens': 0}
        pilote.execute_script.side_effect = executer
        rapport = {'hashtag_url': 'https://www.tiktok.com/@test', 'compte_attendu': 'test'}
        self.assertEqual(app.collect_links(pilote, args, rapport, interact=intervention, validation_initiale=False), [URL])
        self.assertEqual(pilote.get.call_count, 2)
        self.assertEqual(rapport['rechargements'], 1)
        self.assertNotIn('diagnostic', rapport)
        intervention.assert_not_called()

    def test_erreur_tiktok_persistante_ne_demande_pas_un_captcha_inexistant(self):
        args = app.parse_args(['test']); args.interactive = True; args.timeout = .01
        pilote, intervention = Mock(), Mock()
        pilote.execute_script.side_effect = lambda code: False if code == app.BLOCKED_JS else ([] if code == app.DISCOVER_JS else {'erreur_tiktok': True, 'liens': 0})
        rapport = {'hashtag_url': 'https://www.tiktok.com/@test'}
        with self.assertRaisesRegex(RuntimeError, 'erreur de chargement'):
            app.collect_links(pilote, args, rapport, interact=intervention, validation_initiale=False)
        self.assertEqual(pilote.get.call_count, 2)
        self.assertEqual(rapport['discovery_stop'], 'tiktok_error')
        intervention.assert_not_called()

    def test_captcha_prioritaire_sur_erreur_tiktok(self):
        pilote = Mock()
        pilote.execute_script.side_effect = lambda code: True if code == app.BLOCKED_JS else {'erreur_tiktok': True}
        self.assertEqual(app.diagnostiquer_page(pilote, {})['code'], 'verification_tiktok')

    def test_source_suivante_accessible_sans_nouvelle_validation(self):
        args = app.parse_args(['cuisine', '--limit', '1'])
        args.interactive = True
        pilote, intervention = Mock(), Mock()
        pilote.execute_script.side_effect = lambda script: False if script == app.BLOCKED_JS else [URL]
        resultat = app.collect_links(pilote, args, {'hashtag_url': 'https://www.tiktok.com/tag/cuisine'},
                                     interact=intervention, validation_initiale=False)
        self.assertEqual(resultat, [URL])
        intervention.assert_not_called()

    def test_verification_reelle_sur_source_suivante(self):
        args = app.parse_args(['cuisine', '--limit', '1'])
        args.interactive = True
        pilote, intervention = Mock(), Mock()
        pilote.execute_script.side_effect = lambda script: True if script == app.BLOCKED_JS else [URL]
        resultat = app.collect_links(pilote, args, {'hashtag_url': 'https://www.tiktok.com/tag/cuisine'},
                                     interact=intervention, validation_initiale=False)
        self.assertEqual(resultat, [URL])
        intervention.assert_called_once()

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
        self.assertEqual(driver.execute_script.call_args.args, ("window.stop();",))

    def test_delai_sur_page_cible_deja_visible_ne_fige_pas_le_captcha(self):
        driver = Mock()
        driver.get.side_effect = app.TimeoutException()
        driver.execute_script.return_value = {"url": URL, "etat": "interactive", "contenu": True}
        app.open_page(driver, URL)
        self.assertFalse(any(c.args[0] == 'window.stop();' for c in driver.execute_script.call_args_list))

    def test_delai_sur_ancienne_page_ou_autre_domaine_reste_un_echec(self):
        for url in (URL.replace('1234567890','999'), URL.replace('www.tiktok.com','evil.test')):
            driver = Mock()
            driver.get.side_effect = app.TimeoutException()
            driver.execute_script.return_value = {"url":url,"etat":"complete","contenu":True}
            with self.assertRaises(app.TimeoutException): app.open_page(driver,URL)

    def test_aucun_lien_montre_la_page_meme_sans_captcha_detecte(self):
        args=app.parse_args(['test','--limit','1']); args.interactive=True; args.timeout=.01
        driver=Mock(); visible=[]
        def script(code):
            if code==app.BLOCKED_JS: return False
            if code==app.DISCOVER_JS: return visible
            return {'url':'https://www.tiktok.com/@test','etat':'complete','liens':0}
        driver.execute_script.side_effect=script
        def verifier(message): visible.append(URL)
        intervention=Mock(side_effect=verifier)
        report={'hashtag_url':'https://www.tiktok.com/@test','compte_attendu':'test'}
        resultat=app.collect_links(driver,args,report,interact=intervention,validation_initiale=False)
        self.assertEqual(resultat,[URL]); intervention.assert_called_once()
        self.assertIn('Examinez la page',intervention.call_args.args[0])

    def test_page_toujours_vide_une_seule_reprise_et_diagnostic(self):
        args=app.parse_args(['test']); args.interactive=True; args.timeout=.01
        driver=Mock(); intervention=Mock()
        driver.execute_script.side_effect=lambda code: False if code==app.BLOCKED_JS else ([] if code==app.DISCOVER_JS else {'url':'https://www.tiktok.com/@test','etat':'complete','liens':0})
        report={'hashtag_url':'https://www.tiktok.com/@test'}
        with self.assertRaisesRegex(RuntimeError,'après vérification'):
            app.collect_links(driver,args,report,interact=intervention,validation_initiale=False)
        intervention.assert_called_once()
        self.assertEqual(report['diagnostic']['code'],'page_sans_liens')
        self.assertEqual(report['discovery_stop'],'no_accessible_links')

    def test_erreur_reseau_navigation_conservee(self):
        args=app.parse_args(['test']); driver=Mock()
        driver.get.side_effect=app.WebDriverException('unknown error: net::ERR_NAME_NOT_RESOLVED')
        driver.execute_script.return_value=False
        report={'hashtag_url':'https://www.tiktok.com/@test'}
        with self.assertRaises(app.WebDriverException): app.collect_links(driver,args,report)
        self.assertEqual(report['diagnostic']['code'],'erreur_reseau')
        self.assertEqual(report['diagnostic']['erreur_reseau'],'net::ERR_NAME_NOT_RESOLVED')

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
