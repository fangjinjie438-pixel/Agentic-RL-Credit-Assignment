"""CPU regressions for isolated S0 metadata/import evidence and tool boundaries.

Run with the project ``.venv-cpu`` and unittest discovery. All ML imports and GPU
venv subprocesses are mocked; these tests cover masking, project interpreter
restrictions, static CUDA facts, and failure honesty, not GPU compatibility.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from procure_rl import environment_probe as probe


class EnvironmentProbeTests(unittest.TestCase):
    """Protect CPU parent behavior, subprocess policy, and evidence granularity."""

    def _make_project_python(self, directory):
        root = Path(directory)
        base = root / ".tools" / "python" / "cpython-test" / "bin" / "python"
        base.parent.mkdir(parents=True)
        base.write_text("project interpreter placeholder", encoding="utf-8")
        base.chmod(0o700)
        python = root / ".venv-gpu" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.symlink_to(base)
        return root, python

    def test_parent_import_and_dry_spec_do_not_import_ml_or_run_commands(self):
        real_import = builtins.__import__
        forbidden = {"torch", "torchvision", "torchaudio", "transformers", "vllm", "verl", "ray", "peft", "tensordict"}

        def guarded_import(name, *args, **kwargs):
            if name.split(".", 1)[0] in forbidden:
                raise AssertionError(f"ML import reached CPU parent: {name}")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            root, python = self._make_project_python(directory)
            with patch.object(builtins, "__import__", side_effect=guarded_import):
                with patch.object(probe.subprocess, "run") as run:
                    importlib.reload(probe)
                    spec = probe.build_probe_spec(root, command_timeout=1.5)
            run.assert_not_called()
            self.assertFalse(spec["policy"]["parent_imports_ml_libraries"])
            self.assertFalse(spec["policy"]["runs_toolkit_binaries"])
            self.assertEqual(spec["policy"]["child_process_execution"], "forbidden")
            self.assertEqual(spec["environment_overrides"]["CUDA_VISIBLE_DEVICES"], "")
            self.assertEqual(spec["environment_overrides"]["PYTORCH_NVML_BASED_CUDA_CHECK"], "1")
            self.assertIn("torch_fsdp2", {item["id"] for item in spec["commands"]})
            self.assertIn("verl_vllm_async_server", {item["id"] for item in spec["commands"]})
            for item in spec["commands"]:
                self.assertEqual(item["argv"][0], str(python))
                self.assertEqual(item["argv"][1], "-I")
                self.assertEqual(item["timeout_seconds"], 1.5)
                self.assertNotIn("nvcc", item["argv"])
            json.dumps(spec)

    def test_reject_shared_interpreters_and_invalid_timeouts_before_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, python = self._make_project_python(directory)
            with patch.object(probe.subprocess, "run") as run:
                for path in ("/usr/bin/python3", root / ".venv-cpu" / "bin" / "python", sys.executable):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        probe.build_probe_spec(root, path)
                for timeout in (0, -1, float("nan"), float("inf")):
                    with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                        probe.build_probe_spec(root, command_timeout=timeout)
                python.unlink()
                python.symlink_to(sys.executable)
                with self.assertRaisesRegex(ValueError, "inside project"):
                    probe.build_probe_spec(root)
            run.assert_not_called()

    def test_each_import_is_independent_masked_and_gpu_verification_stays_not_run(self):
        def completed(argv, **kwargs):
            definition = json.loads(argv[-1])
            child = {"id": definition["id"], "status": "passed", "cuda_visible_devices": ""}
            if definition["kind"] == "metadata":
                child["distributions"] = {"torch": {"installed_version": "2.7.1+cu126"}}
            return subprocess.CompletedProcess(argv, 0, probe.RESULT_PREFIX + json.dumps(child) + "\n", "")

        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._make_project_python(directory)
            with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "5,7", "CUDA_HOME": "/usr/local/cuda", "PYTHONPATH": "/shared/lib", "LD_LIBRARY_PATH": "/usr/local/cuda/lib64"}):
                with patch.object(probe.subprocess, "run", side_effect=completed) as run:
                    report = probe.collect_environment_report(root, command_timeout=3)
            self.assertEqual(report["status"], "passed")
            self.assertEqual(run.call_count, len(probe.PROBE_DEFINITIONS) + 1)
            for call in run.call_args_list:
                environment = call.kwargs["env"]
                self.assertEqual(environment["CUDA_VISIBLE_DEVICES"], "")
                self.assertEqual(environment["HF_HUB_OFFLINE"], "1")
                self.assertEqual(environment["PATH"], str(root / ".venv-gpu" / "bin"))
                self.assertNotIn("CUDA_HOME", environment)
                self.assertNotIn("PYTHONPATH", environment)
                self.assertNotIn("LD_LIBRARY_PATH", environment)
                self.assertFalse(call.kwargs["shell"])
                self.assertEqual(call.kwargs["timeout"], 3)
            self.assertEqual(report["validation"]["real_gpu_execution"], "not_run")
            self.assertEqual(report["validation"]["candidate_stack_compatibility"], "not_validated_by_imports")
            paths = probe.write_environment_report(report, root / "report")
            self.assertEqual(json.loads(Path(paths["json"]).read_text())["status"], "passed")
            self.assertIn("do not validate GPU", Path(paths["markdown"]).read_text())

    def test_timeout_nonzero_and_invalid_structured_result_are_never_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._make_project_python(directory)
            command = probe.build_probe_spec(root, command_timeout=1)["commands"][0]
            cases = [
                (subprocess.TimeoutExpired(command["argv"], 1, output=b"partial", stderr=b"timeout"), "timeout"),
                (subprocess.CompletedProcess(command["argv"], 0, "ordinary import log\n", ""), "failed"),
                (subprocess.CompletedProcess(command["argv"], 1, "", "ModuleNotFoundError: flash_attn"), "failed"),
                (subprocess.CompletedProcess(command["argv"], 0, probe.RESULT_PREFIX + "not json", ""), "failed"),
                (subprocess.CompletedProcess(command["argv"], 0, probe.RESULT_PREFIX + json.dumps(
                    {"id": "metadata", "status": "passed", "cuda_visible_devices": "5"}), ""), "failed"),
            ]
            for outcome, expected in cases:
                with self.subTest(expected=expected, outcome=outcome):
                    kwargs = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
                    with patch.object(probe.subprocess, "run", **kwargs):
                        item = probe._run_probe(command, root)
                    self.assertEqual(item["status"], expected)
                    if expected == "timeout":
                        self.assertEqual(item["stdout"], "partial")
                        self.assertIsNone(item["returncode"])

    def test_failed_import_checkpoints_each_probe_before_continuing(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._make_project_python(directory)
            output = root / "environment-run"
            completed_ids = []

            def run_probe(command, project_root):
                # Check durability while collection is still in progress, not
                # merely after the final aggregate report has been published.
                if completed_ids:
                    previous = output / "probes" / f"{completed_ids[-1]}.json"
                    self.assertTrue(previous.is_file())
                    self.assertEqual(json.loads(previous.read_text())["id"], completed_ids[-1])
                failed = command["id"] == "peft"
                child = {"id": command["id"], "status": "failed" if failed else "passed",
                         "cuda_visible_devices": ""}
                if command["id"] == "metadata":
                    child["distributions"] = {}
                completed_ids.append(command["id"])
                return {"id": command["id"], "argv": command["argv"],
                        "timeout_seconds": command["timeout_seconds"],
                        "status": child["status"], "returncode": 1 if failed else 0,
                        "stdout": "partial import output" if failed else "import output",
                        "stderr": "ModuleNotFoundError: optional dependency" if failed else "",
                        "result": child, "elapsed_seconds": 0.01}

            with patch.object(probe, "_run_probe", side_effect=run_probe):
                paths = probe.run_environment_probe(root, output, command_timeout=1)
            report = json.loads(Path(paths["json"]).read_text())
            expected_ids = {"metadata", *(item["id"] for item in probe.PROBE_DEFINITIONS)}
            self.assertEqual(set(completed_ids), expected_ids)
            self.assertEqual({path.stem for path in (output / "probes").iterdir()}, expected_ids)
            for name in completed_ids:
                checkpoint = json.loads((output / "probes" / f"{name}.json").read_text())
                self.assertEqual(checkpoint, report["commands"][name])
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failed_probes"], ["peft"])
            self.assertEqual(report["commands"]["peft"]["stderr"], "ModuleNotFoundError: optional dependency")
            self.assertEqual(report["commands"][completed_ids[-1]]["status"], "passed")
            self.assertEqual(report["validation"]["real_gpu_execution"], "not_run")
            self.assertEqual(report["validation"]["candidate_stack_compatibility"], "not_validated_by_imports")

    def test_import_missing_optional_dependency_is_a_structured_failure(self):
        definition = {"id": "verl_fsdp_worker", "kind": "import", "module": "verl.workers.fsdp_workers", "attributes": []}
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": ""}):
            with patch.object(probe.importlib, "import_module", side_effect=ModuleNotFoundError("No module named 'flash_attn'")):
                result = probe._execute_child_probe(definition)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "ModuleNotFoundError")
        self.assertIn("flash_attn", result["error"])
        self.assertIn("traceback", result)

    def test_independent_attention_and_fixed_verl_server_interfaces_are_checked(self):
        def forbidden_execution(*args, **kwargs):
            raise AssertionError("Import evidence must not execute kernels or server constructors")

        # These are the interfaces in the audited d62da495 server source and the
        # independent flash_attn namespace, rather than vLLM's bundled attention.
        attention = SimpleNamespace(flash_attn_func=forbidden_execution,
                                    flash_attn_varlen_func=forbidden_execution)
        server = SimpleNamespace(vLLMHttpServerBase=forbidden_execution,
                                 vLLMHttpServer=forbidden_execution,
                                 vLLMReplica=forbidden_execution)
        modules = {"flash_attn": attention,
                   "verl.workers.rollout.vllm_rollout.vllm_async_server": server}
        definitions = {item["id"]: item | {"kind": "import"} for item in probe.PROBE_DEFINITIONS}
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": ""}):
            with patch.object(probe.importlib, "import_module", side_effect=modules.__getitem__) as importer:
                attention_result = probe._execute_child_probe(definitions["flash_attn"])
                server_result = probe._execute_child_probe(definitions["verl_vllm_async_server"])
                del attention.flash_attn_varlen_func
                missing_result = probe._execute_child_probe(definitions["flash_attn"])
        self.assertEqual(attention_result["status"], "passed")
        self.assertEqual(set(attention_result["attributes"]), {"flash_attn_func", "flash_attn_varlen_func"})
        self.assertEqual(server_result["status"], "passed")
        self.assertEqual(set(server_result["attributes"]), {"vLLMHttpServerBase", "vLLMHttpServer", "vLLMReplica"})
        self.assertEqual(importer.call_args_list[0].args, ("flash_attn",))
        self.assertEqual(missing_result["status"], "failed")
        self.assertEqual(missing_result["error_type"], "AttributeError")
        self.assertIn("flash_attn_varlen_func", missing_result["error"])

    def test_unmasked_child_refuses_import(self):
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "7"}):
            with patch.object(probe.importlib, "import_module") as importer:
                result = probe._execute_child_probe({"id": "torch", "kind": "import", "module": "torch"})
        self.assertEqual(result["status"], "failed")
        importer.assert_not_called()

    def test_metadata_preserves_commit_and_omits_url_credentials(self):
        direct_url = {"url": "https://private-user:secret-password@example.com/verl.git?token=secret-query", "vcs_info": {
            "vcs": "git", "commit_id": probe.VERL_COMMIT, "requested_revision": "v0.6.1"}}

        def distribution(name):
            if name == "flash-attn":
                raise importlib.metadata.PackageNotFoundError(name)
            return SimpleNamespace(version=probe.DISTRIBUTIONS[name] or "1.0", read_text=lambda path: json.dumps(direct_url) if name == "verl" else None)

        with patch.object(probe.metadata, "distribution", side_effect=distribution):
            result = probe._distribution_metadata()
        self.assertEqual(result["verl"]["commit_comparison"], "matches_commit_only")
        self.assertEqual(result["verl"]["direct_url"]["vcs_info"]["commit_id"], probe.VERL_COMMIT)
        self.assertEqual(result["flash-attn"]["status"], "not_installed")
        serialized = json.dumps(result)
        for secret in ("private-user", "secret-password", "secret-query", "example.com"):
            self.assertNotIn(secret, serialized)

    def test_torch_static_build_metadata_never_queries_gpu_support(self):
        def forbidden():
            raise AssertionError("GPU querying is forbidden in static import probe")

        fake_torch = SimpleNamespace(
            __version__="2.7.1+cu126", bfloat16="fake-dtype", version=SimpleNamespace(cuda="12.6"),
            cuda=SimpleNamespace(is_available=forbidden, device_count=forbidden,
                                 is_bf16_supported=forbidden, is_initialized=lambda: False))
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": ""}):
            with patch.dict(sys.modules, {"torch": fake_torch}):
                with patch.object(probe.importlib, "import_module", return_value=fake_torch):
                    result = probe._execute_child_probe(probe.PROBE_DEFINITIONS[0] | {"kind": "import"})
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["torch_cuda_initialized_after_import"])
        self.assertEqual(result["torch"]["hardware_bf16_support"], "not_queried_no_gpu_execution")
        fake_torch.cuda.is_initialized = lambda: True
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": ""}):
            with patch.dict(sys.modules, {"torch": fake_torch}):
                with patch.object(probe.importlib, "import_module", return_value=fake_torch):
                    result = probe._execute_child_probe(probe.PROBE_DEFINITIONS[0] | {"kind": "import"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("policy_violation", result)

    def test_child_audit_hook_forbids_toolkit_compiler_and_shell_execution(self):
        # Never install a permanent hook in unittest itself: that would affect
        # unrelated tests rather than the isolated import child only.
        for event, arguments in (("subprocess.Popen", ("/usr/local/cuda/bin/nvcc",)),
                                 ("subprocess.Popen", ("gcc",)),
                                 ("os.system", ("nvcc --version",)),
                                 ("os.exec", ("/usr/bin/python3",))):
            with self.subTest(event=event), self.assertRaises(FileNotFoundError):
                probe._forbid_child_process(event, arguments)
        probe._forbid_child_process("open", ("metadata.json", "r"))

        # Exercise the real CPython audit boundary in a project CPU interpreter.
        # If the hook were to return rather than deny process creation, the
        # attempted child would create this marker, and the regression fails.
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "forbidden-child-executed"
            child_program = f"from pathlib import Path; Path({str(marker)!r}).write_text('unexpected')"
            source = f"""
import runpy
import subprocess
import sys
namespace = runpy.run_path({str(Path(probe.__file__).resolve())!r})
sys.addaudithook(namespace['_forbid_child_process'])
try:
    child = subprocess.Popen([sys.executable, '-c', {child_program!r}])
except FileNotFoundError:
    print('process_creation_blocked')
else:
    child.wait(timeout=5)
    raise AssertionError('Audit hook allowed forbidden child process creation')
"""
            python = Path(__file__).resolve().parents[1] / ".venv-cpu" / "bin" / "python"
            completed = subprocess.run([str(python), "-I", "-c", source],
                                       capture_output=True, text=True, timeout=10,
                                       check=False, shell=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "process_creation_blocked")
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
