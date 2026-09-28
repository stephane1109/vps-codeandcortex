from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from webapp import runtime


class AnalysisRuntimeRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="iramuteq-runtime-recovery-")
        self.env_patch = patch.dict(
            "os.environ",
            {"IRAMUTEQ_APP_DATA_DIR": self.temp_dir.name},
        )
        self.env_patch.start()
        self.instance_patch = patch.object(runtime, "APP_INSTANCE_ID", "instance-b")
        self.instance_patch.start()

    def tearDown(self) -> None:
        self.instance_patch.stop()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def prepare_remote_job(self, job_id: str, heartbeat_age: float) -> tuple[Path, Path]:
        job_root = runtime.job_root_for_id(job_id)
        job_root.mkdir(parents=True, exist_ok=True)
        runtime.write_json_file(
            runtime.analysis_lock_path(),
            {
                "job_id": job_id,
                "pid": 12345,
                "corpus_name": "english.txt",
                "instance_id": "instance-a",
                "created_at": int(time.time()) - 120,
            },
        )
        status_path = job_root / "status.json"
        runtime.write_json_file(
            status_path,
            {
                "job_id": job_id,
                "state": "running",
                "progress": 20,
                "message": "Calcul CHD.",
                "logs": [],
            },
        )
        heartbeat_path = runtime.analysis_heartbeat_path(job_id)
        runtime.write_json_file(
            heartbeat_path,
            {
                "job_id": job_id,
                "updated_at": time.time() - heartbeat_age,
            },
        )
        return status_path, heartbeat_path

    def test_fresh_remote_heartbeat_preserves_running_job(self) -> None:
        status_path, _heartbeat_path = self.prepare_remote_job("web-fresh", heartbeat_age=1)

        self.assertFalse(runtime.recover_interrupted_analysis("web-fresh"))
        self.assertTrue(runtime.analysis_lock_path().exists())
        self.assertEqual(runtime.read_json_file_with_retry(status_path)["state"], "running")
        self.assertFalse((status_path.parent / "results.json").exists())
        self.assertEqual(runtime.current_analysis_lock()["job_id"], "web-fresh")

    def test_stale_remote_heartbeat_marks_job_interrupted(self) -> None:
        status_path, _heartbeat_path = self.prepare_remote_job("web-stale", heartbeat_age=60)

        self.assertTrue(runtime.recover_interrupted_analysis("web-stale"))
        self.assertFalse(runtime.analysis_lock_path().exists())
        self.assertEqual(runtime.read_json_file_with_retry(status_path)["state"], "failed")
        result = runtime.read_json_file_with_retry(status_path.parent / "results.json")
        self.assertIn("arrêt de l'instance", result["message"])


if __name__ == "__main__":
    import unittest

    unittest.main()
