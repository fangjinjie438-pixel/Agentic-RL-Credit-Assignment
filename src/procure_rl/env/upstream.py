"""Execute checksum-pinned EComAgentBench CPU tools on a read-only split database.

Inputs are a committed SQLite database and project-created persona/clarification
data; outputs are the original nine deterministic tools' dictionaries and schemas.
The project session calls this adapter and owns rewards, budgets, evidence and
terminal state. No official benchmark rubrics, LLM client or GPU code is imported.
"""

from __future__ import annotations

import builtins
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from types import ModuleType
from typing import Any


UPSTREAM_REVISION = "97eff345811fdf652a2135d38d874f2932e11702"
_SOURCE_HASHES = {
    "src/database/product_db.py": "65543222e56086c8918e21903bebdc22c4390cdbcd497a2197c2a5f7617ea026",
    "src/tools/base.py": "bb9d04966c6689a0ec75c472a0b026086675523b703588ff7df1b48fb0d50356",
    "src/tools/answer.py": "c554e8635c6652b475ebb9eda18c33be3eba0a830c213ca1973531472f52fa5c",
    "src/tools/ask_user.py": "a7a4917ee6386061751a1d505bd3a7d26ef1562ad47d581be85198f426a5de84",
    "src/tools/detail.py": "135b54dcb416cf383b0f122e3737fddb14d6a6055a3099a82932c491efdaa635",
    "src/tools/filter.py": "98894217649235b8080c9db11ed75696d1b487089e54cb44e4a4c70b6a89ecb6",
    "src/tools/get_user_profile.py": "80967e89f15285307b6c3a472b79671615f7271fa95cb3a67c3ac8b6f325266b",
    "src/tools/review_content.py": "246b3472e726a77fb8424c10f3211541c60531deb224ceecfc3cefe82ea91490",
    "src/tools/review_stats.py": "431bcee265dd7e657b4643dad00d9049211e6510c1ef0b71f03bc3d4f7d8ab97",
    "src/tools/search_products.py": "7c20d781a02f18f1dfd214ac60e02e235cdebf5d3625031e49b0185100115238",
    "src/tools/store.py": "490778d808ebd400073d3735dc91e145298b8b325f9672ecba0fa9d64af426ea",
}
TOOL_NAMES = (
    "search_products", "filter_by_attribute", "get_product_details",
    "get_review_content", "get_product_review_stats", "get_store_products",
    "get_user_profile", "ask_user", "recommend_product",
)


def default_source_root() -> Path:
    """Locate the vendored source; installation must retain its pinned directory."""
    return Path(__file__).resolve().parents[3] / "third_party" / "ecomagentbench" / UPSTREAM_REVISION


def _load_native(source_root: Path) -> tuple[type, dict[str, type]]:
    """Run original module bytes with a local import map, without a global src alias."""
    source_bytes = {}
    for relative, expected in _SOURCE_HASHES.items():
        data = (source_root / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"EComAgentBench source checksum mismatch: {relative}")
        source_bytes[relative] = data

    modules: dict[str, ModuleType] = {}

    def native_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "src.tools.base" and not level and fromlist:
            return modules["src/tools/base.py"]
        if name == "src" or name.startswith("src."):
            raise ImportError(f"Unapproved upstream import: {name}")
        return builtins.__import__(name, globals, locals, fromlist, level)

    # Do not import src/tools/__init__.py: it eagerly enables python_execute.
    for relative, data in source_bytes.items():
        module = ModuleType("_procure_rl_native_ecom." + relative.replace("/", "."))
        module.__file__ = str(source_root / relative)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": native_import}
        exec(compile(data, module.__file__, "exec"), module.__dict__)
        modules[relative] = module
    registry = modules["src/tools/base.py"].TOOL_REGISTRY
    if set(registry) != set(TOOL_NAMES):
        raise ValueError("Unexpected native tool registry")
    return modules["src/database/product_db.py"].ProductDB, registry


def _validate_arguments(schema: dict, params: dict) -> None:
    if not isinstance(params, dict):
        raise ValueError("Tool arguments must be an object")
    properties = schema["properties"]
    if set(params) - set(properties):
        raise ValueError("Unknown tool argument")
    if set(schema.get("required", [])) - set(params):
        raise ValueError("Missing required tool argument")
    for key, value in params.items():
        spec = properties[key]
        kind = spec["type"]
        if kind == "string" and not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"{key} must be an integer")
        if kind == "array":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"{key} must be an array of strings")
            if len(value) > spec.get("maxItems", len(value)):
                raise ValueError(f"{key} exceeds maxItems")


