"""Verify final S2 evidence after real inference, without API or GPU work.

Inputs are immutable dataset, API/cache collections, actual model reviews and
final audit/test records. Output is a source-bound consistency report; quality
rejections and user-deferred human review remain explicit, never fabricated.
"""
import ast
import json
from pathlib import Path
import re
import sys

from procure_rl.data.pipeline import load_dataset
from procure_rl.env.catalog import digest
from procure_rl.runtime import RunRecord, sha256_file

root = Path.cwd()
base = root / "logs/s2-20261022-api"
run = RunRecord(base / "handoff-final", root, [sys.executable, *sys.argv],
                execution_kind="cpu_final_evidence_consistency", stage="S2")
checks = []
def check(name, passed):
    checks.append({"name": name, "passed": bool(passed)})
def read(path):
    return json.loads(path.read_text())

tests = read(base / "tests-final-v3/run.json")
result = read(base / "tests-final-v3/result.json")
check("160_tests_zero_failures_errors_skips", result == {
    "tests": 160, "failures": 0, "errors": 0, "skipped": 0, "successful": True})
for section in ("source_sha256", "test_sha256", "fixture_sha256"):
    for path, expected in tests[section].items():
        check(section + ":" + path, sha256_file(root / path) == expected)
check("tested_config_unchanged", sha256_file(root / "configs/s2.json") == tests["config"]["sha256"])
dataset = base / "build-identity-v2/dataset"
manifest, products, tasks = load_dataset(dataset)
check("current_dataset_revision", manifest["revision"] == "s2-f692f21320912220be59d4a5")
check("actual_small_counts_preserved", len(products) == 8 and len(tasks) == 7 and manifest["counterfactual_pairs"] == 2)
pilot, cached = [read(base / name / "report.json") for name in ("teacher-pilot-v2", "teacher-cache-v2")]
check("one_expert_candidate_one_quality_rejection", pilot["attempted"] == 2 and pilot["replay_accepted"] == 1
      and pilot["expert_candidates"] == 1 and pilot["rejected"] == 1)
check("cached_replay_no_new_billing", cached["replay_accepted"] == 1 and cached["teacher"]["new_api_calls"] == 0
      and cached["cost_estimate_usd"] == 0)
for episode in (base / "teacher-pilot-v2/episodes").glob("*/episode.json"):
    original = read(episode)
    other = read(base / "teacher-cache-v2/episodes" / episode.parent.name / "episode.json")
    check("cached_actual_dialogue_and_state:" + episode.parent.name,
          all(original[k] == other[k] for k in ("transitions", "public_messages", "final_state_sha256")))
journal = [read(p) for p in (root / ".cache/s2-teacher").glob("*.json")]
check("72_requests_all_completed", len(journal) == 72 and all(r["status"] == "completed" for r in journal))
config = read(root / "configs/s2-teacher.json")
check("provisional_teacher_visible_and_budget_respected", config["selection_status"] == "agent_selected_provisional"
      and len(journal) <= config["max_requests"]
      and sum(max(r.get("reserved_cost_usd", 0), r.get("cost_usd") or 0) for r in journal) <= config["max_cost_usd"] + 1e-12)
check("teacher_actual_revision_not_invented", all(r["model_revision"] is None for r in journal))
model = read(base / "independent-model-download-v2/model-verified.json")
check("official_model_content_verified", model["all_files_verified"] and len(model["files"]) == 13
      and model["revision"] == "b968826d9c46dd6066d109eabc6255188de91218")
gpu = read(base / "independent-review-v1/run.json")
review = read(base / "independent-review-v1/report.json")
check("real_allocated_gpu_inference_performed", gpu["gpu_compute_performed"] is True
      and gpu["gpu_uuid"] == "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af"
      and gpu["model_revision"] == model["revision"])
check("all_seven_model_attempts_accounted_for", review["tasks_attempted"] == 7
      and review["completed_reviews"] + len(review["failures"]) == 7)
decision = read(base / "release-audit-final/release-decision.json")
check("formal_release_withheld_without_fake_human_approval", decision["status"] == "withheld"
      and decision["human_review_count"] == 0 and decision["approved_expert_task_ids"] == [])
