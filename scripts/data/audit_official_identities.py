"""Audit missing official identities using target-product metadata only.

The CPU entry point verifies the pinned benchmark/index hashes, selects only
product ID, title, store, Manufacturer and explicit model-number fields, and
writes additional conservative exclusion aliases plus their source evidence.
The candidate retains metadata_complete=False: store/manufacturer agreement is
useful for quarantine, but does not manufacture an observed Brand or human
identity approval. RunRecord saves command, interpreter and artifact hashes.
"""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import unicodedata
from typing import Any, Iterable

from procure_rl.runtime import RunRecord, sha256_file


REVISION = "97eff345811fdf652a2135d38d874f2932e11702"
SOURCE_SHA256 = "c6585d7adade0bf898dcc6b5377fb4534a699b874bd21ec796acfa96547c9b52"
DEFAULT_SOURCE = Path("third_party/ecomagentbench") / REVISION / "data/benchmark/benchmark.jsonl"
ACCESSED_FIELDS = ["target_product.product_id", "target_product.title", "target_product.store",
                   "target_product.details.Manufacturer", "target_product.details.Item model number",
                   "target_product.details.Model Number"]


def normalize(value: str) -> str:
    """Match the existing whole-brand exclusion normalization."""
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def selected_target(target: dict[str, Any], line_number: int) -> dict[str, Any]:
    """Project an official target onto the explicitly allowed identity fields."""
    details = target.get("details", {})
    if isinstance(details, str):
        details = json.loads(details)
    if not isinstance(details, dict):
        details = {}
    selected = {"source_line_1based": line_number, "product_id": target["product_id"],
                "title": target.get("title"), "store": target.get("store"), "details": {}}
    for key, value in details.items():
        if normalize(key) in {"manufacturer", "item model number", "model number"}:
            selected["details"][key] = value
    return selected


def build_candidate(index: dict[str, Any], targets: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Add corroborated store/manufacturer aliases without changing source facts."""
    candidate = copy.deepcopy(index)
    families = set(index["families"])
    evidence = []
    unresolved = set(index["unknown_family_product_ids"])
    seen = set()
    for target in targets:
        product_id = target["product_id"]
        if product_id not in unresolved or product_id in seen:
            continue
        seen.add(product_id)
        store = target.get("store")
        store = store.strip() if isinstance(store, str) else ""
        manufacturer = next((value.strip() for key, value in target["details"].items()
                             if normalize(key) == "manufacturer" and isinstance(value, str)), "")
        title = target.get("title")
        title = normalize(title) if isinstance(title, str) else ""
        store_key, manufacturer_key = normalize(store), normalize(manufacturer)
        reasons = []
        if store_key and manufacturer_key and store_key == manufacturer_key:
            reasons.append("store_equals_manufacturer")
        if store_key and title and (title == store_key or title.startswith(store_key + " ")):
            reasons.append("title_starts_with_store")
        # A title alone or an uncorroborated seller is insufficient identity evidence.
        aliases = sorted({"brand:" + key for key in (store_key, manufacturer_key) if key}) if reasons else []
        families.update(aliases)
        evidence.append({"product_id": product_id, "source_fields": copy.deepcopy(target),
                         "candidate_exclusion_aliases": aliases, "corroboration": reasons,
                         "status": "candidate_quarantine_only" if aliases else "unresolved",
                         "observed_brand": None, "human_review_status": "pending"})
    covered = {entry["product_id"] for entry in evidence if entry["candidate_exclusion_aliases"]}
    audit = {"source_revision": index["source_revision"], "source_sha256": index["source_sha256"],
             "accessed_fields": ACCESSED_FIELDS, "records": evidence,
             "covered_by_candidate_aliases": sorted(covered),
             "unresolved_candidate_product_ids": sorted(unresolved - covered),
             "new_families": sorted(families - set(index["families"])),
             "human_approval_count": 0, "metadata_complete": False,
             "limitation": "No observed Brand is inferred; family/semantic human review remains required."}
    candidate.update(families=sorted(families), metadata_complete=False,
                     family_exclusion_status="available_brand_metadata_plus_unapproved_conservative_identity_aliases",
                     candidate_identity_alias_audit=audit,
                     purpose="quarantine_only_never_task_or_reward_generation")
    candidate["candidate_exclusion_counts"] = {
        "original_observed_brand_families": len(index["families"]),
        "additional_identity_alias_families": len(audit["new_families"]),
        "total_exclusion_families": len(families),
    }
    return candidate, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--index", type=Path, default=Path("fixtures/s2/official-exclusions.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    run = RunRecord(args.output, root, [sys.executable, *sys.argv], args.index,
                    execution_kind="cpu_official_identity_metadata_audit", stage="S2")
    try:
        index = json.loads(args.index.read_text())
        source_hash = sha256_file(args.source)
        if index["source_revision"] != REVISION or index["source_sha256"] != SOURCE_SHA256 or source_hash != SOURCE_SHA256:
            raise ValueError("Pinned benchmark/index identity mismatch")
        wanted = set(index["unknown_family_product_ids"])
        targets = []
        # Only the target_product key is accessed. No task request/persona/rubric is used.
        for line_number, line in enumerate(args.source.open(), 1):
            target = json.loads(line)["target_product"]
            if target["product_id"] in wanted:
                targets.append(selected_target(target, line_number))
        candidate, audit = build_candidate(index, targets)
        paths = {}
        for name, data in (("official-exclusions-candidate.json", candidate), ("identity-audit.json", audit)):
            path = args.output / name
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            paths[name] = str(path)
        run.record.update(runner_sha256=sha256_file(Path(__file__)),
                          dependencies={d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
                          data_revision=REVISION, input_source={"path": str(args.source), "sha256": source_hash},
                          model_revision=None, policy_version="official-identity-quarantine-audit-v1", seed=None,
                          artifact_sha256={name: sha256_file(Path(path)) for name, path in paths.items()})
        run.finish("succeeded", paths, "cpu_metadata_candidate_audit_only_no_human_approval")
        print(json.dumps({"candidate_alias_covered": len(audit["covered_by_candidate_aliases"]),
                          "new_families": audit["new_families"], "metadata_complete": False}))
        return 0
    except BaseException as exc:
        run.finish("failed", {}, "not_validated", type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
