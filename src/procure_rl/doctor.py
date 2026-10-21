"""Collect read-only S0 evidence and write JSON/Markdown reports.

The CLI calls ``run_doctor(project_root, output_dir)`` using the independent
project interpreter. Collection uses standard library metadata, local files, and
bounded read-only NVIDIA/Git commands; it never executes a system Toolkit binary,
imports a GPU library, or validates allocation, CUDA execution, P2P, or NCCL.
"""

from __future__ import annotations

import csv
import glob
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Sequence


GPU_FIELDS = (
    "index", "uuid", "name", "memory.total", "memory.used", "memory.free",
    "driver_version", "pci.bus_id",
)
PROCESS_FIELDS = ("gpu_uuid", "pid", "process_name", "used_gpu_memory")
ALLOCATION_ENV_KEYS = (
    "CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES", "SLURM_JOB_ID",
    "SLURM_STEP_ID", "SLURM_JOB_GPUS", "SLURM_STEP_GPUS",
    "SLURM_GPUS_ON_NODE", "PBS_JOBID", "LSB_JOBID",
)
CANDIDATE_VERSIONS = {
    "torch": "2.7.1", "verl": "0.6.1", "vllm": "0.10.0",
    "transformers": "4.53.2", "ray": None, "peft": None,
    "flash-attn": None, "accelerate": None, "numpy": None,
    "nvidia-nccl-cu12": None, "nvidia-cuda-runtime-cu12": None,
}


def _text(value: Any) -> str:
    """Normalize subprocess timeout output to serializable UTF-8 text."""
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _run_command(argv: Sequence[str], timeout: float) -> dict[str, Any]:
    """Run a fixed probe without a shell; preserve failures instead of aborting."""
    started = time.monotonic()
    result: dict[str, Any] = {
        "argv": list(argv), "timeout_seconds": timeout,
        "returncode": None, "stdout": "", "stderr": "",
    }
    try:
        completed = subprocess.run(
            list(argv), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False, shell=False,
        )
        result.update(
            returncode=completed.returncode,
            stdout=completed.stdout, stderr=completed.stderr,
            status="ok" if completed.returncode == 0 else "failed",
        )
    except FileNotFoundError as error:
        result.update(status="unavailable", stderr=str(error))
    except subprocess.TimeoutExpired as error:
        result.update(status="timeout", stdout=_text(error.stdout), stderr=_text(error.stderr))
    except OSError as error:
        result.update(status="error", stderr=str(error))
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def _memory_info() -> dict[str, Any]:
    """Read Linux host memory in bytes; leave unsupported fields explicit."""
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                values[key] = int(value.strip().split()[0]) * 1024
        return {"status": "observed", "bytes": values}
    except (OSError, ValueError) as error:
        return {"status": "unavailable", "error": str(error)}


def _cpu_info() -> dict[str, Any]:
    """Read CPU descriptions and the process CPU affinity where supported."""
    result: dict[str, Any] = {"logical_cpu_count": os.cpu_count(), "machine": platform.machine()}
    try:
        entries = Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines()
        models = sorted({line.split(":", 1)[1].strip() for line in entries if line.startswith("model name")})
        sockets = {line.split(":", 1)[1].strip() for line in entries if line.startswith("physical id")}
        result.update(model_names=models, physical_socket_count=len(sockets) or None)
    except OSError as error:
        result["cpuinfo_error"] = str(error)
    if hasattr(os, "sched_getaffinity"):
        try:
            result["process_affinity_cpu_count"] = len(os.sched_getaffinity(0))
        except OSError as error:
            result["affinity_error"] = str(error)
    return result


def _disk_info(path: Path) -> dict[str, Any]:
    """Measure filesystem capacity without creating any files."""
    try:
        usage = shutil.disk_usage(path)
        return {
            "path": str(path), "status": "observed", "total_bytes": usage.total,
            "used_bytes": usage.used, "free_bytes": usage.free,
            "used_percent": round(usage.used / usage.total * 100, 2) if usage.total else None,
        }
    except OSError as error:
        return {"path": str(path), "status": "unavailable", "error": str(error)}


