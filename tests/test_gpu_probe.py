"""CPU-only contract tests for S0's allocation-gated GPU probe orchestration.

The project unittest entry imports ``procure_rl.gpu_probe`` without ML packages;
mock subprocesses exchange real temporary JSON reports. These tests verify UUID
isolation, authorization, timeouts and honest result levels, never CUDA, NCCL or
model execution. Run with the project's .venv-cpu and PYTHONPATH=src.
"""

from __future__ import annotations

import builtins
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from procure_rl import gpu_probe


GPU_A = "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af"
GPU_B = "GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03"


class GPUProbeTests(unittest.TestCase):
    """Mock orchestration checks do not count as real GPU validation."""

    def test_default_dry_run_never_imports_ml_or_starts_process(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            self.assertNotIn(name.split(".")[0], {"torch", "vllm", "transformers"})
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            with patch.object(gpu_probe.subprocess, "Popen") as popen:
                with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "4,5,7"}):
                    report = gpu_probe.run_gpu_probe()
        popen.assert_not_called()
        self.assertEqual(report["status"], "dry_run")
        self.assertEqual(report["allocation"]["gpu_uuids"], [])
        self.assertEqual(report["gpu_validation"], "not_run")
        self.assertFalse(report["gpu_compute_performed"])
        self.assertFalse(report["gpu_execution_attempted"])
        self.assertEqual(report["candidate_stack_compatibility"], "not_established")

    def test_execute_requires_uuid_and_independent_allocation_description(self):
        with patch.object(gpu_probe.subprocess, "Popen") as popen:
            for kwargs in ({}, {"gpu_uuids": [GPU_A]}, {"allocation_source": "user grants GPUs"}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    gpu_probe.run_gpu_probe(execute=True, **kwargs)
        popen.assert_not_called()

    def test_reject_indices_partial_duplicate_and_oversized_allocation(self):
        for uuids in (["5"], ["GPU-2e81"], [GPU_A, GPU_A.upper().replace("GPU", "GPU")],
                      [GPU_A, GPU_A], "5", [GPU_A, GPU_B, GPU_A, GPU_B]):
            with self.subTest(uuids=uuids), self.assertRaises(ValueError):
                gpu_probe.run_gpu_probe(gpu_uuids=uuids)

    def test_invalid_timeout_and_probe_selection_create_no_processes(self):
        with patch.object(gpu_probe.subprocess, "Popen") as popen:
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    gpu_probe.run_gpu_probe(timeout=timeout)
            for probes in ((), ("torch", "torch"), ("unknown",), "torch"):
                with self.subTest(probes=probes), self.assertRaises(ValueError):
                    gpu_probe.run_gpu_probe(probes=probes)
        popen.assert_not_called()

    def test_nccl_requires_multiple_allocated_devices_and_project_interpreter(self):
        with patch.object(gpu_probe.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(ValueError, "NCCL"):
                gpu_probe.run_gpu_probe(gpu_uuids=[GPU_A], allocation_source="user says GPU A",
                                        execute=True, probes=("nccl",))
            with self.assertRaisesRegex(ValueError, "project"):
                gpu_probe.run_gpu_probe(gpu_uuids=[GPU_A], allocation_source="user says GPU A",
                                        execute=True, project_root=Path("/tmp/different-project"))
        popen.assert_not_called()

    def test_vllm_requires_one_gpu_and_local_small_model_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary)
            (model / "config.json").write_text(json.dumps({"model_type": "qwen3", "hidden_size": 2560,
                                                           "num_hidden_layers": 36}))
            for uuids in ([GPU_A], [GPU_A, GPU_B]):
                with self.subTest(uuids=uuids), self.assertRaises(ValueError):
                    gpu_probe.run_gpu_probe(gpu_uuids=uuids, allocation_source="user confirmation",
                                            execute=True, probes=("vllm",), model_path=model)

    def test_subprocess_receives_only_explicit_uuid_visibility_and_json_protocol(self):
        process = Mock(returncode=0)

        def communicate(payload, timeout):
            request = json.loads(payload)
            Path(request["result_path"]).write_text(json.dumps({"status": "passed",
                                                                "gpu_compute_performed": True,
                                                                "evidence": {"mock_only": True}}))
            return "arbitrary diagnostic logs; not parsed", ""

        process.communicate.side_effect = communicate
        with patch.object(gpu_probe, "_validate_project_interpreter"):
            with patch.object(gpu_probe.subprocess, "Popen", return_value=process) as popen:
                with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "0,1,2,3,4,5,6,7",
                                             "LD_LIBRARY_PATH": "/shared/cuda/lib", "LD_PRELOAD": "/shared/lib.so",
                                             "LIBRARY_PATH": "/shared/lib", "CPATH": "/shared/include",
                                             "CPLUS_INCLUDE_PATH": "/shared/include", "CC": "/usr/bin/gcc",
                                             "CXX": "/usr/bin/g++", "PYTHONHOME": "/shared/python"}):
                    report = gpu_probe.run_gpu_probe(gpu_uuids=[GPU_B], allocation_source="explicit user grant",
                                                     execute=True)
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], GPU_B)
        self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertEqual(kwargs["env"]["CUDA_DEVICE_ORDER"], "PCI_BUS_ID")
        self.assertEqual(kwargs["env"]["VLLM_ATTENTION_BACKEND"], "FLASH_ATTN")
        for name in ("HF_HOME", "VLLM_CACHE_ROOT", "VLLM_CONFIG_ROOT", "TORCHINDUCTOR_CACHE_DIR",
                     "TRITON_CACHE_DIR", "CUDA_CACHE_PATH", "TORCH_EXTENSIONS_DIR", "XDG_CACHE_HOME"):
            self.assertTrue(Path(kwargs["env"][name]).is_relative_to(Path.cwd() / ".cache"))
        self.assertEqual(kwargs["env"]["CUDA_HOME"], str(Path.cwd() / ".tools/cuda"))
        self.assertEqual(kwargs["env"]["CC"], str(Path.cwd() / "scripts/toolchain/cc"))
        self.assertEqual(kwargs["env"]["CXX"], str(Path.cwd() / "scripts/toolchain/cxx"))
        self.assertEqual(kwargs["env"]["TRITON_LIBCUDA_PATH"], str(Path.cwd() / ".tools/cuda-driver/lib"))
        self.assertEqual(kwargs["env"]["PYTHONNOUSERSITE"], "1")
        for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LIBRARY_PATH", "CPATH", "CPLUS_INCLUDE_PATH", "PYTHONHOME"):
            self.assertNotIn(name, kwargs["env"])
        self.assertFalse(any(path.startswith("/usr/local/cuda") for path in kwargs["env"]["PATH"].split(os.pathsep)))
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["checks"]["torch"]["visible_gpu_uuids"], [GPU_B])
        self.assertEqual(report["checks"]["torch"]["stdout"], "arbitrary diagnostic logs; not parsed")
        self.assertEqual(report["training_lora_fsdp2_validation"], "not_run")
        self.assertEqual(report["candidate_stack_compatibility"], "not_established")

    def test_failed_exit_cannot_be_overridden_by_worker_success(self):
        process = Mock(returncode=9)

        def communicate(payload, timeout):
            request = json.loads(payload)
            Path(request["result_path"]).write_text(json.dumps({"status": "passed", "gpu_compute_performed": True}))
            return "", "worker terminated later"

        process.communicate.side_effect = communicate
        with patch.object(gpu_probe.subprocess, "Popen", return_value=process):
            result = gpu_probe._run_worker({"probe": "torch", "gpu_uuids": [GPU_A]}, Path.cwd(), 2)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["returncode"], 9)

    def test_timeout_terminates_only_spawned_group_and_never_reports_passed(self):
        process = Mock(returncode=-15, pid=12345)
        process.communicate.side_effect = [subprocess.TimeoutExpired(["mock"], 0.01), ("partial logs", "terminated")]
        with patch.object(gpu_probe, "_validate_project_interpreter"):
            with patch.object(gpu_probe.subprocess, "Popen", return_value=process):
                with patch.object(gpu_probe.os, "killpg") as killpg:
                    report = gpu_probe.run_gpu_probe(gpu_uuids=[GPU_A], allocation_source="explicit grant",
                                                     execute=True, timeout=0.01)
        killpg.assert_called_once_with(12345, gpu_probe.signal.SIGTERM)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["gpu_validation"], "failed")
        self.assertTrue(report["checks"]["torch"]["timeout"])
        self.assertIsNone(report["gpu_compute_performed"])
        self.assertEqual(report["checks"]["torch"]["stdout"], "partial logs")

    def test_process_start_failure_preserves_not_run_compute_state(self):
        with patch.object(gpu_probe.subprocess, "Popen", side_effect=FileNotFoundError("missing interpreter")):
            result = gpu_probe._run_worker({"probe": "torch", "gpu_uuids": [GPU_A]}, Path.cwd(), 1)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["gpu_compute_performed"])
        self.assertIn("missing interpreter", result["error"])

    def test_communicate_error_reaps_started_group_and_preserves_failure(self):
        process = Mock(returncode=0, pid=12345)

        def communicate(payload=None, timeout=None):
            if payload is not None:
                request = json.loads(payload)
                Path(request["result_path"]).write_text(json.dumps({"status": "passed", "gpu_compute_performed": True}))
                raise OSError("pipe read failed")
            return "partial logs", "terminated"

        process.communicate.side_effect = communicate
        with patch.object(gpu_probe.subprocess, "Popen", return_value=process):
            with patch.object(gpu_probe.os, "killpg") as killpg:
                result = gpu_probe._run_worker({"probe": "torch", "gpu_uuids": [GPU_A]}, Path.cwd(), 1)
        killpg.assert_called_once_with(12345, gpu_probe.signal.SIGTERM)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "partial logs")
        self.assertIn("pipe read failed", result["error"])

    def test_attention_is_opt_in_and_requires_one_explicitly_allocated_device(self):
        with patch.object(gpu_probe.subprocess, "Popen") as popen:
            default_report = gpu_probe.run_gpu_probe(gpu_uuids=[GPU_A], allocation_source="user grant")
            dry_report = gpu_probe.run_gpu_probe(gpu_uuids=[GPU_A], allocation_source="user grant",
                                                 probes=("attention",))
            with self.assertRaisesRegex(ValueError, "exactly one"):
                gpu_probe.run_gpu_probe(gpu_uuids=[GPU_A, GPU_B], allocation_source="user grant",
                                        execute=True, probes=("attention",))
        popen.assert_not_called()
        self.assertEqual(default_report["requested_probes"], ["torch"])
        self.assertEqual(dry_report["requested_probes"], ["attention"])
        self.assertEqual(dry_report["gpu_validation"], "not_run")

    def test_worker_rechecks_visibility_before_ml_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            result_path = Path(temporary) / "result.json"
            request = {"project_root": str(Path.cwd()), "result_path": str(result_path),
                       "gpu_uuids": [GPU_A], "allocation_source": "user confirmation",
                       "probe": "torch", "execute": True, "model_path": None, "timeout": 1}
            with patch.object(gpu_probe.sys, "stdin", io.StringIO(json.dumps(request))):
                with patch.object(gpu_probe, "_validate_project_interpreter"):
                    with patch.object(gpu_probe, "_torch_probe") as torch_probe:
                        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": GPU_B}):
                            code = gpu_probe._worker_main()
            report = json.loads(result_path.read_text())
        torch_probe.assert_not_called()
        self.assertEqual(code, 1)
        self.assertFalse(report["gpu_compute_performed"])
        self.assertIn("does not exactly match", report["error"])

    def test_runtime_uuid_normalizes_torch_raw_uuid_and_rejects_wrong_device(self):
        cuda = Mock()
        cuda.device_count.return_value = 1
        cuda.get_device_properties.return_value = SimpleNamespace(
            uuid=GPU_A.removeprefix("GPU-"), name="mock A6000", total_memory=48)
        cuda.get_device_capability.return_value = (8, 6)
        fake_torch = SimpleNamespace(cuda=cuda, distributed=SimpleNamespace(is_nccl_available=lambda: False),
                                     __version__="mock", version=SimpleNamespace(cuda="mock"))
        with patch.dict(sys.modules, {"torch": fake_torch}):
            state = {}
            _, result = gpu_probe._cuda_runtime(state, [GPU_A])
            self.assertEqual(result["devices"][0]["allocated_uuid"], GPU_A)
            self.assertTrue(state["gpu_compute_performed"])
            with self.assertRaisesRegex(RuntimeError, "does not match allocation"):
                gpu_probe._cuda_runtime({}, [GPU_B])

    def test_vllm_visibility_maps_only_allocated_uuid_after_pci_order_check(self):
        nvml = Mock()
        nvml.nvmlDeviceGetCount.return_value = 2
        nvml.nvmlDeviceGetHandleByIndex.side_effect = lambda index: index
        nvml.nvmlDeviceGetUUID.side_effect = lambda index: [GPU_A, GPU_B][index]
        nvml.nvmlDeviceGetPciInfo.side_effect = lambda index: SimpleNamespace(
            busId=[b"00000000:01:00.0", b"00000000:02:00.0"][index])
        with patch.dict(sys.modules, {"vllm": SimpleNamespace(), "vllm.third_party": SimpleNamespace(pynvml=nvml)}):
            with patch.dict(os.environ, {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": GPU_B}):
                report = gpu_probe._vllm_numeric_visibility([GPU_B])
        self.assertEqual(report["uuid_visibility"], GPU_B)
        self.assertEqual(report["numeric_visibility"], "1")
        self.assertEqual(len(report["mapping"]), 1)
        self.assertEqual(report["mapping"][0]["allocated_uuid"], GPU_B)
        self.assertNotIn(GPU_A, json.dumps(report))
        nvml.nvmlInit.assert_called_once_with()
        nvml.nvmlShutdown.assert_called_once_with()

    def test_vllm_visibility_unknown_uuid_or_non_pci_index_order_fails_closed(self):
        nvml = Mock()
        nvml.nvmlDeviceGetCount.return_value = 2
        nvml.nvmlDeviceGetHandleByIndex.side_effect = lambda index: index
        nvml.nvmlDeviceGetUUID.side_effect = lambda index: [GPU_A, GPU_B][index]
        unknown = "GPU-00000000-0000-0000-0000-000000000000"
        with patch.dict(sys.modules, {"vllm": SimpleNamespace(), "vllm.third_party": SimpleNamespace(pynvml=nvml)}):
            for buses, selected, expected in (
                    (["00000000:02:00.0", "00000000:01:00.0"], GPU_A, "NVML index order"),
                    (["00000000:01:00.0", "00000000:02:00.0"], unknown, "not present")):
                nvml.nvmlDeviceGetPciInfo.side_effect = lambda index: SimpleNamespace(busId=buses[index])
                with self.subTest(buses=buses, selected=selected):
                    with patch.dict(os.environ, {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": selected}):
                        with self.assertRaisesRegex(ValueError, expected):
                            gpu_probe._vllm_numeric_visibility([selected])
        self.assertEqual(nvml.nvmlShutdown.call_count, 2)


if __name__ == "__main__":
    unittest.main()
