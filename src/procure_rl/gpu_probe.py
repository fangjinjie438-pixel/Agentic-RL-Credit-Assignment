"""Bounded S0 CUDA checks on explicitly allocated GPU UUIDs only.

The public ``run_gpu_probe`` accepts allocation evidence, probe names and an
optional local 0.6B model, returning a JSON-serializable report for the project
CLI/run manifest. It defaults to a CPU-only dry run. ML dependencies are imported
only inside fresh, UUID-restricted project-venv subprocesses after validation.
Workers exchange JSON files, while stdout/stderr remain diagnostic logs rather
than a state protocol. No system Python, CUDA Toolkit or automatic GPU selection
is used. CPU tests exercise authorization, isolation and failure reporting only.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any, Sequence


PROBES = ("torch", "nccl", "vllm", "attention")
GPU_UUID = re.compile(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")


def _validate_request(gpu_uuids: Sequence[str], allocation_source: str,
                      probes: Sequence[str], timeout: float, execute: bool,
                      model_path: Path | None) -> list[str]:
    """Validate CPU-side inputs before creating any process or ML import."""
    uuids = list(gpu_uuids)
    if isinstance(gpu_uuids, str) or not all(isinstance(x, str) and GPU_UUID.fullmatch(x) for x in uuids):
        raise ValueError("gpu_uuids must contain complete NVIDIA GPU UUIDs, never indices or prefixes")
    if len(set(x.lower() for x in uuids)) != len(uuids):
        raise ValueError("duplicate GPU UUIDs are forbidden")
    if len(uuids) > 3:
        raise ValueError("S0 probes are limited to at most three allocated GPUs")
    if not isinstance(allocation_source, str):
        raise ValueError("allocation_source must be an explicit allocation description")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number")
    if not probes or isinstance(probes, str) or len(set(probes)) != len(probes) or any(p not in PROBES for p in probes):
        raise ValueError(f"probes must be a nonempty unique selection from {PROBES}")
    if execute and (not uuids or not allocation_source.strip()):
        raise ValueError("--execute requires explicit allocated GPU UUIDs and allocation_source; free memory is not allocation")
    if execute and "nccl" in probes and len(uuids) < 2:
        raise ValueError("NCCL requires at least two explicitly allocated GPU UUIDs")
    if execute and "attention" in probes and len(uuids) != 1:
        raise ValueError("the FlashAttention probe requires exactly one allocated GPU UUID")
    if execute and "vllm" in probes:
        if len(uuids) != 1:
            raise ValueError("run the TP=1 vLLM probe separately with exactly one allocated GPU UUID")
        if model_path is None or not model_path.is_dir() or not (model_path / "config.json").is_file():
            raise ValueError("vLLM requires a downloaded local model directory containing config.json")
        config = json.loads((model_path / "config.json").read_text(encoding="utf-8"))
        # S0 deliberately loads the specified Qwen3-0.6B smoke model only.
        if config.get("model_type") != "qwen3" or config.get("hidden_size") != 1024 or config.get("num_hidden_layers") != 28:
            raise ValueError("the S0 vLLM probe is restricted to the local Qwen3-0.6B smoke model")
    return uuids


def _validate_project_interpreter(project_root: Path) -> None:
    """Require the project GPU venv and independently bootstrapped base Python."""
    expected = project_root / ".venv-gpu"
    if Path(sys.prefix).absolute() != expected or not Path(sys.base_prefix).resolve().is_relative_to((project_root / ".tools/python").resolve()):
        raise ValueError("GPU execution requires this project's .venv-gpu and .tools/python interpreter")


def _terminate_process_group(process: subprocess.Popen[str]) -> tuple[str, str]:
    """Reap the probe and its own NCCL/vLLM child processes after a timeout."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return process.communicate(timeout=3.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate()


