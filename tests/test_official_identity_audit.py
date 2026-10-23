"""CPU regression checks for conservative official identity audit candidates.

Synthetic metadata checks alias corroboration, source-field projection and
retained human gates. No network, official requests, model or GPU is accessed.
The standalone S2 script is imported directly for its pure transformation API.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("official_identity_audit", Path(__file__).resolve().parents[1] / "scripts/data/audit_official_identities.py")
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class OfficialIdentityAuditTests(unittest.TestCase):
    def index(self):
        return {"families": ["brand:existing"], "unknown_family_product_ids": ["missing"],
                "source_revision": "fixed", "source_sha256": "source", "metadata_complete": False}

    def target(self, store="Example", manufacturer="Example", title="Example Headphones"):
        return {"product_id": "missing", "store": store, "title": title,
                "source_line_1based": 1, "details": {"Manufacturer": manufacturer}}

    def test_matching_manufacturer_store_adds_conservative_alias_and_preserves_gates(self):
        original = self.index()
        snapshot = copy.deepcopy(original)
        candidate, audit = AUDIT.build_candidate(original, [self.target()])
        self.assertEqual(original, snapshot)
        self.assertIn("brand:example", candidate["families"])
        self.assertEqual(candidate["unknown_family_product_ids"], ["missing"])
        self.assertFalse(candidate["metadata_complete"])
        self.assertEqual(audit["human_approval_count"], 0)
        self.assertIsNone(audit["records"][0]["observed_brand"])

    def test_title_corroboration_adds_manufacturer_alias_without_claiming_brand(self):
        candidate, audit = AUDIT.build_candidate(self.index(), [self.target(manufacturer="Example Digital")])
        self.assertIn("brand:example digital", candidate["families"])
        self.assertEqual(audit["records"][0]["corroboration"], ["title_starts_with_store"])
        self.assertEqual(audit["unresolved_candidate_product_ids"], [])

    def test_uncorroborated_seller_remains_unresolved(self):
        candidate, audit = AUDIT.build_candidate(self.index(), [self.target(title="Generic Headphones", manufacturer="Other")])
        self.assertEqual(candidate["families"], ["brand:existing"])
        self.assertEqual(audit["unresolved_candidate_product_ids"], ["missing"])

    def test_projection_drops_non_identity_target_fields(self):
        target = {"product_id": "missing", "title": "Example Headphones", "store": "Example",
                  "features": ["do not propagate"], "details": {"Manufacturer": "Example", "Color": "Red", "Item model number": "H1"}}
        selected = AUDIT.selected_target(target, 42)
        self.assertNotIn("features", selected)
        self.assertNotIn("Color", selected["details"])
        self.assertEqual(selected["details"]["Item model number"], "H1")
        self.assertEqual(selected["source_line_1based"], 42)

    def test_unlisted_and_duplicate_products_do_not_expand_candidates(self):
        target = self.target()
        other = self.target(store="Another", manufacturer="Another")
        other["product_id"] = "unlisted"
        _, audit = AUDIT.build_candidate(self.index(), [target, target, other])
        self.assertEqual(len(audit["records"]), 1)
        self.assertEqual(audit["new_families"], ["brand:example"])


if __name__ == "__main__":
    unittest.main()
