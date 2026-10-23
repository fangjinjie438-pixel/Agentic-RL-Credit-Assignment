"""Summarize retained S2 HTTP/cached episodes without contacting any provider.

Input is the two actual collection directories and a cache-only reproduction.
Output binds outcome, format, cost and failure metrics to the retained hashes.
This generated audit driver does not approve human reviews or formal training.
"""
import json
from pathlib import Path
import sys

from procure_rl.env.catalog import digest
from procure_rl.runtime import RunRecord, sha256_file

root = Path.cwd()
base = root / "logs/s2-20261022-api"
run = RunRecord(base / "pilot-analysis-v2", root, [sys.executable, *sys.argv],
                execution_kind="cpu_retained_teacher_pilot_analysis", stage="S2")
reports = {}
episodes = {}
for name in ("teacher-pilot-v1", "teacher-pilot-v2", "teacher-cache-v2"):
    report = json.loads((base / name / "report.json").read_text())
    chosen = [json.loads(p.read_text()) for p in sorted((base / name / "episodes").glob("*/episode.json"))]
    records = report["teacher"]["requests"]
    transitions = [t for e in chosen for t in e["transitions"]]
    invalid = sum(any(event["kind"] == "invalid" for event in t["verifier_events"])
                  for t in transitions)
    episodes[name] = {e["task_id"]: e for e in chosen}
    reports[name] = {
        "report_sha256": sha256_file(base / name / "report.json"),
        "dataset_revision": report["data_revision"],
        "attempted": report["attempted"], "replay_accepted": report["replay_accepted"],
        "expert_candidates": report["expert_candidates"],
        "steps": {e["task_id"]: len(e["transitions"]) for e in chosen},
        "new_api_calls": report["teacher"]["new_api_calls"],
        "new_cost_estimate_usd": report["cost_estimate_usd"], "billed_cost_usd": None,
        "response_status_counts": {status: sum(r["status"] == status for r in records)
                                    for status in sorted({r["status"] for r in records})},
        "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in records),
        "completion_tokens": sum(r["usage"]["completion_tokens"] for r in records),
        "actual_tool_attempts": len(transitions), "invalid_tool_attempts": invalid,
        "tool_format_legal_rate": 1 - invalid / len(transitions),
        "model_response_identifiers": sorted({r["model_response"] for r in records}),
        "model_revision": None,
        "provider_fingerprints_not_immutable_revisions": sorted({r["response"].get("system_fingerprint")
                                                                 for r in records}),
        "failures": json.loads((base / name / "accept-reject-ledger.json").read_text()),
    }
original, cached = episodes["teacher-pilot-v2"], episodes["teacher-cache-v2"]
same = set(original) == set(cached) and all(
    original[k]["transitions"] == cached[k]["transitions"]
    and original[k]["public_messages"] == cached[k]["public_messages"]
    and original[k]["final_state_sha256"] == cached[k]["final_state_sha256"]
    for k in original)
assert same
assert reports["teacher-cache-v2"]["new_api_calls"] == 0
assert reports["teacher-cache-v2"]["new_cost_estimate_usd"] == 0
summary = {"collections": reports, "cache_reproduction_identical": same,
           "total_new_api_calls": sum(r["new_api_calls"] for r in reports.values()),
           "total_cost_estimate_usd": sum(r["new_cost_estimate_usd"] for r in reports.values()),
           "billed_cost_usd": None, "stage_complete": False,
           "engineering_acceptance": "HTTP, real environment execution, positive/negative filtering and offline reproduction observed",
           "quality_conclusion": "1/2 accepted under v2 on two training pilot tasks; do not infer general success rate or scale collection yet",
           "failure_classification": {"v1": ["hidden requirement not clarified", "similar color treated as equal"],
                                      "v2": ["search did not retrieve the legal product", "recommendation violates observed color/weight despite evidence"]},
           "next_diagnostic": "Review broad single-term search and actual filter/detail use on training tasks; never change the verifier to accept failed recommendations"}
out = run.output / "summary.json"
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
run.record.update(runner_sha256=sha256_file(Path(__file__)),
                  data_revision=reports["teacher-pilot-v2"]["dataset_revision"],
                  policy_version="s2-retained-pilot-analysis-v1", model_revision=None, seed=0)
run.finish("succeeded", {"summary": str(out)}, "cpu_real_teacher_artifact_analysis")
print(json.dumps({k: summary[k] for k in ("total_new_api_calls", "total_cost_estimate_usd", "cache_reproduction_identical")}))