def _project_info(project_root: Path) -> dict[str, Any]:
    """List visible top-level entries only; a .git path does not prove a repo."""
    result: dict[str, Any] = {
        "path": str(project_root), "inspection_depth": 1,
        "hidden_entries_omitted": 0, "top_level_entries": [],
        "git_directory_present": (project_root / ".git").is_dir(),
        "git_note": "Directory presence is metadata only; consult git command results to establish repository validity.",
    }
    try:
        for entry in sorted(project_root.iterdir(), key=lambda item: item.name):
            if entry.name.startswith("."):
                result["hidden_entries_omitted"] += 1
                continue
            kind = "symlink" if entry.is_symlink() else "directory" if entry.is_dir() else "file" if entry.is_file() else "other"
            result["top_level_entries"].append({"name": entry.name, "type": kind})
        result["status"] = "observed"
    except OSError as error:
        result.update(status="partial_or_unavailable", error=str(error))
    return result


def _dependency_info() -> dict[str, Any]:
    """Inspect installed distribution metadata without importing ML packages."""
    result: dict[str, Any] = {}
    for name, expected in CANDIDATE_VERSIONS.items():
        item: dict[str, Any] = {"candidate_version": expected}
        try:
            distribution = metadata.distribution(name)
            version = distribution.version
            base_version = version.split("+", 1)[0]
            item.update(
                status="installed", installed_version=version,
                version_comparison=(
                    "not_pinned" if expected is None else
                    "matches_version_only" if base_version == expected else "mismatch"
                ),
            )
            # Avoid copying direct_url.json URLs, which can contain credentials.
            direct_url_text = distribution.read_text("direct_url.json")
            if direct_url_text:
                try:
                    vcs = json.loads(direct_url_text).get("vcs_info", {})
                    if vcs:
                        item["vcs"] = {key: vcs[key] for key in ("vcs", "commit_id", "requested_revision") if key in vcs}
                except (ValueError, AttributeError, TypeError):
                    item["vcs_metadata_status"] = "unreadable"
            if name in {"torch", "vllm"}:
                item["candidate_cuda_build"] = "cu126"
                item["cuda_build_evidence"] = (
                    "cu126_in_version_metadata" if "+cu126" in version else "not_established_by_version_metadata"
                )
        except metadata.PackageNotFoundError:
            item.update(status="not_installed", installed_version=None, version_comparison="missing")
        except (OSError, ValueError, UnicodeError) as error:
            item.update(status="metadata_error", error=str(error), version_comparison="unknown")
        result[name] = item
    return result


