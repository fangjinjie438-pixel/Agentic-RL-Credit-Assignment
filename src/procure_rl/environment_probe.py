"""Probe S0 installed metadata and upstream imports in isolated CPU subprocesses.

The CPU CLI calls ``build_probe_spec`` or ``collect_environment_report``; neither
imports an ML package in the parent. Each actual import uses this file as a child
script under the project's GPU interpreter with CUDA devices hidden, offline
model access, bounded runtime, and child process execution forbidden. Structured
child JSON and raw stdout/stderr are retained separately in the returned report.
These checks establish import evidence only, never GPU/BF16 execution or training.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from typing import Any, Callable


VERL_COMMIT = "d62da4950573d7a4b7ef2362337952e7ab59e78d"
RESULT_PREFIX = "PROCURE_RL_ENV_PROBE_RESULT="
BLOCKED_EXECUTIONS: list[str] = []
DISTRIBUTIONS: dict[str, str | None] = {
    "torch": "2.7.1+cu126", "torchvision": "0.22.1+cu126",
    "torchaudio": "2.7.1+cu126", "vllm": "0.10.0+cu126",
    "transformers": "4.53.2", "verl": "0.6.1", "peft": "0.16.0",
    "accelerate": "1.8.1", "torchdata": "0.11.0", "xformers": "0.0.31",
    "ray": None, "tensordict": None,
    "flash-attn": None, "nvidia-cuda-runtime-cu12": None,
    "nvidia-nccl-cu12": None,
}
PROBE_DEFINITIONS = (
    {"id": "torch", "module": "torch", "attributes": ["bfloat16"]},
    {"id": "torchvision", "module": "torchvision", "attributes": ["ops"]},
    {"id": "torchaudio", "module": "torchaudio", "attributes": ["load"]},
    {"id": "xformers_ops", "module": "xformers.ops", "attributes": [
        "memory_efficient_attention"]},
    {"id": "flash_attn", "module": "flash_attn", "attributes": [
        "flash_attn_func", "flash_attn_varlen_func"]},
    {"id": "torch_fsdp2", "module": "torch.distributed.fsdp", "attributes": [
        "fully_shard", "FSDPModule", "MixedPrecisionPolicy", "CPUOffloadPolicy"]},
    {"id": "transformers", "module": "transformers", "attributes": [
        "AutoTokenizer", "AutoModelForCausalLM"]},
    {"id": "qwen3_config", "module": "transformers.models.qwen3.configuration_qwen3",
     "attributes": ["Qwen3Config"]},
    {"id": "qwen3_model", "module": "transformers.models.qwen3.modeling_qwen3",
     "attributes": ["Qwen3ForCausalLM"]},
    {"id": "peft", "module": "peft", "attributes": ["LoraConfig", "get_peft_model"]},
    {"id": "accelerate", "module": "accelerate", "attributes": ["Accelerator"]},
    {"id": "torchdata", "module": "torchdata.stateful_dataloader", "attributes": [
        "StatefulDataLoader"]},
    {"id": "ray", "module": "ray", "attributes": ["init", "remote"]},
    {"id": "tensordict", "module": "tensordict", "attributes": ["TensorDict"]},
    {"id": "vllm", "module": "vllm", "attributes": ["LLM", "SamplingParams"]},
    {"id": "verl", "module": "verl", "attributes": ["DataProto"]},
    {"id": "verl_main_ppo", "module": "verl.trainer.main_ppo", "attributes": [
        "main", "run_ppo"]},
    {"id": "verl_core_algos", "module": "verl.trainer.ppo.core_algos", "attributes": [
        "register_adv_est", "compute_grpo_outcome_advantage"]},
    {"id": "verl_fsdp_utils", "module": "verl.utils.fsdp_utils", "attributes": [
        "apply_fsdp2", "collect_lora_params"]},
    {"id": "verl_fsdp_worker", "module": "verl.workers.fsdp_workers", "attributes": [
        "ActorRolloutRefWorker", "AsyncActorRolloutRefWorker"]},
    {"id": "verl_vllm_rollout", "module": "verl.workers.rollout.vllm_rollout.vllm_rollout_spmd",
     "attributes": ["vLLMRollout", "vLLMAsyncRollout"]},
    {"id": "verl_vllm_async_server", "module": "verl.workers.rollout.vllm_rollout.vllm_async_server",
     "attributes": ["vLLMHttpServerBase", "vLLMHttpServer", "vLLMReplica"]},
    {"id": "verl_agent_loop", "module": "verl.experimental.agent_loop.agent_loop",
     "attributes": ["AgentLoopBase", "AgentLoopOutput", "AgentLoopManager"]},
    {"id": "verl_tool_agent_loop", "module": "verl.experimental.agent_loop.tool_agent_loop",
     "attributes": ["ToolAgentLoop"]},
)
ENVIRONMENT_OVERRIDES = {
    "CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "none",
    "PYTORCH_NVML_BASED_CUDA_CHECK": "1",
    "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1", "VLLM_NO_USAGE_STATS": "1",
    "DO_NOT_TRACK": "1", "PYTHONDONTWRITEBYTECODE": "1",
    "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "2",
    "MKL_NUM_THREADS": "2",
}


def _project_python(project_root: Path, python_executable: str | Path | None) -> Path:
    """Require the project GPU venv and its project-managed base interpreter."""
    expected = project_root / ".venv-gpu" / "bin" / "python"
    requested = expected if python_executable is None else Path(python_executable)
    if not requested.is_absolute():
        requested = project_root / requested
    # Do not resolve before comparing: venv/bin/python is a symlink to the base.
    requested = Path(os.path.abspath(requested))
    if requested != expected:
        raise ValueError("Only the project's .venv-gpu/bin/python is allowed")
    if not requested.is_file() or not os.access(requested, os.X_OK):
        raise ValueError(f"Project GPU interpreter is unavailable: {requested}")
    base_root = (project_root / ".tools" / "python").resolve()
    if not requested.resolve().is_relative_to(base_root):
        raise ValueError("GPU venv must use an interpreter inside project .tools/python")
    return requested


def build_probe_spec(
    project_root: str | Path, python_executable: str | Path | None = None,
    command_timeout: float = 120.0,
) -> dict[str, Any]:
    """Return JSON-ready commands and policy without importing ML or spawning."""
    if not math.isfinite(command_timeout) or command_timeout <= 0:
        raise ValueError("command_timeout must be finite and positive")
    root = Path(project_root).resolve()
    python = _project_python(root, python_executable)
    script = str(Path(__file__).resolve())
    definitions = [{"id": "metadata", "kind": "metadata"}, *(
        {"kind": "import", **item} for item in PROBE_DEFINITIONS)]
    commands = []
    for definition in definitions:
        commands.append({
            "id": definition["id"], "definition": definition,
            "argv": [str(python), "-I", script, "--child", json.dumps(definition)],
            "timeout_seconds": command_timeout,
        })
    return {
        "schema_version": 1, "project_root": str(root),
        "python_executable": str(python), "resolved_python": str(python.resolve()),
        "environment_overrides": dict(ENVIRONMENT_OVERRIDES),
        "policy": {
            "parent_imports_ml_libraries": False, "gpu_devices_hidden": True,
            "imports_run_in_independent_subprocesses": True,
            "child_process_execution": "forbidden", "runs_toolkit_binaries": False,
            "runs_models_or_training": False, "runs_gpu_compute": False,
            "metadata_and_imports_are_not_gpu_validation": True,
        },
        "commands": commands,
    }


def _distribution_metadata() -> dict[str, Any]:
    """Read versions and VCS identifiers; omit direct URLs and their credentials."""
    result: dict[str, Any] = {}
    for name, expected in DISTRIBUTIONS.items():
        item: dict[str, Any] = {"candidate_version": expected}
        try:
            distribution = metadata.distribution(name)
            version = distribution.version
            item.update(status="installed", installed_version=version,
                        version_comparison="unconstrained" if expected is None else
                        "matches_metadata_only" if version == expected else "mismatch")
            direct_url = distribution.read_text("direct_url.json")
            if direct_url:
                try:
                    data = json.loads(direct_url)
                    item["direct_url"] = {"url_omitted_to_protect_credentials": True}
                    vcs = data.get("vcs_info", {})
                    if vcs:
                        item["direct_url"]["vcs_info"] = {
                            key: vcs[key] for key in ("vcs", "commit_id", "requested_revision")
                            if key in vcs}
                    if name == "verl":
                        item["candidate_commit"] = VERL_COMMIT
                        item["commit_comparison"] = (
                            "matches_commit_only" if vcs.get("commit_id") == VERL_COMMIT
                            else "mismatch" if vcs.get("commit_id") else "not_recorded")
                except (AttributeError, TypeError, ValueError):
                    item["direct_url"] = {"status": "unreadable", "url_omitted_to_protect_credentials": True}
            elif name == "verl":
                item.update(candidate_commit=VERL_COMMIT, commit_comparison="not_recorded")
        except metadata.PackageNotFoundError:
            item.update(status="not_installed", installed_version=None, version_comparison="missing")
        except (OSError, ValueError, UnicodeError) as error:
            item.update(status="metadata_error", error=str(error), version_comparison="unknown")
        result[name] = item
    return result


def _execute_child_probe(definition: dict[str, Any]) -> dict[str, Any]:
    """Execute one fixed probe; invoked only in masked children, or mocked tests."""
    result: dict[str, Any] = {
        "id": definition["id"], "status": "failed",
        "python": {"executable": sys.executable, "prefix": sys.prefix,
                   "base_prefix": sys.base_prefix, "version": platform.python_version()},
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    if result["cuda_visible_devices"] != "":
        result["error"] = "CUDA_VISIBLE_DEVICES must be explicitly empty for import probes"
        return result
    try:
        if definition["kind"] == "metadata":
            result["distributions"] = _distribution_metadata()
            # Optional metadata is reported independently, not silently discarded.
            violations = [name for name, item in result["distributions"].items()
                          if item["candidate_version"] is not None and
                          (item["status"] != "installed" or item["version_comparison"] != "matches_metadata_only")]
            verl = result["distributions"]["verl"]
            if verl.get("commit_comparison") != "matches_commit_only":
                violations.append("verl_commit")
            result.update(status="passed" if not violations else "failed",
                          candidate_metadata_violations=violations)
        else:
            result["module"] = definition["module"]
            module = importlib.import_module(definition["module"])
            result["module_file"] = getattr(module, "__file__", None)
            attributes: dict[str, str] = {}
            for name in definition.get("attributes", []):
                getattr(module, name)
                attributes[name] = "present_only_not_executed"
            result["attributes"] = attributes
            if definition["id"] == "torch":
                # Static fields only: never call cuda.is_available/device_count/
                # is_bf16_supported, which would become a hardware probe.
                cuda_runtime = getattr(module.version, "cuda", None)
                result["torch"] = {
                    "version": str(module.__version__), "compiled_cuda_runtime": cuda_runtime,
                    "candidate_compiled_cuda_runtime": "12.6",
                    "cuda_runtime_comparison": "matches_build_metadata_only" if cuda_runtime == "12.6" else "mismatch",
                    "bfloat16_dtype_present": hasattr(module, "bfloat16"),
                    "hardware_bf16_support": "not_queried_no_gpu_execution",
                    "nccl_runtime_version": "not_queried_no_gpu_execution",
                }
                result["status"] = "passed" if cuda_runtime == "12.6" else "failed"
            else:
                result["status"] = "passed"
    except Exception as error:
        result.update(status="failed", error_type=type(error).__name__, error=str(error),
                      traceback=traceback.format_exc())
    torch_module = sys.modules.get("torch")
    if torch_module is not None:
        # is_initialized only inspects PyTorch state; it does not initialize CUDA.
        initialized = torch_module.cuda.is_initialized()
        result["torch_cuda_initialized_after_import"] = initialized
        if initialized:
            result["status"] = "failed"
            result["policy_violation"] = "Import unexpectedly initialized CUDA"
    result["blocked_process_executables"] = list(BLOCKED_EXECUTIONS)
    return result


def _forbid_child_process(event: str, arguments: tuple[Any, ...]) -> None:
    """Prevent imported modules from executing a Toolkit, compiler, or shell."""
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn"}:
        executable = str(arguments[0]) if arguments else "unknown"
        BLOCKED_EXECUTIONS.append(executable)
        # Libraries legitimately catch a missing optional hardware utility.
        # Preserve that fallback without ever starting the utility itself.
        raise FileNotFoundError(f"S0 import probe forbids {event}: {executable}; no Toolkit execution allowed")


def _child_main(definition: dict[str, Any]) -> int:
    """Emit one machine-readable payload alongside retained library output."""
    allowed = [{"id": "metadata", "kind": "metadata"}, *(
        {"kind": "import", **item} for item in PROBE_DEFINITIONS)]
    if definition not in allowed:
        raise ValueError("Unknown environment import probe")
    sys.addaudithook(_forbid_child_process)
    result = _execute_child_probe(definition)
    print(RESULT_PREFIX + json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["status"] == "passed" else 1


def _text(value: Any) -> str:
    """Preserve byte output from a timeout without breaking JSON serialization."""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else "" if value is None else str(value)


def _run_probe(command: dict[str, Any], root: Path) -> dict[str, Any]:
    """Run a fixed child and retain raw evidence even on timeout or import error."""
    started = time.monotonic()
    result = {"id": command["id"], "argv": command["argv"],
              "timeout_seconds": command["timeout_seconds"], "status": "failed",
              "returncode": None, "stdout": "", "stderr": "", "result": None}
    environment = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "CUDA_HOME", "CUDA_PATH", "CUDACXX",
                "LD_LIBRARY_PATH", "LD_PRELOAD", "LIBRARY_PATH", "CPATH",
                "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH"):
        environment.pop(key, None)
    environment.update(ENVIRONMENT_OVERRIDES)
    environment.update(HF_HOME=str(root / ".cache" / "huggingface"),
                       XDG_CACHE_HOME=str(root / ".cache"),
                       TRITON_CACHE_DIR=str(root / ".cache" / "triton"),
                       TORCH_EXTENSIONS_DIR=str(root / ".cache" / "torch_extensions"))
    # Libraries do not need PATH to import; do not expose shared Toolkit binaries.
    environment["PATH"] = str(root / ".venv-gpu" / "bin")
    try:
        completed = subprocess.run(command["argv"], cwd=root, env=environment,
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=command["timeout_seconds"],
                                   check=False, shell=False)
        result.update(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
        payloads = [line[len(RESULT_PREFIX):] for line in completed.stdout.splitlines()
                    if line.startswith(RESULT_PREFIX)]
        if len(payloads) != 1:
            result["protocol_error"] = "Expected exactly one structured child result"
        else:
            try:
                child = json.loads(payloads[0])
                if not isinstance(child, dict) or child.get("id") != command["id"]:
                    raise ValueError("Child result does not match probe id")
                result["result"] = child
                if completed.returncode == 0 and child.get("status") == "passed" and child.get("cuda_visible_devices") == "":
                    result["status"] = "passed"
            except (TypeError, ValueError) as error:
                result["protocol_error"] = str(error)
    except subprocess.TimeoutExpired as error:
        result.update(status="timeout", stdout=_text(error.stdout), stderr=_text(error.stderr))
    except OSError as error:
        result.update(status="unavailable", stderr=str(error))
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def collect_environment_report(
    project_root: str | Path, python_executable: str | Path | None = None,
    command_timeout: float = 120.0,
    on_probe: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Collect CPU import evidence using only the specified project GPU venv."""
    spec = build_probe_spec(project_root, python_executable, command_timeout)
    commands = {}
    for item in spec["commands"]:
        result = _run_probe(item, Path(spec["project_root"]))
        commands[item["id"]] = result
        if on_probe is not None:
            on_probe(result)
    failed = [name for name, item in commands.items() if item["status"] != "passed"]
    metadata_result = (commands["metadata"].get("result") or {}).get("distributions", {})
    return {
        "schema_version": 1, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not failed else "failed", "failed_probes": failed,
        "project_root": spec["project_root"], "python_executable": spec["python_executable"],
        "probe_spec": spec, "commands": commands, "dependencies": metadata_result,
        "validation": {
            "metadata_and_cpu_imports": "passed" if not failed else "failed",
            "dependency_consistency": "not_checked_run_uv_pip_check_separately",
            "candidate_stack_compatibility": "not_validated_by_imports",
            "real_gpu_execution": "not_run", "hardware_bf16": "not_run",
            "p2p_transfer": "not_run", "nccl_collective": "not_run",
            "vllm_inference": "not_run", "multi_turn_lora_sync": "not_run",
        },
    }


