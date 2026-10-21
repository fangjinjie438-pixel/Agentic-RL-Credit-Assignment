"""Collect visible-information-only tool episodes with durable teacher evidence.

The collector passes only reset/step observations and tool schemas to a Teacher.
ScriptedTeacher is an observation-driven engineering probe, never expert data.
OpenAIHTTPTeacher uses standard-library HTTP, explicit budgets and a durable
request journal; uncertain billed calls are never retried automatically.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
from typing import Protocol
import urllib.error
import urllib.parse
import urllib.request

from ..env.catalog import digest

PROMPT_VERSION = "procure-teacher-visible-v1"
SYSTEM_PROMPT = (
    "You are an office procurement agent. Discover user needs using the available tools, "
    "inspect actual product and review evidence, and recommend one product with checks "
    "citing observed evidence IDs for every requirement. Only observations are available; "
    "never invent facts or evidence. Return exactly one tool call per turn. "
    "Clarification questions must be at most 100 characters. Tool results contain the "
    "remaining action budget. Finish within it."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _new_request_cost(records: list[dict]) -> float | None:
    """Estimate only newly sent requests; local cache reuse does not bill again."""
    fresh = [r for r in records if not r.get("cache_hit")]
    if not fresh:
        return 0.0 if records else None
    costs = [r.get("cost_usd") for r in fresh]
    return sum(costs) if all(c is not None for c in costs) else None


class Teacher(Protocol):
    """A policy receives public dialogue/schema and returns one structured action."""

    def next_action(self, messages: list[dict], tools: list[dict]) -> dict: ...


class TeacherError(RuntimeError):
    """A sanitized, retained collection or HTTP boundary failure."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward a bearer credential to a redirected origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ScriptedTeacher:
    """Greedy engineering policy using only observed requirements and evidence.

    Search terms, clarification questions and review terms are public run config,
    not extracted from hidden tasks. This probe does not measure model quality.
    """

    def __init__(self, *, search_query: str = "dock", search_queries: list[str] | None = None,
                 clarification_questions: list[str] | None = None, review_query: str = "power"):
        self.search_query = search_query
        self.search_queries = list(search_queries if search_queries is not None else [search_query])
        if not self.search_queries or any(not isinstance(query, str) or not query for query in self.search_queries):
            raise ValueError("At least one nonempty public search query is required")
        self.questions = list(clarification_questions if clarification_questions is not None else
                              ["How many displays?", "How much power?"])
        self.review_query = review_query

    def metadata(self) -> dict:
        return {"kind": "scripted_engineering", "engineering_only": True,
                "model": None, "model_revision": None, "prompt_version": PROMPT_VERSION,
                "search_query": self.search_query, "search_queries": self.search_queries,
                "clarification_questions": self.questions,
                "review_query": self.review_query, "usage": None, "cost_usd": None}

    @staticmethod
    def _satisfies(value, requirement: dict) -> bool:
        expected, op = requirement["value"], requirement["op"]
        try:
            if op in ("lte", "gte"):
                if type(value) not in (int, float) or type(expected) not in (int, float):
                    return False
                return value <= expected if op == "lte" else value >= expected
            if op == "eq":
                return type(value) is type(expected) and value == expected
            return op == "contains" and expected in value
        except (TypeError, KeyError):
            return False

    def next_action(self, messages: list[dict], tools: list[dict]) -> dict:
        calls, observations = [], []
        for message in messages:
            if message["role"] in ("user", "tool"):
                observations.append(json.loads(message["content"]))
            for call in message.get("tool_calls", []):
                calls.append({"name": call["function"]["name"],
                              "arguments": json.loads(call["function"]["arguments"])})
        def action(name, **arguments):
            return {"name": name, "arguments": arguments}
        if not any(c["name"] == "get_user_profile" for c in calls):
            return action("get_user_profile")
        for question in self.questions:
            if not any(c["name"] == "ask_user" and c["arguments"].get("question") == question for c in calls):
                return action("ask_user", question=question)
        for query in self.search_queries:
            if not any(c["name"] == "search_products" and c["arguments"].get("query") == query for c in calls):
                return action("search_products", query=query)
        requirements, evidence, products = {}, {}, []
        for obs in observations:
            for requirement in obs.get("requirements", []):
                requirements[requirement["id"]] = requirement
            for product in obs.get("products", []):
                if product["product_id"] not in products:
                    products.append(product["product_id"])
            for item in obs.get("evidence", []):
                evidence[item["evidence_id"]] = item
        for product_id in products:
            for name, arguments in (("get_product_details", {"product_id": product_id}),
                                    ("get_review_content", {"product_id": product_id, "query": self.review_query})):
                if not any(c["name"] == name and c["arguments"] == arguments for c in calls):
                    return {"name": name, "arguments": arguments}
            checks = []
            for requirement in requirements.values():
                supporting = [e["evidence_id"] for e in evidence.values()
                              if e["product_id"] == product_id and e["field"] == requirement["field"]
                              and self._satisfies(e["value"], requirement)]
                if not supporting:
                    break
                checks.append({"constraint_id": requirement["id"], "evidence_ids": supporting})
            else:
                return action("recommend_product", product_id=product_id,
                              reasoning="Engineering probe checked the visible requirements against observed evidence.",
                              checks=checks)
        # A genuine failed engineering episode consumes the remaining budget;
        # there is no hidden-answer fallback or fabricated final recommendation.
        return action("search_products", query=self.search_queries[0])


