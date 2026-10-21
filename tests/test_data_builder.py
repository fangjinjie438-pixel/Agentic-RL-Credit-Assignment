"""S2 fact-first task, review gate and real CPU pipeline acceptance checks.

Independent synthetic product facts establish expected multi-solution and
counterfactual behavior. The pinned real excerpt additionally traverses source
verification, normalization, split assignment, SQLite tools, collection/replay
and release audit. No network, teacher API, model or GPU is used by these tests.
Root records the unified unittest command/results; temporary artifacts are local.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from procure_rl.data.builder import (apply_expression_rewrite, audit_expression,
                                    build_tasks, feasible_products)
from procure_rl.data.pipeline import (_source_gate, audit_release, build_dataset,
                                     collect_dataset, load_dataset, verify_raw_artifact)
from procure_rl.data.review import make_review_queue, release_gate
from procure_rl.env import load_tasks
from procure_rl.env.catalog import digest


ROOT = Path(__file__).resolve().parents[1]


def _product(pid, price, interface="USB-C", displays=2, *, split="train", title=None):
    specs = {"host_interface": interface, "display_count": displays}
    evidence = []
    for field, value in {"price": price, **specs}.items():
        evidence.append({"evidence_id": f"{pid}:details:{field}", "product_id": pid,
                         "field": field, "value": value, "channel": "details",
                         "text": f"The documented {field} is {value}."})
    return {"product_id": pid, "family": f"independent family {pid}", "split": split,
            "title": title or f"Office dock model {pid}", "price": price,
            "specs": specs, "evidence": evidence}


def _products():
    return [_product("a", 120), _product("b", 110),
            _product("c", 100, "USB-A"), _product("d", 90, displays=1)]


def _template():
    return {"template_id": "independent-dock-v1", "item_description": "office device",
            "constraints": [
                {"id": "budget", "source": "query", "field": "price", "op": "lte"},
                {"id": "interface", "source": "persona", "field": "host_interface", "op": "eq"},
                {"id": "displays", "source": "clarification", "field": "display_count", "op": "gte",
                 "question": "How many displays must be supported?", "trigger_keywords": ["displays"]}],
            "counterfactual_constraint_ids": ["interface"]}


def _built():
    return build_tasks(_products(), [_template()])


def _base(anchor="a"):
    return next(t for t in _built()["tasks"]
                if t["variant_kind"] == "base" and t["construction_anchor"] == anchor)


def _review(task, *, decision="accept", **extra):
    return {"task_id": task["task_id"], "task_sha256": digest(task), "role": "human",
            "reviewer": "synthetic-test-reviewer", "reviewed_at": "test-only",
            "decision": decision, **extra}


class DataBuilderTests(unittest.TestCase):
    def test_fact_first_task_accepts_both_independently_legal_products(self):
        products = _products()
        before = deepcopy(products)
        built = build_tasks(products, [_template()])
        base = next(t for t in built["tasks"] if t["variant_kind"] == "base" and
                    t["construction_anchor"] == "a")
        self.assertEqual(base["feasible_product_ids"], ["a", "b"])
        self.assertEqual(feasible_products(base, products), ["a", "b"])
        self.assertEqual(products, before)
        self.assertEqual(base["teacher_expression_review"], "not_run")
        self.assertEqual(base["human_review"], "pending")

    def test_interface_counterfactual_changes_one_condition_and_decision(self):
        built = _built()
        parent = next(t for t in built["tasks"] if t["variant_kind"] == "base" and
                      t["construction_anchor"] == "a")
        sibling = next(t for t in built["tasks"] if t.get("parent_task_id") == parent["task_id"])
        changes = [(a["id"], a["value"], b["value"]) for a, b in zip(
            parent["constraints"], sibling["constraints"]) if a != b]
        self.assertEqual(changes, [("interface", "USB-C", "USB-A")])
        self.assertEqual(sibling["feasible_product_ids"], ["c"])
        self.assertTrue(set(parent["feasible_product_ids"]).isdisjoint(sibling["feasible_product_ids"]))
        self.assertEqual(parent["split"], sibling["split"])
        self.assertEqual(parent["pair_id"], sibling["pair_id"])
        self.assertEqual(parent["root_task_id"], sibling["root_task_id"])

    def test_rewrite_preserves_truth_and_remains_separate_from_counterfactual(self):
        base = _base()
        before = deepcopy(base)
        rewrite = apply_expression_rewrite(base, {"query": base["query"].replace("Please recommend", "Find")})
        self.assertEqual(rewrite["variant_kind"], "rewrite")
        self.assertEqual(rewrite["constraints"], base["constraints"])
        self.assertEqual(rewrite["feasible_product_ids"], base["feasible_product_ids"])
        self.assertEqual(rewrite["split"], base["split"])
        self.assertEqual(rewrite["parent_task_id"], base["task_id"])
        self.assertEqual(rewrite["root_task_id"], base["root_task_id"])
        self.assertEqual(base, before)
        with self.assertRaises(ValueError):
            apply_expression_rewrite(base, {"constraints": []})

    def test_literal_hidden_value_leak_is_rejected(self):
        base = _base()
        proposal = {"query": base["query"] + " It must support 2 displays."}
        with self.assertRaises(ValueError):
            apply_expression_rewrite(base, proposal)
        leaked = deepcopy(base)
        leaked.update(proposal)
        self.assertIn("hidden_value_leak", {e["code"] for e in audit_expression(leaked)["errors"]})

    def test_numeric_one_is_not_confused_with_default_one_item_request(self):
        base = _base("d")
        self.assertIn("recommend one", base["query"])
        hidden = next(c for c in base["constraints"] if c["source"] == "clarification")
        self.assertEqual(hidden["value"], 1)
        self.assertTrue(audit_expression(base)["passed"])
        leaked = deepcopy(base)
        leaked["query"] += " The display count must be 1."
        self.assertFalse(audit_expression(leaked)["passed"])

    def test_anchor_title_filter_does_not_hide_other_legal_retrieval_products(self):
        products = [_product("a", 120, title="Anchor docking station"),
                    _product("b", 110, title="Other office expansion device")]
        template = {**_template(), "title_contains": "Anchor"}
        built = build_tasks(products, [template])
        base = next(t for t in built["tasks"] if t["variant_kind"] == "base")
        self.assertEqual(base["feasible_product_ids"], ["a", "b"])
        self.assertEqual(feasible_products(base, products), base["feasible_product_ids"])
        evidence = {e for c in base["constraints"] for e in c["evidence_ids"]}
        self.assertIn("b:details:host_interface", evidence)

    def test_cross_split_duplicate_created_by_counterfactual_is_rejected(self):
        products = [_product("train-c", 100), _product("train-a", 90, "USB-A"),
                    _product("dev-a", 100, "USB-A", split="dev")]
        built = build_tasks(products, [_template()])
        self.assertIn("cross_split_variant_duplicate", {r["reason"] for r in built["rejected"]})
        definitions = {}
        for task in built["tasks"]:
            signature = digest([{key: c[key] for key in ("id", "source", "field", "op", "value")}
                                for c in task["constraints"]])
            definitions.setdefault(signature, set()).add(task["split"])
        self.assertTrue(all(len(splits) == 1 for splits in definitions.values()))

    def test_stale_reviews_id_only_officials_and_engineering_cannot_release(self):
        task = _base()
        stale = _review(task, task_sha256="stale-version")
        engineering_ledger = _source_gate({"engineering_only": True}, {
            "task_id": task["task_id"], "accepted": True, "expert_eligible": True})
        self.assertFalse(engineering_ledger["expert_eligible"])
        gate = release_gate(_products(), [task], [engineering_ledger],
                            {"metadata_complete": False, "coverage": "target_ids_only"},
                            human_reviews=[stale], engineering=True)
        self.assertFalse(gate["ready_for_formal_training"])
        self.assertTrue({"engineering_fixture_not_formal_data", "invalid_or_stale_human_reviews",
                         "official_family_and_near_duplicate_metadata_incomplete",
                         "no_replay_accepted_real_teacher_training_episodes"}.issubset(gate["reasons"]))

    def test_rejected_conflicting_reviews_and_model_disagreements_stay_pending(self):
        task = _base()
        ledger = {"task_id": task["task_id"], "accepted": True, "expert_eligible": True}
        independent = {"task_id": task["task_id"], "task_sha256": digest(task),
                       "status": "completed", "model_revision": "synthetic-test-only", "decision": "reject"}
        gate = release_gate([], [task], [ledger], {"metadata_complete": True},
                            human_reviews=[_review(task), _review(task, decision="reject")],
                            independent_reviews=[independent])
        self.assertTrue({"human_rejected_tasks_pending_removal", "conflicting_human_reviews",
                         "unadjudicated_model_disagreement"}.issubset(gate["reasons"]))
        self.assertFalse(gate["ready_for_formal_training"])
        adjudicated = release_gate([], [task], [ledger], {"metadata_complete": True},
            human_reviews=[_review(task, adjudicates_model_disagreement=True)], independent_reviews=[independent])
        self.assertNotIn("unadjudicated_model_disagreement", adjudicated["reasons"])
        self.assertFalse(adjudicated["ready_for_formal_training"])  # Only one synthetic review, not 200 humans.

    def test_review_queue_keeps_all_disagreements_outside_small_sample(self):
        tasks = []
        for index in range(4):
            task = deepcopy(_base())
            task.update(task_id=f"task-{index}", root_task_id=f"root-{index}", model_disagreement=index > 0)
            tasks.append(task)
        queue = make_review_queue([], tasks, [], sample_size=1)
        queued = {review["task_id"]: review for review in queue["task_reviews"]}
        self.assertTrue({"task-1", "task-2", "task-3"}.issubset(queued))
        self.assertEqual(queued["task-2"]["priority"], "mandatory_disagreement")
        self.assertEqual(queued["task-2"]["task_sha256"], digest(tasks[2]))
        self.assertFalse(queue["human_review_performed"])

    def test_sealed_tasks_require_explicit_loader_access(self):
        task = _base()
        task["split"] = "sealed_test"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sealed.json"
            path.write_text(json.dumps({"revision": "independent-test", "tasks": [task]}))
            with self.assertRaises(ValueError):
                load_tasks(path)
            revision, loaded = load_tasks(path, include_sealed_test=True)
            self.assertEqual(revision, "independent-test")
            self.assertEqual(loaded[task["task_id"]]["split"], "sealed_test")

    def test_real_sources_sqlite_collection_replay_and_release_audit(self):
        config = json.loads((ROOT / "configs/s2.json").read_text())
        config["split_ratios"] = {"train": 1}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            built = build_dataset(ROOT, root / "build", config)
            report = json.loads(Path(built["json"]).read_text())
            self.assertEqual(report["status"], "passed")
            dataset = Path(built["dataset"])
            manifest, products, tasks = load_dataset(dataset)
            self.assertFalse(manifest["engineering_only"])
            self.assertGreater(len(products), 0)
            self.assertGreater(len(tasks), 0)
            for task in tasks.values():
                self.assertEqual(task["feasible_product_ids"], feasible_products(task, products))
            collected = collect_dataset(dataset, root / "collection", mode="engineering", teacher_config={},
                public_config=config["engineering_policy"], limit=2, seed=0)
            collection = json.loads(Path(collected["json"]).read_text())
            self.assertGreaterEqual(collection["replay_accepted"], 1)
            self.assertEqual(collection["expert_candidates"], 0)
            self.assertEqual(Path(collected["expert_candidates"]).read_text(), "")
            audited = audit_release(dataset, root / "collection", root / "audit")
            decision = json.loads(Path(audited["release_decision"]).read_text())
            self.assertEqual(decision["status"], "withheld")
            self.assertEqual(decision["approved_expert_task_ids"], [])
            path = dataset / "tasks/train.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaises(ValueError):
                load_dataset(dataset)

    def test_rehashing_altered_curated_record_cannot_forge_original_source(self):
        payload = json.loads((ROOT / "fixtures/s2/amazon-electronics.json").read_text())
        record = payload["records"][0]
        record["raw"]["title"] = "Forged source title"
        record["raw_sha256"] = hashlib.sha256(json.dumps(record["raw"], sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        with self.assertRaises(ValueError):
            verify_raw_artifact(ROOT, payload)


if __name__ == "__main__":
    unittest.main()
