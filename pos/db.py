"""Mendo POS — SQLite database layer.

Tables
------
admin_users         Admin / staff accounts (hashed passwords)
inventory           Medicine stock (linked to Mendo dataset brands)
transactions        Completed sales
transaction_items   Line items per sale
stock_logs          Full audit trail for every stock movement
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import g, current_app
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = str(Path(__file__).resolve().parents[1] / "data" / "mendo_pos.db")

# ─────────────────────────────────────────────────
# Connection helpers
# ─────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    if "pos_db" not in g:
        g.pos_db = sqlite3.connect(DB_PATH)
        g.pos_db.row_factory = sqlite3.Row
        g.pos_db.execute("PRAGMA journal_mode=WAL")
        g.pos_db.execute("PRAGMA foreign_keys=ON")
    return g.pos_db


def close_db(_exc: Any = None) -> None:
    db = g.pop("pos_db", None)
    if db is not None:
        db.close()


# ─────────────────────────────────────────────────
# Schema creation
# ─────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL,
    role          TEXT    DEFAULT 'staff' CHECK(role IN ('admin','staff','reviewer')),
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT    DEFAULT (datetime('now','localtime')),
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    brand           TEXT    UNIQUE NOT NULL,
    generic_name    TEXT,
    category        TEXT,
    dosage_form     TEXT,
    unit_price      REAL    NOT NULL DEFAULT 0.0,
    unit_price_centavos INTEGER NOT NULL DEFAULT 0,
    stock_quantity  INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_level INTEGER DEFAULT 5,
    is_active       INTEGER DEFAULT 1,
    hardware_slot   INTEGER,
    created_at      TEXT    DEFAULT (datetime('now','localtime')),
    updated_at      TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_ref  TEXT    UNIQUE NOT NULL,
    total_amount     REAL    NOT NULL,
    payment_method   TEXT    DEFAULT 'cash',
    amount_tendered  REAL,
    change_amount    REAL,
    item_count       INTEGER DEFAULT 0,
    status           TEXT    DEFAULT 'completed' CHECK(status IN ('completed','voided','refunded')),
    cashier_id       INTEGER,
    customer_age     INTEGER,
    customer_note    TEXT,
    created_at       TEXT    DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (cashier_id) REFERENCES admin_users(id)
);

CREATE TABLE IF NOT EXISTS transaction_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL,
    inventory_id    INTEGER NOT NULL,
    brand           TEXT    NOT NULL,
    quantity        INTEGER NOT NULL,
    unit_price      REAL    NOT NULL,
    subtotal        REAL    NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id),
    FOREIGN KEY (inventory_id) REFERENCES inventory(id)
);

CREATE TABLE IF NOT EXISTS stock_logs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id     INTEGER NOT NULL,
    brand            TEXT    NOT NULL,
    change_type      TEXT    NOT NULL CHECK(change_type IN ('restock','sale','adjustment','void_return','initial')),
    quantity_change  INTEGER NOT NULL,
    quantity_before  INTEGER NOT NULL,
    quantity_after   INTEGER NOT NULL,
    reference        TEXT,
    performed_by     INTEGER,
    created_at       TEXT    DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (inventory_id) REFERENCES inventory(id),
    FOREIGN KEY (performed_by) REFERENCES admin_users(id)
);

CREATE TABLE IF NOT EXISTS interaction_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id      TEXT    UNIQUE NOT NULL,
    timestamp           TEXT    NOT NULL,
    session_id          TEXT,
    interaction_type    TEXT    NOT NULL,
    user_input          TEXT,
    extracted_symptoms  TEXT    DEFAULT '[]',
    extraction_source   TEXT,
    red_flags           TEXT    DEFAULT '[]',
    pipeline_stages     TEXT    DEFAULT '[]',
    action              TEXT,
    recommendations     TEXT    DEFAULT '[]',
    clarification       TEXT,
    context_override    TEXT,
    severity            INTEGER,
    age                 INTEGER,
    pipeline_detail     TEXT    DEFAULT '{}',
    recommendation_detail TEXT  DEFAULT '{}',
    research_consent      INTEGER NOT NULL DEFAULT 0,
    consent_version       TEXT,
    language              TEXT,
    input_mode            TEXT,
    trace_version         INTEGER NOT NULL DEFAULT 1,
    engine_id             TEXT,
    created_at          TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS interaction_reviews (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id              TEXT NOT NULL,
    reviewer_id                 INTEGER NOT NULL,
    expected_symptoms           TEXT NOT NULL DEFAULT '[]',
    correct_symptoms            TEXT NOT NULL DEFAULT '[]',
    missed_symptoms             TEXT NOT NULL DEFAULT '[]',
    expected_red_flags          TEXT NOT NULL DEFAULT '[]',
    expected_action             TEXT NOT NULL
        CHECK(expected_action IN ('recommend','clarify','refer','no_match')),
    recommendation_appropriateness TEXT NOT NULL
        CHECK(recommendation_appropriateness IN ('appropriate','inappropriate','not_applicable','uncertain')),
    expected_medicines          TEXT NOT NULL DEFAULT '[]',
    error_category              TEXT,
    reviewer_confidence         INTEGER NOT NULL CHECK(reviewer_confidence BETWEEN 1 AND 5),
    notes                       TEXT,
    created_at                  TEXT DEFAULT (datetime('now','localtime')),
    updated_at                  TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(interaction_id, reviewer_id),
    FOREIGN KEY (interaction_id) REFERENCES interaction_logs(interaction_id),
    FOREIGN KEY (reviewer_id) REFERENCES admin_users(id)
);

CREATE TABLE IF NOT EXISTS interaction_adjudications (
    interaction_id              TEXT PRIMARY KEY,
    adjudicator_id              INTEGER NOT NULL,
    final_symptoms              TEXT NOT NULL DEFAULT '[]',
    final_red_flags             TEXT NOT NULL DEFAULT '[]',
    final_action                TEXT NOT NULL
        CHECK(final_action IN ('recommend','clarify','refer','no_match')),
    recommendation_appropriateness TEXT NOT NULL
        CHECK(recommendation_appropriateness IN ('appropriate','inappropriate','not_applicable')),
    expected_medicines          TEXT NOT NULL DEFAULT '[]',
    notes                       TEXT,
    adjudicated_at              TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (interaction_id) REFERENCES interaction_logs(interaction_id),
    FOREIGN KEY (adjudicator_id) REFERENCES admin_users(id)
);

CREATE TABLE IF NOT EXISTS operational_counters (
    counter_date        TEXT NOT NULL,
    interaction_type    TEXT NOT NULL,
    count               INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(counter_date, interaction_type)
);
"""


