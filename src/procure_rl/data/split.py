"""S2 deterministic product clusters, split assignment and leakage audits.

Inputs are structured product records, official exclusion metadata and private
task records. Outputs are deep-copied split products and explicit audit dicts.
The data builder calls these CPU-only helpers before task expression generation;
no model, official rubric, network client or environment tool is imported here.
Lexical semantic candidates require human/independent-model review and cannot
establish absence of semantic duplication.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import itertools
import json
import math
import re
import unicodedata
from typing import Any


SPLITS = ("train", "dev", "sealed_test")
TITLE_JACCARD_THRESHOLD = 0.85
MINHASH_PERMUTATIONS = 128
MINHASH_BANDS = 16
MINHASH_VERSION = "sha256-token-minhash-128-v1"
SEMANTIC_CANDIDATE_THRESHOLD = 0.55
SEMANTIC_SYNONYMS = {
    "notebook": "laptop", "notebooks": "laptop", "laptops": "laptop",
    "display": "monitor", "displays": "monitor", "monitors": "monitor",
    "docking": "dock", "docks": "dock", "hub": "dock", "hubs": "dock",
    "lightweight": "portable", "headphones": "headset",
}


def normalized_text(text: str) -> str:
    """Normalize Unicode, case, punctuation and whitespace without a model."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _tokens(text: str) -> frozenset[str]:
    return frozenset(normalized_text(text).split())


def _minhash(tokens: frozenset[str]) -> tuple[int, ...]:
    if not tokens:
        return ()
    return tuple(min(int.from_bytes(hashlib.sha256(
        f"{index}\0{token}".encode()).digest()[:8], "big") for token in tokens)
        for index in range(MINHASH_PERMUTATIONS))


def minhash_similarity(a: str, b: str) -> float:
    """Return a reproducible MinHash estimate of title-token Jaccard.

    Empty strings match each other at 1 and nonempty strings at 0. Clustering
    never joins absent/empty titles. This estimate alone never confirms a pair.
    """
    left, right = _minhash(_tokens(a)), _minhash(_tokens(b))
    if not left or not right:
        return float(left == right)
    return sum(x == y for x, y in zip(left, right)) / MINHASH_PERMUTATIONS


class _UnionFind:
    def __init__(self, keys: list[str]):
        self.parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a: str, b: str) -> None:
        left, right = self.find(a), self.find(b)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def _near_duplicate_pairs(titles: dict[str, str]) -> tuple[list[dict], dict]:
    """Use MinHash LSH candidates, then exact token Jaccard confirmation.

    A shared-token overlap guard also retrieves every pair that can meet the
    exact threshold, including LSH misses. This is intentionally conservative:
    MinHash candidate recall is probabilistic and is not a leakage guarantee.
    """
    token_sets = {key: _tokens(value) for key, value in titles.items()}
    signatures = {key: _minhash(tokens) for key, tokens in token_sets.items()}
    buckets: dict[tuple, list[str]] = defaultdict(list)
    rows = MINHASH_PERMUTATIONS // MINHASH_BANDS
    for key in sorted(titles):
        signature = signatures[key]
        if signature:
            for band in range(MINHASH_BANDS):
                buckets[(band, signature[band * rows:(band + 1) * rows])].append(key)
    lsh = {pair for keys in buckets.values()
           for pair in itertools.combinations(sorted(keys), 2)}
    postings: dict[str, list[str]] = defaultdict(list)
    for key, tokens in token_sets.items():
        for token in tokens:
            postings[token].append(key)
    overlaps: Counter[tuple[str, str]] = Counter()
    for keys in postings.values():
        overlaps.update(itertools.combinations(sorted(keys), 2))
    guard = {pair for pair, overlap in overlaps.items()
             if overlap / (len(token_sets[pair[0]]) + len(token_sets[pair[1]]) - overlap)
             >= TITLE_JACCARD_THRESHOLD}
    candidates = lsh | guard
    matches = []
    for left, right in sorted(candidates):
        a, b = token_sets[left], token_sets[right]
        score = len(a & b) / len(a | b) if a | b else 0.0
        if score >= TITLE_JACCARD_THRESHOLD:
            matches.append({"left_id": left, "right_id": right,
                            "jaccard": score,
                            "minhash_similarity": sum(x == y for x, y in zip(
                                signatures[left], signatures[right])) / MINHASH_PERMUTATIONS,
                            "candidate_sources": [name for name, pairs in (
                                ("minhash_lsh", lsh), ("exact_overlap_guard", guard))
                                if (left, right) in pairs]})
    return matches, {
        "method": MINHASH_VERSION, "permutations": MINHASH_PERMUTATIONS,
        "bands": MINHASH_BANDS, "jaccard_threshold": TITLE_JACCARD_THRESHOLD,
        "minhash_candidate_pairs": len(lsh), "overlap_guard_pairs": len(guard),
        "exact_comparisons": len(candidates), "confirmed_pairs": len(matches),
        "overlap_guard": "exact token overlap prevents probabilistic LSH false negatives",
    }


