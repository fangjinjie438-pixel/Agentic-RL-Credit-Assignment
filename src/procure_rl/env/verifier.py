"""Deterministic S1 terminal checks and bounded observation-derived events.

The session supplies trusted task/catalog dictionaries and actual tool observations.
``verify_final`` compares catalog facts independently of the agent's assertions and
returns baseline success plus separate evidence-delivery diagnostics. ``process_events``
returns auditable events and their scalar sum; callers retain coverage sets. Neither
function mutates its inputs, performs I/O, loads models, or uses an LLM judge.

Evidence IDs bind facts to ``<product_id>:details|reviews:<field>``. In process
scoring, ``seen_evidence`` contains rewarded *constraint IDs*, not raw evidence IDs:
the same rubric fact cannot earn more reward by visiting another product or source.
"""

from __future__ import annotations

import math
from typing import Any


_MISSING = object()


def _number(value: Any) -> bool:
    """JSON booleans and non-finite floats are not numeric product facts."""
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _equal(actual: Any, expected: Any) -> bool:
    if type(actual) is bool or type(expected) is bool:
        return type(actual) is bool and type(expected) is bool and actual == expected
    if isinstance(actual, list) or isinstance(expected, list):
        return (isinstance(actual, list) and isinstance(expected, list)
                and len(actual) == len(expected)
                and all(_equal(left, right) for left, right in zip(actual, expected)))
    if isinstance(actual, dict) or isinstance(expected, dict):
        return (isinstance(actual, dict) and isinstance(expected, dict)
                and actual.keys() == expected.keys()
                and all(_equal(actual[key], expected[key]) for key in actual))
    return actual == expected


def _matches(actual: Any, constraint: dict) -> bool | None:
    """Return a predicate result, or None for absent/incompatible fact types."""
    expected = constraint.get("value", _MISSING)
    if actual is _MISSING or expected is _MISSING or actual is None:
        return None
    operation = constraint.get("op")
    if operation in ("lte", "gte"):
        if not _number(actual) or not _number(expected):
            return None
        return actual <= expected if operation == "lte" else actual >= expected
    if operation == "eq":
        if isinstance(actual, float) and not math.isfinite(actual):
            return None
        return _equal(actual, expected)
    if operation == "contains":
        if isinstance(actual, str) and isinstance(expected, str):
            return expected in actual
        if isinstance(actual, list):
            return any(_equal(item, expected) for item in actual)
        return None
    return None


def _fact(product: dict | None, field: str) -> Any:
    if not isinstance(product, dict):
        return _MISSING
    if field == "price":
        return product.get("price", _MISSING)
    specs = product.get("specs")
    return specs.get(field, _MISSING) if isinstance(specs, dict) else _MISSING


def _binding(evidence_id: Any, product_id: str, field: str) -> bool:
    return isinstance(evidence_id, str) and evidence_id in (
        f"{product_id}:details:{field}", f"{product_id}:reviews:{field}"
    )


def _constraints(task: dict) -> list[dict]:
    constraints = task.get("constraints", [])
    return constraints if isinstance(constraints, list) else []


