"""S2 CPU checks for product clustering, official isolation and sibling audits.

Inputs are independent tiny product/task dicts. unittest checks public split
outputs and data boundaries without model downloads, network or GPU execution.
Persistent command/results are recorded by the S2 acceptance runner.
"""

from copy import deepcopy
import math
import unittest

from procure_rl.data.split import (audit_task_splits, minhash_similarity,
                                   normalized_text, semantic_candidates, split_products)


def product(pid, family=None, title=None, **extra):
    return {"product_id": pid, "family": family or f"family {pid}",
            "title": title or f"distinct {pid}", "price": 100,
            "specs": {}, "evidence": [], **extra}


def exclusions(**extra):
    return {"product_ids": [], "families": [], "brand_models": [],
            "titles": [], "source_revision": "test-exclusions-v1", **extra}


class ProductSplitTests(unittest.TestCase):
    def test_family_brand_model_and_explicit_edges_are_transitive(self):
        records = [product("a", "family x"),
                   product("b", "family x", brand="Acme", model="Dock 9"),
                   product("c", brand="ACME", model="dock-9", near_duplicate_group="set 8"),
                   product("d", near_duplicate_group="set 8")]
        result = split_products(records, exclusions(), seed=7)
        self.assertEqual(len({item["cluster_id"] for item in result["assignments"].values()}), 1)
        self.assertEqual(len({item["split"] for item in result["assignments"].values()}), 1)

    def test_input_order_and_preexisting_split_do_not_control_assignment(self):
        records = [product(str(index), split="official_test") for index in range(25)]
        first = split_products(records, exclusions(), seed=2)
        second = split_products(list(reversed(records)), exclusions(), seed=2)
        self.assertEqual(first, second)
        changed = deepcopy(records)
        for item in changed:
            item["split"] = "dev"
        self.assertEqual(first["assignments"], split_products(changed, exclusions(), seed=2)["assignments"])
        self.assertTrue(all(item["split"] != "official_test" for item in first["products"]))

    def test_official_overlap_quarantines_whole_transitive_cluster(self):
        records = [product("official", "shared"),
                   product("bridge", "shared", near_duplicate_group="linked"),
                   product("cousin", near_duplicate_group="linked"), product("safe")]
        result = split_products(records, exclusions(product_ids=["official"]))
        self.assertEqual({item["product_id"] for item in result["quarantined"]},
                         {"official", "bridge", "cousin"})
        self.assertEqual([item["product_id"] for item in result["products"]], ["safe"])
        self.assertIn("official_overlap_cluster_quarantine", result["assignments"]["cousin"]["reasons"])

    def test_official_title_near_duplicate_is_isolated(self):
        title = "Acme Orbit dock nine thunderbolt portable office dual display power"
        records = [product("p", title=title + " black"), product("other", title="Owl paper scanner")]
        result = split_products(records, exclusions(titles=[title]))
        self.assertEqual(result["assignments"]["p"]["split"], "quarantine")
        self.assertIn("official_title_near_duplicate", result["assignments"]["p"]["reasons"])

    def test_normalized_hash_and_jaccard_confirm_near_duplicates(self):
        records = [product("a", title="ＡＣＭＥ—Dock 9: Thunderbolt Office Dual Display Power"),
                   product("b", title="acme dock 9 thunderbolt office dual display power"),
                   product("c", title="acme dock 9 thunderbolt office dual display power black")]
        result = split_products(records, exclusions())
        self.assertEqual(result["audit"]["cluster_count"], 1)
        self.assertGreater(result["audit"]["title_deduplication"]["confirmed_pairs"], 0)
        self.assertTrue(any(link["method"] == "normalized_title_hash"
                            for link in result["audit"]["link_edges"]))

    def test_brand_model_and_family_official_metadata_are_normalized(self):
        records = [product("a", brand="Acme", model="X-100"),
                   product("b", family="Official Family"), product("safe")]
        result = split_products(records, exclusions(
            brand_models=[{"brand": "ACME", "model": "x 100"}], families=["official-family"]))
        self.assertEqual(result["audit"]["quarantined_products"], 2)
        self.assertEqual(result["audit"]["official_exclusion_coverage"], "provided_metadata_only")

    def test_exact_title_jaccard_threshold_is_inclusive(self):
        words = [f"token{index}" for index in range(20)]
        baseline = product("a", title=" ".join(words))
        at_boundary = product("b", title=" ".join(words[:17]))
        below_boundary = product("c", title=" ".join(words[:16]))
        self.assertEqual(split_products([baseline, at_boundary], exclusions())[
            "audit"]["cluster_count"], 1)
        self.assertEqual(split_products([baseline, below_boundary], exclusions())[
            "audit"]["cluster_count"], 2)

    def test_empty_titles_and_missing_linkage_do_not_merge_products(self):
        records = [product("a", family="", title=""), product("b", family="", title="")]
        for record in records:
            record["title"] = record["family"] = ""
        result = split_products(records, exclusions())
        self.assertEqual(result["audit"]["cluster_count"], 2)
        self.assertEqual(split_products([], exclusions())["products"], [])

    def test_outputs_do_not_mutate_or_alias_inputs(self):
        records = [product("a"), product("b")]
        before = deepcopy(records)
        result = split_products(records, exclusions(product_ids=["b"]))
        result["products"][0]["specs"]["new"] = 1
        result["quarantined"][0]["specs"]["new"] = 2
        self.assertEqual(records, before)

    def test_invalid_ids_ratios_and_exclusions_fail_closed(self):
        for kwargs in ({"ratios": {"train": 0}}, {"ratios": {"train": math.nan}},
                       {"ratios": {"train": -1}}, {"ratios": {"train": True}},
                       {"ratios": {"official_test": 1}}, {"seed": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                split_products([product("a")], exclusions(), **kwargs)
        with self.assertRaises(ValueError):
            split_products([product("a"), product("a")], exclusions())
        with self.assertRaises(ValueError):
            split_products([product("a")], exclusions(brand_models=[{"brand": "Acme"}]))
        result = split_products([product("a")], exclusions(), ratios={"dev": 1})
        self.assertEqual(result["products"][0]["split"], "dev")

    def test_minhash_stable_symmetric_and_normalized(self):
        self.assertEqual(normalized_text("ＡＣＭＥ—Dock_9!"), "acme dock 9")
        a, b = "portable acme office dock dual display", "acme office dock dual display black"
        self.assertEqual(minhash_similarity(a, b), minhash_similarity(b, a))
        self.assertEqual(minhash_similarity(a, a.upper()), 1.0)
        self.assertEqual(minhash_similarity(a, b), minhash_similarity(a, b))
        self.assertEqual(minhash_similarity("", a), 0)

    def test_sibling_and_counterfactual_cross_split_are_detected(self):
        tasks = [{"task_id": "base", "split": "train", "root_task_id": "root", "pair_id": "pair"},
                 {"task_id": "cf", "split": "dev", "parent_task_id": "base", "pair_id": "pair"},
                 {"task_id": "rewrite", "split": "sealed_test", "root_task_id": "root"}]
        audit = audit_task_splits(tasks, {})
        self.assertFalse(audit["passed"])
        violation = next(item for item in audit["violations"] if item["kind"] == "siblings_cross_split")
        self.assertEqual(violation["task_ids"], ["base", "cf", "rewrite"])

    def test_legal_solution_and_evidence_references_must_match_split(self):
        tasks = [{"task_id": "t", "split": "train", "feasible_product_ids": ["dev-p"],
                  "constraints": [{"evidence_ids": ["train-p:details:price", "unknown:details:price"]}]}]
        audit = audit_task_splits(tasks, {"train-p": {"split": "train"}, "dev-p": {"split": "dev"}})
        self.assertEqual({item["kind"] for item in audit["violations"]},
                         {"product_cross_split", "unknown_evidence_product"})
        tasks[0]["feasible_product_ids"] = ["train-p"]
        tasks[0]["constraints"][0]["evidence_ids"].pop()
        self.assertTrue(audit_task_splits(tasks, {"train-p": {"split": "train"}})["passed"])

    def test_semantic_candidates_are_explicit_pending_lexical_approximation(self):
        records = [{"task_id": "a", "query": "Need a lightweight notebook dock", "split": "train"},
                   {"task_id": "b", "query": "Need a portable laptop hub", "split": "dev"},
                   {"task_id": "c", "query": "ink toner cartridge", "split": "dev"}]
        candidates = semantic_candidates(records)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertTrue(candidate["cross_split"])
        self.assertEqual(candidate["independent_model_review"], "not_run")
        self.assertEqual(candidate["review_status"], "pending_human_review")
        self.assertIn("not proof", candidate["limitation"])
        self.assertEqual(candidates, semantic_candidates(list(reversed(records))))


if __name__ == "__main__":
    unittest.main()