class NativeEComTools:
    """One isolated native tool set, with copy-safe clarification state.

    ``db_path`` must refer to a fully committed database with no pending WAL or
    rollback journal. Immutable/read-only SQLite mode prevents source or sidecar
    writes. The original ProductDB connection factory is replaced by this narrow
    project-owned subclass; all product queries and tool methods are upstream.
    """

    def __init__(
        self,
        db_path: Path | str,
        persona: dict | None = None,
        clarification_script: dict | None = None,
        *,
        source_root: Path | str | None = None,
    ) -> None:
        path = Path(db_path).resolve(strict=True)
        if not path.is_file():
            raise ValueError("Native database must be a regular file")
        for suffix in ("-wal", "-journal"):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists() and sidecar.stat().st_size:
                raise ValueError("Commit and checkpoint the database before read-only native access")
        native_db, registry = _load_native(Path(source_root) if source_root else default_source_root())
        self._lock = threading.RLock()
        self._closed = False
        self.db_path = path
        self._configuration_sha256 = hashlib.sha256(json.dumps({
            "db_path": str(path), "persona": persona,
            "clarification_script": clarification_script,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

        class ReadOnlyProductDB(native_db):
            def __init__(self):
                self._connections = []
                self._connection_lock = threading.Lock()
                super().__init__(str(path))

            def _get_conn(self):
                conn = getattr(self._local, "conn", None)
                if conn is None:
                    conn = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True,
                                           check_same_thread=False)
                    conn.execute("PRAGMA query_only=ON")
                    self._local.conn = conn
                    with self._connection_lock:
                        self._connections.append(conn)
                return conn

            def close(self):
                with self._connection_lock:
                    for conn in self._connections:
                        conn.close()
                    self._connections.clear()

        self.db = ReadOnlyProductDB()
        self._tools = {}
        for name in TOOL_NAMES:
            kwargs = {}
            if name == "get_user_profile":
                kwargs["persona"] = deepcopy(persona)
            elif name == "ask_user":
                kwargs["clarification_script"] = deepcopy(clarification_script)
            self._tools[name] = registry[name](self.db, **kwargs)
        self._initial_slots = deepcopy(self._tools["ask_user"]._slots)

    def schemas(self) -> list[dict]:
        """Return fresh copies of the original nine OpenAI-format tool schemas."""
        return deepcopy([self._tools[name].openai_schema for name in TOOL_NAMES])

    def call(self, name: str, arguments: dict) -> dict:
        """Execute a real native tool; malformed calls raise ValueError."""
        with self._lock:
            if self._closed:
                raise ValueError("Native tool set is closed")
            if name not in self._tools:
                raise ValueError(f"Unsupported native tool: {name}")
            tool = self._tools[name]
            _validate_arguments(tool.parameters, arguments)
            return deepcopy(tool.call(deepcopy(arguments)))

    def snapshot(self) -> dict[str, Any]:
        """Capture native mutable state; project sessions also snapshot budgets/events."""
        with self._lock:
            ask = self._tools["ask_user"]
            return {
                "upstream_revision": UPSTREAM_REVISION,
                "configuration_sha256": self._configuration_sha256,
                "clarification": {
                    "turn_count": ask._turn_count,
                    "slots": [{"slot_id": slot.get("slot_id"),
                               "revealed": bool(slot.get("revealed", False))}
                              for slot in ask._slots],
                },
            }

    def restore(self, state: dict) -> None:
        """Restore counts and revelation flags into the same configured tool set."""
        with self._lock:
            if not isinstance(state, dict) or set(state) != {
                "upstream_revision", "configuration_sha256", "clarification"
            }:
                raise ValueError("Malformed native tool state")
            if state["upstream_revision"] != UPSTREAM_REVISION:
                raise ValueError("Native snapshot revision mismatch")
            if state["configuration_sha256"] != self._configuration_sha256:
                raise ValueError("Native snapshot configuration mismatch")
            clarification = state["clarification"]
            if not isinstance(clarification, dict) or set(clarification) != {"turn_count", "slots"}:
                raise ValueError("Malformed native clarification state")
            count, slots = clarification["turn_count"], clarification["slots"]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("Invalid clarification turn count")
            if not isinstance(slots, list) or len(slots) != len(self._initial_slots):
                raise ValueError("Invalid clarification slots")
            for slot, initial in zip(slots, self._initial_slots):
                if (not isinstance(slot, dict) or set(slot) != {"slot_id", "revealed"}
                        or slot["slot_id"] != initial.get("slot_id")
                        or not isinstance(slot["revealed"], bool)):
                    raise ValueError("Invalid clarification revelation flags")
            ask = self._tools["ask_user"]
            ask._turn_count = count
            ask._slots = deepcopy(self._initial_slots)
            for slot, saved in zip(ask._slots, slots):
                slot["revealed"] = saved["revealed"]

    def close(self) -> None:
        """Release this tool set's read-only connections."""
        with self._lock:
            self.db.close()
            self._closed = True

    def __enter__(self) -> NativeEComTools:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
