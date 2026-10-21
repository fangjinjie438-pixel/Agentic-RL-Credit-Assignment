"""CPU-only doctor checks using mocked host commands, never CUDA execution.

Run ``PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v`` from
the project root using its independent interpreter. Assertions cover partial
evidence, bounded probes, and honest validation states; passing them is not
evidence of real GPU compatibility. System Toolkit programs are never executed.
"""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from procure_rl import doctor


class DoctorTests(unittest.TestCase):
    """Validate the report contract and read-only failure behavior on CPU."""

    def test_missing_tools_are_recorded_without_confirming_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(doctor.subprocess, "run", side_effect=FileNotFoundError("missing tool")) as run:
                with patch.object(doctor.metadata, "distribution", side_effect=importlib.metadata.PackageNotFoundError):
                    with patch.object(doctor, "_toolkit_metadata", return_value={"execution_policy": "no_toolkit_execution"}):
                        with patch.dict(doctor.os.environ, {}, clear=True):
                            report = doctor.collect_report(directory, command_timeout=1.5)
            self.assertEqual(report["allocation"]["status"], "not_confirmed")
            self.assertEqual(report["allocation"]["environment_hints"], {})
            self.assertTrue(all(value["status"] == "unavailable" for value in report["commands"].values()))
            self.assertEqual(report["validation"]["real_gpu_execution"], "pending")
            self.assertEqual(report["candidate_stack"]["status"], "not_validated")
            self.assertFalse(report["probe_policy"]["runs_gpu_compute"])
            self.assertFalse(report["probe_policy"]["runs_toolkit_binaries"])
            self.assertEqual(report["toolkits"]["execution_policy"], "no_toolkit_execution")
            self.assertEqual(report["dependencies"]["torch"]["status"], "not_installed")
            for call in run.call_args_list:
                self.assertEqual(call.kwargs["timeout"], 1.5)
                self.assertFalse(call.kwargs["shell"])
                argv = call.args[0]
                self.assertIn(argv[0], {"nvidia-smi", "git"})
                if argv[0] == "nvidia-smi":
                    self.assertTrue(len(argv) == 1 or argv[1].startswith("--query-") or argv[1] == "topo")
                if argv[0] == "git":
                    self.assertEqual(argv[1], "--no-optional-locks")
                    self.assertIn(argv[4], {"status", "rev-parse"})
            self.assertEqual(list(Path(directory).iterdir()), [])
            # Reports must remain serializable even when all tools are unavailable.
            json.dumps(report)

    def test_failed_command_preserves_exit_code_and_output(self):
        completed = subprocess.CompletedProcess(["nvidia-smi"], 9, stdout="partial", stderr="NVML unavailable")
        with patch.object(doctor.subprocess, "run", return_value=completed):
            result = doctor._run_command(["nvidia-smi"], 2.0)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["returncode"], 9)
        self.assertEqual(result["stdout"], "partial")
        self.assertEqual(result["stderr"], "NVML unavailable")

    def test_timeout_preserves_partial_bytes(self):
        error = subprocess.TimeoutExpired(["nvidia-smi"], timeout=1, output=b"partial", stderr=b"timed out")
        with patch.object(doctor.subprocess, "run", side_effect=error):
            result = doctor._run_command(["nvidia-smi"], 1.0)
        self.assertEqual(result["status"], "timeout")
        self.assertIsNone(result["returncode"])
        self.assertEqual(result["stdout"], "partial")

    def test_free_memory_and_allocation_hint_do_not_authorize_compute(self):
        def probe(argv, timeout):
            output = ""
            if argv[1:2] and argv[1].startswith("--query-gpu="):
                output = "4, GPU-test, NVIDIA RTX A6000, 49140, 0, 49140, 560.35.03, 0000:01:00.0\n"
            return {"argv": argv, "status": "ok", "returncode": 0, "stdout": output, "stderr": ""}

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(doctor, "_run_command", side_effect=probe):
                with patch.object(doctor, "_toolkit_metadata", return_value={"execution_policy": "no_toolkit_execution"}):
                    with patch.dict(doctor.os.environ, {"CUDA_VISIBLE_DEVICES": "4", "SECRET_TOKEN": "hidden"}, clear=True):
                        report = doctor.collect_report(directory)
        self.assertEqual(report["gpu"]["inventory"]["rows"][0]["memory.free"], "49140")
        self.assertEqual(report["allocation"]["status"], "not_confirmed")
        self.assertEqual(report["allocation"]["environment_hints"], {"CUDA_VISIBLE_DEVICES": "4"})
        self.assertNotIn("SECRET_TOKEN", json.dumps(report))
        self.assertTrue(all(value == "pending" for key, value in report["validation"].items() if key != "read_only_inventory"))

    def test_report_artifacts_are_written_only_to_requested_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "reports"
            with patch.object(doctor, "_run_command", return_value={"status": "unavailable", "returncode": None, "stdout": "", "stderr": "missing"}):
                with patch.object(doctor, "_toolkit_metadata", return_value={"execution_policy": "no_toolkit_execution"}):
                    report = doctor.collect_report(directory)
            paths = doctor.write_report(report, target)
            self.assertEqual(set(Path(directory).iterdir()), {target})
            self.assertEqual(set(path.name for path in target.iterdir()), {"report.json", "report.md"})
            self.assertEqual(json.loads(Path(paths["json"]).read_text())["schema_version"], 1)
            self.assertIn("not validated", Path(paths["markdown"]).read_text())

    def test_invalid_timeout_is_rejected_before_running_commands(self):
        with patch.object(doctor, "_run_command") as run:
            with self.assertRaises(ValueError):
                doctor.collect_report(".", command_timeout=0)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
