"""Execute bounded procurement episodes on pinned native ECom CPU tools.

ProcurementEnv consumes a private task and split Catalog. Only reset/step
observations and tool schemas belong in a model prompt; StepResult diagnostics,
snapshots and trajectories are privileged audit data. Snapshots contain the full
state and RNG and are restored by deterministic action replay before adoption.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import asdict, dataclass

from .catalog import Catalog, digest
from .protocol import ActionError, parse_action
from .upstream import NativeEComTools
from .verifier import process_events, verify_final


@dataclass(frozen=True)
class StepResult:
    """Public observation plus separate privileged reward/audit data."""

    observation: dict
    done: bool
    step_reward: float
    terminal_reward: float
    verifier_events: list[dict]
    terminal_validation: dict | None
    action_index: int


class ProcurementEnv:
    """An isolated episode; sharing a Catalog never shares mutable task state."""

    def __init__(self, catalog: Catalog, task: dict, *, policy_version: str = "scripted-s1-v1"):
        if task["split"] != catalog.split:
            raise ValueError("Task and retrieval split differ")
        self.catalog, self.task = catalog, copy.deepcopy(task)
        self.policy_version = policy_version
        self.native = None
        self.reset()

    def close(self) -> None:
        if self.native is not None:
            self.native.close()
            self.native = None

    def _requirements(self, source: str, ids: set[str] | None = None) -> list[dict]:
        return [{k: copy.deepcopy(c[k]) for k in ("id", "source", "field", "op", "value")}
                for c in self.task["constraints"] if c["source"] == source and (ids is None or c["id"] in ids)]

    def reset(self, *, seed: int = 0) -> dict:
        """Start a new episode, revealing only the visible query requirements."""
        if type(seed) is not int:
            raise ValueError("Seed must be an integer")
        self.close()
        script = {"clarification_slots": [
            {"slot_id": s["question_id"], "trigger_keywords": s.get("trigger_keywords", [s["question_id"]]),
             "user_response": s["answer"]} for s in self.task["clarifications"]],
            "max_clarification_turns": self.task["max_clarifications"]}
        self.native = NativeEComTools(self.catalog.path, persona={"description": self.task["persona"]},
                                     clarification_script=script)
        self.seed, self.rng = seed, random.Random(seed)
        self.revealed = {c["id"] for c in self.task["constraints"] if c["source"] == "query"}
        self.observed_evidence, self.covered_evidence, self.seen_calls = set(), set(), set()
        self.history: list[dict] = []
        self.done, self.terminal = False, None
        return {"task_id": self.task["task_id"], "query": self.task["query"],
                "requirements": self._requirements("query"),
                "remaining_steps": self.task["max_steps"], "protocol_version": "procure-ecom-v1"}

    def schemas(self) -> list[dict]:
        """Expose nine native tools; final checks are a project extension."""
        schemas = copy.deepcopy(self.native.schemas())
        for schema in schemas:
            function = schema["function"]
            if function["name"] == "recommend_product":
                function["parameters"]["properties"]["checks"] = {
                    "type": "array", "maxItems": 64, "items": {
                        "type": "object", "properties": {"constraint_id": {"type": "string"},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}}},
                        "required": ["constraint_id", "evidence_ids"]}}
                function["description"] += " Include checks citing observed evidence IDs for each revealed requirement."
        return schemas

    @staticmethod
    def _revealed_slots(state: dict) -> set[str]:
        return {s["slot_id"] for s in state["clarification"]["slots"] if s.get("revealed")}

    def step(self, raw: dict | str) -> StepResult:
        """Count one attempted action, execute real tools, and emit typed audit data."""
        if self.done:
            raise RuntimeError("Episode ended; reset or restore an earlier snapshot")
        # Evidence files must remain JSON serializable even for malformed actions.
        try:
            saved_action = json.loads(json.dumps(raw, allow_nan=False))
        except (ValueError, TypeError, RecursionError):
            saved_action = "<unserializable action>"
        name, args, fingerprint = "invalid_action", {}, digest(saved_action)
        invalid, new_requirements, evidence = False, set(), []
        try:
            action = parse_action(saved_action, self.schemas())
            name, args = action["name"], action["arguments"]
            fingerprint = digest(action)
            before = self.native.snapshot()
            native_args = {k: v for k, v in args.items() if k != "checks"}
            observation = self.native.call(name, native_args)
            invalid = "error" in observation
            if name == "get_user_profile" and not invalid:
                new_requirements = {c["id"] for c in self.task["constraints"] if c["source"] == "persona"}
                observation["requirements"] = self._requirements("persona")
            elif name == "ask_user" and not invalid:
                invalid = (len(args["question"]) > 100 or
                           before["clarification"]["turn_count"] >= self.task["max_clarifications"])
                if invalid:
                    observation["tool_status"] = "invalid_clarification"
                slots = self._revealed_slots(self.native.snapshot()) - self._revealed_slots(before)
                new_requirements = {c for s in self.task["clarifications"] if s["question_id"] in slots
                                    for c in s["constraint_ids"]}
                observation["requirements"] = self._requirements("clarification", new_requirements)
            elif name == "get_product_details" and not invalid:
                evidence = self.catalog.evidence(args["product_id"], "details")
            elif name == "get_review_content" and not invalid:
                # Attach only evidence whose exact source text was actually returned
                # by native FTS, never every fact of the requested product.
                texts = {r["text"] for r in observation.get("reviews", [])}
                evidence = [e for e in self.catalog.evidence(args["product_id"], "reviews") if e["text"] in texts]
            if evidence:
                observation["evidence"] = evidence
            if name == "recommend_product":
                product = self.catalog.product(args["product_id"])
                invalid = invalid or product is None
                recommendation = {k: v for k, v in args.items() if k in ("product_id", "checks")}
                self.terminal = verify_final(self.task, product, recommendation, self.observed_evidence, self.revealed)
                self.done = True
        except (ActionError, KeyError, TypeError, ValueError) as exc:
            invalid = True
            observation = {"error": {"code": "invalid_action", "message": str(exc)}}
        # Native I/O failures are intentionally not converted into agent mistakes;
        # callers retain the exception and failed run manifest for investigation.
        events, reward = process_events(self.task, {"revealed_requirements": sorted(new_requirements),
                                                    "evidence": evidence},
                                         self.revealed, self.covered_evidence,
                                         invalid=invalid, repeated=fingerprint in self.seen_calls)
        self.revealed.update(new_requirements)
        self.observed_evidence.update(e["evidence_id"] for e in evidence)
        self.covered_evidence.update(e["key"] for e in events if e["kind"] == "evidence")
        self.seen_calls.add(fingerprint)
        if not self.done and len(self.history) + 1 >= self.task["max_steps"]:
            self.done = True
            self.terminal = verify_final(self.task, None, {}, self.observed_evidence,
                                         self.revealed, budget_exhausted=True)
            observation["termination"] = "budget_exhausted"
        observation["remaining_steps"] = self.task["max_steps"] - len(self.history) - 1
        result = StepResult(copy.deepcopy(observation), self.done, reward,
                            float(self.terminal["terminal_reward"]) if self.terminal else 0.0,
                            copy.deepcopy(events), copy.deepcopy(self.terminal), len(self.history))
        self.history.append({"action": saved_action, **asdict(result)})
        return result

    def _state(self) -> dict:
        return {"schema_version": 1, "task_sha256": digest(self.task),
                "catalog_sha256": self.catalog.sha256, "catalog_revision": self.catalog.revision,
                "policy_version": self.policy_version, "seed": self.seed,
                "rng_state": json.loads(json.dumps(self.rng.getstate())),
                "native_state": self.native.snapshot(), "revealed_requirements": sorted(self.revealed),
                "observed_evidence": sorted(self.observed_evidence), "covered_evidence": sorted(self.covered_evidence),
                "seen_calls": sorted(self.seen_calls), "remaining_steps": self.task["max_steps"] - len(self.history),
                "history": copy.deepcopy(self.history), "done": self.done, "terminal": copy.deepcopy(self.terminal)}

    def snapshot(self) -> dict:
        """Return a JSON-safe, fully isolated privileged checkpoint of this episode."""
        state = self._state()
        return {"state": state, "sha256": digest(state)}

    def restore(self, snapshot: dict) -> dict:
        """Replay and compare before atomically replacing this session's state."""
        state = copy.deepcopy(snapshot["state"])
        if snapshot["sha256"] != digest(state):
            raise ValueError("Snapshot checksum mismatch")
        if (state["task_sha256"] != digest(self.task) or state["catalog_sha256"] != self.catalog.sha256 or
                state["policy_version"] != self.policy_version or state["schema_version"] != 1):
            raise ValueError("Snapshot task, database, policy or schema differs")
        if len(state["history"]) > self.task["max_steps"]:
            raise ValueError("Snapshot exceeds task budget")
        candidate = ProcurementEnv(self.catalog, self.task, policy_version=self.policy_version)
        try:
            candidate.reset(seed=state["seed"])
            for transition in state["history"]:
                candidate.step(transition["action"])
            if candidate._state() != state:
                raise ValueError("Snapshot does not match deterministic replay")
        except BaseException:
            candidate.close()
            raise
        self.close()
        self.__dict__.update(candidate.__dict__)
        return {"remaining_steps": state["remaining_steps"], "done": self.done}

    def trajectory(self) -> dict:
        """Return structured step data for replay; token spans begin in S3."""
        return {"schema_version": 1, "task_id": self.task["task_id"], "split": self.catalog.split,
                "data_revision": self.catalog.revision, "catalog_sha256": self.catalog.sha256,
                "task_sha256": digest(self.task), "policy_version": self.policy_version, "seed": self.seed,
                "transitions": copy.deepcopy(self.history),
                "step_rewards": [s["step_reward"] for s in self.history],
                "verifier_events": [s["verifier_events"] for s in self.history],
                "turn_spans": [], "tokenization_status": "not_tokenized_S1_CPU_tools_only",
                "done": self.done, "terminal_validation": copy.deepcopy(self.terminal)}
