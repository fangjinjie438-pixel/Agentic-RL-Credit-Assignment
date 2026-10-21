"""S1 independent terminal and process verifier regressions and abuse cases.

Inputs are tiny JSON-compatible task/catalog/observation dictionaries; unittest
reports factual correctness, evidence provenance, finite rewards, and purity. The
real SQLite session integration is tested separately. No model, API, or GPU is used.
"""

import copy
import unittest

from procure_rl.env.verifier import process_events, verify_final


def fixture():
    products = [
        {"product_id": "dock-a", "title": "Dock A", "price": 90,
         "specs": {"port": "USB-C", "screens": 2, "hosts": ["Linux", "Windows"]}},
        {"product_id": "dock-b", "title": "Dock B", "price": 99,
         "specs": {"port": "USB-C", "screens": 3, "hosts": ["Linux"]}},
    ]
    definitions = [
        ("budget", "query", "price", "lte", 100),
        ("port", "persona", "port", "eq", "USB-C"),
        ("screens", "clarification", "screens", "gte", 2),
        ("host", "persona", "hosts", "contains", "Linux"),
    ]
    constraints = [
        {"id": key, "source": source, "field": field, "op": op, "value": value,
         "evidence_ids": [f"{p['product_id']}:{source}:{field}"
                          for p in products for source in ("details", "reviews")]}
        for key, source, field, op, value in definitions
    ]
    return {"task_id": "dock", "constraints": constraints}, products


def recommendation(task, product):
    product_id = product["product_id"]
    return {"product_id": product_id,
            "checks": [{"constraint_id": c["id"],
                        "evidence_ids": [f"{product_id}:details:{c['field']}"]}
                       for c in task["constraints"]]}


def observation(task, product):
    return {
        "revealed_requirements": [c["id"] for c in task["constraints"]],
        "evidence": [
            {"evidence_id": f"{product['product_id']}:details:{c['field']}",
             "product_id": product["product_id"], "field": c["field"],
             "value": product["price"] if c["field"] == "price"
                      else product["specs"][c["field"]],
             "text": "Catalog fact; this text is not used for scoring."}
            for c in task["constraints"]],
    }