# Additive order/payment/dispensing schema. Legacy transaction tables remain
# untouched so historical records and their foreign keys continue to work.
_ORDER_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    order_ref             TEXT UNIQUE NOT NULL,
    idempotency_key       TEXT UNIQUE NOT NULL,
    request_hash          TEXT NOT NULL,
    source                TEXT NOT NULL DEFAULT 'kiosk',
    payment_method        TEXT NOT NULL DEFAULT 'cash',
    total_centavos        INTEGER NOT NULL CHECK(total_centavos >= 0),
    payment_state         TEXT NOT NULL DEFAULT 'unpaid'
        CHECK(payment_state IN ('unpaid','awaiting_cash','paid','cancelled','manual_review','refund_pending','refunded')),
    fulfillment_state     TEXT NOT NULL DEFAULT 'reserved'
        CHECK(fulfillment_state IN ('reserved','dispensing','completed','cancelled','manual_review')),
    fulfillment_result    TEXT NOT NULL DEFAULT 'reserved'
        CHECK(fulfillment_result IN ('reserved','dispensing','dispensed_unverified','cancelled','manual_review')),
    completion_mode       TEXT NOT NULL DEFAULT 'dispense',
    stock_committed_at    TEXT,
    received_cash_centavos INTEGER NOT NULL DEFAULT 0 CHECK(received_cash_centavos >= 0),
    overpayment_centavos  INTEGER NOT NULL DEFAULT 0 CHECK(overpayment_centavos >= 0),
    no_change_consent    INTEGER NOT NULL DEFAULT 0 CHECK(no_change_consent IN (0,1)),
    failure_reason        TEXT,
    external_payment_id  TEXT,
    transaction_id       INTEGER,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_activity_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    paid_at               TEXT,
    completed_at          TEXT,
    cancelled_at          TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id              INTEGER NOT NULL,
    inventory_id          INTEGER NOT NULL,
    slot                  INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 10),
    brand                 TEXT NOT NULL,
    unit_price_centavos   INTEGER NOT NULL CHECK(unit_price_centavos >= 0),
    quantity_ordered     INTEGER NOT NULL CHECK(quantity_ordered > 0),
    quantity_reserved    INTEGER NOT NULL CHECK(quantity_reserved >= 0),
    quantity_dispensed   INTEGER NOT NULL DEFAULT 0 CHECK(quantity_dispensed >= 0),
    line_state            TEXT NOT NULL DEFAULT 'reserved'
        CHECK(line_state IN ('reserved','dispensing','dispensed','released','manual_review')),
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (inventory_id) REFERENCES inventory(id)
);

