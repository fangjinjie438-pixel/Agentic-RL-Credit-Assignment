"""CPU-only CLI for S0 config checks and read-only doctor reports.

Run with python -m procure_rl (PYTHONPATH=src), or the packaged procure-rl entry.
Inputs are a JSON config / new output path; outputs are run manifests and reports.
No model, GPU training or environment-install subcommand exists at this stage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .runtime import RunRecord


def main(argv: list[str] | None = None) -> int:
    """Execute a CPU operation and save its evidence; return a process exit code."""
    args_list = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check-config", help="Validate candidate planning config")
    check.add_argument("--config", type=Path, default=Path("configs/s0.json"))
    check.add_argument("--output", type=Path, required=True)
    doctor = sub.add_parser("doctor", help="Read-only hardware and dependency inventory")
    doctor.add_argument("--output", type=Path, required=True)
    doctor.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(args_list)
    if args.action == "doctor" and args.timeout <= 0:
        parser.error("--timeout must be positive")
    project_root = Path.cwd().resolve()
    run: RunRecord | None = None
    try:
        run = RunRecord(args.output, project_root,
                        [sys.executable, "-m", "procure_rl", *args_list],
                        args.config if args.action == "check-config" else None)
        if args.action == "check-config":
            config = load_config(args.config)
            path = args.output / "validated_config.json"
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            artifacts = {"config": str(path)}
            level = "cpu_schema_only"
        else:
            from .doctor import run_doctor
            artifacts = run_doctor(project_root, args.output, args.timeout)
            level = "read_only_inventory_only"
        run.finish("succeeded", artifacts, level)
        print(json.dumps({"status": "succeeded", "validation_level": level,
                          "gpu_validation": "not_run", "artifacts": artifacts},
                         ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        if run is not None:
            run.finish("failed", {}, "not_validated", f"{type(exc).__name__}: {exc}")
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

