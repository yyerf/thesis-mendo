"""Mendo POS — SQLite database layer.

Tables
------
admin_users         Admin / staff accounts (bcrypt hashed passwords)
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
from typing import Any, Dict, List, Optional, Tuple

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
    role          TEXT    DEFAULT 'staff' CHECK(role IN ('admin','staff')),
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
    stock_quantity  INTEGER NOT NULL DEFAULT 0,
    min_stock_level INTEGER DEFAULT 5,
    is_active       INTEGER DEFAULT 1,
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
"""

# Default prices (PHP) for common PH OTC medicines
_DEFAULT_PRICES: Dict[str, float] = {
    "Bioflu":              12.00,
    "Neozep / Neozep Z+":  9.50,
    "Neozep ":             65.00,   # syrup
    "Decolgen":            7.00,
    "Symdex-D Syrup":      55.00,
    "Symdex-D Forte":      8.00,
    "Tuseran Forte":       10.00,
    "Asc Syrup":           85.00,
    "Ascof Forte":         9.00,
    "Solmux Advance":      75.00,   # syrup
    "Solmux":              12.00,
    "Robitussin":          90.00,
    "Sinecod Forte":       18.00,
    "Biogesic for Kids":   65.00,   # syrup
    "Biogesic":            5.00,
    "Advil":               15.00,
    "Cetrikid Drops":      120.00,
    "Cetirizine":          5.00,
    "Loperamide (Diatabs)": 6.00,
    "Erceflora":           28.00,
    "Aspirin (Philprin)":  4.00,
    "Benadryl AH":         8.00,
    "Sinutab":             12.00,
    "Claritin":            22.00,
    "Allerta":             12.00,
    "Kremil-S":            7.00,
}


