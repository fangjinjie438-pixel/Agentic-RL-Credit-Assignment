"""Verify strict CPU source-coverage diagnostics with synthetic metadata.

Tests cover actual source fields/units, no title-derived facts, conservative
scope exclusions, provenance retention and family quarantine. They exercise
the standalone audit helper without network, teacher, real tasks or GPUs.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from procure_rl.env.catalog import digest
from procure_rl.data.sources import normalize_records


SPEC = importlib.util.spec_from_file_location("source_coverage", Path(__file__).resolve().parents[1] / "scripts/data/audit_source_coverage.py")
assert SPEC and SPEC.loader
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)


class SourceCoverageTests(unittest.TestCase):
    def raw(self, product_id="a", brand="Example"):
        return {"parent_asin": product_id, "title": "Example White Office Keyboard", "price": "12.99",
                "store": "Example", "categories": ["Electronics", "Keyboards"],
                "details": json.dumps({"Brand": brand, "Color": "White", "Item Weight": "2 pounds"})}

    def source(self):
        return {"id": "synthetic", "url": "https://example.invalid", "revision": "synthetic",
                "sha256": "a" * 64, "retrieved_at": "2026-10-22T00:00:00+00:00",
                "license": "synthetic", "currency": "USD"}

    def test_record_retains_raw_hash_original_quotes_and_row_index(self):
        raw = self.raw()
        original = copy.deepcopy(raw)
        record, fields = COVERAGE.extract_record(raw, 19)
        self.assertEqual(set(fields.values()), {"valid"})
        self.assertEqual(raw, original)
        self.assertEqual(record["raw"], raw)
        self.assertEqual(record["raw_sha256"], digest(raw))
        self.assertEqual(record["source_row_index"], 19)
        weight = next(fact for fact in record["facts"] if fact["field"] == "weight_g")
        self.assertEqual(weight["source_field"], ["details", "Item Weight"])
        self.assertEqual(weight["quote"], "2 pounds")
        self.assertEqual(record["review_status"], "not_human_reviewed")

    def test_unicode_raw_hash_matches_source_normalizer_and_not_task_hash(self):
        raw = self.raw()
        raw["title"] = "Example 15.6” Keyboard"
        record, _ = COVERAGE.extract_record(raw, 0)
        self.assertNotEqual(record["raw_sha256"], digest(raw))
        normalized = normalize_records([record], source=self.source())
        self.assertEqual(len(normalized["products"]), 1)
        self.assertEqual(normalized["rejected"], [])

    def test_title_color_and_store_brand_are_never_substituted_for_missing_fields(self):
        raw = self.raw()
        raw["details"] = json.dumps({"Item Weight": "2 pounds"})
        record, fields = COVERAGE.extract_record(raw, 0)
        self.assertIsNone(record)
        self.assertEqual(fields["color"], "missing")
        self.assertEqual(fields["brand"], "missing")

    def test_ambiguous_color_and_mass_units_are_rejected(self):
        for color in ("128MB", "Non-Touchsceen", "CPU-i9 | GPU-4090", "Sliver"):
            raw = self.raw()
            raw["details"] = json.dumps({"Brand": "Example", "Color": color, "Item Weight": "2 pounds"})
            record, fields = COVERAGE.extract_record(raw, 0)
            self.assertIsNone(record)
            self.assertEqual(fields["color"], "not_in_conservative_color_vocabulary")
        raw["details"] = json.dumps({"Brand": "Example", "Color": "White", "Item Weight": "2"})
        self.assertEqual(COVERAGE.extract_record(raw, 0)[1]["weight"], "unsupported_unit_or_ambiguous")

    def test_explicit_color_names_and_combinations_preserve_complete_value(self):
        for color in ("Baby Pink", "Black/Grey+Light Grey/White", "Blue and White"):
            self.assertTrue(COVERAGE.recognized_color(color))
        for color in ("Black with Red Case", "Red-wired", "Black 128MB", "Kailh BOX Brown"):
            self.assertFalse(COVERAGE.recognized_color(color))

    def test_price_precision_zero_weight_and_placeholder_brand_rejected(self):
        raw = self.raw()
        raw["price"] = "12.999"
        raw["details"] = json.dumps({"Brand": "Generic", "Color": "White", "Item Weight": "0 pounds"})
        record, fields = COVERAGE.extract_record(raw, 0)
        self.assertIsNone(record)
        self.assertEqual(fields["price"], "invalid_or_ambiguous")
        self.assertEqual(fields["brand"], "invalid_placeholder")
        self.assertEqual(fields["weight"], "invalid_or_ambiguous")

    def test_misclassified_parts_are_not_office_device_candidates(self):
        raw = self.raw()
        for title in ("Keyboard Stickers for Home", "Replacement Office Keyboard", "Cherry MX Switch 10PCS"):
            raw["title"] = title
            self.assertNotEqual(COVERAGE.scope_status(raw), "office_device_candidate_not_human_reviewed")
        raw["title"] = "Example Keyboard"
        raw["categories"] = ["Electronics", "Cases"]
        self.assertEqual(COVERAGE.scope_status(raw), "outside_office_device_leaf_categories")

    def test_diagnostics_separate_complete_scope_from_quarantine_and_formal_release(self):
        retained, quarantined = self.raw("a"), self.raw("b", "Official")
        quarantined["title"] = "Official Ergonomic Keyboard"
        outside = self.raw("c")
        outside["categories"] = ["Electronics", "Cases"]
        official = {"families": ["brand:official"], "metadata_complete": False}
        result = COVERAGE.analyze_rows([retained, quarantined, outside], self.source(), official)
        report = result["report"]
        self.assertEqual(report["input_rows"], 3)
        self.assertEqual(report["complete_office_candidates_before_normalization"], 2)
        self.assertEqual(report["remaining_candidates"], 1)
        self.assertEqual(report["official_quarantined_candidates"], 1)
        self.assertEqual(result["retained_records"][0]["raw"], retained)
        self.assertEqual(result["quarantined_records"][0]["raw"], quarantined)
        self.assertFalse(report["formal_release"])
        self.assertEqual(report["human_reviews"], 0)
        self.assertEqual(report["tasks_built"], 0)


if __name__ == "__main__":
    unittest.main()
