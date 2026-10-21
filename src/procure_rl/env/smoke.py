"""Produce durable S1 acceptance evidence using real SQLite/native-tool episodes.

The CLI supplies a configuration and new run directory. Output includes a catalog
manifest, structured trajectories, preterminal snapshots, manual-truth comparisons
and a report. No model, official task, API, GPU or training path is involved.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import platform
import sqlite3

from ..runtime import sha256_file
from .catalog import Catalog, build_catalog, load_tasks
from .session import ProcurementEnv
from .upstream import UPSTREAM_REVISION


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _action(name: str, **arguments) -> dict:
    return {"name": name, "arguments": arguments}


def _final(task: dict, product: dict) -> dict:
    # This is an explicitly scripted engineering driver with access to fixtures,
    # not an expert demonstration or a model performance measurement.
    checks = [{"constraint_id": c["id"], "evidence_ids": [
        e["evidence_id"] for e in product["evidence"] if e["field"] == c["field"]]}
        for c in task["constraints"]]
    return _action("recommend_product", product_id=product["product_id"],
                   reasoning="Scripted S1 acceptance against fictional catalog facts.", checks=checks)


def run_smoke(project_root: Path, output: Path, config: dict) -> dict[str, str]:
    """Run each manual candidate truth case plus replay/isolation/budget probes."""
    if config.get("stage") != "S1" or type(config.get("seed")) is not int or not config.get("policy_version"):
        raise ValueError("Invalid S1 acceptance configuration")
    fixture = project_root / config["fixture_directory"]
    revision, tasks = load_tasks(fixture / "tasks.json")
    expected = json.loads((fixture / "expectations.json").read_text())
    manifest = build_catalog(fixture / "catalog.json", output / "catalog")
    if not (revision == manifest["revision"] == expected["revision"]):
        raise ValueError("Fixture revision mismatch")
    checks, scenarios = [], []

    def check(name, passed, **detail):
        checks.append({"name": name, "passed": bool(passed), **detail})

    trajectories = output / "trajectories"
    trajectories.mkdir()
    for task_id, task in tasks.items():
        catalog = Catalog(output / "catalog", task["split"])
        truth = expected["tasks"][task_id]
        for product_id, matrix in truth["constraint_truth"].items():
            env = ProcurementEnv(catalog, task, policy_version=config["policy_version"])
            try:
                initial = env.reset(seed=config["seed"])
                env.step(_action("search_products", query="dock"))
                env.step(_action("get_user_profile"))
                env.step(_action("ask_user", question="How many displays?"))
                env.step(_action("ask_user", question="How much power?"))
                env.step(_action("get_product_details", product_id=product_id))
                env.step(_action("get_review_content", product_id=product_id, query="power"))
                snapshot = env.snapshot()
                product = catalog.product(product_id)
                recommendation = _final(task, product)
                first = env.step(recommendation)
                env.restore(snapshot)
                second = env.step(recommendation)
                check(f"replay:{task_id}:{product_id}", first == second)
                actual = {r["constraint_id"]: r["satisfied"] for r in second.terminal_validation["constraint_results"]}
                is_legal = product_id in truth["acceptable_product_ids"]
                check(f"manual_truth:{task_id}:{product_id}", actual == matrix and
                      second.terminal_reward == float(is_legal) and
                      second.terminal_validation["delivery_success"] == is_legal, expected=matrix, actual=actual)
                positive = sum(max(0.0, step["step_reward"]) for step in env.history)
                check(f"positive_budget:{task_id}:{product_id}", positive <= 1.0 + 1e-12, actual=positive)
                name = task_id + "--" + product_id
                _write(trajectories / (name + ".json"), {"initial_observation": initial, **env.trajectory()})
                _write(trajectories / (name + "--preterminal.json"), snapshot)
                scenarios.append({"task_id": task_id, "product_id": product_id, "tool_calls": len(env.history),
                                  "terminal_reward": second.terminal_reward,
                                  "delivery_success": second.terminal_validation["delivery_success"],
                                  "trajectory": str(trajectories / (name + ".json"))})
            finally:
                env.close()
    task = tasks["task-train-dual"]
    catalog = Catalog(output / "catalog", "train")
    left, right = ProcurementEnv(catalog, task), ProcurementEnv(catalog, task)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(env.step, _action("ask_user", question=q)) for env, q in
                       ((left, "How many displays?"), (right, "How much power?"))]
            concurrent = [asdict(future.result()) for future in futures]
        check("concurrent_isolation", "displays" in left.revealed and "power" not in left.revealed
              and "power" in right.revealed and "displays" not in right.revealed)
        _write(output / "concurrent.json", concurrent)
        left.reset(seed=config["seed"])
        results = left.step(_action("search_products", query="dock")).observation["products"]
        expected_ids = set(expected["tasks"][task["task_id"]]["constraint_truth"])
        check("retrieval_split_isolation", {p["product_id"] for p in results} == expected_ids and
              all(catalog.product(pid) is None for pid in expected["isolation_only_product_ids"]))
        invalid = left.step(_action("python_execute", code="pass"))
        check("disabled_execution", invalid.step_reward == -0.05 and "error" in invalid.observation)
        left.step(_action("get_product_details", product_id="dock-train-a"))
        repeat = left.step(_action("get_product_details", product_id="dock-train-a"))
        check("repeat_penalty", repeat.step_reward == -0.02)
        while not left.done:
            left.step(_action("search_products", query="unmatched"))
        check("budget_exhaustion", left.terminal["budget_exhausted"] and left.terminal["terminal_reward"] == 0.0)
        _write(output / "budget-and-invalid.json", left.trajectory())
        conn = catalog.connect()
        try:
            readonly = False
            try:
                conn.execute("DELETE FROM products")
            except sqlite3.OperationalError:
                readonly = True
            check("readonly_database", readonly)
        finally:
            conn.close()
    finally:
        left.close()
        right.close()
    report = {"stage": "S1", "status": "passed" if all(c["passed"] for c in checks) else "failed",
              "validation_level": "cpu_native_tools_and_project_environment",
              "upstream_revision": UPSTREAM_REVISION, "data_revision": revision,
              "policy_version": config["policy_version"], "seed": config["seed"],
              "python_version": platform.python_version(), "sqlite_version": sqlite3.sqlite_version,
              "dependencies": "Python standard library only; no ML packages imported",
              "fixture_sha256": {name: sha256_file(fixture / name) for name in
                                  ("catalog.json", "tasks.json", "expectations.json")},
              "checks": checks, "scenarios": scenarios,
              "gpu_compute_performed": False, "model_revision": None,
              "limitations": ["Fictional engineering fixtures, not S2 training data or an expert demonstration",
                              "No full official product database or LLM judge evaluation",
                              "No tokenizer, real model multi-turn inference, GPU or training validation"]}
    _write(output / "report.json", report)
    (output / "report.md").write_text(
        "# S1 CPU acceptance\n\n" + f'Status: {report["status"]}; {sum(c["passed"] for c in checks)}/{len(checks)} checks.\n\n' +
        "Seven scripted candidate episodes use real native ECom tools and a fictional SQLite catalog.\n\n" +
        "Baseline reward checks catalog facts. Evidence delivery is reported separately.\n\n" +
        "Full official evaluation, model inference and training were not run.\n", encoding="utf-8")
    return {"json": str(output / "report.json"), "markdown": str(output / "report.md"),
            "catalog_manifest": str(output / "catalog/manifest.json"), "trajectories": str(trajectories)}