class OpenAIHTTPTeacher:
    """Opt-in OpenAI-compatible teacher with journaled, bounded HTTP requests.

    Config requires base_url, model, max_requests, max_cost_usd and a conservative
    request_cost_cap_usd reservation. Credentials come only from env_var/key_file.
    Unknown provider usage/cost/revision remain null. A reservation is a configured
    ceiling, not evidence of the provider's price. No automatic retries are made.
    One process owns a cache directory at a time (exclusive request creation).
    """

    def __init__(self, config: dict, *, cache_directory: Path, policy_version: str,
                 allow_network: bool = False, cache_only: bool = False):
        self.config = copy.deepcopy(config)
        self.cache = Path(cache_directory)
        self.policy_version = policy_version
        self.allow_network, self.cache_only = allow_network, cache_only
        self.records: list[dict] = []
        self.last_assistant_message = None
        if any(re.search(r"(?i)^(api[_-]?key|authorization|headers|password|token|access[_-]?token|secret)$", k)
               for k in config):
            raise ValueError("Credentials must use env_var or key_file")
        parsed = urllib.parse.urlsplit(config.get("base_url", ""))
        if (parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or
                (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"))):
            raise ValueError("Teacher base_url must be HTTPS (HTTP allowed only for local boundary tests)")
        if not config.get("model") or not policy_version:
            raise ValueError("Teacher model and policy_version are required")
        if type(config.get("max_requests")) is not int or config["max_requests"] < 1:
            raise ValueError("An explicit positive request limit is required")
        for name in ("max_cost_usd", "request_cost_cap_usd"):
            if type(config.get(name)) not in (float, int) or not math.isfinite(config[name]) or config[name] <= 0:
                raise ValueError("An explicit positive cost limit/reservation is required")
        if config["request_cost_cap_usd"] > config["max_cost_usd"]:
            raise ValueError("One request reservation exceeds the total cost budget")
        if type(config.get("max_tokens", 1024)) is not int or not 1 <= config.get("max_tokens", 1024) <= 32768:
            raise ValueError("max_tokens must be 1..32768")
        self.cache.mkdir(parents=True, exist_ok=True)
        public_config = {k: v for k, v in config.items() if k not in ("env_var", "key_file")}
        self.identity = {"config": public_config, "policy_version": policy_version,
                         "prompt_version": PROMPT_VERSION}
        self.identity_sha256 = digest(self.identity)
        self.engineering_only = parsed.hostname in ("localhost", "127.0.0.1", "::1")

    def _secret(self) -> str:
        if self.config.get("env_var") and self.config.get("key_file"):
            raise TeacherError("Choose one credential source")
        key = os.environ.get(self.config.get("env_var", ""), "")
        if self.config.get("key_file"):
            try:
                key = Path(self.config["key_file"]).read_text(encoding="utf-8").strip()
            except OSError:
                raise TeacherError("Credential file unavailable") from None
        if not key or "\n" in key or "\r" in key:
            raise TeacherError("Teacher credentials are missing or invalid")
        return key

    @staticmethod
    def _redact(value, secret: str):
        if isinstance(value, dict):
            return {(k.replace(secret, "[REDACTED]") if secret else k):
                    ("[REDACTED]" if re.search(r"(?i)^(authorization|api[_-]?key|password|access[_-]?token|secret)$", k)
                        else OpenAIHTTPTeacher._redact(v, secret)) for k, v in value.items()}
        if isinstance(value, list):
            return [OpenAIHTTPTeacher._redact(v, secret) for v in value]
        return value.replace(secret, "[REDACTED]") if isinstance(value, str) and secret else value

    @staticmethod
    def _action(response: dict) -> dict:
        try:
            message = response["choices"][0]["message"]
            calls = message.get("tool_calls", [])
            if len(calls) != 1:
                raise ValueError("Exactly one tool call is required")
            function = calls[0]["function"]
            if not isinstance(calls[0].get("id"), str) or not calls[0]["id"]:
                raise ValueError("Tool call ID is required")
            arguments = json.loads(function["arguments"])
            if not isinstance(arguments, dict) or not isinstance(function["name"], str):
                raise ValueError("Malformed tool action")
            return {"name": function["name"], "arguments": arguments}
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError):
            raise TeacherError("Teacher response lacks exactly one valid tool call") from None

    def metadata(self) -> dict:
        costs = [r.get("cost_usd") for r in self.records]
        return {"kind": "http_teacher", "engineering_only": self.engineering_only, "model": self.config["model"],
                "model_revision": None, "expected_model_revision": self.config.get("expected_model_revision"),
                "selection_status": self.config.get("selection_status"), "prompt_version": PROMPT_VERSION,
                "identity": copy.deepcopy(self.identity), "identity_sha256": self.identity_sha256,
                "requests": copy.deepcopy(self.records),
                "usage": [r.get("usage") for r in self.records],
                "cost_usd": sum(costs) if costs and all(c is not None for c in costs) else None,
                "new_request_cost_estimate_usd": _new_request_cost(self.records),
                "new_api_calls": sum(bool(r.get("new_api_call")) for r in self.records),
                "billed_cost_usd": None,
                "cost_reservation_usd": sum(r.get("reserved_cost_usd", 0) for r in self.records
                                             if not r.get("cache_hit")),
                "cost_limit_usd": self.config["max_cost_usd"],
                "cost_accounting": "estimate_from_configured_prices_and_provider_usage; billed_amount_unknown; configured reservations bound admission"}

    def next_action(self, messages: list[dict], tools: list[dict]) -> dict:
        # Budget admission and request creation are serialized across cooperating
        # collectors. Process crashes release the lock while retaining pending
        # journal entries that prohibit an uncertain call from being resent.
        with (self.cache / ".request.lock").open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return self._next_action(messages, tools)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _next_action(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {"model": self.config["model"], "messages": copy.deepcopy(messages),
                   "tools": copy.deepcopy(tools), "tool_choice": "required",
                   "max_tokens": self.config.get("max_tokens", 1024), "temperature": self.config.get("temperature", 0)}
        if "thinking" in self.config:
            if self.config["thinking"] != {"type": "disabled"}:
                raise TeacherError("This collector requires nonthinking teacher tool calls")
            payload["thinking"] = {"type": "disabled"}
        request_hash = digest({"identity": self.identity, "payload": payload})
        path = self.cache / (request_hash + ".json")
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if (record.get("request_sha256") != request_hash or record.get("identity_sha256") != self.identity_sha256
                    or record.get("payload_sha256") != digest(payload)):
                raise TeacherError("Cache identity mismatch")
            if record.get("status") != "completed":
                raise TeacherError("A previous request is incomplete or billing-uncertain; no automatic retry")
            response = record.get("response")
            if record.get("response_sha256") != digest(response):
                raise TeacherError("Cache response checksum mismatch")
            action = self._action(response)
            self.last_assistant_message = copy.deepcopy(response["choices"][0]["message"])
            self.records.append(copy.deepcopy(record) | {"cache_hit": True, "new_api_call": False})
            return action
        if self.cache_only or not self.allow_network:
            raise TeacherError("No cached response; network teacher is disabled")
        key = self._secret()
        journal = [json.loads(p.read_text(encoding="utf-8")) for p in self.cache.glob("*.json")]
        own = [r for r in journal if r.get("identity_sha256") == self.identity_sha256]
        reserved = sum(max(r.get("reserved_cost_usd", 0), r.get("cost_usd") or 0) for r in own)
        cap = float(self.config["request_cost_cap_usd"])
        if len(own) >= self.config["max_requests"] or reserved + cap > self.config["max_cost_usd"] + 1e-12:
            raise TeacherError("Teacher request or cost-reservation budget exhausted")
        prices = self.config.get("prices_usd_per_million_tokens", {})
        if not prices and "input_per_million_usd" in self.config:
            prices = {"input": self.config.get("input_per_million_usd"),
                      "output": self.config.get("output_per_million_usd")}
        if all(type(prices.get(k)) in (float, int) and math.isfinite(prices[k]) and prices[k] >= 0
               for k in ("input", "output")):
            # UTF-8 payload byte count conservatively bounds text-token count
            # for byte-based compatible tokenizers, with protocol overhead slack.
            input_token_bound = len(json.dumps(payload, ensure_ascii=False).encode()) + 4096
            conservative_cost = (input_token_bound * prices["input"] +
                                 payload["max_tokens"] * prices["output"]) / 1_000_000
            if conservative_cost > cap:
                raise TeacherError("Conservative request token cost exceeds configured reservation")
        record = {"schema_version": 1, "request_sha256": request_hash, "identity_sha256": self.identity_sha256,
                  "payload_sha256": digest(payload), "payload": self._redact(payload, key),
                  "started_at": _now(), "finished_at": None, "status": "pending", "cache_hit": False,
                  "new_api_call": True, "model_requested": self.config["model"], "model_response": None,
                  "model_revision": None, "expected_model_revision": self.config.get("expected_model_revision"),
                  "prompt_version": PROMPT_VERSION,
                  "policy_version": self.policy_version, "usage": None, "cost_usd": None,
                  "billed_cost_usd": None,
                  "reserved_cost_usd": cap, "response": None, "response_sha256": None}
        # Exclusive creation survives a process crash and prevents duplicate sends
        # of this exact request. A pending record is intentionally never retried.
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, allow_nan=False)
                handle.write("\n")
        except FileExistsError:
            raise TeacherError("Concurrent request already owns this cache entry") from None
        endpoint = self.config["base_url"].rstrip("/") + "/chat/completions"
        request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        try:
            handlers = [_NoRedirect()]
            if self.engineering_only:
                # Loopback transport tests must never route their dummy bearer
                # credential through a machine-wide HTTP proxy.
                handlers.append(urllib.request.ProxyHandler({}))
            with urllib.request.build_opener(*handlers).open(
                    request, timeout=float(self.config.get("timeout_seconds", 60))) as result:
                raw = result.read(8 * 1024 * 1024 + 1)
                record["raw_response_text"] = self._redact(raw[:8 * 1024 * 1024].decode("utf-8", errors="replace"), key)
                if len(raw) > 8 * 1024 * 1024:
                    raise TeacherError("Teacher response exceeds size limit")
                response = json.loads(raw)
            safe_response = self._redact(response, key)
            record.update({"status": "completed", "finished_at": _now(), "response": safe_response,
                           "raw_response_text": self._redact(raw.decode("utf-8"), key),
                           "response_sha256": digest(safe_response), "model_response": safe_response.get("model"),
                           "usage": safe_response.get("usage"), "response_id": safe_response.get("id")})
            usage = record["usage"]
            if (isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                             for k in ("prompt_tokens", "completion_tokens")) and
                    all(type(prices.get(k)) in (float, int) and math.isfinite(prices[k]) and prices[k] >= 0
                        for k in ("input", "output"))):
                record["cost_usd"] = (usage["prompt_tokens"] * prices["input"] +
                                      usage["completion_tokens"] * prices["output"]) / 1_000_000
                record["cost_basis"] = "configured_prices_times_provider_usage"
                record["cost_exceeds_configured_request_reservation"] = record["cost_usd"] > cap
            _write(path, record)
            self.records.append(copy.deepcopy(record))
            action = self._action(safe_response)
            self.last_assistant_message = copy.deepcopy(safe_response["choices"][0]["message"])
            return action
        except Exception as exc:
            if record["status"] == "pending":
                if isinstance(exc, urllib.error.HTTPError):
                    record["http_status"] = exc.code
                    try:
                        record["raw_response_text"] = self._redact(
                            exc.read(8 * 1024 * 1024).decode("utf-8", errors="replace"), key)
                    except OSError:
                        record["response_read_failure"] = True
                record.update({"status": "billing_uncertain", "finished_at": _now(),
                               "failure_type": type(exc).__name__})
                _write(path, record)
                self.records.append(copy.deepcopy(record))
            raise TeacherError("Teacher request failed or response invalid; inspect sanitized journal; no automatic retry") from None


