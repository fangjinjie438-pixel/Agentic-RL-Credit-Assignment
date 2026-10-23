"""Render hash-bound S2 tasks and source evidence for actual human review.

Input is a verified dataset's manifest, products and explicitly selected tasks.
Output is private reviewer material plus pending JSON forms; no decisions are
created and no teacher, model, network, SQLite mutation or GPU is invoked.
The CLI wrapper in scripts/data/prepare_s2_review.py verifies dataset inventory.
"""

from __future__ import annotations

import json

from .builder import feasible_products
from .review import make_review_queue
from ..env.catalog import digest


def prepare_review_material(manifest: dict, products: list[dict], tasks: list[dict],
                            *, seed: int = 0) -> dict:
    """Prepare complete evidence and unsigned forms without approving anything."""
    if any(t["split"] == "official_test" for t in tasks):
        raise ValueError("Official tasks must not enter project review material")
    selected_splits = {"train", "dev"} | {t["split"] for t in tasks}
    selected_products = [p for p in products if p["split"] in selected_splits]
    queue = make_review_queue(selected_products, tasks, [], seed=seed)
    human_entries = {entry["task_id"]: entry for entry in queue["task_reviews"]}
    packets = []
    for task in sorted(tasks, key=lambda t: (t["split"], t["task_id"])):
        entry = human_entries.get(task["task_id"], {"task_id": task["task_id"],
                 "task_sha256": digest(task), "priority": "outside_human_sample", "status": "pending"})
        same_split = [p for p in selected_products if p["split"] == task["split"]]
        actual_legal_ids = feasible_products(task, same_split)
        siblings = [t for t in tasks if t["root_task_id"] == task["root_task_id"]]
        packets.append({**entry, "human_review_required": task["task_id"] in human_entries, "task": task,
                        "recomputed_feasible_product_ids": actual_legal_ids,
                        "recorded_legal_set_matches_recomputed": actual_legal_ids == task["feasible_product_ids"],
                        "siblings": [{"task_id": t["task_id"], "task_sha256": digest(t),
                                      "variant_kind": t["variant_kind"], "constraints": t["constraints"],
                                      "feasible_product_ids": t["feasible_product_ids"]} for t in siblings],
                        "retrievable_product_ids": [p["product_id"] for p in same_split]})
    pending = {"dataset_revision": manifest["revision"], "human_reviews": [
        {"task_id": entry["task_id"], "task_sha256": entry["task_sha256"], "role": "human",
         "reviewer": None, "reviewed_at": None, "decision": None,
         "adjudicates_model_disagreement": False, "notes": None}
        for entry in queue["task_reviews"]], "identity_reviews": [
        {"product_id": entry["product_id"], "product_sha256": entry["product_sha256"],
         "family": entry["family"], "role": "human", "reviewer": None,
         "reviewed_at": None, "decision": None, "notes": None}
        for entry in queue["identity_reviews"]], "independent_reviews": []}
    return {"schema_version": 1, "dataset_revision": manifest["revision"],
            "private_reviewer_material": True, "human_review_performed": False,
            "model_review_performed": False, "formal_release_approved": False,
            "selected_splits": sorted(selected_splits), "seed": seed,
            "human_sample_required": queue["required_human_sample"],
            "human_sample_available": len(queue["task_reviews"]),
            "human_sample_shortfall": max(0, queue["required_human_sample"] - len(queue["task_reviews"])),
            "products": selected_products, "task_packets": packets,
            "pending_reviews": pending}