CREATE TABLE IF NOT EXISTS cash_payment_sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_ref           TEXT UNIQUE NOT NULL,
    order_id              INTEGER UNIQUE NOT NULL,
    state                 TEXT NOT NULL DEFAULT 'active'
        CHECK(state IN ('active','stopped','completed','cancelled','manual_review')),
    accepted_denominations_json TEXT NOT NULL DEFAULT '[100,500,1000,2000,5000,10000]',
    started_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_activity_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    stopped_at            TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS cash_events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id              TEXT UNIQUE NOT NULL,
    session_id            INTEGER NOT NULL,
    order_id              INTEGER NOT NULL,
    source                TEXT NOT NULL CHECK(source IN ('coin','bill')),
    raw_pulses            INTEGER NOT NULL CHECK(raw_pulses >= 0),
    mapped_centavos       INTEGER NOT NULL DEFAULT 0 CHECK(mapped_centavos >= 0),
    event_state           TEXT NOT NULL DEFAULT 'accepted'
        CHECK(event_state IN ('accepted','unknown','rejected','replayed')),
    boot_id               TEXT NOT NULL,
    sequence_no           INTEGER NOT NULL CHECK(sequence_no >= 0),
    pulse_started_at      TEXT,
    cashbox_session_id    INTEGER,
    received_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    acknowledged_at       TEXT,
    UNIQUE(boot_id, sequence_no, source),
    FOREIGN KEY (session_id) REFERENCES cash_payment_sessions(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS payment_attempts (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id              INTEGER NOT NULL,
    provider              TEXT NOT NULL,
    external_id           TEXT UNIQUE NOT NULL,
    provider_payment_id   TEXT,
    amount_centavos       INTEGER NOT NULL CHECK(amount_centavos >= 0),
    currency              TEXT NOT NULL DEFAULT 'PHP',
    status                TEXT NOT NULL DEFAULT 'pending',
    payload_json          TEXT NOT NULL DEFAULT '{}',
    verified_at           TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS motion_profiles (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    slot                  INTEGER UNIQUE NOT NULL CHECK(slot BETWEEN 1 AND 10),
    pca_channel           INTEGER UNIQUE NOT NULL CHECK(pca_channel BETWEEN 0 AND 9),
    position_a_us         INTEGER NOT NULL CHECK(position_a_us BETWEEN 500 AND 2500),
    position_b_us         INTEGER NOT NULL CHECK(position_b_us BETWEEN 500 AND 2500),
    travel_time_ms        INTEGER NOT NULL CHECK(travel_time_ms > 0),
    b_dwell_ms            INTEGER NOT NULL CHECK(b_dwell_ms >= 0),
    return_settle_ms      INTEGER NOT NULL CHECK(return_settle_ms >= 0),
    cooldown_ms           INTEGER NOT NULL CHECK(cooldown_ms >= 0),
    profile_version       TEXT NOT NULL,
    calibrated            INTEGER NOT NULL DEFAULT 0 CHECK(calibrated IN (0,1)),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS dispense_jobs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                TEXT UNIQUE NOT NULL,
    order_id              INTEGER NOT NULL,
    order_item_id         INTEGER NOT NULL,
    unit_sequence         INTEGER NOT NULL CHECK(unit_sequence > 0),
    slot                  INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 10),
    profile_version       TEXT NOT NULL,
    state                 TEXT NOT NULL DEFAULT 'queued'
        CHECK(state IN ('queued','started','done_unverified','failed','manual_review','cancelled')),
    controller_request_id TEXT NOT NULL,
    ack_result             TEXT,
    controller_result      TEXT,
    error_code             TEXT,
    error_detail           TEXT,
    started_at             TEXT,
    ended_at               TEXT,
    restocked_at           TEXT,
    restocked_by           TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(order_id, unit_sequence),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (order_item_id) REFERENCES order_items(id)
);

CREATE TABLE IF NOT EXISTS cashbox_sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_ref           TEXT UNIQUE NOT NULL,
    state                 TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','closed')),
    expected_counts_json  TEXT NOT NULL DEFAULT '{}',
    expected_total_centavos INTEGER NOT NULL DEFAULT 0,
    staff_counted_total_centavos INTEGER,
    variance_centavos     INTEGER,
    opening_staff_id      INTEGER,
    closing_staff_id      INTEGER,
    notes                 TEXT,
    opened_at             TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    closed_at             TEXT,
    FOREIGN KEY (opening_staff_id) REFERENCES admin_users(id),
    FOREIGN KEY (closing_staff_id) REFERENCES admin_users(id)
);

