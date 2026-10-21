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
from unittest.mock import patch

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
    def test_gpu_cli_default_is_configuration_only(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            output = Path(directory) / "dry-run"
            self.assertEqual(main(["gpu-probe", "--output", str(output)]), 0)
            report = json.loads((output / "report.json").read_text())
            record = json.loads((output / "run.json").read_text())
            self.assertEqual(report["status"], "dry_run")
            self.assertFalse(record["gpu_compute_performed"])
            self.assertEqual(record["gpu_validation"], "not_run")

    def test_gpu_cli_propagates_failed_and_unknown_execution(self):
        from procure_rl.gpu_probe import run_gpu_probe
        report = run_gpu_probe()
        report.update(status="failed", gpu_compute_performed=None, gpu_validation="failed",
                      validation_level="real_gpu_probe_subset")
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            output = Path(directory) / "failed"
            with patch("procure_rl.gpu_probe.run_gpu_probe", return_value=report):
                self.assertEqual(main(["gpu-probe", "--execute", "--output", str(output)]), 1)
            record = json.loads((output / "run.json").read_text())
            self.assertEqual(record["status"], "failed")
            self.assertIsNone(record["gpu_compute_performed"])
            self.assertEqual(record["gpu_validation"], "failed")

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

