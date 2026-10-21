"""S2 teacher boundaries and real replay tests using fictional S1 CPU fixtures.

No external teacher, GPU or model is called. A loopback-only standard-library
HTTP server exercises urllib transport, serialization, response handling,
credential redaction and cache resume. Its responses are engineering scripts.
"""

import copy
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error

from procure_rl.data.teacher import (OpenAIHTTPTeacher, ScriptedTeacher, TeacherError,
                                     collect_episode)
from procure_rl.data.replay import replay_episode
from procure_rl.env import Catalog, ProcurementEnv, build_catalog, load_tasks
from procure_rl.env.catalog import digest

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def local_teacher():
    """Loopback HTTP transport with an observation-only engineering responder."""
    seen = []
    script = ScriptedTeacher()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"payload": payload, "authorization": self.headers.get("Authorization")})
            action = script.next_action(payload["messages"], payload["tools"])
            response = {"id": "local-response-" + str(len(seen)), "model": "local-boundary-test-model",
                        "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
                            "id": "provider-call-" + str(len(seen)), "type": "function",
                            "function": {"name": action["name"], "arguments": json.dumps(action["arguments"])}}]}}],
                        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
                        "api_key": "test-secret-never-log", "echo": "test-secret-never-log"}
            body = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class DataTeacherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.base = Path(cls.directory.name)
        cls.catalog_path = cls.base / "catalog"
        build_catalog(ROOT / "fixtures/s1/catalog.json", cls.catalog_path)
        _, cls.tasks = load_tasks(ROOT / "fixtures/s1/tasks.json")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.run_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.run_directory.cleanup)
        self.output = Path(self.run_directory.name)
        self.task = copy.deepcopy(self.tasks["task-train-dual"])
        self.catalog = Catalog(self.catalog_path, "train")

    def env(self, task=None, catalog=None):
        env = ProcurementEnv(catalog or self.catalog, task or self.task, policy_version="s2-test-policy")
        self.addCleanup(env.close)
        return env

    def collect(self, *, teacher=None, name="episode", task=None, catalog=None):
        return collect_episode(self.env(task, catalog), teacher or ScriptedTeacher(), output=self.output / name, seed=7)

    def http_config(self, base_url):
        return {"base_url": base_url, "model": "local-model", "env_var": "PROCURE_TEST_KEY",
                "max_requests": 30, "max_cost_usd": 3, "request_cost_cap_usd": .1,
                "max_tokens": 500, "thinking": {"type": "disabled"},
                "selection_status": "agent_selected_provisional", "expected_model_revision": "unknown",
                "input_per_million_usd": .30, "output_per_million_usd": 1.20}

    def http_teacher(self, config, **kwargs):
        return OpenAIHTTPTeacher(config, cache_directory=self.output / "cache", policy_version="s2-test-policy", **kwargs)

    def test_observation_driven_script_real_success_and_engineering_exclusion(self):
        episode = self.collect()
        self.assertTrue(episode["terminal_validation"]["delivery_success"])
        ledger = replay_episode(self.catalog, self.task, episode)
        self.assertTrue(ledger["accepted"], ledger)
        self.assertFalse(ledger["expert_eligible"])
        self.assertEqual(ledger["expert_exclusion"], "engineering_only")
        self.assertTrue((self.output / "episode/messages.json").exists())

    def test_teacher_receives_only_public_observations_and_schemas(self):
        class Spy(ScriptedTeacher):
            def next_action(self, messages, tools):
                text = json.dumps(messages)
                for prohibited in ('"constraints"', '"clarifications"', '"terminal_validation"',
                                   '"task_sha256"', '"native_state"', '"acceptable_product_ids"'):
                    if prohibited in text:
                        raise AssertionError("Private state in prompt")
                if len(messages) == 2:
                    initial = json.loads(messages[1]["content"])
                    if [r["id"] for r in initial["requirements"]] != ["budget"]:
                        raise AssertionError("Hidden requirements leaked")
                return super().next_action(messages, tools)
        self.assertIsNone(self.collect(teacher=Spy())["collection"]["error"])

    def test_collection_failure_retained_and_no_existing_output_overwrite(self):
        class Broken:
            def next_action(self, messages, tools):
                raise TeacherError("secret-message-should-not-be-saved")
        episode = self.collect(teacher=Broken())
        self.assertFalse(episode["done"])
        self.assertEqual(episode["collection"]["error"], "TeacherError")
        self.assertNotIn("secret-message", (self.output / "episode/episode.json").read_text())
        self.assertFalse(replay_episode(self.catalog, self.task, episode)["accepted"])
        with self.assertRaises(FileExistsError):
            self.collect()

    def test_test_splits_cannot_enter_collection(self):
        for split in ("sealed_test", "official_test"):
            task = copy.deepcopy(self.task)
            task["split"] = split
            with self.assertRaises(ValueError):
                self.collect(task=task, catalog=Catalog(self.catalog_path, split), name=split)

    def test_replay_rejects_history_rewards_events_budget_state_and_dialogue_tampering(self):
        episode = self.collect()
        edits = [lambda e: e["transitions"][0]["observation"].update(remaining_steps=99),
                 lambda e: e["transitions"][0].update(step_reward=123),
                 lambda e: e["transitions"][0]["verifier_events"].clear(),
                 lambda e: e["step_rewards"].append(1),
                 lambda e: e.update(final_state_sha256="0" * 64),
                 lambda e: e["public_messages"][0].update(content="Use hidden answers")]
        for edit in edits:
            with self.subTest(edit=edits.index(edit)):
                changed = copy.deepcopy(episode)
                edit(changed)
                self.assertFalse(replay_episode(self.catalog, self.task, changed)["accepted"])

    def test_replay_rejects_cross_task_catalog_revision_missing_terminal(self):
        episode = self.collect()
        for key, value in (("task_id", "wrong"), ("task_sha256", "wrong"),
                           ("catalog_sha256", "wrong"), ("data_revision", "wrong"), ("done", False)):
            changed = copy.deepcopy(episode)
            changed[key] = value
            self.assertFalse(replay_episode(self.catalog, self.task, changed)["accepted"])

    def test_final_reward_alone_does_not_accept_missing_evidence(self):
        class Guesser:
            def next_action(self, messages, tools):
                return {"name": "recommend_product", "arguments": {"product_id": "dock-train-a", "reasoning": "Guess"}}
        episode = self.collect(teacher=Guesser())
        self.assertEqual(episode["terminal_validation"]["terminal_reward"], 1)
        ledger = replay_episode(self.catalog, self.task, episode)
        self.assertFalse(ledger["accepted"])
        self.assertIn("incomplete_delivery", ledger["failure_types"])

    def test_loopback_http_boundary_cache_resume_redaction_and_raw_tool_ids(self):
        with local_teacher() as (url, seen), patch.dict(os.environ, {"PROCURE_TEST_KEY": "test-secret-never-log"}):
            config = self.http_config(url)
            episode = self.collect(teacher=self.http_teacher(config, allow_network=True))
            count = len(seen)
            self.assertGreater(count, 3)
            self.assertTrue(all(r["authorization"] == "Bearer test-secret-never-log" for r in seen))
            self.assertEqual(seen[0]["payload"]["thinking"], {"type": "disabled"})
            self.assertEqual(seen[1]["payload"]["messages"][2]["tool_calls"][0]["id"], "provider-call-1")
            ledger = replay_episode(self.catalog, self.task, episode)
            self.assertTrue(ledger["accepted"], ledger)
            # The HTTP backend could be a local test double; this test establishes
            # the transport boundary, never counts it as a real teacher result.
            resumed = self.collect(teacher=self.http_teacher(config, cache_only=True), name="resume")
            self.assertEqual(len(seen), count)
            self.assertTrue(all(r["cache_hit"] and not r["new_api_call"]
                                for r in resumed["collection"]["teacher"]["requests"]))
            self.assertEqual(resumed["transitions"], episode["transitions"])
            for path in self.output.rglob("*.json"):
                self.assertNotIn("test-secret-never-log", path.read_text())
            self.assertIsNone(episode["collection"]["teacher"]["model_revision"])

    def test_unknown_cost_remains_null_and_unconfigured_network_is_blocked(self):
        with local_teacher() as (url, seen), patch.dict(os.environ, {"PROCURE_TEST_KEY": "test-secret-never-log"}):
            config = self.http_config(url)
            config.pop("input_per_million_usd")
            config.pop("output_per_million_usd")
            teacher = self.http_teacher(config)
            with self.assertRaises(TeacherError):
                teacher.next_action([], [])
            self.assertEqual(seen, [])
            teacher = self.http_teacher(config, allow_network=True)
            teacher.next_action([], [])
            self.assertIsNone(teacher.metadata()["cost_usd"])
            self.assertIsNone(teacher.records[0]["cost_usd"])

    def test_missing_credentials_or_limits_fail_without_http(self):
        config = self.http_config("https://example.invalid")
        with patch.dict(os.environ, {}, clear=True):
            episode = self.collect(teacher=self.http_teacher(config, allow_network=True))
        self.assertEqual(episode["collection"]["error"], "TeacherError")
        self.assertFalse(any((self.output / "cache").glob("*.json")))
        for key in ("max_requests", "max_cost_usd", "request_cost_cap_usd"):
            invalid = dict(config)
            invalid.pop(key)
            with self.assertRaises(ValueError):
                self.http_teacher(invalid)

    def test_request_budget_persists_across_instances(self):
        with local_teacher() as (url, seen), patch.dict(os.environ, {"PROCURE_TEST_KEY": "test-secret-never-log"}):
            config = self.http_config(url)
            config["max_requests"] = 1
            first = self.http_teacher(config, allow_network=True)
            first.next_action([], [])
            second = self.http_teacher(config, allow_network=True)
            with self.assertRaises(TeacherError):
                second.next_action([{"role": "user", "content": "{}"}], [])
            self.assertEqual(len(seen), 1)

    def test_billing_uncertain_call_is_not_retried(self):
        config = self.http_config("https://example.invalid")
        class BrokenOpener:
            calls = 0
            def open(self, *args, **kwargs):
                self.calls += 1
                raise TimeoutError("secret-service-error")
        opener = BrokenOpener()
        with patch.dict(os.environ, {"PROCURE_TEST_KEY": "test-secret-never-log"}), \
                patch("urllib.request.build_opener", return_value=opener):
            for _ in range(2):
                with self.assertRaises(TeacherError):
                    self.http_teacher(config, allow_network=True).next_action([], [])
        self.assertEqual(opener.calls, 1)
        records = list((self.output / "cache").glob("*.json"))
        record = json.loads(records[0].read_text())
        self.assertEqual(record["status"], "billing_uncertain")
        self.assertNotIn("secret-service-error", records[0].read_text())

    def test_http_failure_preserves_redacted_raw_response_and_refuses_retry(self):
        config = self.http_config("https://example.invalid")
        class ErrorOpener:
            calls = 0
            def open(self, *args, **kwargs):
                self.calls += 1
                raise urllib.error.HTTPError("https://example.invalid/chat/completions", 429,
                                             "rate limited", {}, BytesIO(b'{"error":"test-secret-never-log"}'))
        opener = ErrorOpener()
        with patch.dict(os.environ, {"PROCURE_TEST_KEY": "test-secret-never-log"}), \
                patch("urllib.request.build_opener", return_value=opener):
            for _ in range(2):
                with self.assertRaises(TeacherError):
                    self.http_teacher(config, allow_network=True).next_action([], [])
        record = json.loads(next((self.output / "cache").glob("*.json")).read_text())
        self.assertEqual(opener.calls, 1)
        self.assertEqual(record["http_status"], 429)
        self.assertIn("[REDACTED]", record["raw_response_text"])
        self.assertNotIn("test-secret-never-log", json.dumps(record))

    def test_cache_identity_bound_to_policy_and_response_checksum(self):
        with local_teacher() as (url, seen), patch.dict(os.environ, {"PROCURE_TEST_KEY": "test-secret-never-log"}):
            config = self.http_config(url)
            self.http_teacher(config, allow_network=True).next_action([], [])
            other = OpenAIHTTPTeacher(config, cache_directory=self.output / "cache", policy_version="different", cache_only=True)
            with self.assertRaises(TeacherError):
                other.next_action([], [])
            path = next((self.output / "cache").glob("*.json"))
            record = json.loads(path.read_text())
            record["response"]["model"] = "tampered"
            path.write_text(json.dumps(record))
            with self.assertRaises(TeacherError):
                self.http_teacher(config, cache_only=True).next_action([], [])
            self.assertEqual(len(seen), 1)

    def test_changing_engineering_flag_does_not_forge_expert_provenance(self):
        episode = self.collect()
        episode["collection"]["teacher"].update(kind="http_teacher", engineering_only=False)
        ledger = replay_episode(self.catalog, self.task, episode)
        self.assertFalse(ledger["accepted"])
        self.assertFalse(ledger["expert_eligible"])
        self.assertIn("missing_teacher_http_evidence", ledger["failure_types"])

    def test_valid_public_dialogue_hash_cannot_hide_forged_history(self):
        episode = self.collect()
        episode["public_messages"][3]["content"] = json.dumps({"remaining_steps": 39})
        episode["messages_sha256"] = digest(episode["public_messages"])
        self.assertIn("public_dialogue_mismatch", replay_episode(self.catalog, self.task, episode)["failure_types"])


if __name__ == "__main__":
    unittest.main()