def _run_worker(request: dict[str, Any], project_root: Path,
                timeout: float) -> dict[str, Any]:
    """Launch one bounded process tree, using UUID visibility set before import."""
    env = os.environ.copy()
    # Wheel runtime libraries and the system CUDA driver use their normal
    # loader paths. Shared environment overrides must not inject a Toolkit,
    # compiler, headers or alternate Python packages into this project venv.
    for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_RUN_PATH", "LIBRARY_PATH",
                 "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
                 "COMPILER_PATH", "GCC_EXEC_PREFIX", "CMAKE_PREFIX_PATH",
                 "CUDAHOSTCXX", "CUDAHOSTCC", "TRITON_LIBCUDA_PATH",
                 "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE",
                 "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "NCCL_HOME", "NCCL_ROOT", "CUDNN_ROOT"):
        env.pop(name, None)
    env.update({
        "CUDA_VISIBLE_DEVICES": ",".join(request["gpu_uuids"]),
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID", "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
        "TOKENIZERS_PARALLELISM": "false", "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "VLLM_ATTENTION_BACKEND": "FLASH_ATTN", "VLLM_NO_USAGE_STATS": "1",
        "HF_HOME": str(project_root / ".cache/huggingface"),
        "VLLM_CACHE_ROOT": str(project_root / ".cache/vllm"),
        "VLLM_CONFIG_ROOT": str(project_root / ".cache/vllm-config"),
        "TORCHINDUCTOR_CACHE_DIR": str(project_root / ".cache/torchinductor"),
        "TRITON_CACHE_DIR": str(project_root / ".cache/triton"),
        "CUDA_CACHE_PATH": str(project_root / ".cache/cuda"),
        "TORCH_EXTENSIONS_DIR": str(project_root / ".cache/torch_extensions"),
        "XDG_CACHE_HOME": str(project_root / ".cache"),
        # A missing project Toolkit must fail explicitly instead of using the
        # shared /usr/local/cuda Toolkit through torch's default detection.
        "CUDA_HOME": str(project_root / ".tools/cuda"),
        "CUDA_PATH": str(project_root / ".tools/cuda"),
        "CUDACXX": str(project_root / ".tools/cuda/bin/nvcc"),
        "NVCC": str(project_root / ".tools/cuda/bin/nvcc"),
        "CUDA_ROOT": str(project_root / ".tools/cuda"),
        "CUDAToolkit_ROOT": str(project_root / ".tools/cuda"),
        "CMAKE_CUDA_COMPILER": str(project_root / ".tools/cuda/bin/nvcc"),
        "CC": str(project_root / "scripts/toolchain/cc"),
        "CXX": str(project_root / "scripts/toolchain/cxx"),
        # Driver-only project directory, explicitly prepared from the installed
        # NVIDIA driver; this is not a CUDA Toolkit or a system ldconfig probe.
        "TRITON_LIBCUDA_PATH": str(project_root / ".tools/cuda-driver/lib"),
        "PYTHONNOUSERSITE": "1", "VIRTUAL_ENV": str(project_root / ".venv-gpu"),
    })
    env["PATH"] = os.pathsep.join(path for path in env.get("PATH", "").split(os.pathsep)
                                   if not path.startswith("/usr/local/cuda"))
    env["PYTHONPATH"] = str(project_root / "src")
    # Optional library hardware utilities should be absent rather than finding
    # global developer tools; compiler wrappers and Python are project-local.
    env["PATH"] = os.pathsep.join((str(project_root / ".venv-gpu/bin"),
                                   str(project_root / "scripts/toolchain")))
    argv = [sys.executable, "-m", "procure_rl.gpu_probe", "--worker"]
    started = time.monotonic()
    result: dict[str, Any] = {
        "probe": request["probe"], "argv": argv,
        "visible_gpu_uuids": request["gpu_uuids"],
        "status": "failed", "returncode": None, "timeout": False,
        "gpu_compute_performed": False,
    }
    with tempfile.TemporaryDirectory(prefix="procure-s0-probe-") as temporary:
        request = {**request, "result_path": str(Path(temporary) / "result.json")}
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(argv, cwd=project_root, env=env,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True,
                                       start_new_session=True, shell=False)
            result["gpu_compute_performed"] = None  # Unknown until the worker supplies evidence.
            stdout, stderr = process.communicate(json.dumps(request), timeout=timeout)
            result.update(stdout=stdout, stderr=stderr, returncode=process.returncode)
        except subprocess.TimeoutExpired:
            assert process is not None
            stdout, stderr = _terminate_process_group(process)
            result.update(status="timeout", timeout=True, stdout=stdout,
                          stderr=stderr, returncode=process.returncode,
                          error=f"probe exceeded {timeout:g} seconds; its process group was terminated")
        except (OSError, ValueError) as exc:
            result.update(error=f"{type(exc).__name__}: {exc}", stdout="", stderr="")
            if process is not None:
                try:
                    stdout, stderr = _terminate_process_group(process)
                    result.update(stdout=stdout, stderr=stderr, returncode=process.returncode)
                except (OSError, ValueError) as cleanup_exc:
                    # A text-decoding failure can recur while draining pipes;
                    # kill/reap without decoding instead of leaving a GPU child.
                    result["cleanup_error"] = f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=3.0)
                        result["returncode"] = process.returncode
                    except subprocess.TimeoutExpired:
                        result["cleanup_error"] += "; process did not exit after SIGKILL within 3 seconds"
        except BaseException:
            if process is not None:
                _terminate_process_group(process)
            raise
        result_path = Path(request["result_path"])
        if result_path.is_file():
            try:
                worker = json.loads(result_path.read_text(encoding="utf-8"))
                result["worker"] = worker
                result["gpu_compute_performed"] = worker.get("gpu_compute_performed")
                if not result["timeout"] and "error" not in result and result["returncode"] == 0 and worker.get("status") == "passed":
                    result["status"] = "passed"
                elif not result["timeout"] and "error" not in result:
                    result["error"] = worker.get("error", "worker did not pass")
            except (OSError, ValueError) as exc:
                result["error"] = f"invalid worker report: {type(exc).__name__}: {exc}"
        elif not result["timeout"] and "error" not in result:
            result["error"] = "worker exited without a structured result file"
    result["duration_seconds"] = round(time.monotonic() - started, 6)
    return result


