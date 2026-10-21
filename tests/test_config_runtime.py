"""CPU regressions for S0 config invariants and durable run evidence.

Uses unittest and temporary directories; runs without ML libraries or GPU access.
Invoked via unittest discovery; protects version/assignment drift and log overwrite.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from procure_rl.config import load_config
from procure_rl.__main__ import main
from procure_rl.runtime import RunRecord


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_current_config_and_no_gpu(self):
        config = load_config(ROOT / "configs/s0.json")
        self.assertFalse(config["resources"]["gpu_compute_enabled"])
        self.assertEqual(config["planned_training"]["prompt_batch"], 6)

    def test_unverified_versions_and_assignment_are_enforced(self):
        for key, value in [("status", "verified"), ("stack", {"verl": "0.8.0"}),
                           ("resources", {"gpu_compute_enabled": True,
                                          "assigned_gpu_uuids": ["GPU-other"]})]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                config = json.loads((ROOT / "configs/s0.json").read_text())
                config[key] = value
                path = Path(directory) / "config.json"
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    load_config(path)


class RuntimeTests(unittest.TestCase):
    def test_missing_config_has_failed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing-config-run"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = main(["check-config", "--config", str(Path(directory) / "missing.json"),
                               "--output", str(output)])
            self.assertEqual(status, 1)
            self.assertIn("FileNotFoundError", stderr.getvalue())
            record = json.loads((output / "run.json").read_text())
            self.assertEqual(record["status"], "failed")
            self.assertIn("FileNotFoundError", record["error"])
            self.assertIsNone(record["config"]["sha256"])

    def test_manifest_failure_has_evidence_and_does_not_claim_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run = RunRecord(output, ROOT, ["python", "-m", "procure_rl"])
            run.finish("failed", {}, "not_validated", "example failure")
            record = json.loads((output / "run.json").read_text())
            self.assertEqual(record["status"], "failed")
            self.assertFalse(record["gpu_compute_performed"])
            self.assertEqual(record["gpu_validation"], "not_run")
            self.assertIsNone(record["checkpoint"])
            self.assertTrue(record["source_sha256"])
            self.assertIn("example failure", (output / "run.log").read_text())
            with self.assertRaises(FileExistsError):
                RunRecord(output, ROOT, ["overwrite"])

