"""Persist stage run manifests and event logs without reading secrets.

The CLI passes a new output directory and argv; this module records timestamps,
machine/interpreter, source hashes, optional config hash and explicit validation
levels. Unknown data/model revisions and checkpoints remain null.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shlex
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def timestamp() -> str:
    """Return an unambiguous Shanghai timestamp for the handoff and logs."""
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    """Hash one configuration or source file, without consulting Git state."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RunRecord:
    """Write run.json/run.log; refuse to overwrite earlier evidence directories."""

    def __init__(self, output: Path, project_root: Path, argv: list[str],
                 config_path: Path | None = None,
                 execution_kind: str = "cpu_read_only", stage: str = "S0") -> None:
        output.mkdir(parents=True, exist_ok=False)
        self.output = output
        source_root = project_root / "src"
        self.record: dict[str, Any] = {
            "schema_version": 1, "stage": stage, "status": "running",
            "execution_kind": execution_kind,
            "started_at": timestamp(), "finished_at": None,
            "machine": platform.node(), "platform": platform.platform(),
            "python": sys.version, "executable": sys.executable,
            "resolved_executable": str(Path(sys.executable).resolve()),
            "prefix": sys.prefix, "base_prefix": sys.base_prefix,
            "working_directory": str(Path.cwd()), "argv": argv,
            "command": shlex.join(argv),
            "project_root": str(project_root),
            "source_sha256": {
                str(p.relative_to(project_root)): sha256_file(p)
                for p in sorted(source_root.rglob("*.py"))
            },
            "config": None if config_path is None else {
                "path": str(config_path.resolve()),
                "sha256": None,
            },
            "data_revision": None, "model_revision": None,
            "policy_version": None, "seed": None, "checkpoint": None,
            "gpu_compute_performed": False,
            "gpu_validation": "not_run", "artifacts": {},
        }
        if config_path is not None:
            try:
                self.record["config"]["sha256"] = sha256_file(config_path)
            except OSError as exc:
                self.record["config"]["read_error"] = f"{type(exc).__name__}: {exc}"
        self._save()
        self.log(f"{stage} run started: {execution_kind}; GPU has not been used by this run yet")

    def _save(self) -> None:
        (self.output / "run.json").write_text(
            json.dumps(self.record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def log(self, message: str) -> None:
        """Append one human-readable event; structured state lives in run.json."""
        with (self.output / "run.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp()} {message}\n")

    def finish(self, status: str, artifacts: dict[str, str],
               validation_level: str, error: str | None = None) -> None:
        """Close the run with actual CPU/read-only results and artifact locations."""
        self.record.update(status=status, artifacts=artifacts, error=error,
                           finished_at=timestamp(), validation_level=validation_level)
        self.log(f"Run {status}: {error or validation_level}")
        self._save()