def _nonempty_normalized(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("family, title, brand, model and duplicate group must be strings")
    return normalized_text(value)


def _brand_model(record: dict) -> str:
    brand = _nonempty_normalized(record.get("brand"))
    model = _nonempty_normalized(record.get("model"))
    return f"{brand} {model}" if brand and model else ""


def _exclusion_brand_model(value: Any) -> str:
    if isinstance(value, dict):
        key = _brand_model(value)
        if not key:
            raise ValueError("official brand/model dict needs both brand and model")
        return key
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return _exclusion_brand_model({"brand": value[0], "model": value[1]})
    if isinstance(value, str) and normalized_text(value):
        return normalized_text(value)
    raise ValueError("official brand_models need strings, pairs or brand/model dicts")


def _validated_ratios(ratios: dict | None) -> dict[str, float]:
    supplied = {"train": 8, "dev": 1, "sealed_test": 2} if ratios is None else ratios
    if not isinstance(supplied, dict) or not supplied or set(supplied) - set(SPLITS):
        raise ValueError("ratios must map train/dev/sealed_test to nonnegative weights")
    weights = {}
    for split in SPLITS:
        value = supplied.get(split, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("split ratios must be finite numeric weights")
        if not math.isfinite(value) or value < 0:
            raise ValueError("split ratios must be finite nonnegative weights")
        weights[split] = float(value)
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("at least one split ratio must be positive")
    return {key: value / total for key, value in weights.items()}


def split_products(products: list[dict], official_exclusions: dict, *,
                   seed: int = 0, ratios: dict | None = None) -> dict:
    """Join related products before seeded cluster assignment; quarantine official overlaps.

    Incoming ``split`` is ignored. ``products`` contains only assigned research
    records; ``assignments`` covers every ID, including quarantine. Exclusion
    coverage is limited to the supplied metadata and never claims a full
    official-corpus contamination audit from an empty fixture exclusion list.
    """
    if not isinstance(products, list) or not isinstance(official_exclusions, dict):
        raise ValueError("products and official_exclusions must be list/dict")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    weights = _validated_ratios(ratios)
    records = {}
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("every product must be a dict")
        pid = product.get("product_id")
        if not isinstance(pid, str) or not pid.strip() or pid in records:
            raise ValueError("product_id must be a unique nonempty string")
        records[pid] = deepcopy(product)
        # Validate only linkage fields; fact/schema validation belongs to builder.
        for field in ("family", "title", "brand", "model", "near_duplicate_group"):
            _nonempty_normalized(product.get(field))
    for key in ("product_ids", "families", "brand_models", "titles"):
        if not isinstance(official_exclusions.get(key, []), list):
            raise ValueError(f"official_exclusions.{key} must be a list")
    revision = official_exclusions.get("source_revision")
    if revision is not None and not isinstance(revision, str):
        raise ValueError("official source_revision must be a string or null")
    official_id_values = official_exclusions.get("product_ids", [])
    if any(not isinstance(value, str) or not value for value in official_id_values):
        raise ValueError("official product_ids must be nonempty strings")
    official_ids = set(official_id_values)
    official_families = {_nonempty_normalized(value)
                         for value in official_exclusions.get("families", [])}
    official_models = {_exclusion_brand_model(value)
                       for value in official_exclusions.get("brand_models", [])}
    official_titles = official_exclusions.get("titles", [])
    for title in official_titles:
        if not isinstance(title, str) or not normalized_text(title):
            raise ValueError("official titles must be nonempty strings")
    union = _UnionFind(sorted(records))
    links = []
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for pid, record in sorted(records.items()):
        for method, value in (
                ("family", _nonempty_normalized(record.get("family"))),
                ("brand_model", _brand_model(record)),
                ("explicit_near_duplicate_group", _nonempty_normalized(
                    record.get("near_duplicate_group"))),
                ("normalized_title_hash", _nonempty_normalized(record.get("title")))):
            if value:
                grouped[(method, value)].append(pid)
    for (method, value), pids in sorted(grouped.items()):
        for pid in pids[1:]:
            union.union(pids[0], pid)
            links.append({"left_id": pids[0], "right_id": pid,
                          "method": method, "value_hash": _hash(value)})
    titles = {f"product:{pid}": record.get("title", "")
              for pid, record in records.items()}
    titles.update({f"official:{index}": title
                   for index, title in enumerate(sorted(official_titles))})
    near_pairs, minhash_audit = _near_duplicate_pairs(titles)
    direct_exclusions: dict[str, set[str]] = defaultdict(set)
    for pair in near_pairs:
        left, right = pair["left_id"], pair["right_id"]
        if left.startswith("product:") and right.startswith("product:"):
            a, b = left.removeprefix("product:"), right.removeprefix("product:")
            union.union(a, b)
            links.append({**pair, "left_id": a, "right_id": b,
                          "method": "title_exact_jaccard_after_minhash_candidates"})
        elif left.startswith("official:") != right.startswith("official:"):
            product_key = right if right.startswith("product:") else left
            direct_exclusions[product_key.removeprefix("product:")].add(
                "official_title_near_duplicate")
    for pid, record in records.items():
        if pid in official_ids:
            direct_exclusions[pid].add("official_product_id")
        family = _nonempty_normalized(record.get("family"))
        if family and family in official_families:
            direct_exclusions[pid].add("official_family")
        model = _brand_model(record)
        if model and model in official_models:
            direct_exclusions[pid].add("official_brand_model")
    clusters: dict[str, list[str]] = defaultdict(list)
    for pid in sorted(records):
        clusters[union.find(pid)].append(pid)
    assignments, accepted, quarantined, cluster_audit = {}, [], [], []
    for member_ids in sorted(clusters.values()):
        cluster_id = "cluster-" + _hash(member_ids)[:24]
        excluded_members = sorted(pid for pid in member_ids if direct_exclusions[pid])
        exclusion_reasons = sorted({reason for pid in excluded_members
                                    for reason in direct_exclusions[pid]})
        split = "quarantine"
        if not excluded_members:
            # Integer digest avoids random state and input-order dependence.
            draw = int(_hash({"cluster_id": cluster_id, "seed": seed}), 16) / (1 << 256)
            cumulative = 0.0
            split = next(key for key in reversed(SPLITS) if weights[key] > 0)
            for candidate in SPLITS:
                cumulative += weights[candidate]
                if weights[candidate] and draw < cumulative:
                    split = candidate
                    break
        for pid in member_ids:
            reasons = sorted({link["method"] for link in links
                              if pid in (link["left_id"], link["right_id"])})
            if excluded_members:
                reasons += exclusion_reasons + ["official_overlap_cluster_quarantine"]
            assignments[pid] = {"split": split, "cluster_id": cluster_id,
                                "reasons": sorted(set(reasons))}
            record = deepcopy(records[pid])
            record["split"] = split
            if split == "quarantine":
                record["quarantine_reasons"] = assignments[pid]["reasons"]
                quarantined.append(record)
            else:
                accepted.append(record)
        cluster_audit.append({"cluster_id": cluster_id, "product_ids": member_ids,
                              "split": split, "official_overlap_members": excluded_members,
                              "official_overlap_reasons": exclusion_reasons})
    audit = {
        "method": "connected-product-clusters-seeded-sha256-v1", "seed": seed,
        "ratios": weights, "input_products": len(records),
        "assigned_products": len(accepted), "quarantined_products": len(quarantined),
        "clusters": cluster_audit, "cluster_count": len(cluster_audit),
        "split_counts": {key: sum(item["split"] == key for item in assignments.values())
                         for key in (*SPLITS, "quarantine")},
        "ignored_input_split_count": sum("split" in record for record in records.values()),
        "input_sha256": _hash([records[pid] for pid in sorted(records)]),
        "assignments_sha256": _hash(assignments),
        "official_exclusions_sha256": _hash(official_exclusions),
        "official_exclusions_source_revision": revision,
        "official_exclusion_coverage": "provided_metadata_only",
        "normalization": "NFKC-casefold-unicode-word-tokens-v1",
        "link_edges": links, "title_deduplication": minhash_audit,
        "semantic_review": "not_run; lexical candidates cannot prove semantic disjointness",
    }
    return {"products": sorted(accepted, key=lambda record: record["product_id"]),
            "assignments": assignments,
            "quarantined": sorted(quarantined, key=lambda record: record["product_id"]),
            "audit": audit}


def _semantic_text(record: dict) -> str:
    parts = [record.get(field, "") for field in ("title", "description", "query", "persona")]
    for clarification in record.get("clarifications", []):
        if isinstance(clarification, dict):
            parts.extend(clarification.get(field, "") for field in ("question", "answer"))
    return " ".join(part for part in parts if isinstance(part, str))


def semantic_candidates(records: list[dict]) -> list[dict]:
    """Return controlled-synonym token-cosine pairs for manual review only.

    This offline lexical approximation is not an 8B semantic review. Missing or
    low-scoring pairs never establish that two records are semantically distinct.
    """
    vectors, splits = {}, {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("semantic records must be dicts")
        rid = record.get("task_id", record.get("product_id", record.get("id")))
        if not isinstance(rid, str) or not rid or rid in vectors:
            raise ValueError("semantic records need a unique task_id/product_id/id")
        vectors[rid] = Counter(SEMANTIC_SYNONYMS.get(token, token)
                               for token in normalized_text(_semantic_text(record)).split())
        splits[rid] = record.get("split")
    candidates = []
    for left, right in itertools.combinations(sorted(vectors), 2):
        a, b = vectors[left], vectors[right]
        denom = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
        score = sum(value * b[token] for token, value in a.items()) / denom if denom else 0.0
        if score >= SEMANTIC_CANDIDATE_THRESHOLD:
            candidates.append({
                "left_id": left, "right_id": right, "cosine_similarity": score,
                "cross_split": splits[left] != splits[right],
                "method": "controlled-synonym-token-cosine-v1",
                "threshold": SEMANTIC_CANDIDATE_THRESHOLD,
                "synonyms_sha256": _hash(SEMANTIC_SYNONYMS),
                "synonyms": dict(SEMANTIC_SYNONYMS),
                "review_status": "pending_human_review",
                "independent_model_review": "not_run",
                "limitation": "lexical approximation; low score is not proof of semantic disjointness",
            })
    return candidates


def audit_task_splits(tasks: list[dict], product_assignments: dict) -> dict:
    """Detect sibling leakage and task references to another split's products."""
    if not isinstance(tasks, list) or not isinstance(product_assignments, dict):
        raise ValueError("tasks and product_assignments must be list/dict")
    task_map, violations = {}, []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("tasks must be dicts")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in task_map:
            raise ValueError("tasks need unique nonempty task_id")
        task_map[task_id] = task
    relation_fields = ("parent_task_id", "original_task_id", "root_task_id", "rewrite_of",
                       "counterfactual_of", "pair_id")
    all_keys = set(task_map)
    for task in tasks:
        for field in relation_fields:
            value = task.get(field)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{field} must be a nonempty string when present")
            if value:
                all_keys.add(value)
    union = _UnionFind(sorted(all_keys))
    for task in tasks:
        for field in relation_fields:
            if task.get(field):
                union.union(task["task_id"], task[field])
    groups: dict[str, list[str]] = defaultdict(list)
    for task_id in task_map:
        groups[union.find(task_id)].append(task_id)
    for members in groups.values():
        splits = {task_map[task_id].get("split") for task_id in members}
        if len(splits) > 1:
            violations.append({"kind": "siblings_cross_split", "task_ids": sorted(members),
                               "splits": sorted(str(split) for split in splits)})
    product_ids = sorted(product_assignments, key=lambda value: (-len(value), value))
    for task_id, task in sorted(task_map.items()):
        split = task.get("split")
        if split not in SPLITS:
            violations.append({"kind": "invalid_task_split", "task_id": task_id,
                               "split": split})
        references = set()
        for field in ("product_ids", "candidate_product_ids", "eligible_product_ids",
                      "feasible_product_ids", "legal_product_ids"):
            values = task.get(field, [])
            if not isinstance(values, list) or any(not isinstance(pid, str) for pid in values):
                raise ValueError(f"{field} must be a list of strings")
            references.update(values)
        for field in ("target_product_id", "product_id", "construction_anchor", "anchor_product_id"):
            if task.get(field):
                if not isinstance(task[field], str):
                    raise ValueError(f"{field} must be a string")
                references.add(task[field])
        for constraint in task.get("constraints", []):
            for evidence_id in constraint.get("evidence_ids", []):
                if not isinstance(evidence_id, str):
                    raise ValueError("evidence_ids must contain strings")
                matched = next((pid for pid in product_ids
                                if evidence_id.startswith(pid + ":")), None)
                if matched:
                    references.add(matched)
                else:
                    violations.append({"kind": "unknown_evidence_product", "task_id": task_id,
                                       "evidence_id": evidence_id})
        for pid in sorted(references):
            assignment = product_assignments.get(pid)
            product_split = assignment.get("split") if isinstance(assignment, dict) else assignment
            if product_split is None:
                violations.append({"kind": "unknown_product", "task_id": task_id,
                                   "product_id": pid})
            elif product_split != split:
                violations.append({"kind": "product_cross_split", "task_id": task_id,
                                   "product_id": pid, "task_split": split,
                                   "product_split": product_split})
    return {"passed": not violations, "task_count": len(tasks), "group_count": len(groups),
            "groups": sorted((sorted(group) for group in groups.values())),
            "violations": violations, "task_records_sha256": _hash(sorted(
                tasks, key=lambda task: task["task_id"])),
            "scope": "declared sibling fields and explicit product/evidence references"}
