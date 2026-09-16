from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from webapp import analysis_history


class AnalysisHistoryStoreTests(unittest.TestCase):
    def test_start_endpoint_registers_an_anonymous_history_entry(self) -> None:
        from webapp.main import app

        previous_data_root = os.environ.get("IRAMUTEQ_APP_DATA_DIR")
        previous_cookie_secure = os.environ.get("IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE")
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                os.environ["IRAMUTEQ_APP_DATA_DIR"] = temporary_directory
                os.environ["IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE"] = "0"
                client = TestClient(app)
                with patch("webapp.main.ticket_gate.require_active_ticket", return_value={}), patch(
                    "webapp.main.runtime.start_python_analysis",
                    return_value={"jobId": "web-start", "statusFile": "status.json", "resultsFile": "results.json"},
                ):
                    response = client.post(
                        "/api/tauri/start_python_analysis",
                        json={
                            "corpusName": "corpus-test.txt",
                            "corpusText": "**** *id_1\ntexte",
                            "config": {"analyses": {"chd": True}},
                            "history": {"analysisKind": "chd"},
                        },
                    )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["analysisId"])
                history = client.get("/api/analyses").json()["analyses"]
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["jobId"], "web-start")
                self.assertFalse(history[0]["completed"])
        finally:
            if previous_data_root is None:
                os.environ.pop("IRAMUTEQ_APP_DATA_DIR", None)
            else:
                os.environ["IRAMUTEQ_APP_DATA_DIR"] = previous_data_root
            if previous_cookie_secure is None:
                os.environ.pop("IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE", None)
            else:
                os.environ["IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE"] = previous_cookie_secure

    def test_owner_isolation_and_snapshot_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            created = analysis_history.create_analysis(
                data_root,
                owner_hash="owner-a",
                job_id="web-123",
                corpus_name="corpus-test.txt",
                analysis_kind="chd",
                navigation_target="resultats_chd",
            )

            self.assertEqual(created["jobId"], "web-123")
            self.assertIsNone(analysis_history.get_owned_analysis(data_root, "owner-b", created["id"]))

            updated = analysis_history.update_analysis_from_snapshot(
                data_root,
                owner_hash="owner-a",
                analysis_id=created["id"],
                snapshot={
                    "state": "completed",
                    "completed": True,
                    "success": True,
                    "message": "Analyse terminée.",
                    "summary": {"n_classes": 3},
                    "logs": ["Export prêt."],
                    "outputDir": str(data_root / "jobs" / "web-123" / "exports"),
                    "artifactCount": 4,
                },
            )

            self.assertIsNotNone(updated)
            self.assertTrue(updated["completed"])
            self.assertTrue(updated["success"])
            self.assertEqual(updated["artifactCount"], 4)
            self.assertEqual(updated["summary"], {"n_classes": 3})

            listed = analysis_history.list_owned_analyses(data_root, "owner-a")
            self.assertEqual([item["id"] for item in listed], [created["id"]])

    def test_expired_completed_record_is_returned_for_filesystem_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory)
            created = analysis_history.create_analysis(
                data_root,
                owner_hash="owner-a",
                job_id="web-456",
                corpus_name="corpus-test.txt",
                analysis_kind="chd",
                navigation_target="resultats_chd",
            )
            analysis_history.update_analysis_from_snapshot(
                data_root,
                owner_hash="owner-a",
                analysis_id=created["id"],
                snapshot={"state": "completed", "completed": True, "success": True},
            )

            with sqlite3.connect(analysis_history.database_path(data_root)) as connection:
                connection.execute("UPDATE analyses SET expires_at = 0 WHERE id = ?", (created["id"],))

            expired = analysis_history.purge_expired_analyses(data_root)
            self.assertEqual([item["jobId"] for item in expired], ["web-456"])
            self.assertEqual(analysis_history.list_owned_analyses(data_root, "owner-a"), [])

    def test_http_history_restores_only_the_owner_exports(self) -> None:
        from webapp.main import app

        previous_data_root = os.environ.get("IRAMUTEQ_APP_DATA_DIR")
        previous_cookie_secure = os.environ.get("IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE")
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                data_root = Path(temporary_directory)
                os.environ["IRAMUTEQ_APP_DATA_DIR"] = str(data_root)
                os.environ["IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE"] = "0"

                job_root = data_root / "jobs" / "web-789"
                exports_root = job_root / "exports"
                exports_root.mkdir(parents=True)
                (job_root / "input-corpus-test.txt").write_text("**** *id_1\ntexte", encoding="utf-8")
                (exports_root / "resultat.txt").write_text("résultat", encoding="utf-8")
                (job_root / "status.json").write_text(
                    json.dumps({"state": "completed", "progress": 100, "message": "Terminé."}),
                    encoding="utf-8",
                )
                (job_root / "results.json").write_text(
                    json.dumps(
                        {
                            "success": True,
                            "job_id": "web-789",
                            "message": "Terminé.",
                            "summary": {"n_classes": 3},
                            "logs": ["Export prêt."],
                            "output_dir": str(exports_root),
                        }
                    ),
                    encoding="utf-8",
                )

                client = TestClient(app)
                client.get("/api/analyses")
                owner_token = client.cookies.get(analysis_history.OWNER_COOKIE_NAME)
                self.assertTrue(owner_token)
                record = analysis_history.create_analysis(
                    data_root,
                    owner_hash=analysis_history._hash_owner_token(owner_token),
                    job_id="web-789",
                    corpus_name="corpus-test.txt",
                    analysis_kind="chd",
                    navigation_target="resultats_chd",
                )

                listed = client.get("/api/analyses")
                self.assertEqual(listed.status_code, 200)
                self.assertTrue(listed.json()["analyses"][0]["completed"])
                self.assertFalse((job_root / "input-corpus-test.txt").exists())

                artifacts = client.get(f"/api/analyses/{record['id']}/artifacts")
                self.assertEqual(artifacts.status_code, 200)
                self.assertEqual(artifacts.json()["artifacts"][0]["relativePath"], "resultat.txt")

                archive = client.get(f"/api/analyses/{record['id']}/archive")
                self.assertEqual(archive.status_code, 200)
                self.assertEqual(archive.headers["content-type"], "application/zip")

                other_browser = TestClient(app)
                self.assertEqual(other_browser.get(f"/api/analyses/{record['id']}").status_code, 404)

                deleted = client.delete(f"/api/analyses/{record['id']}")
                self.assertEqual(deleted.status_code, 200)
                self.assertFalse(job_root.exists())
        finally:
            if previous_data_root is None:
                os.environ.pop("IRAMUTEQ_APP_DATA_DIR", None)
            else:
                os.environ["IRAMUTEQ_APP_DATA_DIR"] = previous_data_root
            if previous_cookie_secure is None:
                os.environ.pop("IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE", None)
            else:
                os.environ["IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE"] = previous_cookie_secure


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
