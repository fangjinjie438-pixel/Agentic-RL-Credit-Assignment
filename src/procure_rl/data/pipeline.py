"""Run S2 offline construction and separately authorized teacher collection.

CLI inputs are source/template configs, an immutable dataset and a new output
directory. Outputs inventory facts, split audits, tasks/counterfactuals, review
queues, accept/reject ledgers and explicit release gates. Engineering episodes
never become expert exports; sealed tasks never enter the collection iterator.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from ..env import Catalog, ProcurementEnv, build_catalog, load_tasks
from ..env.catalog import digest
from ..runtime import sha256_file, timestamp
from .builder import audit_expression, build_tasks, feasible_products
from .replay import replay_episode
from .review import make_review_queue, release_gate
from .sources import normalize_records
from .split import audit_task_splits, semantic_candidates, split_products
from .teacher import OpenAIHTTPTeacher, ScriptedTeacher, TeacherError, collect_episode


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_gate(manifest: dict, ledger: dict) -> dict:
    if manifest["engineering_only"]:
        ledger = {**ledger, "expert_eligible": False, "engineering_only": True,
                  "expert_exclusion": "engineering_source"}
    return ledger


def verify_raw_artifact(project_root: Path, payload: dict) -> dict:
    """Bind curated excerpts to the retained, hash-verified original row artifact."""
    source = payload["source"]
    raw_path = (project_root / source["raw_rows_artifact"]).resolve()
    if project_root.resolve() not in raw_path.parents or sha256_file(raw_path) != source["sha256"]:
        raise ValueError("Raw source artifact escapes project or source hash differs")
    rows = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Raw rows artifact must be a JSON array")
    for record in payload["records"]:
        index = record.get("source_row_index")
        if type(index) is not int or not 0 <= index < len(rows) or record["raw"] != rows[index]:
            raise ValueError("Curated raw record does not match its original source row")
    return {"path": str(raw_path.relative_to(project_root.resolve())), "sha256": source["sha256"], "rows": len(rows),
            "verified_excerpt_rows": len(payload["records"])}


def build_dataset(project_root: Path, output: Path, config: dict) -> dict[str, str]:
    """Construct a small unreleased dataset, preserving rejected source/task cases."""
    if config.get("stage") != "S2" or type(config.get("seed")) is not int:
        raise ValueError("S2 stage and integer seed required")
    source_path = project_root / config["source_path"]
    exclusions_path = project_root / config["official_exclusions_path"]
    source = _read(source_path)
    engineering = config.get("source_kind") == "engineering_fixture"
    if engineering:
        products = copy.deepcopy(source["products"])
        for p in products:
            p.pop("split", None)
        normalized = {"products": products, "rejected": [], "source_manifest": {
            "source_kind": "engineering_fixture", "revision": source["revision"],
            "source_sha256": sha256_file(source_path), "formal_training_eligible": False}}
    elif config.get("source_kind") == "attributed_raw_records":
        raw_binding = verify_raw_artifact(project_root, source)
        normalized = normalize_records(source["records"], source=source["source"])
        normalized["source_manifest"]["raw_artifact_binding"] = raw_binding
    else:
        raise ValueError("Unknown source_kind; no implicit synthetic fallback")
    exclusions = _read(exclusions_path)
    split = split_products(normalized["products"], exclusions, seed=config["seed"], ratios=config.get("split_ratios"))
    products = split["products"]
    built = build_tasks(products, config["templates"], max_base_per_split=config.get("max_base_per_split", 8),
                        require_disjoint_counterfactual=config.get("require_disjoint_counterfactual", True))
    tasks = built["tasks"]
    audit = audit_task_splits(tasks, split["assignments"])
    semantic = semantic_candidates([*products, *tasks])
    revision = "s2-" + digest({"products": products, "tasks": tasks,
                              "source": normalized["source_manifest"], "exclusions": exclusions,
                              "seed": config["seed"]})[:24]
    dataset = output / "dataset"
    dataset.mkdir(parents=True, exist_ok=False)
    catalog_source = {"revision": revision, "products": products}
    write_json(dataset / "catalog.json", catalog_source)
    build_catalog(dataset / "catalog.json", dataset / "catalog")
    for name in ("train", "dev", "sealed_test"):
        write_json(dataset / "tasks" / (name + ".json"), {"revision": revision,
                   "tasks": [t for t in tasks if t["split"] == name]})
    # Test tasks have their own file and are not accepted by the default loader.
    for name in ("train", "dev"):
        load_tasks(dataset / "tasks" / (name + ".json"))
    load_tasks(dataset / "tasks/sealed_test.json", include_sealed_test=True)
    write_json(dataset / "source-manifest.json", normalized["source_manifest"])
    write_json(dataset / "official-exclusions.json", exclusions)
    write_json(dataset / "split-audit.json", {**split["audit"], "assignments": split["assignments"]})
    write_json(dataset / "task-audit.json", {**built["audit"], "split_audit": audit,
                                         "expression_audits": {t["task_id"]: audit_expression(t) for t in tasks}})
    write_json(dataset / "quarantine.json", split["quarantined"])
    write_json(dataset / "rejections.json", {"source": normalized["rejected"], "tasks": built["rejected"]})
    write_json(dataset / "review-queue.json", make_review_queue(products, tasks, semantic, seed=config["seed"]))
    gate = release_gate(products, tasks, [], exclusions, engineering=engineering)
    write_json(dataset / "release-gate.json", gate)
    checks = [{"name": "nonempty_source_and_tasks", "passed": bool(products and tasks)},
              {"name": "declared_sibling_and_product_split_isolation", "passed": audit["passed"]},
              {"name": "feasible_solution_sets_match_full_retrieval_split",
               "passed": all(t["feasible_product_ids"] == feasible_products(t, products) for t in tasks)},
              {"name": "literal_hidden_value_checks", "passed": all(audit_expression(t)["passed"] for t in tasks)},
              {"name": "provided_official_id_quarantine", "passed": not
               ({p["product_id"] for p in products} & set(exclusions.get("product_ids", [])))}]
    by_id = {t["task_id"]: t for t in tasks}
    for task in tasks:
        if task["variant_kind"] == "counterfactual":
            parent = by_id[task["parent_task_id"]]
            changed = [a["id"] for a, b in zip(parent["constraints"], task["constraints"]) if a != b]
            checks.append({"name": "single_constraint_counterfactual:" + task["task_id"],
                           "passed": changed == [task["changed_constraint_id"]] and
                           parent["split"] == task["split"] and
                           set(parent["feasible_product_ids"]).isdisjoint(task["feasible_product_ids"])})
    artifacts = {str(p.relative_to(dataset)): sha256_file(p) for p in sorted(dataset.rglob("*")) if p.is_file()}
    manifest = {"schema_version": 1, "stage": "S2", "revision": revision, "created_at": timestamp(),
                "source_kind": config["source_kind"], "engineering_only": engineering,
                "source_path": str(source_path), "source_sha256": sha256_file(source_path),
                "source_revision": normalized["source_manifest"].get("revision"),
                "source_manifest": normalized["source_manifest"], "seed": config["seed"],
                "official_exclusions_sha256": sha256_file(exclusions_path), "products": len(products),
                "quarantined_products": len(split["quarantined"]),
                "task_counts": {name: sum(t["split"] == name for t in tasks) for name in ("train", "dev", "sealed_test")},
                "base_counts": built["audit"]["base_counts"],
                "counterfactual_pairs": built["audit"]["counterfactual_pairs"],
                "expression_augmentations": 0, "source_rejections": len(normalized["rejected"]),
                "task_rejections": len(built["rejected"]), "teacher_successes": 0,
                "human_review_count": 0, "independent_model_reviews": 0,
                "release_status": "withheld", "artifact_sha256": artifacts}
    write_json(dataset / "manifest.json", manifest)
    report = {"stage": "S2", "status": "passed" if all(c["passed"] for c in checks) else "failed",
              "validation_level": "cpu_dataset_construction_only", "checks": checks,
              "data_revision": revision, "counts": manifest["task_counts"], "products": len(products),
              "counterfactual_pairs": manifest["counterfactual_pairs"], "release_gate": gate,
              "stage_complete": False, "gpu_compute_performed": False,
              "limitations": ["CPU build acceptance does not validate a real expert teacher",
                              "Official-family coverage, independent semantic review and human reviews remain explicit gates"]}
    write_json(output / "report.json", report)
    return {"json": str(output / "report.json"), "dataset_manifest": str(dataset / "manifest.json"),
            "dataset": str(dataset), "review_queue": str(dataset / "review-queue.json")}


def load_dataset(dataset: Path) -> tuple[dict, list[dict], dict[str, dict]]:
    """Verify immutable inventories and load collection-eligible tasks only."""
    dataset = dataset.resolve()
    manifest = _read(dataset / "manifest.json")
    for relative, expected in manifest["artifact_sha256"].items():
        path = (dataset / relative).resolve()
        if dataset not in path.parents or sha256_file(path) != expected:
            raise ValueError("Dataset artifact escapes inventory or hash differs: " + relative)
    products = _read(dataset / "catalog.json")["products"]
    tasks = {}
    for split in ("train", "dev"):
        revision, selected = load_tasks(dataset / "tasks" / (split + ".json"))
        if revision != manifest["revision"]:
            raise ValueError("Task revision differs from dataset manifest")
        tasks.update(selected)
    return manifest, products, tasks


def collect_dataset(dataset: Path, output: Path, *, mode: str, teacher_config: dict,
                    public_config: dict, limit: int = 2, seed: int = 0,
                    cache_directory: Path | None = None) -> dict[str, str]:
    """Collect real tool episodes, replay each, and keep all acceptance decisions."""
    if mode not in ("engineering", "api", "cache_only") or type(limit) is not int or limit <= 0:
        raise ValueError("Explicit collection mode and positive limit required")
    manifest, products, tasks = load_dataset(dataset)
    policy_version = "s2-scripted-observation-v1" if mode == "engineering" else "s2-expert-tool-v1"
    if mode == "engineering":
        teacher = ScriptedTeacher(**public_config)
    else:
        teacher = OpenAIHTTPTeacher(teacher_config, cache_directory=cache_directory or output / "teacher-cache",
                                    policy_version=policy_version, allow_network=mode == "api",
                                    cache_only=mode == "cache_only")
    ledgers, episodes, costs = [], [], []
    selected = sorted((t for t in tasks.values() if t["split"] == "train"), key=lambda t: t["task_id"])[:limit]
    for task in selected:
        catalog = Catalog(dataset / "catalog", task["split"])
        env = ProcurementEnv(catalog, task, policy_version=policy_version)
        try:
            episode = collect_episode(env, teacher, output=output / "episodes" / task["task_id"], seed=seed)
            ledger = _source_gate(manifest, replay_episode(catalog, task, episode))
            ledgers.append(ledger)
            episodes.append(episode)
            costs.append(episode["collection"]["teacher"].get("new_request_cost_estimate_usd"))
        finally:
            env.close()
        if episode["collection"].get("error") and mode != "engineering":
            break  # Stop instead of repeating missing-key/billing-uncertain failures.
    write_json(output / "accept-reject-ledger.json", ledgers)
    gate = release_gate(products, list(tasks.values()), ledgers,
                        _read(dataset / "official-exclusions.json"), engineering=manifest["engineering_only"])
    write_json(output / "release-gate.json", gate)
    candidates = output / "expert-candidates.jsonl"
    with candidates.open("x", encoding="utf-8") as handle:
        for episode, ledger in zip(episodes, ledgers):
            if ledger["expert_eligible"]:
                handle.write(json.dumps({"episode": episode, "acceptance": ledger}, ensure_ascii=False) + "\n")
    credential_missing = False
    if mode == "api":
        try:
            teacher._secret()  # Local configuration validation; no request and no secret is logged.
        except TeacherError:
            credential_missing = True
    accepted = sum(r["accepted"] for r in ledgers)
    succeeded = bool(ledgers) and all(r["accepted"] for r in ledgers)
    report = {"stage": "S2", "status": "blocked" if credential_missing else "passed" if succeeded else "failed",
              "validation_level": ("not_run_missing_credentials" if credential_missing else
                  "cpu_engineering_collection_and_replay" if mode == "engineering" else
                  "real_teacher_collection_and_replay" if succeeded else "teacher_collection_attempt_failed"),
              "mode": mode, "data_revision": manifest["revision"], "dataset_manifest_sha256": sha256_file(dataset / "manifest.json"),
              "policy_version": policy_version, "seed": seed, "attempted": len(ledgers), "replay_accepted": accepted,
              "rejected": len(ledgers) - accepted, "expert_candidates": sum(r["expert_eligible"] for r in ledgers),
              "cost_estimate_usd": sum(costs) if costs and all(c is not None for c in costs) else None,
              "billed_cost_usd": None, "release_gate": gate, "stage_complete": False,
              "blockers": ["teacher_credentials_missing"] if credential_missing else [],
              "gpu_compute_performed": False, "teacher": teacher.metadata()}
    write_json(output / "report.json", report)
    return {"json": str(output / "report.json"), "ledger": str(output / "accept-reject-ledger.json"),
            "expert_candidates": str(candidates), "release_gate": str(output / "release-gate.json")}


def audit_release(dataset: Path, collection: Path, output: Path, *, reviews_path: Path | None = None) -> dict[str, str]:
    """Recompute replay ledgers and evaluate supplied hash-bound reviewer decisions."""
    manifest, products, tasks = load_dataset(dataset)
    _, sealed = load_tasks(dataset / "tasks/sealed_test.json", include_sealed_test=True)
    all_tasks = {**tasks, **sealed}
    collection_report = _read(collection / "report.json")
    if (collection_report.get("data_revision") != manifest["revision"] or
            collection_report.get("dataset_manifest_sha256") != sha256_file(dataset / "manifest.json")):
        raise ValueError("Collection belongs to another dataset version")
    ledgers = []
    for path in sorted((collection / "episodes").glob("*/episode.json")):
        episode = _read(path)
        task = tasks.get(episode.get("task_id"))
        if task is None or task["split"] != "train":
            raise ValueError("Collection contains an unknown or test task")
        ledgers.append(_source_gate(manifest, replay_episode(Catalog(dataset / "catalog", "train"), task, episode)))
    reviews = _read(reviews_path) if reviews_path else {}
    gate = release_gate(products, list(all_tasks.values()), ledgers, _read(dataset / "official-exclusions.json"),
                        human_reviews=reviews.get("human_reviews"), identity_reviews=reviews.get("identity_reviews"),
                        independent_reviews=reviews.get("independent_reviews"), engineering=manifest["engineering_only"])
    write_json(output / "replay-ledger.json", ledgers)
    report = {"stage": "S2", "status": "passed", "validation_level": "cpu_replay_and_release_gate_audit",
              "data_revision": manifest["revision"], "release_gate": gate,
              "review_file": None if reviews_path is None else {"path": str(reviews_path), "sha256": sha256_file(reviews_path)},
              "replay_accepted": sum(r["accepted"] for r in ledgers), "episodes": len(ledgers),
              "stage_complete": gate["ready_for_formal_training"], "gpu_compute_performed": False}
    write_json(output / "report.json", report)
    write_json(output / "release-decision.json", {**gate, "dataset_revision": manifest["revision"],
               "dataset_manifest_sha256": sha256_file(dataset / "manifest.json"),
               "approved_expert_task_ids": sorted(r["task_id"] for r in ledgers if r["expert_eligible"])
                if gate["ready_for_formal_training"] else []})
    return {"json": str(output / "report.json"), "ledger": str(output / "replay-ledger.json"),
            "release_decision": str(output / "release-decision.json")}
