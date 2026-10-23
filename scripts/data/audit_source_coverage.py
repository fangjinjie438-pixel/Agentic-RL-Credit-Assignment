"""Measure strict S2 office-device coverage in the already verified raw rows.

Input is the pinned 1,000-row metadata artifact, its source manifest and the
current conservative official exclusion index. CPU-only helpers inspect actual
price/Brand/Item Weight/Color fields, select attributed unreviewed candidates,
and run the existing family/title quarantine logic for diagnostic counts. New
JSON/RunRecord artifacts are written; fixtures, tasks and datasets are unchanged.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from typing import Any

from procure_rl.data.sources import normalize_records, normalize_value
from procure_rl.data.split import split_products
from procure_rl.runtime import RunRecord, sha256_file


SOURCE_REVISION = "2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e"
ROWS_SHA256 = "622128c4abc7252484911050111ddb0e6ac4530a5841c84807bfee752e97e6ac"
MASS_PATTERN = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z]+)\s*$")
MASS_UNITS = {"g", "kg", "lb", "lbs", "pounds", "ounces", "oz", "ounce", "gram", "grams", "kilograms"}
OFFICE_DEVICE_LEAVES = {
    "Traditional Laptops", "2 in 1 Laptops", "Towers", "Mini Computers", "All-in-Ones",
    "Tablets", "Monitors", "Keyboards", "Mice", "Keyboard & Mouse Combos", "Docking Stations",
    "Webcams", "Computer Headsets", "Computer Microphones", "Computer Speakers",
    "Routers", "Modem Router Combos", "Wireless Access Points", "Network Adapters",
    "Laser Printers", "Inkjet Printers", "Scanners", "Document Scanners",
    "External Hard Drives", "External Solid State Drives", "USB Flash Drives",
}
COLOR_NAMES = {
    "black", "white", "silver", "gray", "grey", "blue", "red", "green", "pink", "purple",
    "gold", "rose gold", "space gray", "space grey", "dark gray", "dark grey", "light gray",
    "light grey", "sky blue", "navy blue", "yellow", "orange", "brown", "beige", "ivory",
    "bronze", "clear", "transparent", "multicolor", "multi-color", "violet", "matte black",
    "baby pink", "piano black", "jet black", "deep black",
}
ACCESSORY_TITLE = re.compile(r"\b(replacement|stickers?|decals?|enclosure|barebone|barebones)\b", re.I)


def raw_digest(raw: dict) -> str:
    """Use the source normalizer's UTF-8 JSON hash, distinct from task digests."""
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def recognized_color(value: object) -> bool:
    """Accept only known color names or explicit combinations of those names."""
    if not isinstance(value, str):
        return False
    normalized = " ".join(value.strip().casefold().split())
    parts = re.split(r"\s*(?:[/,&+]|\band\b)\s*", normalized)
    return bool(parts) and all(part in COLOR_NAMES for part in parts)


def details_for(raw: dict) -> dict:
    """Decode the original details value without modifying its source bytes."""
    details = raw.get("details", {})
    if isinstance(details, str):
        details = json.loads(details)
    if not isinstance(details, dict):
        raise ValueError("details_not_object")
    return details


def scope_status(raw: dict) -> str:
    """Select explicit office-device categories; titles only exclude clear parts."""
    categories = raw.get("categories")
    if not isinstance(categories, list) or not categories:
        return "missing_categories"
    leaf = categories[-1]
    if leaf not in OFFICE_DEVICE_LEAVES:
        return "outside_office_device_leaf_categories"
    title = raw.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return "missing_title"
    if ACCESSORY_TITLE.search(title):
        return "explicit_accessory_or_incomplete_device_title"
    if leaf == "Keyboards" and re.search(r"\bswitch(?:es)?\b", title, re.I) and not re.search(r"\bkeyboard\b", title, re.I):
        return "keyboard_switch_part_title"
    if leaf == "Monitors" and re.search(r"raspberry\s*pi", title, re.I):
        return "embedded_display_module_title"
    return "office_device_candidate_not_human_reviewed"