def init_db() -> None:
    """Create tables, seed default admin, and auto-populate inventory."""
    db = get_db()
    db.executescript(_SCHEMA)

    # ── Seed default admin if none exists ──
    row = db.execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()
    if row["c"] == 0:
        db.execute(
            "INSERT INTO admin_users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            ("admin", generate_password_hash("mendo2026"), "System Administrator", "admin"),
        )
        db.commit()

    # ── Auto-populate inventory from Mendo dataset ──
    existing = {r["brand"] for r in db.execute("SELECT brand FROM inventory").fetchall()}
    dataset_path = Path(__file__).resolve().parents[1] / "data" / "datasets" / "Mendo-Datasets.json"
    if dataset_path.exists():
        try:
            obj = json.loads(dataset_path.read_text(encoding="utf-8"))
            for entry in obj.get("Sheet1", []):
                brand = str(entry.get("Brand") or "").strip()
                if not brand or brand in existing:
                    continue
                price = _DEFAULT_PRICES.get(brand, 10.00)
                db.execute(
                    """INSERT INTO inventory
                       (brand, generic_name, category, dosage_form, unit_price, stock_quantity)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        brand,
                        str(entry.get("Generic/Main Use") or ""),
                        str(entry.get("Drug Category") or ""),
                        str(entry.get("Dosage Form") or ""),
                        price,
                        0,   # start with 0 stock — admin must add
                    ),
                )
                existing.add(brand)
        except Exception:
            pass
    db.commit()


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


# ─────────────────────────────────────────────────
# Inventory helpers
# ─────────────────────────────────────────────────

def list_inventory(active_only: bool = False) -> List[Dict[str, Any]]:
    q = "SELECT * FROM inventory"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY brand"
    return [dict(r) for r in get_db().execute(q).fetchall()]


def get_inventory_item(item_id: int) -> Optional[Dict[str, Any]]:
    row = get_db().execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def get_inventory_by_brand(brand: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute("SELECT * FROM inventory WHERE brand=?", (brand,)).fetchone()
    return dict(row) if row else None


def update_stock(item_id: int, new_qty: int, change_type: str, reference: str = "", performed_by: int = 0) -> None:
    db = get_db()
    item = get_inventory_item(item_id)
    if not item:
        raise ValueError("Item not found")
    old_qty = item["stock_quantity"]
    db.execute(
        "UPDATE inventory SET stock_quantity=?, updated_at=? WHERE id=?",
        (new_qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id),
    )
    db.execute(
        """INSERT INTO stock_logs
           (inventory_id, brand, change_type, quantity_change, quantity_before, quantity_after, reference, performed_by)
           VALUES (?,?,?,?,?,?,?,?)""",
        (item_id, item["brand"], change_type, new_qty - old_qty, old_qty, new_qty, reference, performed_by),
    )
    db.commit()


def update_inventory_details(item_id: int, *, unit_price: Optional[float] = None,
                             min_stock_level: Optional[int] = None,
                             is_active: Optional[int] = None) -> None:
    db = get_db()
    updates = []
    params: list = []
    if unit_price is not None:
        updates.append("unit_price=?")
        params.append(unit_price)
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
    items: List[Dict[str, Any]],  # [{"inventory_id":int, "quantity":int}]
    payment_method: str = "cash",
    amount_tendered: float = 0.0,
    cashier_id: int = 0,
    customer_age: Optional[int] = None,
    customer_note: str = "",
) -> Dict[str, Any]:
    db = get_db()
    ref = _next_txn_ref()
    total = 0.0
    item_count = 0
    line_items: List[Dict[str, Any]] = []

    for it in items:
        inv = get_inventory_item(it["inventory_id"])
        if not inv:
            raise ValueError(f"Item id={it['inventory_id']} not found")
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
         cashier_id, customer_age, customer_note),
    )
    txn_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    for li in line_items:
        db.execute(
            """INSERT INTO transaction_items
               (transaction_id, inventory_id, brand, quantity, unit_price, subtotal)
               VALUES (?,?,?,?,?,?)""",
            (txn_id, li["inventory_id"], li["brand"], li["quantity"], li["unit_price"], li["subtotal"]),
        )
        # Deduct stock
        new_qty = get_inventory_item(li["inventory_id"])["stock_quantity"] - li["quantity"]
        db.execute("UPDATE inventory SET stock_quantity=?, updated_at=? WHERE id=?",
                   (new_qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), li["inventory_id"]))
        db.execute(
            """INSERT INTO stock_logs
               (inventory_id, brand, change_type, quantity_change, quantity_before, quantity_after, reference, performed_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (li["inventory_id"], li["brand"], "sale", -li["quantity"],
             new_qty + li["quantity"], new_qty, ref, cashier_id),
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


def void_transaction(txn_id: int, performed_by: int = 0) -> None:
    """Void a transaction — restore stock and mark voided."""
    db = get_db()
    txn = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    if not txn:
        raise ValueError("Transaction not found")
    if txn["status"] != "completed":
        raise ValueError(f"Cannot void: status is '{txn['status']}'")

    items = db.execute("SELECT * FROM transaction_items WHERE transaction_id=?", (txn_id,)).fetchall()
    for it in items:
        inv = get_inventory_item(it["inventory_id"])
        if inv:
            new_qty = inv["stock_quantity"] + it["quantity"]
            db.execute("UPDATE inventory SET stock_quantity=?, updated_at=? WHERE id=?",
                       (new_qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), it["inventory_id"]))
            db.execute(
                """INSERT INTO stock_logs
                   (inventory_id, brand, change_type, quantity_change, quantity_before, quantity_after, reference, performed_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (it["inventory_id"], it["brand"], "void_return", it["quantity"],
                 inv["stock_quantity"], new_qty, txn["transaction_ref"], performed_by),
            )
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

    # Top sellers (all time)
    top_sellers = db.execute("""
        SELECT ti.brand, SUM(ti.quantity) AS total_sold, SUM(ti.subtotal) AS total_revenue
        FROM transaction_items ti
        JOIN transactions t ON ti.transaction_id = t.id
        WHERE t.status='completed'
        GROUP BY ti.brand ORDER BY total_sold DESC LIMIT 5
    """).fetchall()

    # Recent transactions
    recent_txns = list_transactions(limit=5)

    return {
        "today_revenue": today_sales["total"],
        "today_transactions": today_sales["count"],
        "all_time_revenue": all_sales["total"],
        "all_time_transactions": all_sales["count"],
        "total_products": inv_stats["total_products"],
        "out_of_stock": inv_stats["out_of_stock"],
        "low_stock": inv_stats["low_stock"],
        "total_units": inv_stats["total_units"] or 0,
        "top_sellers": [dict(r) for r in top_sellers],
        "recent_transactions": recent_txns,
    }