def run_gpu_probe(*, gpu_uuids: Sequence[str] = (), allocation_source: str = "",
                  execute: bool = False, probes: Sequence[str] = ("torch",),
                  model_path: Path | None = None, model_revision: str | None = None,
                  timeout: float = 180.0,
                  project_root: Path | None = None) -> dict[str, Any]:
    """Return configuration-only evidence by default; execute only explicit probes.

    A successful subset reports that subset only. It never establishes verl,
    LoRA/FSDP2 training or full candidate-stack compatibility. Each probe uses a
    fresh subprocess, so model/communication resources are released between them.
    """
    root = (project_root or Path.cwd()).resolve()
    local_model = None if model_path is None else Path(model_path).resolve()
    uuids = _validate_request(gpu_uuids, allocation_source, probes, timeout,
                             execute, local_model)
    report: dict[str, Any] = {
        "schema_version": 1, "stage": "S0", "status": "dry_run",
        "allocation": {"gpu_uuids": uuids, "source": allocation_source,
                       "status": "explicit_user_claim" if uuids and allocation_source.strip() else "not_confirmed"},
        "execute": execute, "requested_probes": list(probes),
        "model_path": None if local_model is None else str(local_model),
        "model_revision": model_revision, "seed": 0,
        "gpu_execution_attempted": False, "gpu_compute_performed": False,
        "gpu_validation": "not_run", "validation_level": "configuration_only",
        "candidate_stack_compatibility": "not_established",
        "training_lora_fsdp2_validation": "not_run", "checks": {},
    }
    if not execute:
        report["note"] = "CPU-only dry run; no ML import, CUDA context, model load or child process"
        return report
    _validate_project_interpreter(root)
    report.update(gpu_execution_attempted=True, validation_level="real_gpu_probe_subset")
    for probe in probes:
        request = {"probe": probe, "gpu_uuids": uuids,
                   "allocation_source": allocation_source, "execute": True,
                   "project_root": str(root), "timeout": timeout,
                   "model_path": report["model_path"], "model_revision": model_revision}
        report["checks"][probe] = _run_worker(request, root, timeout)
    values = list(report["checks"].values())
    passed = all(value["status"] == "passed" for value in values)
    compute_values = [value["gpu_compute_performed"] for value in values]
    report.update(status="passed" if passed else "failed",
                  gpu_validation="passed" if passed else "failed",
                  gpu_compute_performed=True if True in compute_values else None if None in compute_values else False)
    return report


