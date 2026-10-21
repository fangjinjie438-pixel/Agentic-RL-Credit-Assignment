"""Exercise real pinned upstream CPU tools on independent synthetic SQLite data.

The fixture contains fictional products, reviews and clarification responses;
there are no official evaluation-task fields, model downloads or API calls.
NativeEComTools is used directly to test SQL, FTS, read-only and replay behavior.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from procure_rl.env.upstream import NativeEComTools, UPSTREAM_REVISION


class NativeToolsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "synthetic.db"
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE products(product_id TEXT PRIMARY KEY, title TEXT,
                                  store TEXT, brand TEXT, data TEXT);
            CREATE VIRTUAL TABLE products_fts USING fts5(title, content='products');
            CREATE TABLE reviews(review_id INTEGER PRIMARY KEY,product_id TEXT,
                rating REAL,title TEXT,text TEXT,helpful_vote INTEGER,
                verified_purchase INTEGER,timestamp INTEGER);
            CREATE VIRTUAL TABLE reviews_fts USING fts5(title,text,content='reviews',
                                                       content_rowid='review_id');
        """)
        for pid, brand, power in (("fiction-a", "FictionAlpha", "100 W"),
                                  ("fiction-b", "FictionBeta", "45 W")):
            product = {
                "product_id": pid, "title": f"{brand} Travel Dock",
                "store": "Fiction Store", "price": 90 if power == "100 W" else 55,
                "details": {"Brand": brand, "Power": power}, "features": ["Two displays"],
                "average_rating": 4.2, "rating_number": 19,
            }
            conn.execute("INSERT INTO products VALUES (?,?,?,?,?)",
                         (pid, product["title"], product["store"], brand, json.dumps(product)))
        conn.execute("INSERT INTO reviews VALUES (1,?,?,?,?,?,?,?)",
                     ("fiction-a", 5, "Fictional test", "Stable dual display on travel", 3, 1, 0))
        conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
        conn.execute("INSERT INTO reviews_fts(reviews_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()
        self.script = {
            "clarification_slots": [{"slot_id": "screens", "trigger_keywords": ["display"],
                                     "user_response": "I need two displays."}],
            "default_response": "Nothing else.", "max_clarification_turns": 2,
        }

    def native(self, **kwargs):
        tools = NativeEComTools(self.path, persona={"laptop": "Fiction laptop"},
                               clarification_script=self.script, **kwargs)
        self.addCleanup(tools.close)
        return tools

    def test_real_tools_search_filter_details_reviews_and_recommendation(self):
        native = self.native()
        self.assertEqual(native.call("search_products", {"query": "Travel Dock"})["total_found"], 2)
        self.assertEqual(native.call("search_products", {"query": "100"})["products"], [])
        result = native.call("filter_by_attribute", {
            "product_ids": ["fiction-a", "fiction-b"],
            "attribute_name": "power", "attribute_value": "100",
        })
        self.assertEqual(result["product_ids"], ["fiction-a"])
        self.assertEqual(native.call("get_product_details", {"product_id": "fiction-a"})
                         ["product"]["details"]["Power"], "100 W")
        self.assertEqual(native.call("get_review_content", {
            "query": "dual display", "product_id": "fiction-a"})["reviews"][0]["rating"], 5)
        self.assertEqual(native.call("get_product_review_stats", {
            "product_ids": ["fiction-a"]})["products"][0]["rating_number"], 19)
        self.assertEqual(native.call("get_store_products", {
            "store_name": "Fiction Store"})["total_count"], 2)
        self.assertEqual(native.call("recommend_product", {
            "product_id": "fiction-a", "reasoning": "Checked details"})
            ["recommended_product"]["product_id"], "fiction-a")
        self.assertIsNone(native.call("recommend_product", {
            "product_id": "missing", "reasoning": "Invalid ID"})["recommended_product"])
        self.assertIn("error", native.call("get_product_details", {"product_id": "missing"}))

    def test_read_only_source_no_sidecars_and_schema_limits(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        native = self.native()
        with self.assertRaises(sqlite3.OperationalError):
            native.db._get_conn().execute("DELETE FROM products")
        self.assertEqual(len(native.schemas()), 9)
        self.assertNotIn("python_execute", [s["function"]["name"] for s in native.schemas()])
        for name, args in (("python_execute", {"code": "print(1)"}),
                           ("get_product_details", {}),
                           ("search_products", {"query": "Dock", "page": True}),
                           ("get_user_profile", {"extra": "field"}),
                           ("get_product_review_stats", {"product_ids": ["fiction-a"] * 11})):
            with self.subTest(name=name), self.assertRaises(ValueError):
                native.call(name, args)
        native.close()
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [self.path.name])

    def test_clarification_replay_and_parallel_session_isolation(self):
        left, right = self.native(), self.native()
        state = left.snapshot()
        self.assertEqual(state["upstream_revision"], UPSTREAM_REVISION)
        arguments = {"question": "How many displays?"}
        first = left.call("ask_user", arguments)
        self.assertEqual(first["user_response"], "I need two displays.")
        self.assertEqual(right.snapshot(), state)
        self.assertEqual(left.call("ask_user", arguments)["user_response"], "Nothing else.")
        left.restore(state)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda t: t.call("ask_user", arguments), (left, right)))
        self.assertEqual(results, [first, first])
        left.restore(state)
        profile = left.call("get_user_profile", {})
        profile["profile"]["laptop"] = "changed"
        self.assertEqual(left.call("get_user_profile", {})["profile"]["laptop"], "Fiction laptop")
        self.assertNotIn("revealed", self.script["clarification_slots"][0])
        corrupt = deepcopy(state)
        corrupt["upstream_revision"] = "different"
        with self.assertRaises(ValueError):
            left.restore(corrupt)

    def test_native_long_question_consumes_turn_and_budget_exhausts(self):
        native = self.native()
        long_reply = native.call("ask_user", {"question": "x" * 101})
        self.assertEqual(long_reply["turns_remaining"], 1)
        self.assertIn("100", long_reply["user_response"])
        native.call("ask_user", {"question": "display"})
        exhausted = native.call("ask_user", {"question": "display"})
        self.assertEqual(exhausted["turns_remaining"], 0)
        self.assertIn("too much", exhausted["user_response"])

    def test_source_modification_and_pending_wal_are_rejected(self):
        source = Path(self.directory.name) / "source"
        (source / "src/database").mkdir(parents=True)
        (source / "src/database/product_db.py").write_text("changed upstream")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.native(source_root=source)
        Path(str(self.path) + "-wal").write_bytes(b"uncommitted")
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            self.native()


if __name__ == "__main__":
    unittest.main()