def extract_record(raw: dict, row_index: int) -> tuple[dict | None, dict]:
    """Validate actual structured values; return attributed facts or field reasons."""
    states = {field: "missing" for field in ("price", "brand", "weight", "color")}
    facts = []
    try:
        details = details_for(raw)
    except (ValueError, TypeError):
        return None, {**states, "details": "invalid_details_json_or_object"}
    price = raw.get("price")
    if price is not None and str(price).strip().lower() not in {"", "none", "nan", "n/a"}:
        try:
            numeric, unit = normalize_value(price, "USD")
            if numeric <= 0:
                raise ValueError("nonpositive_price")
            states["price"] = "valid"
            facts.append({"field": "price", "value": price, "unit": unit,
                          "source_field": ["price"], "quote": str(price)})
        except (ValueError, TypeError, ArithmeticError):
            states["price"] = "invalid_or_ambiguous"
    brand = details.get("Brand")
    if isinstance(brand, str) and brand.strip():
        states["brand"] = "invalid_placeholder" if brand.strip().lower() in {"unknown", "generic", "n/a", "none"} else "valid"
    weight = details.get("Item Weight")
    if weight is not None:
        match = MASS_PATTERN.fullmatch(weight) if isinstance(weight, str) else None
        if match and match.group(2).lower() in MASS_UNITS:
            try:
                numeric, _ = normalize_value(match.group(1), match.group(2))
                if numeric <= 0:
                    raise ValueError("nonpositive_weight")
                states["weight"] = "valid"
                facts.append({"field": "weight_g", "value": match.group(1), "unit": match.group(2),
                              "source_field": ["details", "Item Weight"], "quote": weight})
            except (ValueError, ArithmeticError):
                states["weight"] = "invalid_or_ambiguous"
        else:
            states["weight"] = "unsupported_unit_or_ambiguous"
    color = details.get("Color")
    if color is not None:
        if recognized_color(color):
            states["color"] = "valid"
            facts.append({"field": "color", "value": color, "unit": None,
                          "source_field": ["details", "Color"], "quote": color})
        else:
            states["color"] = "not_in_conservative_color_vocabulary"
    if any(value != "valid" for value in states.values()):
        return None, states
    identity = {"brand_source_field": ["details", "Brand"]}
    for model_key in ("Item model number", "Model Number"):
        if isinstance(details.get(model_key), str) and details[model_key].strip():
            identity["model_source_field"] = ["details", model_key]
            break
    return {"raw": copy.deepcopy(raw), "raw_sha256": raw_digest(raw), "source_row_index": row_index,
            "facts": facts, "identity": identity, "review_status": "not_human_reviewed",
            "selection_reason": "strict_office_leaf_and_attributed_price_weight_color_brand",
            "review_notes": ["Diagnostic candidate only; source facts, identity and scope still require human review."]}, states