CREATE TABLE IF NOT EXISTS order_audit_events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id              INTEGER NOT NULL,
    event_type            TEXT NOT NULL,
    from_state            TEXT,
    to_state              TEXT,
    actor                 TEXT NOT NULL DEFAULT 'system',
    detail_json           TEXT NOT NULL DEFAULT '{}',
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_orders_payment_state ON orders(payment_state);
CREATE INDEX IF NOT EXISTS idx_orders_fulfillment_state ON orders(fulfillment_state);
CREATE INDEX IF NOT EXISTS idx_cash_events_order ON cash_events(order_id, id);
CREATE INDEX IF NOT EXISTS idx_dispense_jobs_order ON dispense_jobs(order_id, unit_sequence);
CREATE INDEX IF NOT EXISTS idx_order_audit_order ON order_audit_events(order_id, id);
"""

def init_db() -> None:
    """Create tables, seed default admin, and auto-populate inventory."""
    db = get_db()
    db.executescript(_SCHEMA)
    _migrate_schema(db)
    db.executescript(_ORDER_SCHEMA)
    _migrate_order_schema(db)
    _seed_motion_profiles(db)

    # Seed default admin if none exists
    row = db.execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()
    if row["c"] == 0:
        db.execute(
            "INSERT INTO admin_users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            ("admin", generate_password_hash("mendo2026"), "System Administrator", "admin"),
        )
        db.commit()

    # Reconcile the database with the ten physical vending slots. Historical
    # products are archived in place so transaction and stock-log FKs survive.
    dataset_path = Path(__file__).resolve().parents[1] / "data" / "Mendo-Datasets.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Medicine dataset not found: {dataset_path}")
    from mendo_core.medicine_catalog import inventory_catalog_records

    obj = json.loads(dataset_path.read_text(encoding="utf-8"))
    entries = obj.get("Sheet1")
    if not isinstance(entries, list):
        raise ValueError("Medicine dataset must contain a Sheet1 list")
    _sync_inventory_catalog(db, inventory_catalog_records(entries))
    db.commit()


def _migrate_schema(db: sqlite3.Connection) -> None:
    """Apply additive audit migrations while preserving legacy consultations."""
    columns = {
        row["name"] for row in db.execute("PRAGMA table_info(interaction_logs)").fetchall()
    }
    additions = {
        "research_consent": "INTEGER NOT NULL DEFAULT 0",
        "consent_version": "TEXT",
        "language": "TEXT",
        "input_mode": "TEXT",
        "trace_version": "INTEGER NOT NULL DEFAULT 1",
        "engine_id": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(f"ALTER TABLE interaction_logs ADD COLUMN {name} {definition}")

    inventory_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(inventory)").fetchall()
    }
    if "unit_price_centavos" not in inventory_columns:
        db.execute(
            "ALTER TABLE inventory ADD COLUMN unit_price_centavos INTEGER NOT NULL DEFAULT 0"
        )
    if "reserved_quantity" not in inventory_columns:
        db.execute(
            "ALTER TABLE inventory ADD COLUMN reserved_quantity INTEGER NOT NULL DEFAULT 0"
        )
    if "hardware_slot" not in inventory_columns:
        db.execute("ALTER TABLE inventory ADD COLUMN hardware_slot INTEGER")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_hardware_slot "
        "ON inventory(hardware_slot) WHERE hardware_slot IS NOT NULL"
    )

    review_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(interaction_reviews)").fetchall()
    }
    if "correct_symptoms" not in review_columns:
        db.execute(
            "ALTER TABLE interaction_reviews "
            "ADD COLUMN correct_symptoms TEXT NOT NULL DEFAULT '[]'"
        )

    # Older databases constrained roles to admin/staff. Rebuild only that
    # table, preserving ids so transaction and review foreign keys stay valid.
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='admin_users'"
    ).fetchone()
    table_sql = (row["sql"] or "") if row else ""
    if "'reviewer'" not in table_sql:
        db.commit()
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("PRAGMA legacy_alter_table=ON")
        db.executescript(
            """
            BEGIN;
            ALTER TABLE admin_users RENAME TO admin_users_legacy;
            CREATE TABLE admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'staff'
                    CHECK(role IN ('admin','staff','reviewer')),
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                last_login TEXT
            );
            INSERT INTO admin_users
                (id, username, password_hash, full_name, role, is_active, created_at, last_login)
            SELECT id, username, password_hash, full_name, role, is_active, created_at, last_login
            FROM admin_users_legacy;
            DROP TABLE admin_users_legacy;
            COMMIT;
            """
        )
        db.execute("PRAGMA legacy_alter_table=OFF")
        db.execute("PRAGMA foreign_keys=ON")


def _migrate_order_schema(db: sqlite3.Connection) -> None:
    """Apply additive order fields to databases created by an earlier build."""
    table_columns = {
        table: {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for table in ("orders", "cash_events", "dispense_jobs")
    }
    additions = {
        "orders": {
            "fulfillment_result": "TEXT NOT NULL DEFAULT 'reserved'",
            "completion_mode": "TEXT NOT NULL DEFAULT 'dispense'",
            "stock_committed_at": "TEXT",
        },
        "cash_events": {"cashbox_session_id": "INTEGER"},
        "dispense_jobs": {
            "restocked_at": "TEXT",
            "restocked_by": "TEXT",
        },
    }
    for table, fields in additions.items():
        for name, definition in fields.items():
            if name not in table_columns[table]:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_cash_events_cashbox ON cash_events(cashbox_session_id, id)"
    )


def _sync_inventory_catalog(
    db: sqlite3.Connection,
    records: List[Dict[str, Any]],
) -> None:
    """Map existing inventory to ten slots without deleting historical rows."""
    inventory_columns = {row["name"] for row in db.execute("PRAGMA table_info(inventory)").fetchall()}
    has_centavos = "unit_price_centavos" in inventory_columns
    has_reservations = "reserved_quantity" in inventory_columns
    db.execute("UPDATE inventory SET hardware_slot=NULL")

    for record in records:
        names = tuple(dict.fromkeys(record["aliases"]))
        placeholders = ",".join("?" for _ in names)
        candidates = db.execute(
            f"""
            SELECT i.*,
                   (SELECT COUNT(*) FROM transaction_items ti
                    WHERE ti.inventory_id=i.id) AS transaction_refs,
                   (SELECT COUNT(*) FROM stock_logs sl
                    WHERE sl.inventory_id=i.id) AS stock_refs
            FROM inventory i
            WHERE lower(i.brand) IN ({placeholders})
            """,
            tuple(name.casefold() for name in names),
        ).fetchall()

        desired_form = record["dosage_form"].casefold()
        chosen = None
        if candidates:
            chosen = sorted(
                candidates,
                key=lambda row: (
                    str(row["dosage_form"] or "").casefold() != desired_form,
                    -(int(row["transaction_refs"]) + int(row["stock_refs"])),
                    row["id"],
                ),
            )[0]

            # Free the canonical unique brand before renaming the selected row.
            for row in candidates:
                if row["id"] == chosen["id"]:
                    continue
                archived_brand = f"{row['brand']} [archived #{row['id']}]"
                db.execute(
                    """
                    UPDATE inventory
                    SET brand=?, is_active=0, hardware_slot=NULL,
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (archived_brand, row["id"]),
                )

            if has_centavos:
                db.execute(
                    """
                    UPDATE inventory
                    SET brand=?, generic_name=?, category=?, dosage_form=?,
                        hardware_slot=?,
                        unit_price_centavos=CAST(ROUND(unit_price * 100.0) AS INTEGER),
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (record["brand"], record["generic_name"], record["category"], record["dosage_form"], record["slot"], chosen["id"]),
                )
            else:
                db.execute(
                    """
                    UPDATE inventory
                    SET brand=?, generic_name=?, category=?, dosage_form=?,
                        hardware_slot=?, updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (record["brand"], record["generic_name"], record["category"], record["dosage_form"], record["slot"], chosen["id"]),
                )
        else:
            if has_centavos and has_reservations:
                db.execute(
                    """
                    INSERT INTO inventory
                        (brand, generic_name, category, dosage_form, unit_price,
                         unit_price_centavos, stock_quantity, reserved_quantity,
                         hardware_slot, is_active)
                    VALUES (?,?,?,?,?,?,0,0,?,1)
                    """,
                    (record["brand"], record["generic_name"], record["category"], record["dosage_form"], record["default_price"], int(round(float(record["default_price"]) * 100)), record["slot"]),
                )
            else:
                db.execute(
                    """
                    INSERT INTO inventory
                        (brand, generic_name, category, dosage_form, unit_price,
                         stock_quantity, hardware_slot, is_active)
                    VALUES (?,?,?,?,?,0,?,1)
                    """,
                    (record["brand"], record["generic_name"], record["category"], record["dosage_form"], record["default_price"], record["slot"]),
                )

    # Existing installations have REAL prices. Backfill once without
    # converting through a binary float in the order layer.
    if has_centavos:
        db.execute(
            """
            UPDATE inventory
            SET unit_price_centavos=CAST(ROUND(unit_price * 100.0) AS INTEGER)
            WHERE unit_price_centavos IS NULL OR unit_price_centavos=0
            """
        )

    canonical = tuple(record["brand"] for record in records)
    placeholders = ",".join("?" for _ in canonical)
    db.execute(
        f"""
        UPDATE inventory
        SET is_active=0, hardware_slot=NULL,
            updated_at=datetime('now','localtime')
        WHERE brand NOT IN ({placeholders})
        """,
        canonical,
    )