def write_environment_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write complete JSON evidence and a concise Markdown result index."""
    target = Path(output_dir).resolve()
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    lines = ["# S0 metadata and CPU import probe", "",
             f"Result: **{report['status']}**; interpreter: `{report['python_executable']}`.", "",
             "CUDA devices were hidden. These results do not validate GPU compatibility, BF16 hardware, inference, P2P, NCCL, or training.", "",
             "| Probe | Result | Exit code | Seconds |", "| --- | --- | --- | --- |"]
    for name, item in report["commands"].items():
        lines.append(f"| {name} | {item['status']} | {item['returncode']} | {item['elapsed_seconds']} |")
    lines.extend(["", "Full commands, structured per-import results, stdout, stderr and metadata are retained in `report.json`.", ""])
    target.mkdir(parents=True, exist_ok=True)
    paths = {"json": str(target / "report.json"), "markdown": str(target / "report.md")}
    Path(paths["json"]).write_text(payload, encoding="utf-8")
    Path(paths["markdown"]).write_text("\n".join(lines), encoding="utf-8")
    return paths


def run_environment_probe(
    project_root: str | Path, output_dir: str | Path,
    python_executable: str | Path | None = None, command_timeout: float = 120.0,
) -> dict[str, str]:
    """Publish per-probe checkpoints before the final aggregate report."""
    target = Path(output_dir).resolve()
    checkpoint = target / "probes"
    checkpoint.mkdir(parents=True, exist_ok=True)

    def save_probe(result: dict[str, Any]) -> None:
        (checkpoint / f"{result['id']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return write_environment_report(
        collect_environment_report(project_root, python_executable, command_timeout,
                                   on_probe=save_probe), output_dir)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--child":
        raise SystemExit("Use the project CLI; this module is an internal child probe")
    raise SystemExit(_child_main(json.loads(sys.argv[2])))