def _parse_csv_probe(probe: dict[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    """Parse successful NVIDIA CSV while retaining malformed-row evidence."""
    if probe["status"] != "ok":
        return {"status": "unavailable", "rows": []}
    rows = []
    malformed = []
    for values in csv.reader(io.StringIO(probe["stdout"]), skipinitialspace=True):
        if not values:
            continue
        if len(values) != len(fields):
            malformed.append(values)
        else:
            rows.append(dict(zip(fields, (value.strip() for value in values))))
    return {"status": "partial" if malformed else "observed", "rows": rows, "malformed_rows": malformed}


def _toolkit_metadata() -> dict[str, Any]:
    """List Toolkit paths/symlink metadata without invoking any Toolkit program."""
    result: dict[str, Any] = {
        "status": "metadata_only", "execution_policy": "no_toolkit_execution",
        "installed_versions": "not_verified_no_toolkit_execution",
        "installations": [],
    }
    on_path = shutil.which("nvcc")
    result["nvcc_on_path"] = on_path
    for value in sorted(glob.glob("/usr/local/cuda*")):
        path = Path(value)
        item: dict[str, Any] = {"path": value}
        try:
            item.update(
                is_symlink=path.is_symlink(), resolved_path=str(path.resolve()),
                is_directory=path.is_dir(), nvcc_path_exists=(path / "bin" / "nvcc").is_file(),
            )
            if path.is_symlink():
                item["symlink_target"] = os.readlink(path)
        except OSError as error:
            item["metadata_error"] = str(error)
        result["installations"].append(item)
    return result


def collect_report(project_root: str | Path, command_timeout: float = 10.0) -> dict[str, Any]:
    """Return JSON-ready host evidence; collection performs no writes or GPU work.

    ``project_root`` selects the filesystem to inspect; ``command_timeout`` bounds
    each read-only subprocess. Missing tools and partial visibility are evidence,
    not fatal errors. Allocation and real GPU integration always remain pending.
    """
    if command_timeout <= 0:
        raise ValueError("command_timeout must be positive")
    project_root = Path(project_root).resolve()
    command_specs = {
        "nvidia_smi": ["nvidia-smi"],
        "gpu_inventory": ["nvidia-smi", f"--query-gpu={','.join(GPU_FIELDS)}", "--format=csv,noheader,nounits"],
        "gpu_processes": ["nvidia-smi", f"--query-compute-apps={','.join(PROCESS_FIELDS)}", "--format=csv,noheader,nounits"],
        "gpu_topology": ["nvidia-smi", "topo", "-m"],
        "p2p_read_capability": ["nvidia-smi", "topo", "-p2p", "r"],
        "p2p_write_capability": ["nvidia-smi", "topo", "-p2p", "w"],
        "git_revision": ["git", "--no-optional-locks", "-C", str(project_root), "rev-parse", "HEAD"],
        "git_status": ["git", "--no-optional-locks", "-C", str(project_root), "status", "--short", "--untracked-files=no"],
    }
    commands = {key: _run_command(argv, command_timeout) for key, argv in command_specs.items()}
    environment = {key: os.environ[key] for key in ALLOCATION_ENV_KEYS if key in os.environ}
    try:
        os_release = platform.freedesktop_os_release()
    except OSError as error:
        os_release = {"error": str(error)}
    python_candidate = "3.11"
    python_current = f"{sys.version_info.major}.{sys.version_info.minor}"
    report: dict[str, Any] = {
        "schema_version": 1,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "probe_policy": {
            "read_only": True, "imports_ml_libraries": False,
            "runs_toolkit_binaries": False, "toolkit_execution_policy": "no_toolkit_execution",
            "creates_cuda_context": False, "runs_gpu_compute": False,
            "runs_p2p_transfer_or_nccl": False,
            "allocation_inferred_from_free_memory": False,
        },
        "host": {
            "hostname": platform.node(), "os": platform.platform(),
            "libc": dict(zip(("implementation", "version"), platform.libc_ver())),
            "os_release": os_release, "cpu": _cpu_info(), "memory": _memory_info(),
            "filesystems": [_disk_info(project_root), _disk_info(Path("/tmp")), _disk_info(Path("/dev/shm"))],
        },
        "project": _project_info(project_root),
        "toolkits": _toolkit_metadata(),
        "python": {
            "executable": sys.executable, "version": platform.python_version(),
            "resolved_executable": str(Path(sys.executable).resolve()),
            "prefix": sys.prefix, "base_prefix": sys.base_prefix,
            "candidate_version": python_candidate,
            "version_comparison": "matches_version_only" if python_current == python_candidate else "mismatch",
        },
        "allocation": {
            "status": "not_confirmed", "environment_hints": environment,
            "note": "Environment hints and free memory do not authorize GPU use. Confirm assigned GPU UUIDs externally before computing.",
        },
        "gpu": {
            "inventory": _parse_csv_probe(commands["gpu_inventory"], GPU_FIELDS),
            "compute_processes": _parse_csv_probe(commands["gpu_processes"], PROCESS_FIELDS),
            "memory_unit": "MiB (nvidia-smi CSV without unit labels)",
            "topology_note": "PIX is a PCIe switch path, not NVLink or proof of working P2P. Capability queries are not transfer tests.",
            "cuda_version_note": "nvidia-smi CUDA Version is driver capability, not installed Toolkit or PyTorch CUDA runtime.",
            "torch_cuda_runtime": "not_verified_no_torch_import",
            "nccl_runtime": "not_verified_no_gpu_execution",
        },
        "dependencies": _dependency_info(),
        "candidate_stack": {
            "status": "not_validated", "verl": "0.6.1", "vllm": "0.10.0/cu126",
            "torch": "2.7.1/cu126", "python": "3.11", "transformers": "4.53.2",
            "note": "Version metadata matches alone do not establish dependency compatibility, CUDA runtime health, or multi-turn LoRA synchronization.",
        },
        "validation": {
            "read_only_inventory": "collected_with_per_probe_status",
            "gpu_allocation": "pending", "dependency_installation": "pending",
            "candidate_stack_compatibility": "pending", "real_gpu_execution": "pending",
            "p2p_transfer": "pending", "nccl_collective": "pending",
            "torch_cuda_runtime": "pending", "multi_turn_lora_sync": "pending",
        },
        "commands": commands,
    }
    return report


def _markdown_report(report: dict[str, Any]) -> str:
    """Render a concise readable index plus exact command evidence."""
    lines = [
        "# S0 read-only environment report", "",
        f"Collected (UTC): {report['collected_at_utc']}",
        f"Project: `{report['project_root']}`", "",
        "GPU allocation: **not confirmed**. Real GPU computation: **pending**.",
        "The candidate verl 0.6.1 + vLLM 0.10.0/cu126 + PyTorch 2.7.1/cu126 stack is **not validated**.",
        "nvidia-smi CUDA Version is a driver capability. Toolkit paths are metadata only; no Toolkit executable was invoked and Toolkit versions remain unverified.",
        "PIX and P2P capability matrices describe topology/capability only; no GPU transfer or NCCL operation was executed.", "",
        "## Python and dependencies", "",
        f"Python: `{report['python']['version']}`; executable: `{report['python']['executable']}`; target: 3.11.", "",
        "| Distribution | Installed | Candidate | Version comparison |",
        "| --- | --- | --- | --- |",
    ]
    for name, value in report["dependencies"].items():
        lines.append(f"| {name} | {value.get('installed_version') or value['status']} | {value['candidate_version'] or 'not pinned'} | {value['version_comparison']} |")
    for title, value in (
        ("Host, CPU, memory and filesystems", report["host"]),
        ("Project top-level state", report["project"]),
        ("Toolkit metadata (no Toolkit execution)", report["toolkits"]),
        ("Allocation hints (not authorization)", report["allocation"]),
        ("GPU inventory and processes", report["gpu"]),
        ("Validation status", report["validation"]),
    ):
        lines.extend(["", f"## {title}", "", "```json", json.dumps(value, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Command evidence", ""])
    for name, result in report["commands"].items():
        lines.extend([f"### {name}", "", "```json", json.dumps(result, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def write_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write report.json/report.md only inside the explicitly chosen directory."""
    output_dir = Path(output_dir).resolve()
    # Serialize before creating the directory so invalid input leaves no artifacts.
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    markdown = _markdown_report(report) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {"json": str(output_dir / "report.json"), "markdown": str(output_dir / "report.md")}
    Path(paths["json"]).write_text(payload, encoding="utf-8")
    Path(paths["markdown"]).write_text(markdown, encoding="utf-8")
    return paths


def run_doctor(
    project_root: str | Path, output_dir: str | Path, command_timeout: float = 10.0,
) -> dict[str, str]:
    """CLI facade: collect read-only evidence, then write the two report artifacts."""
    return write_report(collect_report(project_root, command_timeout), output_dir)
