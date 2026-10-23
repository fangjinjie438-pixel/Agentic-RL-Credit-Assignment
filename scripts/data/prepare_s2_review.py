"""Export private S2 review packets from verified data without creating reviews.

Input is an immutable dataset and a new output directory. The script verifies
inventory, loads train/dev by default, and writes Chinese Markdown, source/task
JSON, unsigned review forms and unexecuted independent-model inputs plus a run
manifest. Sealed tasks require explicit opt-in; official tasks are never read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from procure_rl.data.pipeline import load_dataset
from procure_rl.data.review_material import (independent_review_inputs,
                                            prepare_review_material, render_review_markdown)
from procure_rl.env import load_tasks
from procure_rl.runtime import RunRecord, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-sealed-test", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    run = RunRecord(args.output, root, [sys.executable, *sys.argv],
                    execution_kind="cpu_private_review_export", stage="S2")
    try:
        manifest, products, tasks = load_dataset(args.dataset)
        if args.include_sealed_test:
            _, sealed = load_tasks(args.dataset / "tasks/sealed_test.json", include_sealed_test=True)
            tasks.update(sealed)
        material = prepare_review_material(manifest, products, list(tasks.values()), seed=manifest["seed"])
        artifacts = {}
        for name, value in (("review-material.json", material), ("reviews-template.json", material["pending_reviews"])):
            path = args.output / name
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            artifacts[name] = str(path)
        markdown = args.output / "review.md"
        markdown.write_text(render_review_markdown(material), encoding="utf-8")
        artifacts["review.md"] = str(markdown)
        inputs = args.output / "independent-inputs.jsonl"
        inputs.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                  for row in independent_review_inputs(material)), encoding="utf-8")
        artifacts["independent-inputs.jsonl"] = str(inputs)
        run.record.update(data_revision=manifest["revision"], seed=manifest["seed"],
                          dataset_manifest_sha256=sha256_file(args.dataset / "manifest.json"),
                          runner_sha256=sha256_file(Path(__file__)), model_revision=None,
                          human_review_performed=False, model_review_performed=False,
                          included_sealed_test=args.include_sealed_test,
                          artifact_sha256={name: sha256_file(Path(path)) for name, path in artifacts.items()})
        run.finish("succeeded", artifacts, "private_review_material_export_only")
        print(json.dumps({"dataset_revision": manifest["revision"], "human_tasks": material["human_sample_available"],
                          "human_sample_shortfall": material["human_sample_shortfall"],
                          "human_review_performed": False, "model_review_performed": False}))
        return 0
    except BaseException as exc:
        run.finish("failed", {}, "not_validated", type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