def _seed_motion_profiles(db: sqlite3.Connection) -> None:
    """Create clearly-un calibrated placeholder profiles for ten channels."""
    for slot in range(1, 11):
        db.execute(
            """
            INSERT OR IGNORE INTO motion_profiles
                (slot, pca_channel, position_a_us, position_b_us,
                 travel_time_ms, b_dwell_ms, return_settle_ms, cooldown_ms,
                 profile_version, calibrated)
            VALUES (?,?,?,?,?,?,?,?,?,0)
            """,
            (slot, slot - 1, 1500, 1900, 500, 250, 300, 500, "v1-unmeasured"),
        )

# ─────────────────────────────────────────────────
# Admin-user helpers
# ─────────────────────────────────────────────────

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    row = db.execute(
        "SELECT * FROM admin_users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        db.execute(
            "UPDATE admin_users SET last_login=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
        )
        db.commit()
        return dict(row)
    return None


def get_user_by_id(uid: int) -> Optional[Dict[str, Any]]:
    row = get_db().execute("SELECT * FROM admin_users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def create_user(username: str, password: str, full_name: str, role: str = "staff") -> int:
    db = get_db()
    db.execute(
        "INSERT INTO admin_users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
        (username, generate_password_hash(password), full_name, role),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_users() -> List[Dict[str, Any]]:
    return [dict(r) for r in get_db().execute(
        "SELECT id, username, full_name, role, is_active, created_at, last_login FROM admin_users ORDER BY id"
    ).fetchall()]


def change_password(uid: int, new_password: str) -> None:
    db = get_db()
    db.execute("UPDATE admin_users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), uid))
    db.commit()


def toggle_user_active(uid: int) -> bool:
    db = get_db()
    row = db.execute("SELECT is_active FROM admin_users WHERE id=?", (uid,)).fetchone()
    if not row:
        raise ValueError("User not found")
    new_status = 0 if row["is_active"] else 1
    db.execute("UPDATE admin_users SET is_active=? WHERE id=?", (new_status, uid))
    db.commit()
    return bool(new_status)


# ─────────────────────────────────────────────────
# Inventory helpers
# ─────────────────────────────────────────────────

def list_inventory(
    active_only: bool = False,
    catalog_only: bool = False,
) -> List[Dict[str, Any]]:
    q = "SELECT * FROM inventory"
    clauses = []
    if active_only:
        clauses.append("is_active=1")
    if catalog_only:
        clauses.append("hardware_slot IS NOT NULL")
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY hardware_slot IS NULL, hardware_slot, brand"
    result = []
    for row in get_db().execute(q).fetchall():
        item = dict(row)
        item["available_quantity"] = max(
            0, int(item.get("stock_quantity") or 0) - int(item.get("reserved_quantity") or 0)
        )
        result.append(item)
    return result


def get_inventory_item(item_id: int) -> Optional[Dict[str, Any]]:
    row = get_db().execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["available_quantity"] = max(
        0, int(item.get("stock_quantity") or 0) - int(item.get("reserved_quantity") or 0)
    )
    return item


def get_inventory_by_brand(brand: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute("SELECT * FROM inventory WHERE brand=?", (brand,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["available_quantity"] = max(
        0, int(item.get("stock_quantity") or 0) - int(item.get("reserved_quantity") or 0)
    )
    return item


def update_stock(item_id: int, new_qty: int, change_type: str, reference: str = "", performed_by: Optional[int] = None) -> None:
    db = get_db()
    item = get_inventory_item(item_id)
    if not item:
        raise ValueError("Item not found")
    if int(new_qty) < 0:
        raise ValueError("Stock quantity cannot be negative")
    if int(new_qty) < int(item.get("reserved_quantity") or 0):
        raise ValueError("Stock quantity cannot be below the reserved quantity")
    old_qty = item["stock_quantity"]
    actor_id = performed_by if performed_by and performed_by > 0 else None
    db.execute(
        "UPDATE inventory SET stock_quantity=?, updated_at=? WHERE id=?",
        (new_qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id),
    )
    db.execute(
        """INSERT INTO stock_logs
           (inventory_id, brand, change_type, quantity_change, quantity_before, quantity_after, reference, performed_by)
           VALUES (?,?,?,?,?,?,?,?)""",
          (item_id, item["brand"], change_type, new_qty - old_qty, old_qty, new_qty, reference, actor_id),
    )
    db.commit()


def update_inventory_details(item_id: int, *, unit_price: Optional[float] = None,
                             min_stock_level: Optional[int] = None,
                             is_active: Optional[int] = None,
                             unit_price_centavos: Optional[int] = None) -> None:
    db = get_db()
    updates = []
    params: list = []
    if unit_price is not None:
        updates.append("unit_price=?")
        params.append(unit_price)
        updates.append("unit_price_centavos=?")
        params.append(int(round(float(unit_price) * 100)))
    elif unit_price_centavos is not None:
        updates.append("unit_price_centavos=?")
        params.append(int(unit_price_centavos))
        updates.append("unit_price=?")
        params.append(int(unit_price_centavos) / 100)
    if min_stock_level is not None:
        updates.append("min_stock_level=?")
        params.append(min_stock_level)
    if is_active is not None:
        updates.append("is_active=?")
        params.append(is_active)
    if not updates:
        return
    updates.append("updated_at=?")
    params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    params.append(item_id)
    db.execute(f"UPDATE inventory SET {','.join(updates)} WHERE id=?", params)
    db.commit()


# ─────────────────────────────────────────────────
# Transaction helpers
# ─────────────────────────────────────────────────

def _next_txn_ref() -> str:
    today = datetime.now().strftime("%Y%m%d")
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS c FROM transactions WHERE transaction_ref LIKE ?",
        (f"TXN-{today}-%",),
    ).fetchone()
    seq = (row["c"] or 0) + 1
    return f"TXN-{today}-{seq:04d}"


def create_transaction(
    items: List[Dict[str, Any]],
    payment_method: str = "cash",
    amount_tendered: float = 0.0,
    cashier_id: Optional[int] = None,
    customer_age: Optional[int] = None,
    customer_note: str = "",
) -> Dict[str, Any]:
    db = get_db()
    ref = _next_txn_ref()
    actor_id = cashier_id if cashier_id and cashier_id > 0 else None
    total = 0.0
    item_count = 0
    line_items: List[Dict[str, Any]] = []

    for it in items:
        inv = get_inventory_item(it["inventory_id"])
        if not inv:
            raise ValueError(f"Item id={it['inventory_id']} not found")
        if not inv["is_active"] or inv.get("hardware_slot") is None:
            raise ValueError(f"{inv['brand']} is not available in the hardware catalog")
        qty = int(it["quantity"])
        if qty <= 0:
            raise ValueError(f"Invalid quantity for {inv['brand']}")
        if inv["stock_quantity"] < qty:
            raise ValueError(f"Insufficient stock for {inv['brand']} (have {inv['stock_quantity']}, need {qty})")
        subtotal = round(inv["unit_price"] * qty, 2)
        total += subtotal
        item_count += qty
        line_items.append({
            "inventory_id": inv["id"],
            "brand": inv["brand"],
            "quantity": qty,
            "unit_price": inv["unit_price"],
            "subtotal": subtotal,
        })

    total = round(total, 2)
    change = round(amount_tendered - total, 2) if amount_tendered else 0.0

    db.execute(
        """INSERT INTO transactions
           (transaction_ref, total_amount, payment_method, amount_tendered, change_amount,
            item_count, status, cashier_id, customer_age, customer_note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (ref, total, payment_method, amount_tendered, change, item_count, "completed",
            actor_id, customer_age, customer_note),
    )
    txn_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    for li in line_items:
        db.execute(
            """INSERT INTO transaction_items
               (transaction_id, inventory_id, brand, quantity, unit_price, subtotal)
               VALUES (?,?,?,?,?,?)""",
            (txn_id, li["inventory_id"], li["brand"], li["quantity"], li["unit_price"], li["subtotal"]),
        )
        new_qty = get_inventory_item(li["inventory_id"])["stock_quantity"] - li["quantity"]
        db.execute("UPDATE inventory SET stock_quantity=?, updated_at=? WHERE id=?",
                   (new_qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), li["inventory_id"]))
        db.execute(
            """INSERT INTO stock_logs
               (inventory_id, brand, change_type, quantity_change, quantity_before, quantity_after, reference, performed_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (li["inventory_id"], li["brand"], "sale", -li["quantity"],
                 new_qty + li["quantity"], new_qty, ref, actor_id),
        )

    db.commit()
    return {
        "transaction_id": txn_id,
        "transaction_ref": ref,
        "total_amount": total,
        "amount_tendered": amount_tendered,
        "change_amount": change,
        "item_count": item_count,
        "items": line_items,
    }


def void_transaction(txn_id: int, performed_by: Optional[int] = None) -> None:
    """Void the financial receipt without assuming medicine was returned.

    Physical stock is intentionally unchanged. Staff must use an explicit
    return-to-stock workflow after verifying a physical return.
    """
    db = get_db()
    actor_id = performed_by if performed_by and performed_by > 0 else None
    txn = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    if not txn:
        raise ValueError("Transaction not found")
    if txn["status"] != "completed":
        raise ValueError(f"Cannot void: status is '{txn['status']}'")

    db.execute("UPDATE transactions SET status='voided' WHERE id=?", (txn_id,))
    db.commit()


def get_transaction(txn_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    txn = db.execute("""
        SELECT t.*, u.full_name AS cashier_name
        FROM transactions t
        LEFT JOIN admin_users u ON t.cashier_id = u.id
        WHERE t.id=?
    """, (txn_id,)).fetchone()
    if not txn:
        return None
    items = db.execute("SELECT * FROM transaction_items WHERE transaction_id=?", (txn_id,)).fetchall()
    result = dict(txn)
    result["items"] = [dict(i) for i in items]
    return result


def count_transactions(status: str = "") -> int:
    """Return total number of transactions (for pagination)."""
    db = get_db()
    q = "SELECT COUNT(*) AS c FROM transactions"
    params: list = []
    if status:
        q += " WHERE status=?"
        params.append(status)
    return db.execute(q, params).fetchone()["c"]


def list_transactions(limit: int = 50, offset: int = 0, status: str = "") -> List[Dict[str, Any]]:
    db = get_db()
    q = """SELECT t.*, u.full_name AS cashier_name
           FROM transactions t LEFT JOIN admin_users u ON t.cashier_id = u.id"""
    params: list = []
    if status:
        q += " WHERE t.status=?"
        params.append(status)
    q += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return [dict(r) for r in db.execute(q, params).fetchall()]


def get_stock_logs(limit: int = 100, inventory_id: int = 0) -> List[Dict[str, Any]]:
    db = get_db()
    q = """SELECT sl.*, u.full_name AS performed_by_name
           FROM stock_logs sl LEFT JOIN admin_users u ON sl.performed_by = u.id"""
    params: list = []
    if inventory_id:
        q += " WHERE sl.inventory_id=?"
        params.append(inventory_id)
    q += " ORDER BY sl.id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.execute(q, params).fetchall()]


# ─────────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────────

def get_dashboard_stats() -> Dict[str, Any]:
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    today_sales = db.execute(
        "SELECT COALESCE(SUM(total_amount),0) AS total, COUNT(*) AS count FROM transactions WHERE DATE(created_at)=? AND status='completed'",
        (today,),
    ).fetchone()

    all_sales = db.execute(
        "SELECT COALESCE(SUM(total_amount),0) AS total, COUNT(*) AS count FROM transactions WHERE status='completed'",
    ).fetchone()

    inv_stats = db.execute("""
        SELECT
            COUNT(*) AS total_products,
            SUM(CASE WHEN stock_quantity=0 THEN 1 ELSE 0 END) AS out_of_stock,
            SUM(CASE WHEN stock_quantity > 0 AND stock_quantity <= min_stock_level THEN 1 ELSE 0 END) AS low_stock,
            SUM(stock_quantity) AS total_units
        FROM inventory WHERE is_active=1
    """).fetchone()

    top_sellers = db.execute("""
        SELECT ti.brand, SUM(ti.quantity) AS total_sold, SUM(ti.subtotal) AS total_revenue
        FROM transaction_items ti
        JOIN transactions t ON ti.transaction_id = t.id
        WHERE t.status='completed'
        GROUP BY ti.brand ORDER BY total_sold DESC LIMIT 5
    """).fetchall()

    recent_txns = list_transactions(limit=5)

    return {
        "today_revenue": today_sales["total"],
        "today_transactions": today_sales["count"],
        "all_time_revenue": all_sales["total"],
        "all_time_transactions": all_sales["count"],
        "total_products": inv_stats["total_products"],
        "out_of_stock": inv_stats["out_of_stock"] or 0,
        "low_stock": inv_stats["low_stock"] or 0,
        "total_units": inv_stats["total_units"] or 0,
        "top_sellers": [dict(r) for r in top_sellers],
        "recent_transactions": recent_txns,
    }