def verify_final(
    task: dict,
    product: dict | None,
    recommendation: dict,
    observed_evidence: set[str],
    revealed_requirements: set[str],
    *,
    budget_exhausted: bool = False,
) -> dict:
    """Check every hard constraint and separately audit the final cited checks.

    Baseline ``terminal_reward`` is 1 iff the named product is valid, all catalog
    constraints hold, and the tool budget was not exceeded. Missing/invalid evidence
    affects ``delivery_success`` and ``errors`` only, preserving PLAN's terminal
    baseline. Query constraints are visible from reset; persona/clarification
    constraints must occur in ``revealed_requirements`` for complete delivery.
    """
    errors: list[dict] = []
    constraints = _constraints(task)
    valid_constraints = [item for item in constraints if isinstance(item, dict)]
    constraint_ids = [item.get("id") for item in valid_constraints]
    task_valid = (
        bool(constraints)
        and len(valid_constraints) == len(constraints)
        and all(isinstance(key, str) and key for key in constraint_ids)
        and len(set(constraint_ids)) == len(constraint_ids)
    )
    if not task_valid:
        errors.append({"code": "invalid_task_constraints"})
    # A malformed task must not cause a partial or vacuously true acceptance.
    indexed = {item["id"]: item for item in valid_constraints
               if isinstance(item.get("id"), str)}
    recommendation_valid = isinstance(recommendation, dict)
    rec = recommendation if recommendation_valid else {}
    product_id = product.get("product_id") if isinstance(product, dict) else None
    valid_product = (
        isinstance(product_id, str) and bool(product_id)
        and isinstance(product.get("title"), str)
        and _number(product.get("price"))
        and isinstance(product.get("specs"), dict)
        and rec.get("product_id") == product_id
    )
    if not valid_product:
        errors.append({"code": "invalid_product"})
    if not recommendation_valid:
        errors.append({"code": "invalid_recommendation"})
    elif set(rec) - {"product_id", "checks"}:
        errors.append({"code": "unknown_recommendation_fields"})
    if budget_exhausted:
        errors.append({"code": "budget_exhausted"})

    checks = rec.get("checks", [])
    if not isinstance(checks, list):
        errors.append({"code": "invalid_checks"})
        checks = []
    checked: dict[str, dict] = {}
    invalid_checks: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            errors.append({"code": "invalid_check"})
            continue
        key = check.get("constraint_id")
        if not isinstance(key, str) or key not in indexed:
            errors.append({"code": "unknown_constraint", "constraint_id": key})
            continue
        if key in checked:
            errors.append({"code": "duplicate_constraint", "constraint_id": key})
            invalid_checks.add(key)
            continue
        checked[key] = check
        if set(check) != {"constraint_id", "evidence_ids"}:
            errors.append({"code": "invalid_check_fields", "constraint_id": key})
            invalid_checks.add(key)

    results = []
    by_source: dict[str, dict] = {}
    for key, constraint in indexed.items():
        source = constraint.get("source", "unknown")
        field = constraint.get("field", "")
        actual = _fact(product, field)
        satisfied = _matches(actual, constraint) is True
        revealed = source == "query" or key in revealed_requirements
        check = checked.get(key)
        refs = check.get("evidence_ids", []) if check else []
        local_errors = []
        if check is None:
            local_errors.append("missing_check")
        if not isinstance(refs, list) or not refs:
            local_errors.append("missing_evidence")
            refs = []
        evidence_valid = bool(refs) and key not in invalid_checks
        seen_refs: set[str] = set()
        for reference in refs:
            reason = None
            if not isinstance(reference, str):
                reason = "invalid_evidence_id"
            elif reference in seen_refs:
                reason = "duplicate_evidence"
            elif reference not in observed_evidence:
                reason = "unobserved_evidence"
            elif not _binding(reference, product_id, field):
                reason = "wrong_evidence_binding"
            elif reference not in constraint.get("evidence_ids", []):
                reason = "unsupported_evidence"
            if isinstance(reference, str):
                seen_refs.add(reference)
            if reason:
                evidence_valid = False
                local_errors.append(reason)
                errors.append({"code": reason, "constraint_id": key,
                               "evidence_id": reference})
        if not revealed:
            local_errors.append("unrevealed_requirement")
        # Repeating a constraint invalidates its entire check, including the first.
        if key in invalid_checks:
            local_errors.append("invalid_or_duplicate_check")
        for code in local_errors:
            if code in ("missing_check", "missing_evidence", "unrevealed_requirement"):
                errors.append({"code": code, "constraint_id": key})
        results.append({
            "constraint_id": key, "source": source, "field": field,
            "satisfied": satisfied, "revealed": revealed,
            "evidence_valid": evidence_valid, "evidence_ids": refs,
            "errors": local_errors,
        })
        source_result = by_source.setdefault(source, {"total": 0, "satisfied": 0})
        source_result["total"] += 1
        source_result["satisfied"] += int(satisfied)
    for source_result in by_source.values():
        source_result["rate"] = source_result["satisfied"] / source_result["total"]
    satisfied_count = sum(item["satisfied"] for item in results)
    success = bool(task_valid and valid_product and results
                   and all(item["satisfied"] for item in results)
                   and not budget_exhausted)
    return {
        "success": success,
        "terminal_reward": float(success),
        "delivery_success": success and not errors
                            and all(item["revealed"] and item["evidence_valid"]
                                    for item in results),
        "valid_product": bool(valid_product),
        "budget_exhausted": bool(budget_exhausted),
        "constraint_satisfaction": satisfied_count / len(results) if results else 0.0,
        "constraints_by_source": by_source,
        "constraint_results": results,
        "errors": errors,
    }


def process_events(
    task: dict,
    observation: dict,
    seen_requirements: set[str],
    seen_evidence: set[str],
    *,
    invalid: bool = False,
    repeated: bool = False,
) -> tuple[list[dict], float]:
    """Score actual structured observations once per finite task-rubric item.

    Hidden requirements share 0.4; evidence facts share 0.6. ``seen_evidence``
    records constraint IDs so alternate candidates/sources cannot refresh a fact.
    Evidence may support or exclude a candidate, but must have usable typed values
    and a task-whitelisted ID with matching product and field. Inputs are untouched.
    Invalid actions earn only -0.05; repeated actions earn -0.02 only without a new
    positive event. Free text, keywords, and agent assertions are never scored.
    """
    if invalid:
        return [{"kind": "invalid", "key": "invalid_call", "reward": -0.05}], -0.05
    constraints = {item["id"]: item for item in _constraints(task)
                   if isinstance(item, dict) and isinstance(item.get("id"), str)}
    hidden = {key: value for key, value in constraints.items()
              if value.get("source") in ("persona", "clarification")}
    events: list[dict] = []
    new_requirements: set[str] = set()
    new_evidence: set[str] = set()
    revealed = observation.get("revealed_requirements", [])
    for key in revealed if isinstance(revealed, list) else []:
        if not isinstance(key, str) or key not in hidden:
            continue
        if key in seen_requirements or key in new_requirements:
            continue
        new_requirements.add(key)
        events.append({"kind": "hidden_requirement", "key": key,
                       "constraint_id": key, "source": hidden[key]["source"],
                       "reward": 0.4 / len(hidden)})
    evidence = observation.get("evidence", [])
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("evidence_id")
        product_id, field = item.get("product_id"), item.get("field")
        if not isinstance(product_id, str) or not product_id or not isinstance(field, str):
            continue
        if not _binding(evidence_id, product_id, field):
            continue
        for key, constraint in constraints.items():
            if key in seen_evidence or key in new_evidence:
                continue
            if field != constraint.get("field"):
                continue
            if evidence_id not in constraint.get("evidence_ids", []):
                continue
            satisfied = _matches(item.get("value", _MISSING), constraint)
            if satisfied is None:
                continue
            new_evidence.add(key)
            events.append({"kind": "evidence", "key": key,
                           "constraint_id": key, "evidence_id": evidence_id,
                           "product_id": product_id, "field": field,
                           "supports": satisfied,
                           "reward": 0.6 / len(constraints)})
    if repeated and not events:
        events.append({"kind": "repeat", "key": "no_progress", "reward": -0.02})
    return events, sum(item["reward"] for item in events)
