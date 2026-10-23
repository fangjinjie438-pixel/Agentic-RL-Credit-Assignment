"""CPU checks for private review boundaries and strict independent JSON output.

Uses tiny synthetic tasks/model text only; no download, model import, API or GPU.
The real S2 Qwen3-8B execution has separate retained runtime evidence.
"""

import copy
import json
import unittest

from procure_rl.data.independent import CHECKS, make_independent_prompt, parse_independent_response
from procure_rl.env.catalog import digest


class IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        self.task = {"task_id": "review-task", "root_task_id": "root", "split": "train",
                     "query": "A device below $50", "persona": "Blue", "constraints": [
                         {"id": "budget", "field": "price", "source": "query", "op": "lte", "value": 50,
                          "evidence_ids": ["p1-price"]}],
                     "feasible_product_ids": ["p1"]}
        self.product = {"product_id": "p1", "title": "Travel keyboard", "price": 49,
                        "specs": {"color": "Blue", "weight_g": 1000}, "units": {"weight_g": "g"},
                        "evidence": [{"evidence_id": "p1-weight", "field": "weight_g", "value": 1000,
                                      "channel": "details", "text": "1 kg", "provenance": {
                                          "source_field": ["details", "Weight"], "raw_value": "1 kg",
                                          "raw_unit": "kg", "unit": "g", "source_row_index": 3,
                                          "raw_record_sha256": "a" * 64}}]}
        self.packet = {"task": self.task, "task_sha256": digest(self.task), "siblings": [], "products": [self.product]}

    def response(self, **changes):
        value = {"decision": "accept", "checks": {key: "pass" for key in CHECKS},
                 "reasons": ["All checks are supported by supplied facts."]}
        value.update(changes)
        return value

    def test_prompt_binds_complete_task_and_rejects_hidden_splits(self):
        original = copy.deepcopy(self.packet)
        prompt = make_independent_prompt(self.packet, dataset_revision="s2-test", related_tasks=[self.task],
                                         dataset_manifest_sha256="b" * 64)
        self.assertEqual(prompt["task"], self.task)
        self.assertEqual(prompt["task_sha256"], digest(self.task))
        self.assertEqual(prompt["dataset_manifest_sha256"], "b" * 64)
        self.assertEqual(prompt["complete_products_sha256"], digest([self.product]))
        projected = prompt["products"][0]
        self.assertEqual(projected["price"], 49)
        self.assertEqual(projected["specs"], self.product["specs"])
        self.assertEqual(projected["units"], self.product["units"])
        self.assertEqual(projected["evidence"][0]["text"], "1 kg")
        self.assertEqual(projected["evidence"][0]["value"], 1000)
        self.assertEqual(projected["evidence"][0]["provenance"], {
            "source_field": ["details", "Weight"], "raw_value": "1 kg", "raw_unit": "kg",
            "unit": "g", "source_row_index": 3})
        self.assertEqual(prompt["related_tasks"][0]["constraints"], [
            {"id": "budget", "source": "query", "field": "price", "op": "lte", "value": 50}])
        self.assertEqual(self.packet, original)
        for split in ("sealed_test", "official_test"):
            other = {**self.task, "split": split}
            with self.assertRaises(ValueError):
                make_independent_prompt(self.packet, dataset_revision="s2-test", related_tasks=[other])
            with self.assertRaises(ValueError):
                make_independent_prompt({**self.packet, "task": other, "task_sha256": digest(other)},
                                        dataset_revision="s2-test", related_tasks=[])

    def test_stale_review_input_hash_is_rejected(self):
        with self.assertRaises(ValueError):
            make_independent_prompt({**self.packet, "task_sha256": "bad"}, dataset_revision="s2-test", related_tasks=[])

    def test_accept_and_explicit_uncertainty_are_parsed(self):
        accepted = self.response()
        self.assertEqual(parse_independent_response(json.dumps(accepted)), accepted)
        rejected = copy.deepcopy(accepted)
        rejected["decision"] = "reject"
        rejected["checks"][CHECKS[0]] = "uncertain"
        self.assertEqual(parse_independent_response(json.dumps(rejected)), rejected)

    def test_no_repair_of_malformed_or_unfaithful_response(self):
        cases = ["", "```json\n{}\n```", '{"decision":"accept","decision":"reject"}',
                 json.dumps(self.response(extra="invented")), json.dumps(self.response(reasons=[])),
                 json.dumps(self.response(checks={"one_check": "pass"})),
                 json.dumps(self.response(decision="reject")), json.dumps(self.response(reasons=[False]))]
        contradictory = self.response()
        contradictory["checks"][CHECKS[0]] = "fail"
        cases.append(json.dumps(contradictory))
        for case in cases:
            with self.subTest(case=case), self.assertRaises((ValueError, TypeError)):
                parse_independent_response(case)


if __name__ == "__main__":
    unittest.main()