def _cuda_runtime(state: dict[str, Any], uuids: Sequence[str]) -> tuple[Any, dict[str, Any]]:
    """Initialize CUDA only after worker allocation/visibility checks have passed."""
    import torch

    count = torch.cuda.device_count()
    if count != len(uuids):
        raise RuntimeError(f"visible CUDA device count {count} differs from allocated count {len(uuids)}")
    torch.cuda.init()
    state["gpu_compute_performed"] = True
    devices = []
    for index, expected_uuid in enumerate(uuids):
        properties = torch.cuda.get_device_properties(index)
        actual_uuid = str(getattr(properties, "uuid", "unknown"))
        # torch2.7.1 _CUuuid.__str__ emits the raw 8-4-4-4-12 value,
        # while nvidia-smi/CUDA_VISIBLE_DEVICES use a GPU- prefix.
        normalized_uuid = actual_uuid.lower().removeprefix("gpu-")
        if actual_uuid != "unknown" and normalized_uuid != expected_uuid.lower().removeprefix("gpu-"):
            raise RuntimeError(f"logical device {index} UUID {actual_uuid} does not match allocation {expected_uuid}")
        devices.append({"logical_index": index, "allocated_uuid": expected_uuid,
                        "runtime_uuid": actual_uuid, "name": properties.name,
                        "total_memory_bytes": properties.total_memory,
                        "compute_capability": list(torch.cuda.get_device_capability(index))})
    nccl = torch.cuda.nccl.version() if torch.distributed.is_nccl_available() else None
    return torch, {"torch_version": torch.__version__, "torch_cuda_runtime": torch.version.cuda,
                   "nccl_runtime_version": nccl, "devices": devices}


