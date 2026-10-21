"""Load and validate S0 JSON configuration for the CLI; no training or GPU work is run.

Input is a candidate configuration path; output is a checked dictionary. This is
a project planning schema, not a verl/Hydra training configuration or lock file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXPECTED_STACK = {
    "python": "3.11",
    "verl": "0.6.1",
    "torch": "2.7.1+cu126",
    "vllm": "0.10.0+cu126",
    "transformers": "4.53.2",
}


def load_config(path: str | Path) -> dict[str, Any]:
    """Return validated candidate settings; raise ValueError on protocol drift."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("Expected schema_version=1 JSON object")
    if config.get("stage") != "S0" or config.get("status") != "candidate_unverified":
        raise ValueError("S0 settings must remain candidate_unverified")
    if config.get("stack") != EXPECTED_STACK:
        raise ValueError("Candidate stack differs from PLAN; do not silently upgrade")
    models = config.get("models", {})
    if models.get("smoke") != "Qwen/Qwen3-0.6B":
        raise ValueError("Smoke model must be Qwen3-0.6B")
    if models.get("main") != "Qwen/Qwen3-4B-Instruct-2507":
        raise ValueError("Main model must remain Qwen3-4B-Instruct-2507")
    if models.get("extension") != "Qwen/Qwen3-8B" or models.get("extension_gate") != "dev_diagnostics":
        raise ValueError("8B requires development-set diagnostics")
    resources = config.get("resources", {})
    if resources.get("gpu_compute_enabled") is not False:
        raise ValueError("S0 tooling must not enable GPU compute")
    if resources.get("assigned_gpu_uuids") != []:
        raise ValueError("Record future GPU allocation in a new run; S0 is read-only")
    training = config.get("planned_training", {})
    fixed = {
        "prompt_batch": 6, "rollouts_per_prompt": 4,
        "tensor_parallel": 1, "sequence_parallel": 1,
        "lora_rank": 32, "lora_alpha": 64,
        "microbatch": 1, "initial_rollout_concurrency_per_gpu": 1,
        "smoke_context_tokens": 4096, "main_context_tokens": 12288,
    }
    if training != fixed:
        raise ValueError("Planned training defaults differ from the current S0 schema")
    return config

