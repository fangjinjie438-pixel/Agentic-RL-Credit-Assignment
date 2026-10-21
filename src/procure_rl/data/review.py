"""Prepare S2 human review queues and evidence-based formal-release gates.

Input is built tasks/products, replay ledgers and explicitly supplied review
records. Outputs contain pending actions and release reasons. This module never
fabricates human decisions, semantic model results or official family coverage.
"""

from __future__ import annotations

from ..env.catalog import digest


def make_review_queue(products: list[dict], tasks: list[dict], semantic_pairs: list[dict],
                      *, seed: int = 0, sample_size: int = 200) -> dict:
    """Sample reproducibly and retain every marked disagreement as mandatory."""
    ordered = sorted(tasks, key=lambda t: digest([seed, t["root_task_id"], t["task_id"]]))
    selected = {t["task_id"] for t in ordered[:sample_size]}
    selected.update(t["task_id"] for t in tasks if t.get("model_disagreement"))
    return {"schema_version": 1, "seed": seed, "required_human_sample": sample_size,
            "available_tasks": len(tasks), "human_review_performed": False,
            "task_reviews": [{"task_id": t["task_id"], "task_sha256": digest(t),
                              "split": t["split"], "root_task_id": t["root_task_id"],
                              "priority": "mandatory_disagreement" if t.get("model_disagreement") else "sample",
                              "status": "pending", "checks": ["fact_quotes_and_units", "all_legal_solutions",
                              "hidden_source_separation", "family_identity", "single_change_counterfactual",
                              "semantic_expression_fidelity"]} for t in ordered if t["task_id"] in selected],
            "identity_reviews": [{"product_id": p["product_id"], "product_sha256": digest(p), "family": p["family"],
                                  "status": "pending"} for p in products if p.get("identity_review_required")],
            "semantic_candidates": semantic_pairs,
            "independent_model_review": {"status": "not_run", "preferred_plan": "allocated single-GPU 8B",
                                         "lexical_candidates_are_not_model_reviews": True}}


def release_gate(products: list[dict], tasks: list[dict], ledgers: list[dict],
                 official_exclusions: dict, *, human_reviews: list[dict] | None = None,
                 independent_reviews: list[dict] | None = None,
                 identity_reviews: list[dict] | None = None, engineering: bool = False) -> dict:
    """Require real evidence before publishing any formal training release."""
    human_reviews, independent_reviews = human_reviews or [], independent_reviews or []
    indexed = {t["task_id"]: t for t in tasks}
    valid_human, accepted, adjudicated = set(), set(), set()
    human_decisions = {}
    invalid_reviews = []
    for review in human_reviews:
        task = indexed.get(review.get("task_id"))
        if (task is None or review.get("task_sha256") != digest(task) or
                review.get("role") != "human" or not review.get("reviewer") or not review.get("reviewed_at") or
                review.get("decision") not in ("accept", "reject")):
            invalid_reviews.append(review.get("task_id"))
            continue
        valid_human.add(task["task_id"])
        human_decisions.setdefault(task["task_id"], set()).add(review["decision"])
        if review["decision"] == "accept":
            accepted.add(task["task_id"])
            if review.get("adjudicates_model_disagreement") is True:
                adjudicated.add(task["task_id"])
    rejected_ids = {key for key, values in human_decisions.items() if "reject" in values}
    conflicting_ids = {key for key, values in human_decisions.items() if len(values) > 1}
    accepted.difference_update(rejected_ids)
    reasons = []
    if engineering:
        reasons.append("engineering_fixture_not_formal_data")
    if rejected_ids:
        reasons.append("human_rejected_tasks_pending_removal")
    if conflicting_ids:
        reasons.append("conflicting_human_reviews")
    if not official_exclusions.get("metadata_complete"):
        reasons.append("official_family_and_near_duplicate_metadata_incomplete")
    product_map = {p["product_id"]: p for p in products}
    valid_identities = [r for r in (identity_reviews or [])
                          if r.get("product_id") in product_map and r.get("role") == "human"
                          and r.get("reviewer") and r.get("reviewed_at") and r.get("decision") in ("accept", "reject")
                          and r.get("product_sha256") == digest(product_map[r["product_id"]])
                          and r.get("family") == product_map[r["product_id"]]["family"]]
    rejected_identities = {r["product_id"] for r in valid_identities if r["decision"] == "reject"}
    confirmed_identity = {r["product_id"] for r in valid_identities if r["decision"] == "accept"} - rejected_identities
    if any(p.get("identity_review_required") and p["product_id"] not in confirmed_identity for p in products):
        reasons.append("product_family_identities_pending_review")
    if len(valid_human) < 200:
        reasons.append("fewer_than_200_hash_bound_human_task_reviews")
    if invalid_reviews:
        reasons.append("invalid_or_stale_human_reviews")
    valid_independent = [r for r in independent_reviews if r.get("status") == "completed"
                       and r.get("model_revision") and r.get("task_id") in indexed
                       and r.get("decision") in ("accept", "reject")
                       and r.get("task_sha256") == digest(indexed[r["task_id"]])]
    independent_ids = {r["task_id"] for r in valid_independent}
    disagreements = {t["task_id"] for t in tasks if t.get("model_disagreement")}
    disagreements.update(r["task_id"] for r in valid_independent if r["decision"] == "reject")
    if disagreements - adjudicated:
        reasons.append("unadjudicated_model_disagreement")
    if any(t["task_id"] not in independent_ids for t in tasks if t["split"] == "train"):
        reasons.append("independent_semantic_review_pending")
    expert_ids = {r["task_id"] for r in ledgers if r.get("expert_eligible") and r.get("accepted")
                  and r.get("task_id") in indexed and indexed[r["task_id"]]["split"] == "train"}
    if not expert_ids:
        reasons.append("no_replay_accepted_real_teacher_training_episodes")
    if expert_ids - accepted:
        reasons.append("expert_candidates_not_human_approved")
    return {"ready_for_formal_training": not reasons, "status": "ready" if not reasons else "withheld",
            "reasons": reasons, "human_review_count": len(valid_human),
            "independent_review_count": len(independent_ids), "expert_candidate_task_count": len(expert_ids),
            "invalid_review_task_ids": invalid_reviews,
            "human_rejected_task_ids": sorted(rejected_ids), "conflicting_task_ids": sorted(conflicting_ids),
            "unadjudicated_task_ids": sorted(disagreements - adjudicated),
            "quantity_targets": {"train": 1600, "dev": 200, "sealed_test": 400, "counterfactual_pairs": 100,
                                 "expert_successes": 600},
            "quantity_targets_are_not_claimed_achieved": True}