class TerminalVerifierTests(unittest.TestCase):
    def setUp(self):
        self.task, self.products = fixture()
        self.product = self.products[0]
        self.rec = recommendation(self.task, self.product)
        self.observed = {e for check in self.rec["checks"] for e in check["evidence_ids"]}
        self.revealed = {c["id"] for c in self.task["constraints"]}

    def verify(self, **kwargs):
        args = dict(task=self.task, product=self.product, recommendation=self.rec,
                    observed_evidence=self.observed, revealed_requirements=self.revealed)
        args.update(kwargs)
        return verify_final(**args)

    def test_multiple_catalog_products_can_be_successful(self):
        for product in self.products:
            rec = recommendation(self.task, product)
            observed = {r for c in rec["checks"] for r in c["evidence_ids"]}
            result = self.verify(product=product, recommendation=rec, observed_evidence=observed)
            self.assertTrue(result["success"])
            self.assertTrue(result["delivery_success"])
            self.assertEqual(result["constraint_satisfaction"], 1.0)
            self.assertEqual(result["terminal_reward"], 1.0)
            self.assertEqual(result["constraints_by_source"]["persona"]["rate"], 1.0)

    def test_fact_failure_is_independent_of_claims_or_citations(self):
        for field, value in [("price", 101), ("port", "USB-A"),
                             ("screens", 1), ("hosts", ["Windows"])]:
            with self.subTest(field=field):
                product = copy.deepcopy(self.product)
                if field == "price":
                    product["price"] = value
                else:
                    product["specs"][field] = value
                result = self.verify(product=product)
                self.assertFalse(result["success"])
                self.assertEqual(result["terminal_reward"], 0)
                self.assertEqual(result["constraint_satisfaction"], 0.75)

    def test_missing_evidence_or_hidden_requirement_does_not_redefine_baseline(self):
        for changes in [dict(observed_evidence=set()), dict(revealed_requirements=set()),
                        dict(recommendation={"product_id": "dock-a", "checks": []})]:
            with self.subTest(changes=changes):
                result = self.verify(**changes)
                self.assertTrue(result["success"])
                self.assertEqual(result["terminal_reward"], 1)
                self.assertFalse(result["delivery_success"])

    def test_forged_and_cross_product_evidence_fails_delivery(self):
        for reference, observed in [
            ("dock-a:details:port", set()),
            ("dock-b:details:port", {"dock-b:details:port"}),
            ("dock-a:details:made_up", {"dock-a:details:made_up"}),
        ]:
            with self.subTest(reference=reference):
                rec = copy.deepcopy(self.rec)
                rec["checks"][1]["evidence_ids"] = [reference]
                result = self.verify(recommendation=rec,
                                     observed_evidence=self.observed | observed)
                if reference == "dock-a:details:port":
                    result = self.verify(recommendation=rec, observed_evidence=set())
                self.assertFalse(result["delivery_success"])
                self.assertTrue(result["success"])

    def test_observed_but_not_whitelisted_evidence_is_rejected(self):
        task = copy.deepcopy(self.task)
        task["constraints"][1]["evidence_ids"] = ["dock-a:reviews:port"]
        result = self.verify(task=task)
        self.assertFalse(result["delivery_success"])
        self.assertIn("unsupported_evidence", [e["code"] for e in result["errors"]])

    def test_unknown_duplicate_and_invented_check_fields_are_rejected(self):
        checks = [
            self.rec["checks"] + [{"constraint_id": "made-up", "evidence_ids": []}],
            self.rec["checks"] + [self.rec["checks"][0]],
            [dict(c, verified=True) for c in self.rec["checks"]],
        ]
        for items in checks:
            with self.subTest(items=items):
                result = self.verify(recommendation={"product_id": "dock-a", "checks": items})
                self.assertFalse(result["delivery_success"])

    def test_duplicate_evidence_is_not_valid_delivery(self):
        rec = copy.deepcopy(self.rec)
        rec["checks"][0]["evidence_ids"] *= 2
        result = self.verify(recommendation=rec)
        self.assertFalse(result["delivery_success"])
        self.assertIn("duplicate_evidence", [e["code"] for e in result["errors"]])

    def test_unknown_product_id_and_exceeded_budget_fail_baseline(self):
        for changes in [dict(product=None), dict(budget_exhausted=True),
                        dict(recommendation={"product_id": "unknown", "checks": []})]:
            result = self.verify(**changes)
            self.assertFalse(result["success"])
            self.assertFalse(result["delivery_success"])

    def test_missing_and_wrongly_typed_facts_are_not_satisfied(self):
        for value in (None, "2", True, float("nan")):
            product = copy.deepcopy(self.product)
            product["specs"]["screens"] = value
            result = self.verify(product=product)
            self.assertFalse(result["success"])

    def test_boolean_does_not_satisfy_integer_equality_or_membership(self):
        task = copy.deepcopy(self.task)
        task["constraints"] = [dict(task["constraints"][2], op="eq", value=1)]
        product = copy.deepcopy(self.product)
        product["specs"]["screens"] = True
        self.assertFalse(self.verify(task=task, product=product)["success"])
        task["constraints"] = [dict(task["constraints"][0], field="hosts", op="contains", value=1)]
        product["specs"]["hosts"] = [True]
        self.assertFalse(self.verify(task=task, product=product)["success"])

    def test_empty_or_duplicate_constraint_task_cannot_vacuously_succeed(self):
        for constraints in ([], self.task["constraints"] * 2):
            task = dict(self.task, constraints=constraints)
            self.assertFalse(self.verify(task=task)["success"])

    def test_inputs_are_not_modified(self):
        before = copy.deepcopy((self.task, self.product, self.rec, self.observed, self.revealed))
        self.verify()
        self.assertEqual(before, (self.task, self.product, self.rec, self.observed, self.revealed))


