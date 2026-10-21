"""Strict JSON action protocol shared by sessions and future rollout adapters.

Input is {name, arguments} or its JSON string; output is validated JSON data.
Tool schemas come from the pinned native tools, extended with final evidence checks.
"""

from __future__ import annotations

import json
import math
from typing import Any


class ActionError(ValueError):
    """An action cannot be executed; sessions count and record the attempt."""


def _unique(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ActionError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate(value: Any, schema: dict, path: str) -> None:
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": type(value) is int,
             "number": type(value) in (float, int), "boolean": type(value) is bool}
    if kind in valid and not valid[kind]:
        raise ActionError(f"{path} must be {kind}")
    if kind == "integer" and not -(2**31) <= value < 2**31:
        raise ActionError(f"{path} integer outside supported tool range")
    if isinstance(value, (int, float)) and (type(value) is not bool):
        if not math.isfinite(value):
            raise ActionError(f"{path} must be finite")
        if value < schema.get("minimum", -float("inf")):
            raise ActionError(f"{path} below minimum")
    if isinstance(value, str) and len(value) > schema.get("maxLength", 4096):
        raise ActionError(f"{path} string too long")
    if kind == "object":
        properties = schema.get("properties", {})
        if set(value) - set(properties):
            raise ActionError(f"{path} has unknown fields: {sorted(set(value) - set(properties))}")
        if set(schema.get("required", [])) - set(value):
            raise ActionError(f"{path} missing required fields")
        for key, item in value.items():
            _validate(item, properties[key], f"{path}.{key}")
    elif kind == "array":
        if len(value) > schema.get("maxItems", 100):
            raise ActionError(f"{path} array too long")
        for item in value:
            _validate(item, schema.get("items", {}), path + "[]")


def parse_action(raw: dict | str, schemas: list[dict]) -> dict:
    """Validate exact tool names/arguments without coercion or code execution."""
    try:
        if isinstance(raw, str):
            if len(raw) > 32768:
                raise ActionError("Action exceeds 32768 characters")
            action = json.loads(raw, object_pairs_hook=_unique,
                                parse_constant=lambda x: (_ for _ in ()).throw(ActionError(x)))
        else:
            action = json.loads(json.dumps(raw, allow_nan=False))
        if not isinstance(action, dict) or set(action) != {"name", "arguments"}:
            raise ActionError("Action must contain exactly name and arguments")
        if not isinstance(action["name"], str):
            raise ActionError("Tool name must be a string")
        by_name = {s["function"]["name"]: s["function"]["parameters"] for s in schemas}
        if action["name"] not in by_name:
            raise ActionError("Unknown or disabled tool: " + action["name"])
        _validate(action["arguments"], by_name[action["name"]], "arguments")
        return action
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        if isinstance(exc, ActionError):
            raise
        raise ActionError(str(exc)) from exc
