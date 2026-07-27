"""Regression tests for the ten-slot physical medicine catalog."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from mendo_core.medicine_catalog import (
    CATALOG_BRANDS,
    MEDICINE_CATALOG,
    MEDICINE_CATALOG_VERSION,
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
    "Advil",
    "Bioflu",
    "Biogesic",
    "Cetirizine",
    "Solmux",
    "Tuseran",
    "Symdex",
    "Neozep",
    "Loperamide",
    "Erceflora",
)


class RuntimeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_mendo_dataset(DATASET_DEFAULT)

    def test_exact_ten_slot_catalog_and_formulations(self):
        self.assertEqual(CATALOG_BRANDS, EXPECTED_CATALOG)
        self.assertEqual(tuple(row.brand for row in self.rows), EXPECTED_CATALOG)
        self.assertEqual([item.slot for item in MEDICINE_CATALOG], list(range(1, 11)))
        self.assertEqual(
            {row.brand: row.dosage_form for row in self.rows},
            {
                "Advil": "Tablet",
                "Bioflu": "Tablet",
                "Biogesic": "Tablet",
                "Cetirizine": "Tablet",
                "Solmux": "Capsule",
                "Tuseran": "Tablet",
                "Symdex": "Tablet",
                "Neozep": "Tablet",
                "Loperamide": "Tablet",
                "Erceflora": "Oral Suspension",
            },
        )
        self.assertEqual(
            {row.brand: row.min_age for row in self.rows},
            {
                "Advil": "12",
                "Bioflu": "12",
                "Biogesic": "12",
                "Cetirizine": "6",
                "Solmux": "12",
                "Tuseran": "12",
                "Symdex": "6",
                "Neozep": "6",
                "Loperamide": "6",
                "Erceflora": "All ages",
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
            ["Biogesic", "Advil"],
        )
        self.assertNotIn("Bioflu", [row["brand"] for row in fever["recommendations"]])

        dry = recommend_from_dataset(["COUGH_DRY"], self.rows, user_input="dry cough")
        productive = recommend_from_dataset(
            ["COUGH_PRODUCTIVE"], self.rows, user_input="cough with phlegm"
        )
        self.assertEqual([row["brand"] for row in dry["recommendations"]], ["Tuseran"])
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
            [row["brand"] for row in infectious["recommendations"]], ["Erceflora"]
        )
        warning = " ".join(infectious["safety_warnings"]).lower()
        self.assertIn("only an adjunct", warning)
        self.assertIn("oral rehydration", warning)

    def test_prediction_trace_versions_the_catalog(self):
        report = predict_symptoms("masakit ulo ko")
        self.assertEqual(
            report["engine"]["medicine_catalog_version"],
            MEDICINE_CATALOG_VERSION,
        )


class InventoryCatalogMigrationTests(unittest.TestCase):
    def test_first_run_creates_only_the_ten_hardware_slots(self):
        original_path = pos_db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            pos_db.DB_PATH = str(Path(tmp) / "fresh.sqlite")
            app = Flask(__name__)
            try:
                with app.app_context():
                    pos_db.init_db()
                    db = pos_db.get_db()
                    rows = db.execute(
                        """
                        SELECT hardware_slot,brand,is_active
                        FROM inventory ORDER BY hardware_slot
                        """
                    ).fetchall()
                    self.assertEqual(len(rows), 10)
                    self.assertEqual([row["brand"] for row in rows], list(EXPECTED_CATALOG))
                    self.assertEqual(
                        [row["hardware_slot"] for row in rows],
                        list(range(1, 11)),
                    )
                    self.assertTrue(all(row["is_active"] for row in rows))
                    self.assertEqual(
                        db.execute("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
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
                (8,'Decolgen','Tablet',7,50,1);
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
        self.assertEqual([row["brand"] for row in active], list(EXPECTED_CATALOG))
        self.assertEqual([row["hardware_slot"] for row in active], list(range(1, 11)))
        self.assertEqual(
            conn.execute("SELECT brand FROM inventory WHERE id=2").fetchone()["brand"],
            "Neozep",
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
        conn.close()

    def test_transactions_reject_items_outside_the_hardware_catalog(self):
        original_path = pos_db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            pos_db.DB_PATH = str(Path(tmp) / "transaction.sqlite")
            app = Flask(__name__)
            try:
                with app.app_context():
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
                pos_db.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