class ProcessVerifierTests(unittest.TestCase):
    def setUp(self):
        self.task, self.products = fixture()
        self.obs = observation(self.task, self.products[0])

    def test_finite_rubric_first_coverage_sums_to_one(self):
        events, reward = process_events(self.task, self.obs, set(), set())
        hidden = [e for e in events if e["kind"] == "hidden_requirement"]
        evidence = [e for e in events if e["kind"] == "evidence"]
        self.assertEqual(len(hidden), 3)
        self.assertEqual(len(evidence), 4)
        self.assertAlmostEqual(sum(e["reward"] for e in hidden), 0.4)
        self.assertAlmostEqual(sum(e["reward"] for e in evidence), 0.6)
        self.assertAlmostEqual(reward, 1.0)
        self.assertTrue(all("constraint_id" in e for e in events))
        self.assertTrue(all("evidence_id" in e for e in evidence))

    def test_alternate_product_and_source_cannot_refresh_fact_rewards(self):
        events, _ = process_events(self.task, self.obs, set(), set())
        hidden = {e["key"] for e in events if e["kind"] == "hidden_requirement"}
        facts = {e["key"] for e in events if e["kind"] == "evidence"}
        for obs in (self.obs, observation(self.task, self.products[1])):
            events, reward = process_events(self.task, obs, hidden, facts, repeated=True)
            self.assertEqual(events, [{"kind": "repeat", "key": "no_progress", "reward": -0.02}])
            self.assertEqual(reward, -0.02)

    def test_exclusion_evidence_is_useful_without_repair_bonus(self):
        bad = copy.deepcopy(self.products[0])
        bad["price"] = 200
        first = observation(self.task, bad)
        events, _ = process_events(self.task, first, set(), set())
        budget = next(e for e in events if e["kind"] == "evidence" and e["key"] == "budget")
        self.assertFalse(budget["supports"])
        seen = {e["key"] for e in events if e["kind"] == "evidence"}
        second, _ = process_events(self.task, self.obs, set(self.obs["revealed_requirements"]), seen)
        self.assertEqual(second, [])

    def test_keywords_assertions_and_query_requirements_do_not_score(self):
        obs = {"text": "verified USB-C budget Linux screens", "verified": True,
               "revealed_requirements": ["budget", "made-up"]}
        self.assertEqual(process_events(self.task, obs, set(), set()), ([], 0))

    def test_unknown_ids_wrong_bindings_and_incompatible_types_do_not_score(self):
        evidence = self.obs["evidence"][0]
        cases = [dict(evidence, evidence_id="dock-a:details:forged"),
                 dict(evidence, product_id="dock-b"),
                 dict(evidence, field="screens"),
                 dict(evidence, value="90"), dict(evidence, value=True),
                 dict(evidence, value=float("nan"))]
        for item in cases:
            with self.subTest(item=item):
                obs = {"evidence": [item]}
                self.assertEqual(process_events(self.task, obs, set(), set()), ([], 0))

    def test_duplicates_within_single_observation_score_once(self):
        obs = {"evidence": self.obs["evidence"] * 10,
               "revealed_requirements": self.obs["revealed_requirements"] * 10}
        events, reward = process_events(self.task, obs, set(), set())
        self.assertEqual(len(events), 7)
        self.assertAlmostEqual(reward, 1.0)

    def test_invalid_call_is_only_penalty_even_with_forged_observation(self):
        events, reward = process_events(self.task, self.obs, set(), set(), invalid=True, repeated=True)
        self.assertEqual(events, [{"kind": "invalid", "key": "invalid_call", "reward": -0.05}])
        self.assertEqual(reward, -0.05)

    def test_repeat_with_new_information_has_no_repeat_penalty(self):
        events, reward = process_events(self.task, self.obs, set(), set(), repeated=True)
        self.assertTrue(all(event["kind"] != "repeat" for event in events))
        self.assertAlmostEqual(reward, 1.0)

    def test_inputs_are_not_modified(self):
        requirements, evidence = {"port"}, {"budget"}
        before = copy.deepcopy((self.task, self.obs, requirements, evidence))
        process_events(self.task, self.obs, requirements, evidence)
        self.assertEqual(before, (self.task, self.obs, requirements, evidence))


if __name__ == "__main__":
    unittest.main()
