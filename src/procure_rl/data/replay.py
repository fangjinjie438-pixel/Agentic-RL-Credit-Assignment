"""Validate a collected trajectory by real deterministic environment execution.

replay_episode receives a split Catalog, private task and recorded trajectory.
It never trusts recorded rewards, success flags or target IDs: every transition,
aggregate, task/catalog identity and final audit state is recomputed. Its returned
ledger separates replay acceptance from eligibility for expert training exports.
"""

from __future__ import annotations

import copy
import json
from urllib.parse import urlsplit

from ..env import ProcurementEnv
from ..env.catalog import digest
from .teacher import OpenAIHTTPTeacher, PROMPTS


def replay_episode(catalog, task: dict, trajectory: dict) -> dict:
    """Return an accept/reject ledger; no teacher, model or GPU is invoked."""
    failures: list[str] = []
    detail: list[dict] = []
    def fail(code: str, **information):
        if code not in failures:
            failures.append(code)
        detail.append({"code": code, **information})
    try:
        trajectory_hash = digest(trajectory)
    except (TypeError, ValueError, RecursionError):
        return {"accepted": False, "expert_eligible": False, "failure_types": ["non_json_trajectory"],
                "trajectory_sha256": None, "details": []}
    expected = {"schema_version": 1, "task_id": task["task_id"], "split": catalog.split,
                "data_revision": catalog.revision, "catalog_sha256": catalog.sha256, "task_sha256": digest(task)}
    for key, value in expected.items():
        if trajectory.get(key) != value:
            fail("identity_mismatch", field=key)
    if not isinstance(trajectory.get("policy_version"), str) or not trajectory.get("policy_version"):
        fail("missing_policy_version")
    if type(trajectory.get("seed")) is not int:
        fail("invalid_seed")
    transitions = trajectory.get("transitions")
    if not isinstance(transitions, list) or not transitions or len(transitions) > task["max_steps"]:
        fail("invalid_transition_count")
    if trajectory.get("done") is not True or not isinstance(trajectory.get("terminal_validation"), dict):
        fail("missing_terminal")
    if not isinstance(trajectory.get("final_state_sha256"), str):
        fail("missing_state_hash")
    prompt_version = trajectory.get("collection", {}).get("prompt_version")
    if not isinstance(prompt_version, str) or prompt_version not in PROMPTS:
        fail("unknown_prompt_version")
    final = None
    state_hash = None
    if not failures:
        env = ProcurementEnv(catalog, copy.deepcopy(task), policy_version=trajectory["policy_version"])
        try:
            initial = env.reset(seed=trajectory["seed"])
            if initial != trajectory.get("initial_observation"):
                fail("initial_observation_mismatch")
            messages = trajectory.get("public_messages")
            if (not isinstance(messages, list) or len(messages) != 2 + 2 * len(transitions) or
                    trajectory.get("messages_sha256") != digest(messages)):
                fail("public_dialogue_mismatch")
                messages = None
            elif (messages[0] != {"role": "system", "content": PROMPTS[prompt_version]} or
                  messages[1] != {"role": "user", "content": json.dumps(initial, ensure_ascii=False, sort_keys=True)}):
                fail("public_dialogue_mismatch")
            for index, transition in enumerate(transitions):
                if not isinstance(transition, dict) or "action" not in transition:
                    fail("malformed_transition", action_index=index)
                    break
                if env.done:
                    fail("actions_after_terminal", action_index=index)
                    break
                env.step(copy.deepcopy(transition["action"]))
                if env.history[-1] != transition:
                    fail("transition_mismatch", action_index=index,
                         fields=sorted(k for k in set(transition) | set(env.history[-1])
                                       if transition.get(k) != env.history[-1].get(k)))
                if messages:
                    try:
                        assistant, observed = messages[2 + index * 2:4 + index * 2]
                        call = assistant["tool_calls"][0]
                        if (assistant["role"] != "assistant" or len(assistant["tool_calls"]) != 1 or
                                {"name": call["function"]["name"], "arguments": json.loads(call["function"]["arguments"])}
                                != transition["action"] or observed != {"role": "tool", "tool_call_id": call["id"],
                                "content": json.dumps(env.history[-1]["observation"], ensure_ascii=False, sort_keys=True)}):
                            fail("public_dialogue_mismatch", action_index=index)
                    except (KeyError, TypeError, ValueError, IndexError):
                        fail("public_dialogue_mismatch", action_index=index)
            teacher = trajectory.get("collection", {}).get("teacher", {})
            if teacher.get("kind") == "http_teacher":
                records, identity = teacher.get("requests"), teacher.get("identity")
                if (not isinstance(records, list) or len(records) != len(transitions) or
                        not isinstance(identity, dict) or digest(identity) != teacher.get("identity_sha256")):
                    fail("missing_teacher_http_evidence")
                elif not messages:
                    fail("missing_teacher_http_evidence")
                else:
                    for index, record in enumerate(records):
                        try:
                            payload, response = record["payload"], record["response"]
                            assistant = copy.deepcopy(response["choices"][0]["message"])
                            assistant["role"] = "assistant"
                            if (record.get("status") != "completed" or
                                    record.get("policy_version") != trajectory["policy_version"] or
                                    record.get("prompt_version") != prompt_version or
                                    record.get("identity_sha256") != digest(identity) or
                                    record.get("payload_sha256") != digest(payload) or
                                    record.get("request_sha256") != digest({"identity": identity, "payload": payload}) or
                                    record.get("response_sha256") != digest(response) or
                                    payload.get("messages") != messages[:2 + index * 2] or
                                    payload.get("tools") != env.schemas() or
                                    OpenAIHTTPTeacher._action(response) != transitions[index]["action"] or
                                    assistant != messages[2 + index * 2]):
                                fail("teacher_http_evidence_mismatch", action_index=index)
                        except (KeyError, TypeError, ValueError, RuntimeError, IndexError):
                            fail("teacher_http_evidence_mismatch", action_index=index)
            actual = env.trajectory()
            for key in ("step_rewards", "verifier_events", "done", "terminal_validation"):
                if trajectory.get(key) != actual[key]:
                    fail("aggregate_mismatch", field=key)
            state_hash = env.snapshot()["sha256"]
            if trajectory["final_state_sha256"] != state_hash:
                fail("state_hash_mismatch")
            final = env.terminal
            if not env.done or final is None:
                fail("missing_terminal")
            elif final.get("budget_exhausted"):
                fail("budget_exhausted")
            elif final.get("terminal_reward") != 1.0 or not final.get("success"):
                fail("hard_constraint_failure")
            if final and not final.get("delivery_success"):
                fail("incomplete_delivery")
                for error in final.get("errors", []):
                    fail("delivery_" + error["code"])
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            fail("replay_execution_error", exception=type(exc).__name__)
        finally:
            env.close()
    collection = trajectory.get("collection", {})
    if collection.get("error"):
        fail("collection_failure")
    teacher = collection.get("teacher", {})
    engineering = teacher.get("engineering_only") is not False or teacher.get("kind") != "http_teacher"
    try:
        endpoint = urlsplit(teacher.get("identity", {}).get("config", {}).get("base_url", ""))
        if endpoint.scheme != "https" or endpoint.hostname in (None, "localhost", "127.0.0.1", "::1"):
            engineering = True
    except (TypeError, ValueError):
        engineering = True
    accepted = not failures
    eligible = accepted and not engineering and catalog.split == "train"
    return {"schema_version": 1, "accepted": accepted, "expert_eligible": eligible,
            "engineering_only": engineering, "task_id": task["task_id"], "split": catalog.split,
            "trajectory_sha256": trajectory_hash, "replay_state_sha256": state_hash,
            "terminal_success": bool(final and final.get("success")),
            "delivery_success": bool(final and final.get("delivery_success")),
            "failure_types": failures, "details": detail,
            "expert_exclusion": None if eligible else ("rejected" if not accepted else
                                 "engineering_only" if engineering else "non_training_split")}