reviews = read(base / "independent-review-v1/reviews.json")["independent_reviews"]
rejected = {r["task_id"] for r in reviews if r["decision"] == "reject"}
check("model_disagreements_queued_for_real_human", rejected.issubset(set(decision["unadjudicated_task_ids"])))
supplement = ["# S2 后续人工裁决索引", "",
              "用户已明确人工审核稍后进行。本文件不含人工签核或正式放行。", "",
              "先查看 ../review-material-v2/review.md 的商品原句、单位和完整解集；再对照下面模型意见。",
              "模型拒收意见不是确定的数据错误。程序已验证Decimal单位换算、完整可行解和2对单改动反事实；"
              "对单位混用、额外商品属性即泄漏、无反事实的base也必须有反事实等意见，应结合原始记录人工裁决。", "",
              "签核时复制原 reviews-template.json，填写真实身份/时间/accept或reject/理由；"
              "只有已实际裁决的模型分歧才填写 adjudicates_model_disagreement=true。",
              "后续审计需把人工表内human_reviews/identity_reviews与独立模型reviews.json内independent_reviews合并，"
              "保持dataset_revision一致并另存新文件，再传s2-audit --reviews。不得拿空表或模型accept充当人审。", ""]
for item in reviews:
    supplement.extend(["## " + item["task_id"], "",
                       "模型决定：" + item["decision"] + "；待人工复核，原始记录SHA：`" + digest(item) + "`。", "",
                       "```json", json.dumps({k: item[k] for k in ("checks", "reasons")}, ensure_ascii=False, indent=2),
                       "```", ""])
supplement_path = run.output / "human-next.md"
supplement_path.write_text("\n".join(supplement) + "\n")
check("review_material_bound_to_current_dataset", read(base / "review-material-v2/review-material.json")["dataset_revision"]
      == manifest["revision"])
for directory in (root / "src", root / "scripts", root / "tests"):
    for path in directory.rglob("*.py"):
        check("module_description:" + str(path.relative_to(root)), bool(ast.get_docstring(ast.parse(path.read_text()))))
        readme = path.parent / "README.md"
        check("documented_code:" + str(path.relative_to(root)), readme.is_file() and path.name in readme.read_text())
secret = (root / config["key_file"]).read_text().strip().encode()
leaks = []
for directory in (base, root / ".cache/s2-teacher"):
    for path in directory.rglob("*"):
        if path.is_file() and secret and secret in path.read_bytes():
            leaks.append(str(path.relative_to(root)))
check("credential_not_present_in_new_logs_or_cache", not leaks)
doc_paths = [root / name for name in ("README.md", "PROGRESS.md", "docs/stages/S2.md",
                                     "src/procure_rl/data/README.md", "scripts/data/README.md", "tests/README.md")]
for path in doc_paths:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        local = target.strip("<>").split("#", 1)[0]
        check("document_link:" + str(path.relative_to(root)) + ":" + local, (path.parent / local).exists())
report = {"checks": checks, "passed": all(c["passed"] for c in checks),
          "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks),
          "stage_complete": False, "human_review_deferred_by_user": True,
          "formal_release": "withheld", "data_revision": manifest["revision"],
          "teacher_new_api_calls": len(journal), "teacher_cost_estimate_usd": sum(r["cost_usd"] for r in journal),
          "billed_cost_usd": None, "credential_leak_paths": leaks,
          "next_stage_started": False, "checkpoint": None}
path = run.output / "audit.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
run.record.update(data_revision=manifest["revision"], runner_sha256=sha256_file(Path(__file__)), seed=0,
                  policy_version="s2-final-evidence-audit-v1", model_revision=None)
run.finish("succeeded" if report["passed"] else "failed", {"audit": str(path), "human_next": str(supplement_path)}, "cpu_evidence_consistency_only")
print(json.dumps({k: report[k] for k in ("passed", "checks_passed", "checks_total", "stage_complete")}))
raise SystemExit(0 if report["passed"] else 1)
