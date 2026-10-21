"""CLI for S0 runtime, S1 environment acceptance and S2 dataset preparation.

Run with python -m procure_rl (PYTHONPATH=src), or the packaged procure-rl entry.
Inputs are a JSON config / new output path; outputs are run manifests and reports.
GPU probes require explicit execute and allocation arguments. S1 executes native
CPU tools; S2 defaults to offline construction with explicit bounded teacher modes.
No training subcommand exists.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .config import load_config
from .runtime import RunRecord, sha256_file


def main(argv: list[str] | None = None) -> int:
    """Execute one explicit stage operation and retain its actual evidence."""
    args_list = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check-config", help="Validate candidate planning config")
    check.add_argument("--config", type=Path, default=Path("configs/s0.json"))
    check.add_argument("--output", type=Path, required=True)
    smoke = sub.add_parser("s1-smoke", help="Real CPU environment acceptance on fictional engineering fixtures")
    smoke.add_argument("--config", type=Path, default=Path("configs/s1.json"))
    smoke.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("s2-build", help="Offline fact-first pilot construction and release gates")
    build.add_argument("--config", type=Path, default=Path("configs/s2.json"))
    build.add_argument("--output", type=Path, required=True)
    collect = sub.add_parser("s2-collect", help="Bounded collection and real deterministic replay")
    collect.add_argument("--config", type=Path, default=Path("configs/s2.json"))
    collect.add_argument("--teacher-config", type=Path, default=Path("configs/s2-teacher.json"))
    collect.add_argument("--dataset", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--cache-directory", type=Path)
    collect.add_argument("--limit", type=int, default=2)
    mode = collect.add_mutually_exclusive_group(required=True)
    mode.add_argument("--engineering", action="store_true")
    mode.add_argument("--execute-api", action="store_true")
    mode.add_argument("--cache-only", action="store_true")
    audit = sub.add_parser("s2-audit", help="Replay and evaluate hash-bound human/model review gates")
    audit.add_argument("--dataset", type=Path, required=True)
    audit.add_argument("--collection", type=Path, required=True)
    audit.add_argument("--reviews", type=Path)
    audit.add_argument("--output", type=Path, required=True)
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
                        args.config if args.action in ("check-config", "s1-smoke", "s2-build", "s2-collect") else None,
                        execution_kind=("guarded_gpu" if args.action == "gpu-probe" and args.execute else
                                        "cpu_dataset" if args.action.startswith("s2-") else
                                        "cpu_environment" if args.action == "s1-smoke" else "cpu_read_only"),
                        stage="S2" if args.action.startswith("s2-") else "S1" if args.action == "s1-smoke" else "S0")
        status = "succeeded"
        if args.action == "check-config":
            config = load_config(args.config)
            path = args.output / "validated_config.json"
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            artifacts = {"config": str(path)}
            level = "cpu_schema_only"
        elif args.action.startswith("s2-"):
            from .data.pipeline import audit_release, build_dataset, collect_dataset
            config = {} if args.action == "s2-audit" else json.loads(args.config.read_text(encoding="utf-8"))
            run.record.update(seed=config.get("seed"), model_revision=None, checkpoint=None)
            if args.action == "s2-build":
                artifacts = build_dataset(project_root, args.output, config)
            elif args.action == "s2-collect":
                teacher_config = json.loads(args.teacher_config.read_text(encoding="utf-8"))
                run.record["teacher_configuration"] = {"path": str(args.teacher_config),
                    "sha256": sha256_file(args.teacher_config),
                    "model": teacher_config.get("model"), "selection_status": teacher_config.get("selection_status")}
                artifacts = collect_dataset(args.dataset, args.output,
                    mode="engineering" if args.engineering else "api" if args.execute_api else "cache_only",
                    teacher_config=teacher_config, public_config=config.get("engineering_policy", {}),
                    limit=args.limit, seed=config["seed"], cache_directory=args.cache_directory)
            else:
                artifacts = audit_release(args.dataset, args.collection, args.output, reviews_path=args.reviews)
            report = json.loads(Path(artifacts["json"]).read_text(encoding="utf-8"))
            status = "succeeded" if report["status"] == "passed" else report["status"]
            level = report["validation_level"]
            run.record.update(data_revision=report["data_revision"], stage_complete=report["stage_complete"],
                              release_gate=report["release_gate"], policy_version=report.get("policy_version"))
        elif args.action == "s1-smoke":
            from .env.smoke import run_smoke
            config = json.loads(args.config.read_text(encoding="utf-8"))
            run.record.update(policy_version=config.get("policy_version"), seed=config.get("seed"),
                              model_revision=None, checkpoint=None)
            artifacts = run_smoke(project_root, args.output, config)
            report = json.loads(Path(artifacts["json"]).read_text(encoding="utf-8"))
            status = "succeeded" if report["status"] == "passed" else "failed"
            level = report["validation_level"]
            run.record.update(data_revision=report["data_revision"], fixture_sha256=report["fixture_sha256"],
                              upstream_revision=report["upstream_revision"], dependencies=report["dependencies"],
                              sqlite_version=report["sqlite_version"])
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

