"""Regression tests for the ten-slot physical medicine catalog."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from flask import Flask

from mendo_core.medicine_catalog import (
    CATALOG_BRANDS,
    MEDICINE_CATALOG,
    MEDICINE_CATALOG_VERSION,
    NUTRABLISS_PRODUCT,
    inventory_catalog_records,
)
from mendo_core.prediction_pipeline import predict_symptoms
from mendo_core.step4_recommend import (
    DATASET_DEFAULT,
    load_mendo_dataset,
    recommend_from_dataset,
)
from pos import db as pos_db
from pos.db import _sync_inventory_catalog


EXPECTED_CATALOG = (
    "Kremil-S",
    "Bioflu",
    "Biogesic",
    "Cetirizine",
    "Solmux",
    "Sinecod",
    "Symdex",
    "Buscopan",
    "Loperamide",
)


class RuntimeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_mendo_dataset(DATASET_DEFAULT)

    def test_exact_ten_slot_catalog_and_formulations(self):
        self.assertEqual(CATALOG_BRANDS, EXPECTED_CATALOG)
        self.assertEqual(tuple(row.brand for row in self.rows), EXPECTED_CATALOG)
        self.assertEqual([item.slot for item in MEDICINE_CATALOG], list(range(1, 10)))
        self.assertEqual(
            {row.brand: row.dosage_form for row in self.rows},
            {
                "Kremil-S": "Chewable Tablet",
                "Bioflu": "Tablet",
                "Biogesic": "Tablet",
                "Cetirizine": "Tablet",
                "Solmux": "Capsule",
                "Sinecod": "Tablet",
                "Symdex": "Tablet",
                "Buscopan": "Tablet",
                "Loperamide": "Capsule",
            },
        )
        self.assertEqual(
            {row.brand: row.min_age for row in self.rows},
            {
                "Kremil-S": "12",
                "Bioflu": "12",
                "Biogesic": "12",
                "Cetirizine": "6",
                "Solmux": "12",
                "Sinecod": "13",
                "Symdex": "6",
                "Buscopan": "6",
                "Loperamide": "12",
            },
        )

    def test_recommendations_never_leave_physical_catalog(self):
        scenarios = (
            (["FEVER"], None),
            (["HEADACHE"], None),
            (["COUGH_DRY"], None),
            (["COUGH_PRODUCTIVE"], None),
            (["ALLERGIC_RHINITIS"], None),
            (["RASHES"], "RASHES_BREATHING_NO"),
            (["DIARRHEA"], "DIARRHEA_NON_INFECTIOUS"),
            (["NASAL_CONGESTION"], "SIPON_VIRAL_COLD"),
        )
        allowed = set(EXPECTED_CATALOG)
        for symptoms, context in scenarios:
            with self.subTest(symptoms=symptoms, context=context):
                result = recommend_from_dataset(
                    symptoms,
                    self.rows,
                    user_input="catalog regression",
                    context_override=context,
                )
                brands = {
                    row["brand"] for row in result.get("recommendations", [])
                }
                self.assertLessEqual(brands, allowed)

    def test_catalog_specific_routing_and_safety(self):
        fever = recommend_from_dataset(["FEVER"], self.rows, user_input="fever")
        self.assertEqual(
            [row["brand"] for row in fever["recommendations"]],
            ["Biogesic"],
        )
        self.assertNotIn("Bioflu", [row["brand"] for row in fever["recommendations"]])

        dry = recommend_from_dataset(["COUGH_DRY"], self.rows, user_input="dry cough")
        productive = recommend_from_dataset(
            ["COUGH_PRODUCTIVE"], self.rows, user_input="cough with phlegm"
        )
        self.assertEqual([row["brand"] for row in dry["recommendations"]], ["Sinecod"])
        self.assertEqual(
            [row["brand"] for row in productive["recommendations"]], ["Solmux"]
        )

        allergy = recommend_from_dataset(
            ["NASAL_CONGESTION"],
            self.rows,
            user_input="allergy",
            context_override="SIPON_ALLERGY",
        )
        self.assertEqual(
            [row["brand"] for row in allergy["recommendations"]], ["Cetirizine"]
        )

        infectious = recommend_from_dataset(
            ["DIARRHEA"],
            self.rows,
            user_input="food poisoning",
            context_override="DIARRHEA_FOOD_POISONING",
        )
        self.assertEqual(
            [row["brand"] for row in infectious["recommendations"]], []
        )
        warning = " ".join(infectious["safety_warnings"]).lower()
        self.assertIn("only an adjunct", warning)
        self.assertIn("oral rehydration", warning)

    def test_prediction_trace_versions_the_catalog(self):
        with patch("mendo_core.step3_hybrid._get_semantic_extractor", side_effect=RuntimeError("semantic not needed for catalog trace test")):
            report = predict_symptoms("masakit ulo ko")
        self.assertEqual(
            report["engine"]["medicine_catalog_version"],
            MEDICINE_CATALOG_VERSION,
        )


class InventoryCatalogMigrationTests(unittest.TestCase):
    def test_generic_probiotic_is_visible_in_inventory_without_legacy_products(self):
        from pos.routes_admin import _inventory_listings
        items = [
            {"brand": "Biogesic", "hardware_slot": 3},
            {"brand": NUTRABLISS_PRODUCT["brand"], "hardware_slot": None},
            {"brand": "Legacy Product", "hardware_slot": None},
        ]
        with patch("pos.routes_admin.list_inventory", return_value=items):
            self.assertEqual(_inventory_listings(), items[:2])

    def test_first_run_creates_only_the_ten_hardware_slots(self):
        original_path = pos_db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            pos_db.DB_PATH = str(Path(tmp) / "fresh.sqlite")
            app = Flask(__name__)
            try:
                with app.app_context():
                    try:
                        pos_db.init_db()
                        db = pos_db.get_db()
                        rows = db.execute(
                            """
                            SELECT hardware_slot,brand,is_active
                            FROM inventory WHERE hardware_slot IS NOT NULL ORDER BY hardware_slot
                            """
                        ).fetchall()
                        self.assertEqual(len(rows), 10)
                        self.assertEqual(
                            [row["brand"] for row in rows], [*EXPECTED_CATALOG, NUTRABLISS_PRODUCT["brand"]]
                        )
                        self.assertEqual(
                            [row["hardware_slot"] for row in rows],
                            list(range(1, 11)),
                        )
                        self.assertTrue(all(row["is_active"] for row in rows))
                        pending = db.execute(
                            "SELECT is_active,hardware_slot,stock_quantity,unit_price FROM inventory WHERE brand=?",
                            (NUTRABLISS_PRODUCT["brand"],),
                        ).fetchone()
                        self.assertEqual(tuple(pending), (1, 10, 0, 35.0))
                        self.assertEqual(
                            db.execute("PRAGMA integrity_check").fetchone()[0],
                            "ok",
                        )
                    finally:
                        pos_db.close_db()
            finally:
                pos_db.DB_PATH = original_path

    def test_aliases_migrate_without_deleting_history(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT UNIQUE NOT NULL,
                generic_name TEXT,
                category TEXT,
                dosage_form TEXT,
                unit_price REAL NOT NULL DEFAULT 0,
                stock_quantity INTEGER NOT NULL DEFAULT 0,
                min_stock_level INTEGER DEFAULT 5,
                is_active INTEGER DEFAULT 1,
                hardware_slot INTEGER,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE transaction_items (inventory_id INTEGER);
            CREATE TABLE stock_logs (inventory_id INTEGER);
            INSERT INTO inventory
                (id,brand,dosage_form,unit_price,stock_quantity,is_active)
            VALUES
                (2,'Neozep / Neozep Z+','Tablet',9.5,49,1),
                (3,'Neozep','Syrup',10,50,1),
                (7,'Tuseran Forte','Tablet',10,46,1),
                (8,'Decolgen','Tablet',7,50,1),
                (9,'Advil','Tablet',8,30,1),
                (10,'Erceflora','Oral Suspension',28,20,1),
                (11,'Lactobacillus acidophilus (pending verification)','Unverified',0,0,0);
            INSERT INTO transaction_items VALUES (2);
            INSERT INTO stock_logs VALUES (2);
            """
        )
        source = json.loads(Path(DATASET_DEFAULT).read_text(encoding="utf-8"))
        _sync_inventory_catalog(
            conn,
            inventory_catalog_records(source["Sheet1"]),
        )

        active = conn.execute(
            """
            SELECT hardware_slot,brand,dosage_form
            FROM inventory WHERE hardware_slot IS NOT NULL
            ORDER BY hardware_slot
            """
        ).fetchall()
        self.assertEqual([row["brand"] for row in active], [*EXPECTED_CATALOG, NUTRABLISS_PRODUCT["brand"]])
        self.assertEqual([row["hardware_slot"] for row in active], list(range(1, 11)))
        self.assertEqual(
            conn.execute("SELECT brand FROM inventory WHERE id=2").fetchone()["brand"],
            "Neozep / Neozep Z+",
        )
        self.assertEqual(
            conn.execute("SELECT inventory_id FROM transaction_items").fetchone()[0],
            2,
        )
        self.assertEqual(
            conn.execute("SELECT inventory_id FROM stock_logs").fetchone()[0],
            2,
        )
        retired = conn.execute(
            "SELECT is_active,hardware_slot FROM inventory WHERE id=8"
        ).fetchone()
        self.assertEqual((retired["is_active"], retired["hardware_slot"]), (0, None))
        for inventory_id in (2, 3, 7, 9, 10):
            retired = conn.execute(
                "SELECT is_active,hardware_slot FROM inventory WHERE id=?", (inventory_id,)
            ).fetchone()
            self.assertEqual(tuple(retired), (0, None))
        for brand in ("Kremil-S", "Sinecod", "Buscopan"):
            stock = conn.execute("SELECT stock_quantity FROM inventory WHERE brand=?", (brand,)).fetchone()[0]
            self.assertEqual(stock, 0, "Replacement must not inherit a different drug's stock")
        probiotic = conn.execute(
            "SELECT id,brand,is_active,hardware_slot FROM inventory WHERE id=11"
        ).fetchone()
        self.assertEqual(tuple(probiotic), (11, "Lactobacillus acidophilus (pending verification)", 0, None))
        named = conn.execute("SELECT id,hardware_slot,is_active,stock_quantity FROM inventory WHERE brand=?", (NUTRABLISS_PRODUCT["brand"],)).fetchone()
        self.assertNotEqual(named["id"], 11, "A generic placeholder must not be renamed into a different verified product")
        self.assertEqual((named["hardware_slot"], named["is_active"], named["stock_quantity"]), (10, 1, 0))
        _sync_inventory_catalog(conn, inventory_catalog_records(source["Sheet1"]))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM inventory WHERE hardware_slot IS NOT NULL").fetchone()[0], 10)
        conn.close()

    def test_transactions_reject_items_outside_the_hardware_catalog(self):
        original_path = pos_db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            pos_db.DB_PATH = str(Path(tmp) / "transaction.sqlite")
            app = Flask(__name__)
            try:
                with app.app_context():
                    try:
                        pos_db.init_db()
                        db = pos_db.get_db()
                        cursor = db.execute(
                            """
                            INSERT INTO inventory
                                (brand,unit_price,stock_quantity,is_active,hardware_slot)
                            VALUES ('Legacy Product',10,1,1,NULL)
                            """
                        )
                        db.commit()
                        with self.assertRaisesRegex(ValueError, "hardware catalog"):
                            pos_db.create_transaction(
                                [{"inventory_id": cursor.lastrowid, "quantity": 1}]
                            )
                    finally:
                        pos_db.close_db()
            finally:
                pos_db.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
