"""Check that S2 review exports preserve evidence without granting approval.

Input is the versioned engineering source, built into temporary real datasets.
The project CPU interpreter exports unsigned forms and model-review inputs;
tests independently check split boundaries, hashes, source quotes and failures.
No external model, network or GPU is used.
"""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from procure_rl.data.pipeline import build_dataset, load_dataset
from procure_rl.data.independent import CHECKS
from procure_rl.data.review import release_gate
from procure_rl.data.review_material import (independent_review_inputs,
                                            prepare_review_material, render_review_markdown)
from procure_rl.env.catalog import digest


ROOT = Path(__file__).resolve().parents[1]


class ReviewMaterialTests(unittest.TestCase):
    def test_real_export_is_unsigned_and_keeps_sealed_tasks_out_by_default(self):
        config = json.loads((ROOT / "configs/s2-engineering.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            built = build_dataset(ROOT, root / "build", config)
            dataset = Path(built["dataset"])
            command = [sys.executable, str(ROOT / "scripts/data/prepare_s2_review.py"),
                       "--dataset", str(dataset), "--output", str(root / "review")]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            material = json.loads((root / "review/review-material.json").read_text())
            forms = json.loads((root / "review/reviews-template.json").read_text())
            self.assertFalse(material["human_review_performed"])
            self.assertFalse(material["model_review_performed"])
            self.assertFalse(material["formal_release_approved"])
            self.assertTrue(material["private_reviewer_material"])
            self.assertEqual({p["task"]["split"] for p in material["task_packets"]}, {"train", "dev"})
            self.assertFalse(any(p["split"] == "sealed_test" for p in material["products"]))
            self.assertTrue(all(p["recorded_legal_set_matches_recomputed"] for p in material["task_packets"]))
            self.assertTrue(all(p["decision"] is None and p["reviewer"] is None for p in forms["human_reviews"]))
            self.assertEqual(forms["independent_reviews"], [])
            manifest, products, tasks = load_dataset(dataset)
            gate = release_gate(products, list(tasks.values()), [], {"metadata_complete": False},
                                human_reviews=forms["human_reviews"], identity_reviews=forms["identity_reviews"])
            self.assertEqual(gate["human_review_count"], 0)
            self.assertFalse(gate["ready_for_formal_training"])
            run = json.loads((root / "review/run.json").read_text())
            self.assertEqual(run["data_revision"], manifest["revision"])
            self.assertEqual(run["validation_level"], "private_review_material_export_only")
            self.assertFalse(run["gpu_compute_performed"])
            self.assertFalse(run["included_sealed_test"])

    def test_full_inputs_preserve_quotes_siblings_and_content_hashes(self):
        config = json.loads((ROOT / "configs/s2-engineering.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            dataset = Path(build_dataset(ROOT, Path(temporary) / "build", config)["dataset"])
            manifest, products, tasks = load_dataset(dataset)
            material = prepare_review_material(manifest, products, list(tasks.values()))
            raw = independent_review_inputs(material)
            self.assertEqual(len(raw), len(tasks))
            for row in raw:
                self.assertEqual(row["task_sha256"], digest(row["task"]))
                self.assertEqual(row["status"], "not_run")
                self.assertTrue(all(p["split"] == row["task"]["split"] for p in row["products"]))
                self.assertTrue(all(s["task_id"] in tasks for s in row["siblings"]))
            markdown = render_review_markdown(material)
            self.assertIn("尚未签核", markdown)
            self.assertIn("不要发送给执行教师或学生策略", markdown)
            evidence = material["products"][0]["evidence"][0]
            self.assertIn(json.dumps(evidence["text"], ensure_ascii=False), markdown)
            self.assertIn("200 条人工抽检", markdown)
            self.assertGreater(material["human_sample_shortfall"], 0)

    def test_official_tasks_cannot_be_exported_as_project_review_inputs(self):
        task = {"task_id": "official-only", "split": "official_test"}
        with self.assertRaises(ValueError):
            prepare_review_material({"revision": "test-only"}, [], [deepcopy(task)])

    def test_minimal_labels_tampered_responses_and_same_model_cannot_count_as_independent_review(self):
        task = {"task_id": "test-task", "root_task_id": "test-task", "split": "train"}
        review = {"task_id": task["task_id"], "task_sha256": digest(task), "status": "completed",
                  "model": "independent-test-reviewer", "model_revision": "synthetic-test-only",
                  "decision": "accept", "reviewed_at": "2026-10-22T00:00:00+08:00",
                  "prompt_version": "synthetic-test-v1", "prompt": {"task": task, "task_sha256": digest(task)},
                  "checks": {key: "pass" for key in CHECKS}, "reasons": ["Synthetic test fixture."],
                  "independence_basis": {"method": "different_model", "generation_models": ["synthetic-teacher"]}}
        review["raw_response"] = {key: review[key] for key in ("decision", "checks", "reasons")}
        review.update(prompt_sha256=digest(review["prompt"]), response_sha256=digest(review["raw_response"]))
        good = release_gate([], [task], [], {"metadata_complete": True}, independent_reviews=[review])
        self.assertEqual(good["independent_review_count"], 1)
        self.assertNotIn("independent_semantic_review_pending", good["reasons"])
        cases = {"minimal_label": {key: review[key] for key in
                 ("task_id", "task_sha256", "status", "model_revision", "decision")},
                 "tampered_response": {**review, "raw_response": {"decision": "reject"}},
                 "contradictory_rehashed_response": {**review, "raw_response": {"decision": "reject"},
                                                     "response_sha256": digest({"decision": "reject"})},
                 "tampered_prompt": {**review, "prompt": {"task": "another version"}},
                 "rehashed_wrong_task_prompt": {**review, "prompt": {"task": "another version"},
                                                "prompt_sha256": digest({"task": "another version"})},
                 "same_model": {**review, "model": "synthetic-teacher"},
                 "no_timezone": {**review, "reviewed_at": "2026-10-22T00:00:00"},
                 "unknown_revision": {**review, "model_revision": "unknown"}}
        for label, candidate in cases.items():
            with self.subTest(label=label):
                gate = release_gate([], [task], [], {"metadata_complete": True}, independent_reviews=[candidate])
                self.assertEqual(gate["independent_review_count"], 0)
                self.assertIn("invalid_or_untraceable_independent_reviews", gate["reasons"])
                self.assertIn("independent_semantic_review_pending", gate["reasons"])
                self.assertFalse(gate["ready_for_formal_training"])

    def test_runner_generated_text_is_reparsed_before_recorded_decision_can_count(self):
        task = {"task_id": "test-task", "root_task_id": "test-task", "split": "train"}
        parsed = {"decision": "reject", "checks": {key: "pass" for key in CHECKS},
                  "reasons": ["Synthetic task is too shallow."]}
        parsed["checks"]["procurement_quality"] = "fail"
        raw = {"generated_text": json.dumps(parsed), "generated_token_ids": [1, 2, 3],
               "input_tokens": 100, "output_tokens": 3, "finish_reason": "eos", "elapsed_seconds": 1.0}
        review = {"task_id": task["task_id"], "task_sha256": digest(task), "status": "completed", **parsed,
                  "model": "independent-test-reviewer", "model_revision": "synthetic-test-only",
                  "reviewed_at": "2026-10-22T00:00:00+08:00", "prompt_version": "synthetic-test-v1",
                  "prompt": {"task": task, "task_sha256": digest(task)}, "raw_response": raw,
                  "independence_basis": {"method": "different_model", "generation_models": ["synthetic-teacher"]}}
        review.update(prompt_sha256=digest(review["prompt"]), response_sha256=digest(raw))
        good = release_gate([], [task], [], {"metadata_complete": True}, independent_reviews=[review])
        self.assertEqual(good["independent_review_count"], 1)
        self.assertEqual(good["unadjudicated_task_ids"], [task["task_id"]])
        bad = {"decision_only": {**review, "decision": "accept"},
               "decision_and_checks": {**review, "decision": "accept", "checks": {key: "pass" for key in CHECKS}},
               "changed_checks": {**review, "checks": {key: "uncertain" for key in CHECKS}},
               "changed_reasons": {**review, "reasons": ["Different from raw output."]}}
        for label, payload in (("malformed_generated_text", {**raw, "generated_text": "not JSON"}),
                               ("uninterpretable_raw", {"provider_payload": "unparsed"}),
                               ("truncated_generation", {**raw, "finish_reason": "length"})):
            bad[label] = {**review, "raw_response": payload, "response_sha256": digest(payload)}
        for label, candidate in bad.items():
            with self.subTest(label=label):
                gate = release_gate([], [task], [], {"metadata_complete": True}, independent_reviews=[candidate])
                self.assertEqual(gate["independent_review_count"], 0)
                self.assertIn("invalid_or_untraceable_independent_reviews", gate["reasons"])
        raw_string = raw["generated_text"]
        string_review = {**review, "raw_response": raw_string, "response_sha256": digest(raw_string)}
        good_string = release_gate([], [task], [], {"metadata_complete": True}, independent_reviews=[string_review])
        self.assertEqual(good_string["independent_review_count"], 1)
        bad_string = release_gate([], [task], [], {"metadata_complete": True},
                                  independent_reviews=[{**string_review, "decision": "accept"}])
        self.assertEqual(bad_string["independent_review_count"], 0)


if __name__ == "__main__":
    unittest.main()
