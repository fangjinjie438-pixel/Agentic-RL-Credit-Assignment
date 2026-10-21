"""S1 real native-tool/session integration on fictional versioned SQLite facts.

No tool mocks, models, network or GPU. Manually written expectations supply the
terminal truth matrix; snapshot replay, concurrent isolation and attack cases
exercise the public reset/step/snapshot/restore contract used by future rollouts.
"""

from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from procure_rl.env import Catalog, ProcurementEnv, build_catalog, load_tasks
from procure_rl.env.catalog import digest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/s1"


def action(name, **arguments):
    return {"name": name, "arguments": arguments}


def final_action(product_id):
    fields = {"budget": ("details", "price"), "interface": ("details", "host_interface"),
              "displays": ("details", "display_count"), "power": ("reviews", "power_w")}
    return action("recommend_product", product_id=product_id, reasoning="Verified the observed product facts.",
                  checks=[{"constraint_id": key, "evidence_ids": [f"{product_id}:{channel}:{field}"]}
                          for key, (channel, field) in fields.items()])


def prepare(env, product_id):
    return [env.step(a) for a in (
        action("get_user_profile"), action("ask_user", question="How many displays?"),
        action("ask_user", question="How much power?"),
        action("get_product_details", product_id=product_id),
        action("get_review_content", product_id=product_id, query="power"))]


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "catalog"
        build_catalog(FIXTURE / "catalog.json", cls.path)
        cls.revision, cls.tasks = load_tasks(FIXTURE / "tasks.json")
        cls.expected = json.loads((FIXTURE / "expectations.json").read_text())["tasks"]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def env(self, task_id="task-train-dual", task=None):
        task = task or self.tasks[task_id]
        env = ProcurementEnv(Catalog(self.path, task["split"]), task)
        self.addCleanup(env.close)
        return env

    def test_manual_matrix_all_candidates_and_multiple_legal_answers(self):
        for task_id, expected in self.expected.items():
            for pid, truth in expected["constraint_truth"].items():
                with self.subTest(task_id=task_id, product=pid):
                    env = self.env(task_id)
                    prepare(env, pid)
                    result = env.step(final_action(pid))
                    report = result.terminal_validation
                    self.assertEqual({r["constraint_id"]: r["satisfied"] for r in report["constraint_results"]}, truth)
                    self.assertEqual(result.terminal_reward, float(pid in expected["acceptable_product_ids"]))
                    self.assertEqual(report["delivery_success"], pid in expected["acceptable_product_ids"])

    def test_public_observations_gate_hidden_needs_and_review_evidence(self):
        env = self.env()
        initial = env.reset(seed=13)
        self.assertEqual([r["id"] for r in initial["requirements"]], ["budget"])
        self.assertNotIn("persona", initial)
        self.assertNotIn("clarifications", initial)
        self.assertEqual([r["id"] for r in env.step(action("get_user_profile")).observation["requirements"]], ["interface"])
        details = env.step(action("get_product_details", product_id="dock-train-a"))
        self.assertNotIn("power_w", details.observation["product"]["details"])
        self.assertFalse(any(e["field"] == "power_w" for e in details.observation["evidence"]))
        empty = env.step(action("get_review_content", product_id="dock-train-a", query="nonexistentword"))
        self.assertNotIn("evidence", empty.observation)
        review = env.step(action("get_review_content", product_id="dock-train-a", query="power"))
        self.assertEqual([e["field"] for e in review.observation["evidence"]], ["power_w"])

    def test_same_snapshot_action_observation_events_rng_and_budget(self):
        env = self.env()
        env.reset(seed=7)
        env.step(action("get_user_profile"))
        snapshot = json.loads(json.dumps(env.snapshot()))
        call = action("ask_user", question="How many displays?")
        first = env.step(call)
        env.restore(snapshot)
        self.assertEqual(env.step(call), first)
        fork = self.env()
        fork.restore(snapshot)
        self.assertEqual(fork.step(call), first)
        snapshot["state"]["history"].clear()
        self.assertEqual(len(env.history), 2)

    def test_snapshot_tampering_rejected_even_with_recomputed_checksum(self):
        env = self.env()
        snapshot = env.snapshot()
        snapshot["state"]["remaining_steps"] += 5
        with self.assertRaises(ValueError):
            env.restore(snapshot)
        snapshot["sha256"] = digest(snapshot["state"])
        with self.assertRaises(ValueError):
            env.restore(snapshot)
        self.assertEqual(len(env.history), 0)

    def test_cross_task_or_policy_snapshot_rejected(self):
        snapshot = self.env().snapshot()
        with self.assertRaises(ValueError):
            self.env("task-dev-dual").restore(snapshot)
        other = self.env()
        other.policy_version = "another-policy"
        with self.assertRaises(ValueError):
            other.restore(snapshot)

    def test_non_json_action_rejection_can_be_restored(self):
        env = self.env()
        result = env.step(action("search_products", query=float("nan")))
        self.assertEqual(result.step_reward, -0.05)
        snapshot = env.snapshot()
        env.restore(json.loads(json.dumps(snapshot)))
        self.assertEqual(env.snapshot(), snapshot)

    def test_deep_json_is_a_recorded_invalid_attempt(self):
        env = self.env()
        result = env.step("[" * 1200 + "0" + "]" * 1200)
        self.assertEqual(result.step_reward, -0.05)
        self.assertEqual(result.observation["remaining_steps"], 39)
        snapshot = env.snapshot()
        env.restore(snapshot)
        self.assertEqual(env.snapshot(), snapshot)

    def test_concurrent_sessions_are_independent(self):
        left, right = self.env(), self.env()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(env.step, action("ask_user", question=question))
                       for env, question in ((left, "How many displays?"), (right, "How much power?"))]
            results = [future.result() for future in futures]
        self.assertEqual([r["id"] for r in results[0].observation["requirements"]], ["displays"])
        self.assertEqual([r["id"] for r in results[1].observation["requirements"]], ["power"])
        self.assertNotIn("power", left.revealed)
        self.assertNotIn("displays", right.revealed)

    def test_split_scoping_search_detail_filter_reviews_recommendation(self):
        env = self.env()
        result = env.step(action("search_products", query="dock"))
        self.assertEqual({p["product_id"] for p in result.observation["products"]},
                         set(self.expected["task-train-dual"]["constraint_truth"]))
        self.assertIsNone(env.catalog.product("dock-dev-a"))
        for pid in ("dock-dev-a", "dock-sealed-a", "dock-official-a"):
            result = env.step(action("get_product_details", product_id=pid))
            self.assertIn("error", result.observation)
            self.assertLess(result.step_reward, 0)
            result = env.step(action("get_review_content", product_id=pid, query="power"))
            self.assertFalse(result.observation["reviews"])
        result = env.step(final_action("dock-dev-a"))
        self.assertTrue(result.done)
        self.assertEqual(result.terminal_reward, 0)

    def test_readonly_query_and_no_sidecar_writes(self):
        catalog = Catalog(self.path, "train")
        conn = catalog.connect()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM products")
        finally:
            conn.close()
        env = self.env()
        prepare(env, "dock-train-a")
        self.assertFalse(Path(str(catalog.path) + "-wal").exists())
        self.assertEqual(digest(env.catalog.product("dock-train-a")), digest(catalog.product("dock-train-a")))

    def test_invalid_actions_are_logged_penalized_and_consume_budget(self):
        env = self.env()
        for raw in ("bad json", '{"name":"x","name":"y","arguments":{}}',
                    action("python_execute", code="pass"), action("get_product_details", product_id=7),
                    action("search_products", query="dock", page=True),
                    action("search_products", query="dock", page=10**30),
                    action("get_user_profile", injected="displays power")):
            result = env.step(raw)
            self.assertAlmostEqual(result.step_reward, -0.05)
            self.assertIn("error", result.observation)
        self.assertEqual(len(env.history), 7)

    def test_reward_cap_repeat_keyword_stuffing_and_self_repair(self):
        env = self.env()
        results = prepare(env, "dock-train-a")
        self.assertAlmostEqual(sum(r.step_reward for r in results), 1.0)
        for _ in range(3):
            result = env.step(action("get_product_details", product_id="dock-train-a"))
            self.assertAlmostEqual(result.step_reward, -0.02)
        bad = env.step(action("get_product_details", product_id="missing"))
        self.assertAlmostEqual(bad.step_reward, -0.05)
        fixed = env.step(action("get_product_details", product_id="dock-train-b"))
        self.assertEqual(fixed.step_reward, 0)
        stuffed = env.step(action("ask_user", question="power displays budget interface " * 5))
        self.assertEqual(stuffed.step_reward, -0.05)
        self.assertLessEqual(sum(max(0, r["step_reward"]) for r in env.history), 1.0 + 1e-12)

    def test_clarification_limit_preserved_in_snapshot(self):
        task = copy.deepcopy(self.tasks["task-train-dual"])
        task["max_clarifications"] = 1
        env = self.env(task=task)
        env.step(action("ask_user", question="How many displays?"))
        snapshot = env.snapshot()
        exhausted = env.step(action("ask_user", question="How much power?"))
        self.assertEqual(exhausted.step_reward, -0.05)
        self.assertNotIn("power", env.revealed)
        env.restore(snapshot)
        self.assertEqual(env.step(action("ask_user", question="How much power?")), exhausted)

    def test_budget_boundary_and_ended_session_requires_reset(self):
        task = copy.deepcopy(self.tasks["task-train-dual"])
        task["max_steps"] = 1
        env = self.env(task=task)
        result = env.step(action("search_products", query="dock"))
        self.assertTrue(result.done)
        self.assertTrue(result.terminal_validation["budget_exhausted"])
        self.assertEqual(result.terminal_reward, 0)
        with self.assertRaises(RuntimeError):
            env.step(final_action("dock-train-a"))
        env.reset()
        result = env.step(final_action("dock-train-a"))
        self.assertEqual(result.terminal_reward, 1)
        self.assertFalse(result.terminal_validation["delivery_success"])

    def test_missing_and_forged_evidence_are_separate_from_fact_reward(self):
        env = self.env()
        result = env.step(final_action("dock-train-a"))
        self.assertEqual(result.terminal_reward, 1)
        self.assertFalse(result.terminal_validation["delivery_success"])
        self.assertIn("unobserved_evidence", {e["code"] for e in result.terminal_validation["errors"]})

    def test_preterminal_restore_can_branch_but_cannot_undo_online_terminal(self):
        env = self.env()
        prepare(env, "dock-train-a")
        snapshot = env.snapshot()
        self.assertEqual(env.step(final_action("dock-train-one")).terminal_reward, 0)
        env.restore(snapshot)
        self.assertEqual(env.step(final_action("dock-train-a")).terminal_reward, 1)
        trajectory = env.trajectory()
        self.assertEqual(len(trajectory["step_rewards"]), len(trajectory["transitions"]))
        self.assertEqual(trajectory["policy_version"], "scripted-s1-v1")
        self.assertEqual(trajectory["turn_spans"], [])

    def test_catalog_hash_and_cross_split_family_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.json"
            data = json.loads((FIXTURE / "catalog.json").read_text())
            data["products"][-1]["family"] = data["products"][0]["family"]
            source.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                build_catalog(source, Path(directory) / "output")


if __name__ == "__main__":
    unittest.main()
