from pathlib import Path
import sys
import tempfile
import time
import unittest

from mmd_mouth.constants import WORKER_PROTOCOL_VERSION
from mmd_mouth.recognition.runtime import (
    WorkerManager,
    probe_worker,
    resolve_worker,
)


class WorkerRuntimeTests(unittest.TestCase):
    def test_missing_packaged_worker_is_reported_without_fallback(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            resolution = resolve_worker(temporary_dir, mode="PACKAGED")

        self.assertFalse(resolution.available)
        self.assertEqual(resolution.kind, "PACKAGED")
        self.assertIn("packaged worker", resolution.reason)

    def test_configured_python_creates_module_command(self):
        current_python = Path(sys.executable)
        resolution = resolve_worker(
            Path.cwd(),
            mode="PYTHON",
            configured_python=str(current_python),
        )

        self.assertTrue(resolution.available)
        self.assertEqual(resolution.kind, "PYTHON")
        self.assertEqual(resolution.command_prefix[0], str(current_python.resolve()))
        self.assertEqual(resolution.command_prefix[-1], "mmd_mouth.recognition.worker")

    def test_protocol_version_is_stable(self):
        self.assertEqual(WORKER_PROTOCOL_VERSION, 2)

    def test_source_worker_health_probe_uses_package_parent(self):
        addon_package = Path(__file__).resolve().parents[1] / "mmd_mouth"
        resolution = resolve_worker(
            addon_package,
            mode="PYTHON",
            configured_python=sys.executable,
        )

        payload = probe_worker(resolution, addon_root=addon_package)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["protocol_version"], WORKER_PROTOCOL_VERSION)

    @unittest.skipUnless(
        (
            Path(__file__).resolve().parents[1]
            / "mmd_mouth"
            / "runtime"
            / "mmd_mouth_worker"
            / "mmd_mouth_worker.exe"
        ).is_file(),
        "packaged worker is optional in source checkouts",
    )
    def test_packaged_worker_job_round_trip(self):
        addon_package = Path(__file__).resolve().parents[1] / "mmd_mouth"
        manager = WorkerManager(addon_package)
        resolution = resolve_worker(addon_package, mode="AUTO")
        job = {
            "audio_path": "missing.wav",
            "models": [
                {
                    "model_id": "missing",
                    "language_code": "en-US",
                    "model_path": "missing-model",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_dir:
            task = manager.start(
                job,
                temporary_dir,
                resolution=resolution,
                task_id="runtime-test",
            )
            result = None
            deadline = time.monotonic() + 20.0
            while time.monotonic() < deadline:
                result = manager.poll(task)
                if result.state != "RUNNING":
                    break
                time.sleep(0.05)

        self.assertIsNotNone(result)
        self.assertEqual(result.state, "ERROR")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
