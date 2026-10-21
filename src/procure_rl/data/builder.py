"""Construct feasible English tasks and single-condition counterfactual siblings.

Inputs are already split, provenance-bearing S1 products and explicit templates.
The builder proves legal solutions before rendering query/persona/clarifications;
it returns tasks, rejected cases and an audit rather than filling target counts.
Private feasible IDs and construction anchors never enter teacher observations.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from ..env.catalog import digest
from ..env.verifier import verify_final

OPS = {"eq": "exactly", "lte": "at most", "gte": "at least", "contains": "including"}


def _value(product: dict, field: str) -> Any:
    return product.get("price") if field == "price" else product.get("specs", {}).get(field)


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        raise ValueError("Task templates require scalar grounded facts")
    return str(value)


def feasible_products(task: dict, products: list[dict]) -> list[str]:
    """Compute all legal IDs in this split, independent of any preferred target."""
    return sorted(p["product_id"] for p in products if p["split"] == task["split"] and
                  verify_final(task, p, {"product_id": p["product_id"]}, set(), set())["success"])


def _render(task: dict, template: dict) -> dict:
    result = copy.deepcopy(task)
    definitions = {c["id"]: c for c in template["constraints"]}
    statements = {"query": [], "persona": [], "clarification": []}
    slots = []
    for c in result["constraints"]:
        definition = definitions[c["id"]]
        label = definition.get("label", c["field"].replace("_", " "))
        text = f'My required {label} is {OPS[c["op"]]} {_display(c["value"])}.'
        statements[c["source"]].append(text)
        if c["source"] == "clarification":
            slots.append({"question_id": c["id"],
                          "question": definition.get("question", f"What is your requirement for {label}?"),
                          "answer": text, "constraint_ids": [c["id"]],
                          "trigger_keywords": definition.get("trigger_keywords", [c["id"], c["field"], label])})
    result["query"] = "Please recommend one " + template["item_description"] + ". " + " ".join(statements["query"])
    result["persona"] = " ".join(statements["persona"])
    result["clarifications"] = slots
    result["expression_method"] = "grounded_template_v1"
    result["teacher_expression_review"] = "not_run"
    result["human_review"] = "pending"
    return result


def _mentions(text: str, value: Any) -> bool:
    raw = str(value).casefold()
    alternatives = [raw]
    if type(value) in (int, float):
        if value in (2, 3):
            alternatives.append({2: "two", 3: "three"}[value])
        if value == 2:
            alternatives.append("dual")
        expression = r"(?<!\d)" + re.escape(raw) + r"(?!\d)"
        if re.search(expression, text.casefold()):
            return True
        alternatives = alternatives[1:]
    return any(re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", text.casefold()) for s in alternatives)


def audit_expression(task: dict) -> dict:
    """Reject literal hidden-value leaks and missing facts; semantic review is separate."""
    errors = []
    constraints = task["constraints"]
    for location, visible_sources in (("query", {"query"}), ("persona", {"persona"})):
        text = task.get(location, "")
        allowed = [c["value"] for c in constraints if c["source"] in visible_sources]
        for c in constraints:
            if c["source"] in visible_sources:
                if not _mentions(text, c["value"]):
                    errors.append({"code": "missing_visible_fact", "location": location, "constraint_id": c["id"]})
            elif c["source"] == "clarification" or location == "query":
                if c["value"] not in allowed and _mentions(text, c["value"]):
                    errors.append({"code": "hidden_value_leak", "location": location, "constraint_id": c["id"]})
    answers = {c: s["answer"] for s in task["clarifications"] for c in s["constraint_ids"]}
    for c in constraints:
        if c["source"] == "clarification" and (c["id"] not in answers or not _mentions(answers[c["id"]], c["value"])):
            errors.append({"code": "missing_clarification_fact", "constraint_id": c["id"]})
    return {"passed": not errors, "errors": errors, "method": "literal_value_coverage_v1",
            "semantic_review": "pending; lexical checks do not establish semantic fidelity"}


def apply_expression_rewrite(task: dict, proposal: dict) -> dict:
    """Apply prose-only augmentation while preserving facts, split and sibling root."""
    if set(proposal) - {"query", "persona", "clarification_questions"}:
        raise ValueError("Expression rewrite attempted to change private task data")
    result = copy.deepcopy(task)
    for field in ("query", "persona"):
        if field in proposal:
            if not isinstance(proposal[field], str) or not proposal[field].strip():
                raise ValueError("Empty or non-text rewrite")
            result[field] = proposal[field]
    questions = proposal.get("clarification_questions", {})
    if not isinstance(questions, dict) or set(questions) - {s["question_id"] for s in task["clarifications"]}:
        raise ValueError("Unknown clarification rewrite")
    for slot in result["clarifications"]:
        if slot["question_id"] in questions:
            value = questions[slot["question_id"]]
            if not isinstance(value, str) or not value.strip() or len(value) > 100:
                raise ValueError("Invalid clarification question")
            slot["question"] = value
    audit = audit_expression(result)
    if not audit["passed"]:
        raise ValueError("Rewrite failed visible/hidden fact checks: " + str(audit["errors"]))
    result.update(task_id=task["task_id"] + "-rewrite-" + digest(proposal)[:10],
                  parent_task_id=task["task_id"], root_task_id=task.get("root_task_id", task["task_id"]),
                  variant_kind="rewrite", expression_method="prose_rewrite_v1", human_review="pending")
    return result


def _signature(task: dict) -> str:
    return digest({"template_id": task["template_id"], "constraints": [
        {k: c[k] for k in ("id", "source", "field", "op", "value")} for c in task["constraints"]]})


def build_tasks(products: list[dict], templates: list[dict], *, max_base_per_split: int = 8,
                require_disjoint_counterfactual: bool = True) -> dict:
    """Return feasible bases/counterfactuals and explicit rejection reasons."""
    if type(max_base_per_split) is not int or max_base_per_split <= 0:
        raise ValueError("Positive task cap required")
    tasks, rejected, candidates = [], [], []
    for template in templates:
        definitions = template["constraints"]
        if (len({c["id"] for c in definitions}) != len(definitions) or
                {c["source"] for c in definitions} != {"query", "persona", "clarification"} or
                any(c["op"] not in OPS for c in definitions)):
            raise ValueError("Template requires unique query/persona/clarification constraints")
        for anchor in sorted(products, key=lambda p: p["product_id"]):
            if anchor["split"] not in ("train", "dev", "sealed_test"):
                raise ValueError("Official/quarantined product entered task construction")
            if template.get("title_contains") and template["title_contains"].casefold() not in anchor["title"].casefold():
                continue
            # Anchor selection is not a hard constraint. Every product in the
            # actual retrieval split participates in legal-solution enumeration.
            pool = [p for p in products if p["split"] == anchor["split"]]
            constraints = []
            for definition in definitions:
                value = _value(anchor, definition["field"])
                references = sorted({e["evidence_id"] for p in pool for e in p["evidence"]
                                     if e["field"] == definition["field"]})
                anchor_refs = [e for e in anchor["evidence"] if e["field"] == definition["field"]]
                if value is None or isinstance(value, (dict, list, bool)) or not references or not anchor_refs:
                    break
                constraints.append({"id": definition["id"], "source": definition["source"],
                                    "field": definition["field"], "op": definition["op"],
                                    "value": value, "evidence_ids": references})
            if len(constraints) != len(definitions):
                rejected.append({"product_id": anchor["product_id"], "template_id": template["template_id"],
                                 "reason": "missing_grounded_template_fact"})
                continue
            task = {"template_id": template["template_id"], "split": anchor["split"],
                    "constraints": constraints, "max_steps": 40, "max_clarifications": 10,
                    "construction_anchor": anchor["product_id"], "variant_kind": "base"}
            task["feasible_product_ids"] = feasible_products(task, pool)
            if not task["feasible_product_ids"]:
                rejected.append({"product_id": anchor["product_id"], "reason": "no_feasible_solution"})
                continue
            task["task_id"] = "task-" + digest({"definition": _signature(task), "split": task["split"]})[:20]
            task["root_task_id"] = task["task_id"]
            task = _render(task, template)
            expression = audit_expression(task)
            if not expression["passed"]:
                rejected.append({"task_id": task["task_id"], "reason": "expression_leak_or_missing_fact", "audit": expression})
                continue
            candidates.append((task, template, pool))
    groups = {}
    for task, template, pool in candidates:
        groups.setdefault(_signature(task), []).append((task, template, pool))
    split_counts = {s: 0 for s in ("train", "dev", "sealed_test")}
    for signature, group in sorted(groups.items()):
        if len({task["split"] for task, _, _ in group}) > 1:
            rejected.append({"signature": signature, "reason": "cross_split_identical_task", "count": len(group)})
            continue
        task, template, pool = group[0]
        if split_counts[task["split"]] >= max_base_per_split:
            rejected.append({"task_id": task["task_id"], "reason": "pilot_task_cap"})
            continue
        if len(group) > 1:
            rejected.append({"task_id": task["task_id"], "reason": "duplicate_fact_task", "count": len(group) - 1})
        split_counts[task["split"]] += 1
        counterfactual = None
        for index, constraint in enumerate(task["constraints"]):
            if constraint["id"] not in template.get("counterfactual_constraint_ids", [c["id"] for c in task["constraints"]]):
                continue
            values = {_display(_value(p, constraint["field"])): _value(p, constraint["field"])
                      for p in pool if _value(p, constraint["field"]) is not None}
            for _, value in sorted(values.items()):
                if value == constraint["value"]:
                    continue
                sibling = copy.deepcopy(task)
                sibling["constraints"][index]["value"] = value
                feasible = feasible_products(sibling, pool)
                old = set(task["feasible_product_ids"])
                changed = bool(feasible) and set(feasible) != old
                disjoint = old.isdisjoint(feasible)
                if not changed or (require_disjoint_counterfactual and not disjoint):
                    continue
                sibling.update(task_id=task["task_id"] + "-cf-" + digest({"id": constraint["id"], "value": value})[:8],
                               parent_task_id=task["task_id"], variant_kind="counterfactual",
                               feasible_product_ids=feasible, changed_constraint_id=constraint["id"],
                               decision_change_required=disjoint)
                sibling = _render(sibling, template)
                if not audit_expression(sibling)["passed"]:
                    continue
                counterfactual = sibling
                pair_id = "pair-" + digest([task["task_id"], sibling["task_id"]])[:16]
                task["pair_id"] = sibling["pair_id"] = pair_id
                break
            if counterfactual:
                break
        tasks.append(task)
        if counterfactual:
            tasks.append(counterfactual)
        else:
            rejected.append({"task_id": task["task_id"], "reason": "no_nonempty_disjoint_single_change_counterfactual"})
    # Counterfactuals are constructed after base dedup; recheck the complete set.
    final_signatures = {}
    for task in tasks:
        final_signatures.setdefault(_signature(task), []).append(task)
    blocked_roots = set()
    for signature, duplicates in final_signatures.items():
        if len({t["split"] for t in duplicates}) > 1:
            blocked_roots.update(t["root_task_id"] for t in duplicates)
            rejected.append({"signature": signature, "reason": "cross_split_variant_duplicate",
                             "task_ids": [t["task_id"] for t in duplicates]})
    tasks = [task for task in tasks if task["root_task_id"] not in blocked_roots]
    split_counts = {s: sum(t["split"] == s and t["variant_kind"] == "base" for t in tasks)
                    for s in ("train", "dev", "sealed_test")}
    return {"tasks": sorted(tasks, key=lambda t: t["task_id"]), "rejected": rejected,
            "audit": {"method": "fact_first_v1", "base_counts": split_counts,
                      "counterfactual_pairs": sum(t["variant_kind"] == "counterfactual" for t in tasks),
                      "expression_augmentation_count": 0, "human_review": "pending",
                      "teacher_expression_review": "not_run", "target_counts_are_not_completion_evidence": True}}
