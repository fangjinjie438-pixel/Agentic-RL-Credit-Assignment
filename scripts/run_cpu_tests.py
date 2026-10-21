"""Run project CPU unittest discovery with durable stage-specific evidence.

Input is a new output directory, optional config and stage label. The script
calls unittest discovery, writes the original log/result plus RunRecord source,
test/config/data hashes, machine and interpreter metadata, and exits nonzero on
failure. It hides GPU visibility and never requests a model or external teacher.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import unittest

from procure_rl.runtime import RunRecord, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("S0", "S1", "S2"), default="S2")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HF_HUB_OFFLINE"] = "1"
    run = RunRecord(args.output, root, [sys.executable, *sys.argv], args.config,
                    execution_kind="cpu_tests", stage=args.stage)
    run.record.update(test_sha256={str(p.relative_to(root)): sha256_file(p) for p in sorted((root / "tests").glob("test_*.py"))},
                      runner_sha256=sha256_file(Path(__file__)),
                      fixture_sha256={str(p.relative_to(root)): sha256_file(p) for p in sorted((root / "fixtures").rglob("*.json"))},
                      dependencies={d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
                      data_revision="mixed_versioned_test_fixtures", model_revision=None,
                      policy_version="test_specific; no external teacher or model", seed=None)
    try:
        with (args.output / "unittest.log").open("w") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            suite = unittest.defaultTestLoader.discover("tests")
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        summary = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                   "skipped": len(result.skipped), "successful": result.wasSuccessful()}
        (args.output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
        run.finish("succeeded" if result.wasSuccessful() else "failed",
                   {"log": str(args.output / "unittest.log"), "summary": str(args.output / "result.json")},
                   "cpu_unit_and_native_integration_tests")
        print(json.dumps(summary))
        return 0 if result.wasSuccessful() else 1
    except BaseException as exc:
        run.finish("failed", {}, "not_validated", type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