def render_review_markdown(material: dict) -> str:
    """Render private facts, quotes and unresolved review checks in Chinese."""
    lines = ["# S2 人工审阅材料（尚未签核）", "",
             f"数据 revision：`{material['dataset_revision']}`。",
             "本文件包含私有约束、完整合法解和原始证据，仅供数据审核。不要发送给执行教师或学生策略。",
             "尚未进行人工/独立模型审核，也未批准正式训练数据。空白表单不是通过记录。", "",
             f"本包覆盖 {', '.join(material['selected_splits']) or '无任务'}；"
             f"可审 {material['human_sample_available']} 条，PLAN 的 200 条人工抽检仍差 "
             f"{material['human_sample_shortfall']} 条。数量不足不能通过复制记录补齐。", "",
             "## 如何完成真实签核", "",
             "1. 逐条核对下面原字段/原句、数值与单位、所有合法商品，以及隐藏约束是否在正确渠道出现。",
             "2. 对照同 root 的反事实，只允许一个约束值改变，并确认合法解非空且要求决策改变。",
             "3. 检查任务是否符合办公电子设备采购、表达是否自然、是否具备有意义的检索与核验难度；泛泛的品类或浅层模板可拒收。",
             "4. 检查品牌/型号/家族保守聚类。若家族错误，先修来源和重建新 revision，再重新签核；不要只改审核表。",
             "5. 实际完成后复制 `reviews-template.json` 为新文件，填写真实 reviewer、带时区 reviewed_at、accept/reject 和具体 notes。未审核项应删除或保持空白；空白项不能通过审计。",
             "6. 模型分歧必须由实际人工裁决，并仅在已完成裁决时填 `adjudicates_model_disagreement=true`。拒收任务仍在数据包内时发布保持 withheld。", "",
             "独立模型输入位于 `independent-inputs.jsonl`，只是尚未执行的审阅输入。实际记录需 model/model_revision、带时区 reviewed_at、prompt_version、含完整task与task_sha256的prompt对象、raw_response；prompt_sha256与response_sha256使用catalog.digest规范JSON算法。另存 independence_basis={method: different_model, generation_models: [实际生成教师标识]}。同名模型或缺原始内容/哈希的记录不计入复核。声明与哈希不能自动认证执行或分辨模型别名，仍须检查真实执行记录；不得把本脚本或词面检查称为独立模型。", "",
             "## 商品事实与来源", ""]
    for product in material["products"]:
        lines.extend([f"### {product['product_id']} · {product['title']}", "",
                      f"split=`{product['split']}`；family=`{product['family']}`；"
                      f"brand=`{product.get('brand')}`；model=`{product.get('model')}`。", "",
                      f"商品哈希：`{digest(product)}`。", ""])
        for evidence in product["evidence"]:
            provenance = evidence.get("provenance", {})
            lines.append(f"- `{evidence['evidence_id']}`：{evidence['field']} = "
                         f"{json.dumps(evidence['value'], ensure_ascii=False)}；原句 "
                         f"{json.dumps(evidence['text'], ensure_ascii=False)}；"
                         f"原字段 `{json.dumps(provenance.get('source_field'), ensure_ascii=False)}`；"
                         f"原行 `{provenance.get('source_row_index')}`；"
                         f"原单位 `{provenance.get('raw_unit')}` → `{provenance.get('unit')}`；"
                         f"原记录 SHA `{provenance.get('raw_record_sha256')}`。")
        lines.append("")
    lines.extend(["## 逐条任务核对", ""])
    for packet in material["task_packets"]:
        task = packet["task"]
        lines.extend([f"### {task['task_id']} ({task['variant_kind']}, {task['split']})", "",
                      f"任务 SHA：`{packet['task_sha256']}`；root：`{task['root_task_id']}`。", "",
                      f"Query: {task['query']}", "", f"Persona: {task['persona']}", "",
                      "```json", json.dumps({key: task[key] for key in
                          ("clarifications", "constraints", "feasible_product_ids")}, ensure_ascii=False, indent=2),
                      "```", "", f"程序独立重算解集一致：`{packet['recorded_legal_set_matches_recomputed']}`。"
                      "这只是程序检查，不是人工通过。", "",
                      "同 root 任务：" + ", ".join(f"`{s['task_id']}` ({s['variant_kind']})" for s in packet["siblings"]), "",
                      "待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。", ""])
    return "\n".join(lines) + "\n"


def independent_review_inputs(material: dict) -> list[dict]:
    """Return unexecuted review inputs; private answers are for reviewers only."""
    products = {p["product_id"]: p for p in material["products"]}
    return [{"task_id": p["task_id"], "task_sha256": p["task_sha256"],
             "prompt_version": "s2-independent-semantic-review-v1", "status": "not_run",
             "instruction": "Independently review grounded fact/unit fidelity, all legal solutions, "
             "query/persona/clarification separation, single-constraint counterfactuals, natural language "
             "fidelity and realistic office-electronics procurement difficulty. Return accept or reject "
             "with specific evidence and uncertainties. This is reviewer-only private material.",
             "task": p["task"], "siblings": p["siblings"],
             "products": [products[pid] for pid in p["retrievable_product_ids"]]}
            for p in material["task_packets"]]
