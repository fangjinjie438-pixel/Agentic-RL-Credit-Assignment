"""S0 CLI for configuration, inventory, isolated imports and guarded GPU probes.

Run with python -m procure_rl (PYTHONPATH=src), or the packaged procure-rl entry.
Inputs are a JSON config / new output path; outputs are run manifests and reports.
GPU probes require explicit execute and allocation arguments. No training or
environment-install subcommand exists at this stage.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .config import load_config
from .runtime import RunRecord


def main(argv: list[str] | None = None) -> int:
    """Execute an explicit S0 operation and save evidence and its actual exit code."""
    args_list = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check-config", help="Validate candidate planning config")
    check.add_argument("--config", type=Path, default=Path("configs/s0.json"))
    check.add_argument("--output", type=Path, required=True)
    doctor = sub.add_parser("doctor", help="Read-only hardware and dependency inventory")
    doctor.add_argument("--output", type=Path, required=True)
    doctor.add_argument("--timeout", type=float, default=10.0)
    environment = sub.add_parser("check-environment", help="GPU-hidden dependency/interface imports")
    environment.add_argument("--output", type=Path, required=True)
    environment.add_argument("--python", type=Path, default=Path(".venv-gpu/bin/python"))
    environment.add_argument("--timeout", type=float, default=120.0)
    environment.add_argument("--dry-run", action="store_true")
    gpu = sub.add_parser("gpu-probe", help="Explicitly allocated GPU subset checks; defaults to dry-run")
    gpu.add_argument("--output", type=Path, required=True)
    gpu.add_argument("--gpu-uuid", action="append", default=[])
    gpu.add_argument("--allocation-source", default="")
    gpu.add_argument("--execute", action="store_true")
    gpu.add_argument("--probe", action="append", choices=("torch", "nccl", "attention", "vllm"))
    gpu.add_argument("--model-path", type=Path)
    gpu.add_argument("--model-revision")
    gpu.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(args_list)
    if hasattr(args, "timeout") and (not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error("--timeout must be finite and positive")
    project_root = Path.cwd().resolve()
    run: RunRecord | None = None
    try:
        run = RunRecord(args.output, project_root,
                        [sys.executable, "-m", "procure_rl", *args_list],
                        args.config if args.action == "check-config" else None,
                        execution_kind="guarded_gpu" if args.action == "gpu-probe" and args.execute else "cpu_read_only")
        status = "succeeded"
        if args.action == "check-config":
            config = load_config(args.config)
            path = args.output / "validated_config.json"
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            artifacts = {"config": str(path)}
            level = "cpu_schema_only"
        elif args.action == "doctor":
            from .doctor import run_doctor
            artifacts = run_doctor(project_root, args.output, args.timeout)
            level = "read_only_inventory_only"
        elif args.action == "check-environment":
            from .environment_probe import build_probe_spec, run_environment_probe
            if args.dry_run:
                report = build_probe_spec(project_root, args.python, args.timeout)
                path = args.output / "probe_spec.json"
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                artifacts = {"specification": str(path)}
                level = "configuration_only"
            else:
                artifacts = run_environment_probe(project_root, args.output, args.python, args.timeout)
                report = json.loads(Path(artifacts["json"]).read_text(encoding="utf-8"))
                status = "succeeded" if report["status"] == "passed" else "failed"
                level = "gpu_hidden_imports_only"
        else:
            from .gpu_probe import run_gpu_probe
            report = run_gpu_probe(gpu_uuids=args.gpu_uuid, allocation_source=args.allocation_source,
                                   execute=args.execute, probes=args.probe or ("torch",),
                                   model_path=args.model_path, model_revision=args.model_revision,
                                   timeout=args.timeout, project_root=project_root)
            path = args.output / "report.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            artifacts = {"json": str(path)}
            status = "failed" if report["status"] == "failed" else "succeeded"
            level = report["validation_level"]
            run.record.update(gpu_compute_performed=report["gpu_compute_performed"],
                              gpu_validation=report["gpu_validation"],
                              allocation=report["allocation"], model_revision=args.model_revision,
                              seed=report["seed"], model_path=report["model_path"],
                              requested_probes=report["requested_probes"])
        run.finish(status, artifacts, level)
        print(json.dumps({"status": status, "validation_level": level,
                          "gpu_validation": run.record["gpu_validation"], "artifacts": artifacts},
                         ensure_ascii=False, indent=2))
        return 0 if status == "succeeded" else 1
    except Exception as exc:
        if run is not None:
            run.finish("failed", {}, "not_validated", f"{type(exc).__name__}: {exc}")
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

