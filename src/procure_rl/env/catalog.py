"""Build engineering SQLite fixtures and expose immutable split-scoped facts.

build_catalog consumes a versioned product JSON and writes one native-compatible
database per split plus a content manifest. Catalog opens only one split read-only;
session delegates all user-facing queries to the pinned ECom tools on this file.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from ..runtime import sha256_file

SPLITS = ("train", "dev", "sealed_test", "official_test")


def digest(value: object) -> str:
    """Content hash of canonical JSON, used for task/snapshot identity."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def build_catalog(source: Path, output: Path) -> dict:
    """Create physically separate split databases; never overwrite artifacts."""
    data = json.loads(source.read_text(encoding="utf-8"))
    ids, evidence_ids, families = set(), set(), {}
    for p in data["products"]:
        if p["split"] not in SPLITS or p["product_id"] in ids:
            raise ValueError("Invalid split or duplicate product")
        ids.add(p["product_id"])
        if families.setdefault(p["family"], p["split"]) != p["split"]:
            raise ValueError("Product family crosses split boundary")
        for e in p["evidence"]:
            field, channel = e["field"], e["channel"]
            fact = p["price"] if field == "price" else p["specs"][field]
            if (e["product_id"] != p["product_id"] or digest(e["value"]) != digest(fact) or
                    channel not in ("details", "reviews") or
                    e["evidence_id"] != f'{p["product_id"]}:{channel}:{field}' or
                    e["evidence_id"] in evidence_ids or not e["text"]):
                raise ValueError("Evidence contradicts or does not identify its source fact")
            evidence_ids.add(e["evidence_id"])
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "revision": data["revision"],
                "source_sha256": sha256_file(source), "databases": {}}
    for split in SPLITS:
        path = output / (split + ".sqlite")
        conn = sqlite3.connect(path)
        try:
            conn.executescript('''
                CREATE TABLE products(product_id TEXT PRIMARY KEY,title TEXT,store TEXT,brand TEXT,data TEXT);
                CREATE VIRTUAL TABLE products_fts USING fts5(title,content='products');
                CREATE TABLE reviews(review_id INTEGER PRIMARY KEY,product_id TEXT,rating REAL,title TEXT,text TEXT,
                    helpful_vote INTEGER,verified_purchase INTEGER,timestamp INTEGER);
                CREATE VIRTUAL TABLE reviews_fts USING fts5(title,text,content='reviews',content_rowid='review_id');
                CREATE TABLE facts(product_id TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE evidence(evidence_id TEXT PRIMARY KEY, product_id TEXT, channel TEXT, data TEXT);
            ''')
            products = [p for p in data["products"] if p["split"] == split]
            for p in products:
                # Native details expose only details-channel facts. Review-only facts
                # remain gated behind a real native FTS review result.
                details = {e["field"]: e["value"] for e in p["evidence"] if e["channel"] == "details"}
                native = {"product_id": p["product_id"], "title": p["title"],
                          "price": p["price"], "store": p["family"], "brand": p["family"],
                          "main_category": "Office Electronics", "details": details,
                          "features": [], "description": [], "average_rating": 4.0, "rating_number": 1}
                conn.execute("INSERT INTO products VALUES(?,?,?,?,?)", (p["product_id"], p["title"],
                             p["family"], p["family"], json.dumps(native)))
                conn.execute("INSERT INTO facts VALUES(?,?)", (p["product_id"], json.dumps(p)))
                for e in p["evidence"]:
                    conn.execute("INSERT INTO evidence VALUES(?,?,?,?)", (e["evidence_id"], p["product_id"],
                                 e["channel"], json.dumps(e)))
                    if e["channel"] == "reviews":
                        conn.execute("INSERT INTO reviews(product_id,rating,title,text,helpful_vote,verified_purchase,timestamp) "
                                     "VALUES(?,4.0,?,?,0,1,0)", (p["product_id"], e["field"], e["text"]))
            conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
            conn.execute("INSERT INTO reviews_fts(reviews_fts) VALUES('rebuild')")
            conn.commit()
        finally:
            conn.close()
        manifest["databases"][split] = {"file": path.name, "sha256": sha256_file(path),
                                           "product_count": len(products)}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


class Catalog:
    """Private verifier facts and observation evidence, scoped to one split file."""

    def __init__(self, directory: Path, split: str):
        if split not in SPLITS:
            raise ValueError("Unknown split")
        manifest = json.loads((directory / "manifest.json").read_text())
        self.path = (directory / manifest["databases"][split]["file"]).resolve()
        if self.path.parent != directory.resolve():
            raise ValueError("Database escapes catalog directory")
        self.sha256 = sha256_file(self.path)
        if self.sha256 != manifest["databases"][split]["sha256"]:
            raise ValueError("Database hash mismatch")
        self.split, self.revision = split, manifest["revision"]

    def connect(self) -> sqlite3.Connection:
        """A fresh connection is thread-local by use; never permits writes."""
        conn = sqlite3.connect(self.path.as_uri() + "?mode=ro&immutable=1", uri=True)
        conn.execute("PRAGMA query_only=ON")
        return conn

    def product(self, product_id: str) -> dict | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT data FROM facts WHERE product_id=?", (product_id,)).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            conn.close()

    def evidence(self, product_id: str, channel: str) -> list[dict]:
        conn = self.connect()
        try:
            rows = conn.execute("SELECT data FROM evidence WHERE product_id=? AND channel=? ORDER BY evidence_id",
                                (product_id, channel)).fetchall()
            return [json.loads(r[0]) for r in rows]
        finally:
            conn.close()


def load_tasks(path: Path) -> tuple[str, dict[str, dict]]:
    """Load versioned private tasks, rejecting ambiguous or unsupported rubrics."""
    data = json.loads(path.read_text())
    tasks = {}
    for task in data["tasks"]:
        if task["task_id"] in tasks or task["split"] not in ("train", "dev"):
            raise ValueError("Duplicate task or test task used for engineering")
        if type(task["max_steps"]) is not int or task["max_steps"] not in range(1, 81):
            raise ValueError("Task budget must be 1..80")
        if type(task["max_clarifications"]) is not int or not 0 <= task["max_clarifications"] <= 10:
            raise ValueError("Clarification budget must be 0..10")
        constraint_ids = set()
        for c in task["constraints"]:
            if (c["id"] in constraint_ids or c["source"] not in ("query", "persona", "clarification") or
                    c["op"] not in ("lte", "gte", "eq", "contains") or not c["evidence_ids"]):
                raise ValueError("Duplicate/unsupported constraint or absent evidence")
            constraint_ids.add(c["id"])
        if not constraint_ids:
            raise ValueError("Empty constraints")
        slot_ids, covered = set(), set()
        hidden = {c["id"] for c in task["constraints"] if c["source"] == "clarification"}
        for slot in task["clarifications"]:
            if slot["question_id"] in slot_ids or not set(slot["constraint_ids"]) <= hidden:
                raise ValueError("Invalid clarification mapping")
            slot_ids.add(slot["question_id"])
            covered.update(slot["constraint_ids"])
        if covered != hidden:
            raise ValueError("Unreachable hidden constraint")
        tasks[task["task_id"]] = task
    return data["revision"], tasks