def analyze_rows(rows: list[dict], source: dict, official: dict) -> dict[str, Any]:
    """Return strict field/scope coverage and conservative quarantine diagnostics."""
    row_audit, complete_office, all_scope_states, scope_counts = [], [], Counter(), Counter()
    office_field_states: dict[str, Counter] = {field: Counter() for field in ("price", "brand", "weight", "color")}
    for index, raw in enumerate(rows):
        scope = scope_status(raw)
        record, fields = extract_record(raw, index)
        scope_counts[scope] += 1
        is_office = scope == "office_device_candidate_not_human_reviewed"
        all_scope_states.update(["all_four_fields_valid" if record else "one_or_more_fields_missing_or_invalid"])
        if is_office:
            for field in office_field_states:
                office_field_states[field][fields[field]] += 1
            if record:
                complete_office.append(record)
        row_audit.append({"source_row_index": index, "product_id": raw.get("parent_asin"),
                          "leaf_category": (raw.get("categories") or [None])[-1],
                          "scope_status": scope, "field_status": fields})
    normalized = normalize_records(complete_office, source=source)
    split = split_products(normalized["products"], official, seed=0)
    retained_ids = {product["product_id"] for product in split["products"]}
    quarantine_ids = {product["product_id"] for product in split["quarantined"]}
    retained = [record for record in complete_office if record["raw"]["parent_asin"] in retained_ids]
    quarantined = [record for record in complete_office if record["raw"]["parent_asin"] in quarantine_ids]
    category_counts = Counter((record["raw"]["categories"][-1]) for record in retained)
    report = {"input_rows": len(rows), "scope_counts": dict(scope_counts),
              "all_rows_field_coverage": dict(all_scope_states),
              "office_field_status_counts": {field: dict(counts) for field, counts in office_field_states.items()},
              "complete_office_candidates_before_normalization": len(complete_office),
              "normalization_accepted": len(normalized["products"]), "normalization_rejected": len(normalized["rejected"]),
              "official_quarantined_candidates": len(quarantined), "remaining_candidates": len(retained),
              "remaining_candidate_leaf_counts": dict(category_counts),
              "remaining_brand_families": len({product["family"] for product in split["products"]}),
              "official_metadata_complete": official.get("metadata_complete"),
              "human_reviews": 0, "tasks_built": 0, "teacher_calls": 0, "formal_release": False,
              "limitations": ["The first 1,000 selected rows are not a representative or exhaustive source sample.",
                              "Conservative fixed color vocabulary rejects unknown descriptors rather than correcting them.",
                              "Category/title scope selection and source truth remain subject to real human review.",
                              "Official metadata coverage remains partial; quarantine absence is not full contamination clearance.",
                              "Only price, color and weight are extracted; this does not supply long-horizon interface/compatibility evidence."]}
    return {"report": report, "row_audit": row_audit, "retained_records": retained,
            "quarantined_records": quarantined, "normalization_rejected": normalized["rejected"],
            "quarantine_audit": split["audit"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, default=Path("logs/s2-source-parquet-v1/rows.json"))
    parser.add_argument("--source-manifest", type=Path, default=Path("fixtures/s2/amazon-electronics.json"))
    parser.add_argument("--official-exclusions", type=Path, default=Path("fixtures/s2/official-exclusions-candidate.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    run = RunRecord(args.output, root, [sys.executable, *sys.argv], args.source_manifest,
                    execution_kind="cpu_source_coverage_diagnostic", stage="S2")
    try:
        source = copy.deepcopy(json.loads(args.source_manifest.read_text())["source"])
        if source["revision"] != SOURCE_REVISION or source["sha256"] != ROWS_SHA256 or sha256_file(args.rows) != ROWS_SHA256:
            raise ValueError("Pinned source rows/manifest hash mismatch")
        rows = json.loads(args.rows.read_text())
        official = json.loads(args.official_exclusions.read_text())
        result = analyze_rows(rows, source, official)
        artifacts = {}
        for name, value in (("report.json", result["report"]), ("row-audit.json", result["row_audit"]),
                            ("quarantine-audit.json", result["quarantine_audit"]),
                            ("normalization-rejected.json", result["normalization_rejected"])):
            path = args.output / name
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            artifacts[name] = str(path)
        for key, name in (("retained_records", "candidate-records.json"), ("quarantined_records", "quarantined-records.json")):
            selected_source = copy.deepcopy(source)
            selected_source["selected_rows"] = [record["source_row_index"] for record in result[key]]
            payload = {"schema_version": 1, "source": selected_source,
                       "status": "diagnostic_only_unreviewed_not_formal_dataset", "records": result[key]}
            path = args.output / name
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            artifacts[name] = str(path)
        run.record.update(runner_sha256=sha256_file(Path(__file__)),
                          dependencies={dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()},
                          data_revision=SOURCE_REVISION, policy_version="strict-source-coverage-v1", seed=0,
                          input_rows_sha256=ROWS_SHA256, official_exclusions_sha256=sha256_file(args.official_exclusions),
                          artifact_sha256={name: sha256_file(Path(path)) for name, path in artifacts.items()})
        run.finish("succeeded", artifacts, "cpu_unreviewed_source_coverage_and_quarantine_diagnostic")
        print(json.dumps(result["report"], ensure_ascii=False))
        return 0
    except BaseException as exc:
        run.finish("failed", {}, "not_validated", type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