def _torch_probe(request: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Run tiny BF16 forward/backward and real cross-device copy checks."""
    torch, evidence = _cuda_runtime(state, request["gpu_uuids"])
    torch.manual_seed(0)
    matrix_results = []
    for index in range(len(request["gpu_uuids"])):
        with torch.cuda.device(index):
            if not torch.cuda.is_bf16_supported():
                raise RuntimeError(f"logical GPU {index} does not support BF16")
            x = torch.ones((64, 64), dtype=torch.bfloat16, device=f"cuda:{index}", requires_grad=True)
            y = x @ x
            loss = y.float().mean()
            loss.backward()
            torch.cuda.synchronize(index)
            if not bool(torch.isfinite(loss).item()) or x.grad is None or not bool(torch.isfinite(x.grad).all().item()):
                raise RuntimeError(f"nonfinite BF16 forward/backward on logical GPU {index}")
            if float(loss.item()) != 64.0:
                raise RuntimeError(f"unexpected BF16 matmul result on logical GPU {index}")
            matrix_results.append({"logical_index": index, "dtype": "bfloat16",
                                   "shape": [64, 64], "loss": float(loss.item()),
                                   "backward": "passed", "peak_allocated_bytes": torch.cuda.max_memory_allocated(index)})
            del x, y, loss
    p2p = []
    for source in range(len(request["gpu_uuids"])):
        for target in range(len(request["gpu_uuids"])):
            if source == target:
                continue
            capable = bool(torch.cuda.can_device_access_peer(source, target))
            if not capable:
                p2p.append({"source": source, "target": target, "peer_access": False,
                            "copy": "not_run", "reason": "CUDA peer access unsupported"})
                continue
            tensor = torch.arange(1024, dtype=torch.float32, device=f"cuda:{source}")
            torch.cuda.synchronize(source)
            started = time.monotonic()
            copied = tensor.to(device=f"cuda:{target}", non_blocking=False)
            torch.cuda.synchronize(target)
            elapsed = time.monotonic() - started
            if not torch.equal(copied.cpu(), torch.arange(1024, dtype=torch.float32)):
                raise RuntimeError(f"P2P copy corruption between logical GPUs {source} and {target}")
            p2p.append({"source": source, "target": target, "peer_access": True,
                        "copy": "passed", "bytes": tensor.numel() * tensor.element_size(),
                        "duration_seconds": elapsed,
                        "note": "small correctness check; not a bandwidth benchmark"})
            del tensor, copied
    if p2p and not all(pair["peer_access"] and pair["copy"] == "passed" for pair in p2p):
        # Preserve runtime and matrix results while marking requested P2P evidence incomplete.
        state["partial_evidence"] = {**evidence, "bf16": matrix_results, "p2p": p2p}
        raise RuntimeError("at least one allocated GPU pair lacks validated peer access and copy")
    return {**evidence, "bf16": matrix_results, "p2p": p2p,
            "p2p_status": "passed" if p2p else "not_applicable_single_gpu"}


def _nccl_rank(rank: int, world_size: int, init_path: str,
               output_directory: str, timeout: float) -> None:
    """One spawn rank with one assigned logical device and a tiny NCCL reduction."""
    import torch
    import torch.distributed as dist

    torch.cuda.set_device(rank)
    try:
        dist.init_process_group("nccl", init_method=Path(init_path).as_uri(),
                                rank=rank, world_size=world_size,
                                timeout=timedelta(seconds=max(1, min(timeout, 60))))
        tensor = torch.full((16,), rank + 1, dtype=torch.float32, device=f"cuda:{rank}")
        started = time.monotonic()
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
        torch.cuda.synchronize(rank)
        expected = world_size * (world_size + 1) / 2
        if not bool(torch.all(tensor == expected).item()):
            raise RuntimeError(f"NCCL rank {rank}: incorrect all_reduce result")
        result = {"rank": rank, "logical_gpu": rank, "status": "passed",
                  "elements": 16, "dtype": "float32", "expected": expected,
                  "result": tensor.cpu().tolist(),
                  "duration_seconds": time.monotonic() - started}
        (Path(output_directory) / f"rank-{rank}.json").write_text(json.dumps(result), encoding="utf-8")
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


def _nccl_probe(request: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Spawn at most three allocated ranks; parent timeout bounds the whole group."""
    torch, evidence = _cuda_runtime(state, request["gpu_uuids"])
    if not torch.distributed.is_nccl_available():
        raise RuntimeError("torch.distributed NCCL backend is unavailable")
    world_size = len(request["gpu_uuids"])
    with tempfile.TemporaryDirectory(prefix="procure-s0-nccl-") as temporary:
        torch.multiprocessing.spawn(_nccl_rank,
                                    args=(world_size, str(Path(temporary) / "store"),
                                          temporary, request["timeout"]),
                                    nprocs=world_size, join=True)
        ranks = [json.loads((Path(temporary) / f"rank-{rank}.json").read_text(encoding="utf-8"))
                 for rank in range(world_size)]
    return {**evidence, "backend": "nccl", "world_size": world_size,
            "start_method": "spawn", "ranks": ranks,
            "note": "tiny correctness check; not throughput or training validation"}


def _attention_probe(request: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Exercise the separately installed FlashAttention wheel with tiny BF16 IO."""
    torch, evidence = _cuda_runtime(state, request["gpu_uuids"])
    import flash_attn
    from flash_attn import flash_attn_func

    torch.manual_seed(0)
    shape = (1, 16, 2, 64)
    tensors = [torch.randn(shape, device="cuda:0", dtype=torch.bfloat16,
                           requires_grad=True) for _ in range(3)]
    torch.cuda.synchronize(0)
    started = time.monotonic()
    output = flash_attn_func(*tensors, dropout_p=0.0, causal=True)
    if tuple(output.shape) != shape or output.dtype != torch.bfloat16:
        raise RuntimeError("FlashAttention returned an unexpected output shape or dtype")
    loss = output.float().square().mean()
    loss.backward()
    torch.cuda.synchronize(0)
    if not bool(torch.isfinite(output).all().item()) or not bool(torch.isfinite(loss).item()):
        raise RuntimeError("FlashAttention produced a nonfinite forward result")
    if any(tensor.grad is None or not bool(torch.isfinite(tensor.grad).all().item()) for tensor in tensors):
        raise RuntimeError("FlashAttention produced missing or nonfinite q/k/v gradients")
    return {**evidence, "flash_attn_version": flash_attn.__version__,
            "torch_cxx11_abi": bool(torch._C._GLIBCXX_USE_CXX11_ABI),
            "logical_gpu": 0, "shape_qkv": list(shape), "dtype": "bfloat16",
            "causal": True, "dropout_p": 0.0, "forward": "passed",
            "backward_qkv": "passed", "loss": float(loss.item()),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(0),
            "duration_seconds": time.monotonic() - started,
            "scope": "tiny wheel kernel forward/backward only; not LoRA, FSDP2, multi-turn or training validation"}


def _vllm_numeric_visibility(gpu_uuids: Sequence[str]) -> dict[str, Any]:
    """Bridge allocated UUIDs to v0.10.0's numeric-only NVML platform interface.

    This performs NVML metadata reads only, creating no CUDA context. Numeric
    visibility is returned only when the complete NVML index order equals the
    PCI bus ordering requested from CUDA. The caller must first verify its
    current CUDA runtime UUID using ``_cuda_runtime``. No free-memory selection
    or unallocated device computation is permitted.
    """
    if len(gpu_uuids) != 1 or not GPU_UUID.fullmatch(gpu_uuids[0]):
        raise ValueError("vLLM visibility conversion requires exactly one complete allocated UUID")
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID":
        raise ValueError("vLLM numeric visibility requires CUDA_DEVICE_ORDER=PCI_BUS_ID")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != ",".join(gpu_uuids):
        raise ValueError("vLLM visibility conversion requires the original allocated UUID visibility")
    # v0.10.0 vendors NVML bindings. Importing this namespace only loads
    # vllm's lazy package initializer, not LLM/platform capability resolution.
    from vllm.third_party import pynvml

    def as_text(value: Any) -> str:
        return value.decode("ascii") if isinstance(value, bytes) else str(value)

    initialized = False
    try:
        pynvml.nvmlInit()
        initialized = True
        devices = []
        pci_order = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            uuid = as_text(pynvml.nvmlDeviceGetUUID(handle))
            bus_id = as_text(pynvml.nvmlDeviceGetPciInfo(handle).busId)
            match = re.fullmatch(r"([0-9a-fA-F]{4,8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])", bus_id)
            if match is None or not GPU_UUID.fullmatch(uuid):
                raise ValueError("NVML returned an unsupported PCI bus ID or GPU UUID")
            pci_order.append(tuple(int(part, 16) for part in match.groups()))
            devices.append({"nvml_index": index, "gpu_uuid": uuid, "pci_bus_id": bus_id})
        if not devices or len(set(pci_order)) != len(pci_order) or pci_order != sorted(pci_order):
            raise ValueError("NVML index order does not match unique ascending PCI_BUS_ID order; refusing numeric GPU visibility")
        by_uuid = {device["gpu_uuid"].lower(): device for device in devices}
        if len(by_uuid) != len(devices):
            raise ValueError("NVML returned duplicate GPU UUIDs")
        mapped = []
        for uuid in gpu_uuids:
            if uuid.lower() not in by_uuid:
                raise ValueError(f"allocated UUID {uuid} is not present in the NVML inventory")
            mapped.append({"allocated_uuid": uuid, **by_uuid[uuid.lower()]})
        return {"uuid_visibility": ",".join(gpu_uuids),
                "numeric_visibility": ",".join(str(device["nvml_index"]) for device in mapped),
                "cuda_device_order": "PCI_BUS_ID", "nvml_pci_index_order_verified": True,
                "mapping": mapped,
                "reason": "vLLM 0.10.0 platform physical_device_id requires numeric identifiers; UUID authorization and CUDA identity were verified before this conversion"}
    finally:
        if initialized:
            pynvml.nvmlShutdown()


def _vllm_probe(request: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Load local Qwen3-0.6B in a single-GPU eager engine and generate <=16 tokens."""
    torch, evidence = _cuda_runtime(state, request["gpu_uuids"])
    visibility = _vllm_numeric_visibility(request["gpu_uuids"])
    # torch's parent runtime is already restricted and identity-checked by UUID.
    # vLLM's NVML calls and fresh spawn workers need its equivalent numeric form.
    os.environ["CUDA_VISIBLE_DEVICES"] = visibility["numeric_visibility"]
    state["visibility_conversion"] = visibility
    import vllm
    from vllm import LLM, SamplingParams

    options = {"model": request["model_path"], "tokenizer": request["model_path"],
               "tensor_parallel_size": 1, "dtype": "bfloat16", "max_model_len": 512,
               "max_num_seqs": 1, "gpu_memory_utilization": 0.2, "enforce_eager": True,
               "disable_log_stats": True, "trust_remote_code": False,
               "enable_prefix_caching": False, "seed": 0,
               "max_num_batched_tokens": 512, "swap_space": 0,
               # v0.10.0 entrypoints/llm.py accepts an integer optimization
               # level; eager mode alone disables CUDA graphs, not compilation.
               "compilation_config": 0}
    engine = LLM(**options)
    try:
        tokenizer = engine.get_tokenizer()
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": "Reply with exactly the word OK."}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        started = time.monotonic()
        outputs = engine.generate([prompt], SamplingParams(temperature=0, max_tokens=16), use_tqdm=False)
        torch.cuda.synchronize(0)
        duration = time.monotonic() - started
        if len(outputs) != 1 or len(outputs[0].outputs) != 1 or not outputs[0].outputs[0].token_ids:
            raise RuntimeError("vLLM returned no generated tokens")
        output = outputs[0].outputs[0]
        return {**evidence, "vllm_version": vllm.__version__, "engine_options": options,
                "visibility_conversion": visibility,
                "enable_thinking": False, "max_output_tokens": 16,
                "generated_token_ids": list(output.token_ids), "text": output.text,
                "finish_reason": output.finish_reason, "duration_seconds": duration,
                "model_revision": request["model_revision"],
                "scope": "single prompt only; not multi-turn, LoRA, FSDP2 or RL validation"}
    finally:
        # Fixed v0.10.0 V1 exposes engine_core.shutdown(); V0 exposes the
        # executor's shutdown(). Do not depend on interpreter GC for cleanup.
        core = getattr(engine.llm_engine, "engine_core", None)
        if core is not None:
            core.shutdown()
        elif (executor := getattr(engine.llm_engine, "model_executor", None)) is not None:
            executor.shutdown()


def _worker_main() -> int:
    """Internal JSON worker protocol; re-check authorization before any ML import."""
    request = json.loads(sys.stdin.read())
    state: dict[str, Any] = {"status": "failed", "gpu_compute_performed": False}
    result_path = Path(request["result_path"])
    try:
        root = Path(request["project_root"]).resolve()
        _validate_request(request["gpu_uuids"], request["allocation_source"],
                          (request["probe"],), request["timeout"],
                          request["execute"],
                          None if request["model_path"] is None else Path(request["model_path"]))
        if request["execute"] is not True:
            raise ValueError("worker requires explicit execute=True")
        _validate_project_interpreter(root)
        if os.environ.get("CUDA_VISIBLE_DEVICES") != ",".join(request["gpu_uuids"]):
            raise ValueError("worker CUDA_VISIBLE_DEVICES does not exactly match allocated UUIDs")
        state["evidence"] = {"torch": _torch_probe, "nccl": _nccl_probe, "attention": _attention_probe,
                             "vllm": _vllm_probe}[request["probe"]](request, state)
        state["status"] = "passed"
    except Exception as exc:
        state.update(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    result_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if state["status"] == "passed" else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone CPU dry-run / guarded GPU entry; normal CLI adds run manifests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gpu-uuid", action="append", default=[])
    parser.add_argument("--allocation-source", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--probe", action="append", choices=PROBES)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--model-revision")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    if args.worker:
        return _worker_main()
    try:
        report = run_gpu_probe(gpu_uuids=args.gpu_uuid,
                               allocation_source=args.allocation_source,
                               execute=args.execute, probes=args.probe or ("torch",),
                               model_path=args.model_path, model_revision=args.model_revision,
                               timeout=args.timeout)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["status"] == "failed" else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "gpu_compute_performed": False,
                          "gpu_validation": "not_run", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