def collect_episode(env, teacher: Teacher, *, output: Path, seed: int = 0) -> dict:
    """Execute one bounded real environment episode; save failures as evidence.

    Test splits are rejected before collection. Audit state is used only after
    actions for durable replay, never passed to next_action or embedded in prompts.
    """
    if env.catalog.split not in ("train", "dev"):
        raise ValueError("Teacher collection is restricted to train/dev")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    initial = env.reset(seed=seed)
    tools = env.schemas()
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(initial, ensure_ascii=False, sort_keys=True)}]
    started_at, error = _now(), None
    record_start = len(getattr(teacher, "records", []))
    while True:
        try:
            action = teacher.next_action(copy.deepcopy(messages), copy.deepcopy(tools))
            result = env.step(action)
            # Native schema validation belongs to env.step. Serialize its actual
            # recorded action so malformed attempts remain reproducible.
            recorded = env.history[-1]["action"]
            if not isinstance(recorded, dict) or not isinstance(recorded.get("arguments"), dict):
                error = "non_structured_teacher_action"
                break
            assistant_message = copy.deepcopy(getattr(teacher, "last_assistant_message", None))
            call_id = "call_" + str(result.action_index)
            if assistant_message:
                call_id = assistant_message["tool_calls"][0]["id"]
                assistant_message["role"] = "assistant"
            else:
                assistant_message = {"role": "assistant", "content": None, "tool_calls": [{"id": call_id,
                             "type": "function", "function": {"name": recorded.get("name", "invalid_action"),
                             "arguments": json.dumps(recorded["arguments"], sort_keys=True)}}]}
            messages.append(assistant_message)
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": json.dumps(result.observation, ensure_ascii=False, sort_keys=True)})
            if result.done:
                break
        except Exception as exc:
            error = type(exc).__name__
            break
    metadata = teacher.metadata() if hasattr(teacher, "metadata") else {
        "kind": "unidentified_policy", "engineering_only": True, "model": None, "model_revision": None}
    if "requests" in metadata:
        metadata["requests"] = metadata["requests"][record_start:]
        costs = [r.get("cost_usd") for r in metadata["requests"]]
        metadata["usage"] = [r.get("usage") for r in metadata["requests"]]
        metadata["cost_usd"] = sum(costs) if costs and all(c is not None for c in costs) else None
        metadata["new_request_cost_estimate_usd"] = _new_request_cost(metadata["requests"])
        metadata["new_api_calls"] = sum(bool(r.get("new_api_call")) for r in metadata["requests"])
        metadata["cost_reservation_usd"] = sum(r.get("reserved_cost_usd", 0) for r in metadata["requests"]
                                               if not r.get("cache_hit"))
    trajectory = {**env.trajectory(), "initial_observation": initial,
                  "final_state_sha256": env.snapshot()["sha256"], "messages_sha256": digest(messages),
                  "public_messages": copy.deepcopy(messages),
                  "collection": {"started_at": started_at, "finished_at": _now(), "error": error,
                                 "prompt_version": PROMPT_VERSION, "teacher": metadata,
                                 "tools_sha256": digest(tools), "teacher_information_boundary": "observations_and_schemas_only"}}
    _write(output / "episode.json", trajectory)
    _write(output / "messages.json", messages)
    _write(output / "tools.json", tools)
    return trajectory
