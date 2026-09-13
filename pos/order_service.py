"""Recoverable order, cash, inventory, and dispensing state machine.

The legacy POS transaction tables are deliberately kept as a receipt/audit
projection.  This module owns the new workflow and uses ``BEGIN IMMEDIATE``
for every reservation, payment-event, dispense, and recovery transition.
Physical delivery is never inferred from a successful software command; the
initial fulfillment state is always ``done_unverified``.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from mendo_core.money import format_php, to_centavos
from hardware.pulses import PulseMapping

from .db import get_db


SUPPORTED_DENOMINATIONS_CENTAVOS = (100, 500, 1000, 2000, 5000, 10000)
COIN_DENOMINATIONS_CENTAVOS = (100, 500, 1000, 2000)
BILL_DENOMINATIONS_CENTAVOS = (2000, 5000, 10000)
# Coins are linear: one pulse is one peso, and a rapid burst merges into a
# single train, so a legitimate coin event can be any whole-peso multiple up to
# this ceiling. Bills stay a strict denomination lookup. Measured 2026-08-04;
# see docs/architecture/tb74-pulse-protocol-analysis.md.
COIN_MAX_TRAIN_CENTAVOS = 20000
MAX_QTY_PER_ITEM = 3
MAX_DISTINCT_ITEMS = 5
PAYMENT_TIMEOUT_SECONDS = 180


class OrderError(ValueError):
    """Base class for a safe, user-visible order failure."""


class OrderNotFound(OrderError):
    pass


class IdempotencyConflict(OrderError):
    pass


class InvalidTransition(OrderError):
    pass


class ConsentRequired(OrderError):
    pass


class StockUnavailable(OrderError):
    pass


class ExclusiveCashSession(OrderError):
    pass


class HardwareJobUnknown(OrderError):
    pass


PAYMENT_TRANSITIONS = {
    "unpaid": {"awaiting_cash", "paid", "cancelled", "manual_review"},
    "awaiting_cash": {"unpaid", "paid", "cancelled", "manual_review"},
    "paid": {"refund_pending", "refunded", "manual_review"},
    "manual_review": {"paid", "refund_pending", "refunded", "cancelled"},
    "refund_pending": {"refunded", "manual_review"},
    "cancelled": set(),
    "refunded": set(),
}

FULFILLMENT_TRANSITIONS = {
    # A payment-only POS sale commits reserved stock without claiming that a
    # motor moved. That path legitimately goes straight to completed.
    "reserved": {"dispensing", "completed", "cancelled", "manual_review"},
    "dispensing": {"completed", "manual_review", "cancelled"},
    "manual_review": {"dispensing", "completed", "cancelled"},
    "completed": {"manual_review"},
    "cancelled": set(),
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _ref(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10].upper()}"


def _request_hash(items: Sequence[Dict[str, int]], source: str, payment_method: str) -> str:
    payload = {
        "items": sorted(
            [{"inventory_id": int(i["inventory_id"]), "quantity": int(i["quantity"])} for i in items],
            key=lambda row: row["inventory_id"],
        ),
        "source": source,
        "payment_method": payment_method,
    }
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


@contextmanager
def _immediate(db):
    """Run one state transition with a RESERVED SQLite write lock."""
    # A previous helper call should not leave an implicit transaction open.
    # Committing here is safer than allowing an accidental nested transaction
    # to turn an apparently atomic order transition into a partial write.
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def _transition(current: str, target: str, allowed: Dict[str, set], label: str) -> None:
    if current == target:
        return
    if target not in allowed.get(current, set()):
        raise InvalidTransition(f"Illegal {label} transition: {current} → {target}")


class OrderService:
    """Application service for one recoverable order workflow."""

    def __init__(self, connection=None):
        self.connection = connection

    @property
    def db(self):
        return self.connection or get_db()

    # ── read models ──────────────────────────────────────────────────────

    def _order_row(self, order_ref: str):
        row = self.db.execute("SELECT * FROM orders WHERE order_ref=?", (order_ref,)).fetchone()
        if not row:
            raise OrderNotFound(f"Order {order_ref} not found")
        return row

    def get_order(self, order_ref: str) -> Dict[str, Any]:
        db = self.db
        order = dict(self._order_row(order_ref))
        items = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)
            ).fetchall()
        ]
        for item in items:
            item["unit_price"] = item["unit_price_centavos"] / 100
            item["subtotal_centavos"] = item["unit_price_centavos"] * item["quantity_ordered"]
            item["subtotal"] = item["subtotal_centavos"] / 100
            inv = db.execute(
                "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?",
                (item["inventory_id"],),
            ).fetchone()
            item["stock_available"] = max(
                0, int(inv["stock_quantity"]) - int(inv["reserved_quantity"])
            ) if inv else 0

        jobs = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM dispense_jobs WHERE order_id=? ORDER BY unit_sequence",
                (order["id"],),
            ).fetchall()
        ]
        cash_events = [
            dict(row)
            for row in db.execute(
                """
                SELECT event_id,source,raw_pulses,mapped_centavos,event_state,
                       boot_id,sequence_no,received_at,acknowledged_at
                FROM cash_events WHERE order_id=? ORDER BY id
                """,
                (order["id"],),
            ).fetchall()
        ]
        session_row = db.execute(
            """
            SELECT session_ref,state,accepted_denominations_json,started_at,
                   last_activity_at,stopped_at
            FROM cash_payment_sessions WHERE order_id=?
            """,
            (order["id"],),
        ).fetchone()

        due = int(order["total_centavos"])
        received = int(order["received_cash_centavos"])
        result = {
            **order,
            # ``fulfillment_state`` remains the compatibility lifecycle field;
            # ``fulfillment_result`` states what the actuator actually proves.
            "fulfillment_verification": order.get("fulfillment_result", "reserved"),
            "amount_due_centavos": due,
            "amount_due": due / 100,
            "amount_due_display": format_php(due, centavos=True),
            "received_cash": received / 100,
            "received_cash_display": format_php(received, centavos=True),
            "remaining_centavos": max(0, due - received),
            "remaining": max(0, due - received) / 100,
            "remaining_display": format_php(max(0, due - received), centavos=True),
            "overpayment": int(order["overpayment_centavos"]) / 100,
            "overpayment_display": format_php(order["overpayment_centavos"], centavos=True),
            "items": items,
            "dispense_jobs": jobs,
            "cash_events": cash_events,
            "cash_session": dict(session_row) if session_row else None,
            "accepted_denominations_centavos": list(SUPPORTED_DENOMINATIONS_CENTAVOS),
            "accepted_denominations": [value / 100 for value in SUPPORTED_DENOMINATIONS_CENTAVOS],
        }
        if order.get("transaction_id"):
            transaction = db.execute(
                "SELECT transaction_ref FROM transactions WHERE id=?", (order["transaction_id"],)
            ).fetchone()
            if transaction:
                result["transaction_ref"] = transaction["transaction_ref"]
        return result

    def list_orders(self, limit: int = 100, offset: int = 0, state: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        query = "SELECT order_ref FROM orders"
        if state:
            query += " WHERE payment_state=? OR fulfillment_state=?"
            params.extend([state, state])
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 500)), max(0, offset)])
        return [self.get_order(row["order_ref"]) for row in self.db.execute(query, params).fetchall()]

    # ── order creation and reservation ──────────────────────────────────

    def _normalize_cart(self, items: Iterable[Dict[str, Any]]) -> List[Dict[str, int]]:
        aggregate: Dict[int, int] = {}
        for raw in items:
            try:
                inventory_id = int(raw.get("inventory_id") or 0)
                quantity = int(raw.get("quantity") or 0)
            except (AttributeError, TypeError, ValueError) as exc:
                raise OrderError("Each order item needs an inventory_id and quantity") from exc
            if inventory_id <= 0 or quantity <= 0:
                raise OrderError("Order quantities must be positive")
            aggregate[inventory_id] = aggregate.get(inventory_id, 0) + quantity
        if not aggregate:
            raise OrderError("Cart is empty")
        if len(aggregate) > MAX_DISTINCT_ITEMS:
            raise OrderError(f"Maximum {MAX_DISTINCT_ITEMS} different medicines allowed")
        if any(quantity > MAX_QTY_PER_ITEM for quantity in aggregate.values()):
            raise OrderError(f"Maximum {MAX_QTY_PER_ITEM} units per medicine allowed")
        return [
            {"inventory_id": inventory_id, "quantity": quantity}
            for inventory_id, quantity in sorted(aggregate.items())
        ]

    def create_order(
        self,
        items: Iterable[Dict[str, Any]],
        *,
        idempotency_key: str,
        source: str = "kiosk",
        payment_method: str = "cash",
    ) -> Dict[str, Any]:
        if not str(idempotency_key or "").strip():
            raise OrderError("Idempotency-Key is required")
        if payment_method not in {"cash", "xendit_cashless", "cashier_cash", "cashier_xendit"}:
            raise OrderError("Unsupported payment method")
        normalized = self._normalize_cart(items)
        request_hash = _request_hash(normalized, source, payment_method)
        db = self.db
        with _immediate(db):
            existing = db.execute(
                "SELECT order_ref,request_hash FROM orders WHERE idempotency_key=?",
                (str(idempotency_key),),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict("Idempotency key was already used for another cart")
                return self.get_order(existing["order_ref"])

            line_items: List[Tuple[Dict[str, Any], int]] = []
            total = 0
            for line in normalized:
                inv = db.execute(
                    """
                    SELECT id,brand,unit_price,unit_price_centavos,stock_quantity,
                           reserved_quantity,is_active,hardware_slot
                    FROM inventory WHERE id=?
                    """,
                    (line["inventory_id"],),
                ).fetchone()
                if not inv or not inv["is_active"] or inv["hardware_slot"] is None:
                    raise OrderError(f"Inventory item {line['inventory_id']} is not an active slot")
                available = int(inv["stock_quantity"]) - int(inv["reserved_quantity"] or 0)
                if available < line["quantity"]:
                    raise StockUnavailable(
                        f"Insufficient available stock for {inv['brand']} (available: {max(0, available)})"
                    )
                cents = int(inv["unit_price_centavos"] or to_centavos(inv["unit_price"]))
                total += cents * line["quantity"]
                line_items.append((dict(inv), line["quantity"]))

            order_ref = _ref("ORD")
            now = _now()
            db.execute(
                """
                INSERT INTO orders
                    (order_ref,idempotency_key,request_hash,source,payment_method,
                     total_centavos,payment_state,fulfillment_state,
                     received_cash_centavos,overpayment_centavos,last_activity_at,
                     created_at,updated_at)
                VALUES (?,?,?,?,?,?, 'unpaid','reserved',0,0,?,?,?)
                """,
                (order_ref, str(idempotency_key), request_hash, source, payment_method, total, now, now, now),
            )
            order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for inv, quantity in line_items:
                db.execute(
                    """
                    INSERT INTO order_items
                        (order_id,inventory_id,slot,brand,unit_price_centavos,
                         quantity_ordered,quantity_reserved,quantity_dispensed,line_state)
                    VALUES (?,?,?,?,?,?,?,0,'reserved')
                    """,
                    (
                        order_id,
                        inv["id"],
                        inv["hardware_slot"],
                        inv["brand"],
                        int(inv["unit_price_centavos"] or to_centavos(inv["unit_price"])),
                        quantity,
                        quantity,
                    ),
                )
                db.execute(
                    """
                    UPDATE inventory
                    SET reserved_quantity=COALESCE(reserved_quantity,0)+?,
                        updated_at=? WHERE id=?
                    """,
                    (quantity, now, inv["id"]),
                )
            self._audit(db, order_id, "ORDER_CREATED", None, "reserved", "system", {"source": source})
        return self.get_order(order_ref)

    # ── cash session and exactly-once events ──────────────────────────────

    def start_cash(self, order_ref: str, *, no_change_consent: bool) -> Dict[str, Any]:
        if not no_change_consent:
            raise ConsentRequired("Explicit no-change consent is required before accepting cash")
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if order["payment_state"] == "awaiting_cash":
                session_row = db.execute(
                    "SELECT * FROM cash_payment_sessions WHERE order_id=?", (order["id"],)
                ).fetchone()
                if session_row and session_row["state"] == "active":
                    return {"session_ref": session_row["session_ref"], "order_ref": order_ref, "already_active": True}
                accepted = db.execute(
                    "SELECT COUNT(*) AS c FROM cash_events WHERE order_id=? AND event_state='accepted'",
                    (order["id"],),
                ).fetchone()["c"]
                if accepted:
                    raise InvalidTransition("A stopped cash session with accepted money requires staff review")
                if session_row:
                    now = _now()
                    db.execute(
                        "UPDATE cash_payment_sessions SET state='active',started_at=?,last_activity_at=?,stopped_at=NULL WHERE id=?",
                        (now, now, session_row["id"]),
                    )
                    db.execute(
                        "UPDATE orders SET updated_at=?,last_activity_at=? WHERE id=?",
                        (now, now, order["id"]),
                    )
                    return {"session_ref": session_row["session_ref"], "order_ref": order_ref, "already_active": False}
                raise OrderError("Cash session record is missing; staff review is required")
            _transition(order["payment_state"], "awaiting_cash", PAYMENT_TRANSITIONS, "payment")
            active = db.execute(
                "SELECT session_ref,order_id FROM cash_payment_sessions WHERE state='active' LIMIT 1"
            ).fetchone()
            if active and int(active["order_id"]) != int(order["id"]):
                raise ExclusiveCashSession("Another cash payment session is already active")
            session_ref = _ref("CASH")
            now = _now()
            db.execute(
                """
                INSERT INTO cash_payment_sessions
                    (session_ref,order_id,state,accepted_denominations_json,started_at,last_activity_at)
                VALUES (?,?, 'active',?,?,?)
                """,
                (session_ref, order["id"], _json(list(SUPPORTED_DENOMINATIONS_CENTAVOS)), now, now),
            )
            db.execute(
                """
                UPDATE orders SET payment_state='awaiting_cash', no_change_consent=1,
                    updated_at=?,last_activity_at=? WHERE id=?
                """,
                (now, now, order["id"]),
            )
            self._audit(db, order["id"], "CASH_STARTED", "unpaid", "awaiting_cash", "system", {})
        return {"session_ref": session_ref, "order_ref": order_ref, "already_active": False}

    def reset_cash_start(self, order_ref: str, *, reason: str = "hardware_start_failed") -> Dict[str, Any]:
        """Roll back a cash-session handshake before any cash event exists."""
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if int(order["received_cash_centavos"] or 0) or db.execute(
                "SELECT 1 FROM cash_events WHERE order_id=? AND event_state='accepted' LIMIT 1",
                (order["id"],),
            ).fetchone():
                raise InvalidTransition("Cannot roll back a cash start after money entered")
            if order["payment_state"] == "awaiting_cash":
                _transition(order["payment_state"], "unpaid", PAYMENT_TRANSITIONS, "payment")
                now = _now()
                db.execute(
                    "UPDATE orders SET payment_state='unpaid',no_change_consent=0,updated_at=?,last_activity_at=?,failure_reason=? WHERE id=?",
                    (now, now, reason, order["id"]),
                )
                db.execute(
                    "UPDATE cash_payment_sessions SET state='stopped',stopped_at=? WHERE order_id=? AND state='active'",
                    (now, order["id"]),
                )
                self._audit(db, order["id"], "CASH_START_ROLLED_BACK", "awaiting_cash", "unpaid", "system", {"reason": reason})
        return self.get_order(order_ref)

    def record_cash_event(
        self,
        order_ref: str,
        *,
        session_ref: str,
        event_id: str,
        source: str,
        raw_pulses: int,
        mapped_centavos: int,
        boot_id: str,
        sequence_no: int,
        pulse_started_at: Optional[str] = None,
        quality: str = "ok",
    ) -> Dict[str, Any]:
        if source not in {"coin", "bill"}:
            raise OrderError("Cash source must be coin or bill")
        if int(raw_pulses) < 0 or int(sequence_no) < 0:
            raise OrderError("Pulse and sequence values must be non-negative")
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            session_row = db.execute(
                "SELECT * FROM cash_payment_sessions WHERE session_ref=? AND order_id=?",
                (session_ref, order["id"]),
            ).fetchone()
            if not session_row:
                raise OrderError("Cash session does not belong to this order")

            duplicate = db.execute(
                """
                SELECT * FROM cash_events
                WHERE event_id=? OR (boot_id=? AND sequence_no=? AND source=?)
                LIMIT 1
                """,
                (str(event_id), str(boot_id), int(sequence_no), source),
            ).fetchone()
            if duplicate:
                if int(duplicate["order_id"]) != int(order["id"]):
                    raise IdempotencyConflict("Cash event identity is already bound to another order")
                return {
                    "duplicate": True,
                    "credited": duplicate["event_state"] == "accepted",
                    "event_id": duplicate["event_id"],
                    "order_ref": order_ref,
                    "order": self.get_order(order_ref),
                }

            reported_mapped = int(mapped_centavos or 0)
            expected_mapped = PulseMapping().map(source, int(raw_pulses)) or 0
            # The controller deliberately sends mapped_centavos=0: monetary
            # policy lives on the host, while firmware reports validated pulse
            # evidence. A non-zero daemon value is accepted only when it
            # exactly agrees with the host calibration.
            mapping_mismatch = bool(
                reported_mapped and reported_mapped != expected_mapped
            )
            mapped = expected_mapped
            allowed_for_source = COIN_DENOMINATIONS_CENTAVOS if source == "coin" else BILL_DENOMINATIONS_CENTAVOS
            # A train the controller flagged as `suspect` contained physically
            # impossible timing. It never credits, even when the pulse count
            # happens to land on a real denomination -- a noise burst can
            # coincidentally total 5 pulses.
            suspect = (
                str(quality or "ok").lower() == "suspect"
                or mapping_mismatch
            )
            if source == "coin":
                # Linear: any whole-peso multiple up to the ceiling is a real
                # coin train, because rapid insertions merge into one event.
                recognised = (
                    mapped > 0
                    and mapped % 100 == 0
                    and mapped <= COIN_MAX_TRAIN_CENTAVOS
                )
            else:
                recognised = mapped in allowed_for_source
            event_state = "accepted" if (recognised and not suspect) else "unknown"
            now = _now()
            cashbox = db.execute(
                "SELECT id FROM cashbox_sessions WHERE state='open' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            db.execute(
                """
                INSERT INTO cash_events
                    (event_id,session_id,order_id,source,raw_pulses,mapped_centavos,
                     event_state,boot_id,sequence_no,pulse_started_at,cashbox_session_id,received_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(event_id), session_row["id"], order["id"], source,
                    int(raw_pulses), mapped if event_state == "accepted" else 0,
                    event_state, str(boot_id), int(sequence_no), pulse_started_at,
                    cashbox["id"] if cashbox else None, now,
                ),
            )

            if event_state == "unknown":
                if mapping_mismatch:
                    reason = (
                        f"Cash mapping mismatch for {source}: {raw_pulses} pulses "
                        f"reported {reported_mapped} centavos"
                    )
                elif suspect:
                    reason = f"Suspect {source} pulse train ({raw_pulses} pulses, impossible timing)"
                else:
                    reason = f"Unknown {source} pulse train ({raw_pulses} pulses)"
                self._set_order_states(
                    db, order, payment="manual_review", fulfillment="manual_review",
                    reason=reason,
                )
                db.execute(
                    "UPDATE cash_payment_sessions SET state='manual_review',stopped_at=?,last_activity_at=? WHERE id=?",
                    (now, now, session_row["id"]),
                )
                self._audit(db, order["id"], "CASH_SUSPECT_TRAIN" if suspect else "CASH_UNKNOWN_TRAIN", order["payment_state"], "manual_review", "hardware", {"raw_pulses": raw_pulses, "source": source, "quality": quality})
                return {
                    "duplicate": False, "credited": False, "manual_review": True,
                    "stop_acceptors": True, "event_id": event_id,
                    "order_ref": order_ref, "order": self.get_order(order_ref),
                }

            if order["payment_state"] == "paid":
                # Late cash on an already-paid order. This is not exotic: a
                # coin already inside the mechanism when the last note completes
                # payment will still finish its train, and inhibit cannot recall
                # it. The customer physically parted with the money, so it has
                # to land as overpayment. Marking it 'rejected' would leave the
                # physical drawer over by that amount with nothing explaining
                # why at cashbox reconciliation.
                received = int(order["received_cash_centavos"]) + mapped
                overpayment = max(0, received - int(order["total_centavos"]))
                db.execute(
                    "UPDATE orders SET received_cash_centavos=?,overpayment_centavos=?,"
                    "updated_at=?,last_activity_at=? WHERE id=?",
                    (received, overpayment, now, now, order["id"]),
                )
                self._audit(
                    db, order["id"], "CASH_LATE_OVERPAYMENT", "paid", "paid", "hardware",
                    {"event_id": event_id, "mapped_centavos": mapped, "source": source},
                )
                return {
                    "duplicate": False, "credited": False, "overpaid": True,
                    "manual_review": False, "stop_acceptors": True,
                    "event_id": event_id, "order_ref": order_ref,
                    "order": self.get_order(order_ref),
                }

            if order["payment_state"] != "awaiting_cash" or session_row["state"] != "active":
                # Cash on an order that is not collecting at all: cancelled,
                # expired, or already under review. It is in the drawer, so the
                # event stays 'accepted' for reconciliation, but no automated
                # outcome is safe -- a human has to resolve it.
                #
                # 'cancelled' is deliberately terminal, so a stray coin must not
                # resurrect a closed order. When the transition is illegal the
                # order is left alone and the discrepancy is carried by the
                # audit trail and the cashbox count instead.
                current_payment = order["payment_state"]
                if "manual_review" in PAYMENT_TRANSITIONS.get(current_payment, set()):
                    self._set_order_states(
                        db, order, payment="manual_review", fulfillment="manual_review",
                        reason=f"Cash arrived on a non-collecting order ({source}, {mapped} centavos)",
                    )
                    db.execute(
                        "UPDATE cash_payment_sessions SET state='manual_review',stopped_at=?,"
                        "last_activity_at=? WHERE id=?",
                        (now, now, session_row["id"]),
                    )
                    resolved = "manual_review"
                else:
                    resolved = current_payment
                self._audit(
                    db, order["id"], "CASH_ON_CLOSED_ORDER", current_payment,
                    resolved, "hardware",
                    {"event_id": event_id, "mapped_centavos": mapped, "source": source},
                )
                return {
                    "duplicate": False, "credited": False, "manual_review": True,
                    "stop_acceptors": True, "event_id": event_id,
                    "order_ref": order_ref, "order": self.get_order(order_ref),
                }

            received = int(order["received_cash_centavos"]) + mapped
            due = int(order["total_centavos"])
            complete = received >= due
            next_payment = "paid" if complete else "awaiting_cash"
            overpayment = max(0, received - due)
            db.execute(
                """
                UPDATE orders SET received_cash_centavos=?,overpayment_centavos=?,
                    payment_state=?,paid_at=CASE WHEN ? THEN ? ELSE paid_at END,
                    updated_at=?,last_activity_at=? WHERE id=?
                """,
                (received, overpayment, next_payment, int(complete), now, now, now, order["id"]),
            )
            if complete:
                db.execute(
                    "UPDATE cash_payment_sessions SET state='completed',stopped_at=?,last_activity_at=? WHERE id=?",
                    (now, now, session_row["id"]),
                )
            else:
                db.execute(
                    "UPDATE cash_payment_sessions SET last_activity_at=? WHERE id=?",
                    (now, session_row["id"]),
                )
            self._audit(db, order["id"], "CASH_ACCEPTED", order["payment_state"], next_payment, "hardware", {"event_id": event_id, "mapped_centavos": mapped})
            return {
                "duplicate": False, "credited": True, "manual_review": False,
                "payment_complete": complete, "stop_acceptors": complete,
                "event_id": event_id, "order_ref": order_ref,
                "order": self.get_order(order_ref),
            }

    def stop_cash(self, order_ref: str, *, reason: str = "stopped") -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            row = db.execute(
                "SELECT * FROM cash_payment_sessions WHERE order_id=?", (order["id"],)
            ).fetchone()
            if row and row["state"] == "active":
                db.execute(
                    "UPDATE cash_payment_sessions SET state='stopped',stopped_at=? WHERE id=?",
                    (_now(), row["id"]),
                )
            if order["payment_state"] == "awaiting_cash" and int(order["received_cash_centavos"]) > 0:
                self._set_order_states(db, order, payment="manual_review", fulfillment="manual_review", reason=reason)
        return self.get_order(order_ref)

    def cancel_order(self, order_ref: str, *, reason: str = "customer_cancelled", timeout: bool = False) -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            accepted_count = db.execute(
                "SELECT COUNT(*) AS c FROM cash_events WHERE order_id=? AND event_state='accepted'",
                (order["id"],),
            ).fetchone()["c"]
            evidence_count = db.execute(
                "SELECT COUNT(*) AS c FROM cash_events WHERE order_id=? AND event_state IN ('accepted','unknown','rejected','replayed')",
                (order["id"],),
            ).fetchone()["c"]
            unknown_count = db.execute(
                "SELECT COUNT(*) AS c FROM cash_events WHERE order_id=? AND event_state='unknown'",
                (order["id"],),
            ).fetchone()["c"]
            if evidence_count and not timeout:
                raise InvalidTransition("Cash orders cannot be cancelled after money is accepted")
            if order["payment_state"] in {"paid", "refunded"}:
                raise InvalidTransition("A paid order requires staff recovery, not cancellation")
            needs_review = bool(accepted_count or unknown_count)
            target_payment = "manual_review" if needs_review else "cancelled"
            target_fulfillment = "manual_review" if needs_review else "cancelled"
            self._set_order_states(db, order, payment=target_payment, fulfillment=target_fulfillment, reason=reason)
            # A timed-out partial payment releases its reservation. An
            # unknown physical pulse keeps the reservation for staff because
            # the device may have swallowed a denomination that software could
            # not map.
            if not unknown_count or accepted_count:
                self._release_reservations(db, order["id"], reason)
            db.execute(
                "UPDATE cash_payment_sessions SET state=?,stopped_at=? WHERE order_id=? AND state='active'",
                ("manual_review" if needs_review else "cancelled", _now(), order["id"]),
            )
            self._audit(db, order["id"], "ORDER_CANCELLED" if not needs_review else "ORDER_TIMEOUT_REVIEW", order["payment_state"], target_payment, "system", {"reason": reason, "unknown_events": unknown_count})
        return self.get_order(order_ref)

    def ensure_xendit_attempt(
        self,
        order_ref: str,
        *,
        external_id: str,
        amount_centavos: int,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a provider attempt before contacting Xendit.

        The unique external id is the idempotency boundary for invoice
        creation/webhooks. A duplicate call returns the same attempt instead
        of reserving stock or creating a second payment sequence.
        """
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if int(amount_centavos) != int(order["total_centavos"]):
                raise OrderError("Xendit amount does not match the order total")
            row = db.execute("SELECT * FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone()
            if row:
                if int(row["order_id"]) != int(order["id"]):
                    raise IdempotencyConflict("External payment id belongs to another order")
                return dict(row)
            now = _now()
            db.execute(
                """
                INSERT INTO payment_attempts
                    (order_id,provider,external_id,amount_centavos,currency,status,payload_json,created_at,updated_at)
                VALUES (?, 'xendit', ?, ?, 'PHP', 'pending', ?, ?, ?)
                """,
                (order["id"], external_id, int(amount_centavos), _json(payload or {}), now, now),
            )
            self._audit(db, order["id"], "XENDIT_ATTEMPT_CREATED", order["payment_state"], order["payment_state"], "system", {"external_id": external_id})
        return dict(self.db.execute("SELECT * FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone())

    def attach_xendit_invoice(self, external_id: str, invoice_id: str) -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            row = db.execute("SELECT * FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone()
            if not row:
                raise OrderError("Payment attempt not found")
            db.execute("UPDATE payment_attempts SET provider_payment_id=?,updated_at=? WHERE external_id=?", (str(invoice_id), _now(), external_id))
        return dict(self.db.execute("SELECT * FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone())

    def save_xendit_payload(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            row = db.execute("SELECT payload_json FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone()
            if not row:
                raise OrderError("Payment attempt not found")
            existing = _decode(row["payload_json"], {})
            existing.update(payload)
            db.execute("UPDATE payment_attempts SET payload_json=?,updated_at=? WHERE external_id=?", (_json(existing), _now(), external_id))
        return dict(self.db.execute("SELECT * FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone())

    def complete_xendit_payment(
        self,
        order_ref: str,
        *,
        external_id: str,
        provider_payment_id: Optional[str],
        amount_centavos: int,
        currency: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Apply a verified Xendit callback exactly once."""
        if str(currency).upper() != "PHP":
            raise OrderError("Only PHP Xendit payments are accepted")
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if str(external_id) != str(order["external_payment_id"] or external_id):
                # Before the first callback the order has no provider id; the
                # attempt lookup below still binds it to this exact order.
                attempt = db.execute("SELECT order_id FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone()
                if not attempt or int(attempt["order_id"]) != int(order["id"]):
                    raise OrderError("Xendit external id does not match order")
            if int(amount_centavos) != int(order["total_centavos"]):
                raise OrderError("Xendit callback amount does not match order total")
            attempt = db.execute("SELECT * FROM payment_attempts WHERE external_id=?", (external_id,)).fetchone()
            if not attempt or int(attempt["order_id"]) != int(order["id"]):
                raise OrderError("Unknown Xendit payment attempt")
            now = _now()
            db.execute(
                """
                UPDATE payment_attempts SET provider_payment_id=COALESCE(?,provider_payment_id),
                    amount_centavos=?,currency='PHP',status='paid',payload_json=?,verified_at=COALESCE(verified_at,?),updated_at=?
                WHERE external_id=?
                """,
                (provider_payment_id, int(amount_centavos), _json(payload or {}), now, now, external_id),
            )
            if order["payment_state"] != "paid":
                _transition(order["payment_state"], "paid", PAYMENT_TRANSITIONS, "payment")
                db.execute(
                    """
                    UPDATE orders SET payment_state='paid',received_cash_centavos=total_centavos,
                        overpayment_centavos=0,external_payment_id=?,paid_at=?,updated_at=?,last_activity_at=?
                    WHERE id=?
                    """,
                    (external_id, now, now, now, order["id"]),
                )
                self._audit(db, order["id"], "XENDIT_PAID", order["payment_state"], "paid", "xendit", {"external_id": external_id})
            else:
                db.execute("UPDATE orders SET external_payment_id=COALESCE(external_payment_id,?),updated_at=? WHERE id=?", (external_id, now, order["id"]))
        return self.get_order(order_ref)

    def record_cashier_payment(
        self,
        order_ref: str,
        *,
        received_centavos: int,
        actor: str = "cashier",
    ) -> Dict[str, Any]:
        """Credit a cashier-counted payment into the same order ledger.

        Cashier tender is not a hardware pulse train, so it is stored as a
        completed cash session with a ledger event whose source is ``bill``
        and raw pulse evidence is zero. Hardware kiosk routes never use this
        shortcut; they must supply calibrated pulse evidence.
        """
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            received = int(received_centavos)
            if received < int(order["total_centavos"]):
                raise OrderError("Insufficient cashier tender")
            if order["payment_state"] == "paid":
                return self.get_order(order_ref)
            _transition(order["payment_state"], "paid", PAYMENT_TRANSITIONS, "payment")
            now = _now()
            session_ref = _ref("CASHIER")
            db.execute(
                "INSERT INTO cash_payment_sessions (session_ref,order_id,state,accepted_denominations_json,started_at,last_activity_at,stopped_at) VALUES (?,?,'completed','[]',?,?,?)",
                (session_ref, order["id"], now, now, now),
            )
            session_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            cashbox = db.execute(
                "SELECT id FROM cashbox_sessions WHERE state='open' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            db.execute(
                "INSERT INTO cash_events (event_id,session_id,order_id,source,raw_pulses,mapped_centavos,event_state,boot_id,sequence_no,cashbox_session_id,received_at,acknowledged_at) VALUES (?,?,?,'bill',0,?,'accepted',?,?,?,?,?)",
                (
                    _ref("CE"), session_id, order["id"], received,
                    f"cashier-{actor}", int(session_id),
                    cashbox["id"] if cashbox else None,
                    now, now,
                ),
            )
            db.execute(
                "UPDATE orders SET payment_state='paid',received_cash_centavos=?,overpayment_centavos=?,paid_at=?,updated_at=?,last_activity_at=? WHERE id=?",
                (received, max(0, received - int(order["total_centavos"])), now, now, now, order["id"]),
            )
            self._audit(db, order["id"], "CASHIER_PAYMENT_ACCEPTED", order["payment_state"], "paid", actor, {"received_centavos": received})
        return self.get_order(order_ref)

    def finalize_payment_only_sale(
        self,
        order_ref: str,
        *,
        actor: str = "payment",
    ) -> Dict[str, Any]:
        """Commit inventory and create a receipt without running a motor.

        This is the temporary real-POS completion path requested for cash
        acceptance testing. Payment, inventory deduction, reservation release,
        stock logs, receipt creation, and the completion marker share one
        ``BEGIN IMMEDIATE`` transaction. Replaying the call therefore returns
        the same sale without subtracting stock a second time.
        """
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if order["payment_state"] != "paid":
                raise InvalidTransition("Only a paid order can commit stock")
            if order["stock_committed_at"]:
                return self.get_order(order_ref)
            if order["fulfillment_state"] not in {"reserved", "completed"}:
                raise InvalidTransition(
                    "Payment-only completion cannot run after motor fulfillment starts"
                )
            if db.execute(
                "SELECT 1 FROM dispense_jobs WHERE order_id=? LIMIT 1",
                (order["id"],),
            ).fetchone():
                raise InvalidTransition(
                    "Payment-only completion cannot run for an order with motor jobs"
                )

            lines = db.execute(
                "SELECT * FROM order_items WHERE order_id=? ORDER BY id",
                (order["id"],),
            ).fetchall()
            now = _now()
            for line in lines:
                quantity = int(line["quantity_reserved"])
                if quantity != int(line["quantity_ordered"]):
                    raise StockUnavailable(
                        f"Reservation changed before sale completion for {line['brand']}"
                    )
                inventory = db.execute(
                    "SELECT * FROM inventory WHERE id=?", (line["inventory_id"],)
                ).fetchone()
                if (
                    not inventory
                    or int(inventory["stock_quantity"]) < quantity
                    or int(inventory["reserved_quantity"] or 0) < quantity
                ):
                    raise StockUnavailable(
                        f"Reserved stock is no longer available for {line['brand']}"
                    )
                before = int(inventory["stock_quantity"])
                after = before - quantity
                db.execute(
                    """
                    UPDATE inventory
                    SET stock_quantity=?, reserved_quantity=reserved_quantity-?,
                        updated_at=?
                    WHERE id=?
                    """,
                    (after, quantity, now, inventory["id"]),
                )
                db.execute(
                    """
                    INSERT INTO stock_logs
                        (inventory_id,brand,change_type,quantity_change,
                         quantity_before,quantity_after,reference,performed_by)
                    VALUES (?,?,?,?,?,?,?,NULL)
                    """,
                    (
                        inventory["id"], inventory["brand"], "sale", -quantity,
                        before, after, f"PAYMENT_ONLY:{order_ref}:{line['id']}",
                    ),
                )
                # No unit is labelled dispensed: motors are intentionally out
                # of scope. ``released`` here means the reservation has been
                # consumed by the recorded sale, not returned to availability.
                db.execute(
                    "UPDATE order_items SET quantity_reserved=0,line_state='released' WHERE id=?",
                    (line["id"],),
                )

            transaction_id = self._create_final_transaction_locked(db, order)
            db.execute(
                """
                UPDATE orders
                SET fulfillment_state='completed', fulfillment_result='reserved',
                    completion_mode='payment_only', stock_committed_at=?,
                    transaction_id=?, completed_at=?, updated_at=?
                WHERE id=?
                """,
                (now, transaction_id, now, now, order["id"]),
            )
            self._audit(
                db, order["id"], "PAYMENT_ONLY_SALE_COMPLETED",
                order["fulfillment_state"], "completed", actor,
                {
                    "transaction_id": transaction_id,
                    "motor_command_sent": False,
                    "stock_committed": True,
                },
            )
        return self.get_order(order_ref)

    def expire_cash_sessions(self, *, timeout_seconds: int = PAYMENT_TIMEOUT_SECONDS, now: Optional[datetime] = None) -> List[str]:
        now_dt = now or datetime.now()
        threshold = now_dt - timedelta(seconds=timeout_seconds)
        rows = self.db.execute(
            "SELECT session_ref,last_activity_at FROM cash_payment_sessions WHERE state='active'"
        ).fetchall()
        expired: List[str] = []
        for row in rows:
            try:
                activity = datetime.strptime(row["last_activity_at"], "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue
            if activity <= threshold:
                order_row = self.db.execute(
                    "SELECT order_ref FROM orders o JOIN cash_payment_sessions s ON s.order_id=o.id WHERE s.session_ref=?",
                    (row["session_ref"],),
                ).fetchone()
                if order_row:
                    self.cancel_order(order_row["order_ref"], reason="cash_timeout", timeout=True)
                    expired.append(order_row["order_ref"])
        return expired

    # ── dispensing ───────────────────────────────────────────────────────

    def enqueue_dispense_jobs(self, order_ref: str) -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if order["payment_state"] != "paid":
                raise InvalidTransition("Only paid orders can be dispensed")
            existing = db.execute(
                "SELECT COUNT(*) AS c FROM dispense_jobs WHERE order_id=?", (order["id"],)
            ).fetchone()["c"]
            if existing:
                return self.get_order(order_ref)
            lines = db.execute(
                "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)
            ).fetchall()
            sequence = 0
            for line in lines:
                profile = db.execute(
                    "SELECT profile_version FROM motion_profiles WHERE slot=?", (line["slot"],)
                ).fetchone()
                if not profile:
                    raise OrderError(f"No motion profile configured for slot {line['slot']}")
                for _ in range(int(line["quantity_ordered"])):
                    sequence += 1
                    job_id = _ref("JOB")
                    db.execute(
                        """
                        INSERT INTO dispense_jobs
                            (job_id,order_id,order_item_id,unit_sequence,slot,profile_version,
                             state,controller_request_id)
                        VALUES (?,?,?,?,?,?, 'queued',?)
                        """,
                        (job_id, order["id"], line["id"], sequence, line["slot"], profile["profile_version"], job_id),
                    )
                db.execute(
                    "UPDATE order_items SET line_state='dispensing' WHERE id=?", (line["id"],)
                )
            self._set_order_states(db, order, fulfillment="dispensing")
            self._audit(db, order["id"], "DISPENSE_JOBS_CREATED", order["fulfillment_state"], "dispensing", "system", {"count": sequence})
        return self.get_order(order_ref)

    def next_dispense_job(self, order_ref: str) -> Optional[Dict[str, Any]]:
        order = self._order_row(order_ref)
        row = self.db.execute(
            """
            SELECT j.* FROM dispense_jobs j
            WHERE j.order_id=? AND j.state='queued'
              AND NOT EXISTS (
                  SELECT 1 FROM dispense_jobs prior
                  WHERE prior.order_id=j.order_id
                    AND prior.unit_sequence<j.unit_sequence
                    AND prior.state NOT IN ('done_unverified','cancelled')
              )
            ORDER BY j.unit_sequence LIMIT 1
            """,
            (order["id"],),
        ).fetchone()
        return dict(row) if row else None

    def started_dispense_job(self, order_ref: str) -> Optional[Dict[str, Any]]:
        """Return the one in-flight job that needs controller reconciliation."""
        order = self._order_row(order_ref)
        row = self.db.execute(
            """
            SELECT * FROM dispense_jobs
            WHERE order_id=? AND state='started'
            ORDER BY unit_sequence LIMIT 1
            """,
            (order["id"],),
        ).fetchone()
        return dict(row) if row else None

    def claim_dispense_job(self, job_id: str) -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            row = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise OrderError("Dispense job not found")
            if row["state"] == "queued":
                prior = db.execute(
                    """
                    SELECT COUNT(*) AS c FROM dispense_jobs
                    WHERE order_id=? AND unit_sequence<?
                      AND state NOT IN ('done_unverified','cancelled')
                    """,
                    (row["order_id"], row["unit_sequence"]),
                ).fetchone()["c"]
                if prior:
                    raise InvalidTransition("Dispense jobs must execute sequentially")
                db.execute(
                    "UPDATE dispense_jobs SET state='started',started_at=? WHERE job_id=?",
                    (_now(), job_id),
                )
            elif row["state"] in {"started", "done_unverified"}:
                pass
            else:
                raise InvalidTransition(f"Cannot claim job in state {row['state']}")
        return dict(self.db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone())

    def record_dispense_event(
        self,
        job_id: str,
        event: str,
        *,
        ack_result: str = "ack",
        error_code: Optional[str] = None,
        error_detail: Optional[str] = None,
        controller_result: Optional[str] = None,
    ) -> Dict[str, Any]:
        event = str(event).upper()
        if event not in {"DISPENSE_STARTED", "DISPENSE_DONE_UNVERIFIED", "DISPENSE_FAILED"}:
            raise OrderError(f"Unknown dispense event {event}")
        if event == "DISPENSE_STARTED":
            return self.claim_dispense_job(job_id)
        if event == "DISPENSE_FAILED":
            return self.fail_dispense_job(
                job_id, error_code=error_code or "CONTROLLER_FAILURE",
                error_detail=error_detail or "Controller reported failure",
                controller_result=controller_result or "unknown",
            )

        db = self.db
        with _immediate(db):
            job = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job:
                raise OrderError("Dispense job not found")
            if job["state"] == "done_unverified":
                return self.get_order_by_id(job["order_id"])
            if job["state"] not in {"queued", "started"}:
                raise InvalidTransition(f"Cannot complete job in state {job['state']}")
            inv = db.execute(
                "SELECT * FROM inventory WHERE hardware_slot=?", (job["slot"],)
            ).fetchone()
            if not inv or int(inv["stock_quantity"]) <= 0 or int(inv["reserved_quantity"] or 0) <= 0:
                self._fail_job_locked(db, job, "INVENTORY_STATE", "Reserved stock was not available", "unknown")
                return self.get_order_by_id(job["order_id"])
            now = _now()
            db.execute(
                """
                UPDATE inventory SET stock_quantity=stock_quantity-1,
                    reserved_quantity=reserved_quantity-1,updated_at=? WHERE id=?
                """,
                (now, inv["id"]),
            )
            db.execute(
                """
                INSERT INTO stock_logs
                    (inventory_id,brand,change_type,quantity_change,quantity_before,
                     quantity_after,reference,performed_by)
                VALUES (?,?,?,?,?,?,?,NULL)
                """,
                (inv["id"], inv["brand"], "sale", -1, inv["stock_quantity"], int(inv["stock_quantity"]) - 1, f"DISPENSE:{job_id}:UNVERIFIED"),
            )
            db.execute(
                """
                UPDATE dispense_jobs SET state='done_unverified',ack_result=?,
                    controller_result=?,ended_at=? WHERE job_id=?
                """,
                (ack_result, controller_result or "executed", now, job_id),
            )
            line = db.execute("SELECT * FROM order_items WHERE id=?", (job["order_item_id"],)).fetchone()
            next_dispensed = int(line["quantity_dispensed"]) + 1
            next_reserved = max(0, int(line["quantity_reserved"]) - 1)
            line_state = "dispensed" if next_dispensed >= int(line["quantity_ordered"]) else "dispensing"
            db.execute(
                "UPDATE order_items SET quantity_dispensed=?,quantity_reserved=?,line_state=? WHERE id=?",
                (next_dispensed, next_reserved, line_state, line["id"]),
            )
            order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
            remaining = db.execute(
                "SELECT COUNT(*) AS c FROM dispense_jobs WHERE order_id=? AND state NOT IN ('done_unverified','cancelled')",
                (job["order_id"],),
            ).fetchone()["c"]
            if remaining == 0:
                transaction_id = self._create_final_transaction_locked(db, order)
                db.execute(
                    "UPDATE orders SET fulfillment_state='completed',fulfillment_result='dispensed_unverified',transaction_id=?,completed_at=?,updated_at=? WHERE id=?",
                    (transaction_id, now, now, order["id"]),
                )
                self._audit(db, order["id"], "ORDER_COMPLETED_UNVERIFIED", order["fulfillment_state"], "completed", "controller", {"transaction_id": transaction_id})
            else:
                self._audit(db, order["id"], "DISPENSE_DONE_UNVERIFIED", order["fulfillment_state"], order["fulfillment_state"], "controller", {"job_id": job_id})
            order_ref = order["order_ref"]
        return self.get_order(order_ref)

    def fail_dispense_job(
        self,
        job_id: str,
        *,
        error_code: str,
        error_detail: str,
        controller_result: str = "unknown",
    ) -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            job = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job:
                raise OrderError("Dispense job not found")
            if job["state"] == "done_unverified":
                return self.get_order_by_id(job["order_id"])
            self._fail_job_locked(db, job, error_code, error_detail, controller_result)
            order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
            return_order_ref = order["order_ref"]
        return self.get_order(return_order_ref)

    def _fail_job_locked(self, db, job, error_code: str, error_detail: str, controller_result: str) -> None:
        now = _now()
        db.execute(
            """
            UPDATE dispense_jobs SET state='manual_review',error_code=?,error_detail=?,
                controller_result=?,ack_result='nack',ended_at=? WHERE job_id=?
            """,
            (error_code, error_detail, controller_result, now, job["job_id"]),
        )
        order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
        self._set_order_states(db, order, fulfillment="manual_review", reason=f"{error_code}: {error_detail}")
        # An explicit controller result of unexecuted permits reservation
        # release. Unknown physical state stays reserved for staff review.
        if controller_result == "unexecuted":
            self._release_reservations(db, order["id"], f"dispense:{job['job_id']}:unexecuted")
        else:
            db.execute(
                "UPDATE order_items SET line_state='manual_review' WHERE order_id=? AND quantity_dispensed<quantity_ordered",
                (order["id"],),
            )
        self._audit(db, order["id"], "DISPENSE_FAILED", order["fulfillment_state"], "manual_review", "controller", {"job_id": job["job_id"], "error_code": error_code, "controller_result": controller_result})

    def get_order_by_id(self, order_id: int) -> Dict[str, Any]:
        row = self.db.execute("SELECT order_ref FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise OrderNotFound("Order not found")
        return self.get_order(row["order_ref"])

    # ── manual recovery, profiles, and cashbox ───────────────────────────

    def retry_unexecuted_dispense(self, job_id: str, *, actor: str = "staff") -> Dict[str, Any]:
        """Re-queue only a controller-confirmed unexecuted job.

        A lost/unknown controller result is deliberately not retryable. The
        physical actuator may already have moved, so staff must query or
        inspect it first. Re-queueing also creates a fresh reservation for the
        one unit that the failed job still needs.
        """
        db = self.db
        with _immediate(db):
            job = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["state"] not in {"manual_review", "failed"}:
                raise InvalidTransition("Only an unresolved dispense job can be retried")
            if job["controller_result"] != "unexecuted":
                raise HardwareJobUnknown("Retry is allowed only after the controller confirms the job was unexecuted")
            prior = db.execute(
                "SELECT COUNT(*) AS c FROM dispense_jobs WHERE order_id=? AND unit_sequence<? AND state NOT IN ('done_unverified','cancelled')",
                (job["order_id"], job["unit_sequence"]),
            ).fetchone()["c"]
            if prior:
                raise InvalidTransition("Earlier dispense jobs must be resolved before retrying this job")
            inv = db.execute("SELECT * FROM inventory WHERE id=(SELECT inventory_id FROM order_items WHERE id=?)", (job["order_item_id"],)).fetchone()
            if not inv or int(inv["stock_quantity"]) - int(inv["reserved_quantity"] or 0) < 1:
                raise StockUnavailable("No available unit to reserve for the retry")
            line = db.execute("SELECT * FROM order_items WHERE id=?", (job["order_item_id"],)).fetchone()
            now = _now()
            db.execute(
                "UPDATE inventory SET reserved_quantity=reserved_quantity+1,updated_at=? WHERE id=?",
                (now, inv["id"]),
            )
            db.execute(
                "UPDATE order_items SET quantity_reserved=quantity_reserved+1,line_state='dispensing' WHERE id=?",
                (line["id"],),
            )
            db.execute(
                """
                UPDATE dispense_jobs SET state='queued',ack_result=NULL,controller_result=NULL,
                    error_code=NULL,error_detail=NULL,started_at=NULL,ended_at=NULL WHERE job_id=?
                """,
                (job_id,),
            )
            order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
            if order["fulfillment_state"] == "manual_review":
                _transition(order["fulfillment_state"], "dispensing", FULFILLMENT_TRANSITIONS, "fulfillment")
                db.execute("UPDATE orders SET fulfillment_state='dispensing',fulfillment_result='dispensing',updated_at=? WHERE id=?", (now, order["id"]))
            self._audit(db, order["id"], "DISPENSE_RETRY_QUEUED", order["fulfillment_state"], "dispensing", actor, {"job_id": job_id})
            ref = order["order_ref"]
        return self.get_order(ref)

    def return_dispensed_to_stock(self, job_id: str, *, actor: str = "staff") -> Dict[str, Any]:
        """Record an explicit physical return; financial refund is separate."""
        db = self.db
        with _immediate(db):
            job = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["state"] != "done_unverified":
                raise InvalidTransition("Only a completed actuator job can be returned to stock")
            if job["restocked_at"]:
                return self.get_order_by_id(job["order_id"])
            inv = db.execute("SELECT * FROM inventory WHERE hardware_slot=?", (job["slot"],)).fetchone()
            if not inv:
                raise OrderError("Inventory slot no longer exists")
            now = _now()
            db.execute(
                "UPDATE inventory SET stock_quantity=stock_quantity+1,updated_at=? WHERE id=?",
                (now, inv["id"]),
            )
            db.execute(
                """
                INSERT INTO stock_logs
                    (inventory_id,brand,change_type,quantity_change,quantity_before,quantity_after,reference,performed_by)
                VALUES (?,?,?,?,?,?,?,NULL)
                """,
                (inv["id"], inv["brand"], "void_return", 1, inv["stock_quantity"], int(inv["stock_quantity"]) + 1, f"RETURN:{job_id}"),
            )
            db.execute(
                "UPDATE dispense_jobs SET restocked_at=?,restocked_by=? WHERE job_id=?",
                (now, actor, job_id),
            )
            line = db.execute("SELECT * FROM order_items WHERE id=?", (job["order_item_id"],)).fetchone()
            db.execute(
                "UPDATE order_items SET quantity_dispensed=MAX(0,quantity_dispensed-1),line_state='manual_review' WHERE id=?",
                (line["id"],),
            )
            order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
            _set_order_states(db, order, fulfillment="manual_review", reason="Staff confirmed a physical return to stock")
            self._audit(db, order["id"], "PHYSICAL_RETURN_TO_STOCK", order["fulfillment_state"], "manual_review", actor, {"job_id": job_id, "stock_restored": True})
            ref = order["order_ref"]
        return self.get_order(ref)

    def confirm_physical_dispensed(self, job_id: str, *, actor: str = "staff") -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            job = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["state"] not in {"manual_review", "failed"}:
                raise InvalidTransition("Only an unresolved dispense job can be confirmed")
            # The same atomic path used for controller completion is not
            # re-entered because this method already owns the write lock.
            if job["controller_result"] == "executed":
                raise InvalidTransition("Controller already confirmed execution; query job result")
            inv = db.execute("SELECT * FROM inventory WHERE hardware_slot=?", (job["slot"],)).fetchone()
            if not inv or int(inv["stock_quantity"]) <= 0:
                raise StockUnavailable("Physical confirmation has no on-hand unit to deduct")
            now = _now()
            db.execute("UPDATE inventory SET stock_quantity=stock_quantity-1, reserved_quantity=MAX(0,reserved_quantity-1),updated_at=? WHERE id=?", (now, inv["id"]))
            db.execute("INSERT INTO stock_logs (inventory_id,brand,change_type,quantity_change,quantity_before,quantity_after,reference,performed_by) VALUES (?,?,?,?,?,?,?,NULL)", (inv["id"], inv["brand"], "sale", -1, inv["stock_quantity"], int(inv["stock_quantity"]) - 1, f"MANUAL_DISPENSE:{job_id}"))
            db.execute("UPDATE dispense_jobs SET state='done_unverified',controller_result='staff_confirmed',ack_result='manual_ack',ended_at=? WHERE job_id=?", (now, job_id))
            line = db.execute("SELECT * FROM order_items WHERE id=?", (job["order_item_id"],)).fetchone()
            db.execute("UPDATE order_items SET quantity_dispensed=quantity_dispensed+1,quantity_reserved=MAX(0,quantity_reserved-1),line_state=CASE WHEN quantity_dispensed+1>=quantity_ordered THEN 'dispensed' ELSE 'dispensing' END WHERE id=?", (line["id"],))
            order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
            remaining = db.execute("SELECT COUNT(*) AS c FROM dispense_jobs WHERE order_id=? AND state NOT IN ('done_unverified','cancelled')", (order["id"],)).fetchone()["c"]
            if remaining == 0:
                tx_id = self._create_final_transaction_locked(db, order)
                db.execute("UPDATE orders SET fulfillment_state='completed',fulfillment_result='dispensed_unverified',payment_state=CASE WHEN payment_state='manual_review' THEN 'paid' ELSE payment_state END,transaction_id=?,completed_at=?,updated_at=? WHERE id=?", (tx_id, now, now, order["id"]))
            else:
                db.execute("UPDATE orders SET fulfillment_state='dispensing',fulfillment_result='dispensing',updated_at=? WHERE id=?", (now, order["id"]))
            self._audit(db, order["id"], "MANUAL_CONFIRM_DISPENSED", order["fulfillment_state"], "completed" if remaining == 0 else "dispensing", actor, {"job_id": job_id})
            ref = order["order_ref"]
        return self.get_order(ref)

    def confirm_no_dispense(self, job_id: str, *, actor: str = "staff") -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            job = db.execute("SELECT * FROM dispense_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["state"] not in {"manual_review", "failed"}:
                raise InvalidTransition("Only an unresolved dispense job can be marked no-dispense")
            order = db.execute("SELECT * FROM orders WHERE id=?", (job["order_id"],)).fetchone()
            self._release_reservations(db, order["id"], f"manual_no_dispense:{job_id}")
            db.execute("UPDATE dispense_jobs SET state='failed',controller_result='unexecuted',ack_result='manual_nack',ended_at=? WHERE job_id=?", (_now(), job_id))
            self._set_order_states(db, order, fulfillment="manual_review", reason="Staff confirmed no dispense")
            self._audit(db, order["id"], "MANUAL_CONFIRM_NO_DISPENSE", order["fulfillment_state"], "manual_review", actor, {"job_id": job_id})
            ref = order["order_ref"]
        return self.get_order(ref)

    def refund_order(self, order_ref: str, *, actor: str = "staff", reason: str = "staff_refund") -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            order = self._order_row(order_ref)
            if order["payment_state"] == "refunded":
                return self.get_order(order_ref)
            _transition(order["payment_state"], "refunded", PAYMENT_TRANSITIONS, "payment")
            now = _now()
            # A financial refund never restores physical stock, but units that
            # were only reserved must stop blocking the catalog. Already
            # dispensed units remain deducted until an explicit physical
            # return-to-stock action is recorded.
            has_undispensed = db.execute(
                "SELECT 1 FROM order_items WHERE order_id=? AND quantity_reserved>0 LIMIT 1",
                (order["id"],),
            ).fetchone()
            if has_undispensed:
                self._release_reservations(db, order["id"], f"refund:{reason}")
            fulfillment_target = None
            if order["fulfillment_state"] in {"reserved", "dispensing"}:
                fulfillment_target = "cancelled"
            if fulfillment_target:
                _transition(order["fulfillment_state"], fulfillment_target, FULFILLMENT_TRANSITIONS, "fulfillment")
            sets = ["payment_state='refunded'", "failure_reason=?", "updated_at=?"]
            params: List[Any] = [reason, now]
            if fulfillment_target:
                sets.append("fulfillment_state=?")
                params.append(fulfillment_target)
                sets.append("fulfillment_result=?")
                params.append(fulfillment_target)
            params.append(order["id"])
            db.execute(f"UPDATE orders SET {','.join(sets)} WHERE id=?", params)
            self._audit(db, order["id"], "REFUND_RECORDED", order["payment_state"], "refunded", actor, {"reason": reason, "physical_stock_restored": False})
        return self.get_order(order_ref)

    def list_profiles(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.db.execute("SELECT * FROM motion_profiles ORDER BY slot").fetchall()]

    def update_profile(self, slot: int, profile: Dict[str, Any], *, actor: str = "staff") -> Dict[str, Any]:
        values = {
            "position_a_us": int(profile["position_a_us"]),
            "position_b_us": int(profile["position_b_us"]),
            "travel_time_ms": int(profile["travel_time_ms"]),
            "b_dwell_ms": int(profile["b_dwell_ms"]),
            "return_settle_ms": int(profile["return_settle_ms"]),
            "cooldown_ms": int(profile["cooldown_ms"]),
            "profile_version": str(profile["profile_version"]),
            "calibrated": 1 if profile.get("calibrated", False) else 0,
        }
        if not 500 <= values["position_a_us"] <= 2500 or not 500 <= values["position_b_us"] <= 2500:
            raise OrderError("Servo pulse widths must be within 500–2500 µs")
        db = self.db
        with _immediate(db):
            db.execute(
                """
                UPDATE motion_profiles SET position_a_us=?,position_b_us=?,travel_time_ms=?,
                    b_dwell_ms=?,return_settle_ms=?,cooldown_ms=?,profile_version=?,
                    calibrated=?,updated_at=? WHERE slot=?
                """,
                (values["position_a_us"], values["position_b_us"], values["travel_time_ms"], values["b_dwell_ms"], values["return_settle_ms"], values["cooldown_ms"], values["profile_version"], values["calibrated"], _now(), int(slot)),
            )
            row = db.execute("SELECT * FROM motion_profiles WHERE slot=?", (int(slot),)).fetchone()
            if not row:
                raise OrderError("Motion profile slot not found")
        return dict(row)

    def open_cashbox(self, *, staff_id: Optional[int] = None, notes: str = "") -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            active = db.execute("SELECT * FROM cashbox_sessions WHERE state='open' LIMIT 1").fetchone()
            if active:
                return dict(active)
            row = db.execute("SELECT COUNT(*) AS c FROM cashbox_sessions").fetchone()
            session_ref = f"BOX-{int(row['c']) + 1:06d}"
            db.execute("INSERT INTO cashbox_sessions (session_ref,state,opening_staff_id,notes) VALUES (?, 'open', ?, ?)", (session_ref, staff_id if staff_id and staff_id > 0 else None, notes))
        return dict(db.execute("SELECT * FROM cashbox_sessions WHERE session_ref=?", (session_ref,)).fetchone())

    def close_cashbox(self, session_ref: str, *, staff_id: int, counted_total_centavos: int, notes: str = "") -> Dict[str, Any]:
        db = self.db
        with _immediate(db):
            row = db.execute("SELECT * FROM cashbox_sessions WHERE session_ref=? AND state='open'", (session_ref,)).fetchone()
            if not row:
                raise OrderError("Open cashbox session not found")
            counts = db.execute("SELECT mapped_centavos,COUNT(*) AS count FROM cash_events WHERE event_state='accepted' AND cashbox_session_id=? GROUP BY mapped_centavos", (row["id"],)).fetchall()
            counts_dict = {str(int(r["mapped_centavos"])): int(r["count"]) for r in counts}
            expected = db.execute("SELECT COALESCE(SUM(mapped_centavos),0) AS total FROM cash_events WHERE event_state='accepted' AND cashbox_session_id=?", (row["id"],)).fetchone()["total"]
            variance = int(counted_total_centavos) - int(expected)
            now = _now()
            db.execute("UPDATE cashbox_sessions SET state='closed',expected_counts_json=?,expected_total_centavos=?,staff_counted_total_centavos=?,variance_centavos=?,closing_staff_id=?,notes=?,closed_at=? WHERE id=?", (_json(counts_dict), expected, int(counted_total_centavos), variance, staff_id, notes, now, row["id"]))
        return dict(db.execute("SELECT * FROM cashbox_sessions WHERE id=?", (row["id"],)).fetchone())

    def accounting_summary(self) -> Dict[str, Any]:
        """Return gross sales, tender, overage, refunds, and drawer variance."""
        db = self.db
        totals = db.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN transaction_id IS NOT NULL AND payment_state != 'refunded' THEN total_centavos ELSE 0 END),0) AS sales,
                COALESCE(SUM(CASE WHEN payment_state='refunded' THEN total_centavos ELSE 0 END),0) AS refunded,
                COALESCE(SUM(CASE WHEN payment_method IN ('cash','cashier_cash') THEN received_cash_centavos ELSE 0 END),0) AS received_cash,
                COALESCE(SUM(CASE WHEN payment_method IN ('cash','cashier_cash') THEN overpayment_centavos ELSE 0 END),0) AS overpayment
            FROM orders
            """
        ).fetchone()
        drawer = db.execute(
            """
            SELECT
                COALESCE(SUM(expected_total_centavos),0) AS expected_cashbox,
                COALESCE(SUM(CASE WHEN state='closed' THEN variance_centavos ELSE 0 END),0) AS closed_variance,
                COUNT(CASE WHEN state='open' THEN 1 END) AS open_count
            FROM cashbox_sessions
            """
        ).fetchone()
        result = {
            "sales_revenue_centavos": int(totals["sales"]),
            "refunded_centavos": int(totals["refunded"]),
            "received_cash_centavos": int(totals["received_cash"]),
            "overpayment_centavos": int(totals["overpayment"]),
            "expected_cashbox_centavos": int(drawer["expected_cashbox"]),
            "closed_cashbox_variance_centavos": int(drawer["closed_variance"]),
            "open_cashbox_count": int(drawer["open_count"]),
        }
        for key, value in list(result.items()):
            if key.endswith("_centavos"):
                base = key.removesuffix("_centavos")
                result[base] = value / 100
                result[f"{base}_display"] = format_php(value, centavos=True)
        return result

    # ── internal transaction helpers ─────────────────────────────────────

    def _set_order_states(self, db, order, *, payment: Optional[str] = None, fulfillment: Optional[str] = None, reason: Optional[str] = None) -> None:
        if payment:
            _transition(order["payment_state"], payment, PAYMENT_TRANSITIONS, "payment")
        if fulfillment:
            _transition(order["fulfillment_state"], fulfillment, FULFILLMENT_TRANSITIONS, "fulfillment")
        now = _now()
        sets = ["updated_at=?", "last_activity_at=?"]
        params: List[Any] = [now, now]
        if payment:
            sets.append("payment_state=?")
            params.append(payment)
        if fulfillment:
            sets.append("fulfillment_state=?")
            params.append(fulfillment)
            result = "dispensed_unverified" if fulfillment == "completed" else fulfillment
            sets.append("fulfillment_result=?")
            params.append(result)
        if reason is not None:
            sets.append("failure_reason=?")
            params.append(reason)
        params.append(order["id"])
        db.execute(f"UPDATE orders SET {','.join(sets)} WHERE id=?", params)

    def _release_reservations(self, db, order_id: int, reason: str) -> None:
        rows = db.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
        now = _now()
        for row in rows:
            release = int(row["quantity_reserved"])
            if release:
                db.execute(
                    "UPDATE inventory SET reserved_quantity=MAX(0,COALESCE(reserved_quantity,0)-?),updated_at=? WHERE id=?",
                    (release, now, row["inventory_id"]),
                )
            next_state = "released" if int(row["quantity_dispensed"]) == 0 else "manual_review"
            db.execute("UPDATE order_items SET quantity_reserved=0,line_state=? WHERE id=?", (next_state, row["id"]))
        self._audit(db, order_id, "RESERVATIONS_RELEASED", None, None, "system", {"reason": reason})

    def _create_final_transaction_locked(self, db, order) -> int:
        if order["transaction_id"]:
            return int(order["transaction_id"])
        day = datetime.now().strftime("%Y%m%d")
        count = db.execute("SELECT COUNT(*) AS c FROM transactions WHERE transaction_ref LIKE ?", (f"TXN-{day}-%",)).fetchone()["c"]
        ref = f"TXN-{day}-{int(count) + 1:04d}"
        while db.execute("SELECT 1 FROM transactions WHERE transaction_ref=?", (ref,)).fetchone():
            count += 1
            ref = f"TXN-{day}-{int(count) + 1:04d}"
        items = db.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall()
        total_qty = sum(int(row["quantity_ordered"]) for row in items)
        db.execute(
            """
            INSERT INTO transactions
                (transaction_ref,total_amount,payment_method,amount_tendered,change_amount,
                 item_count,status,cashier_id,customer_note)
            VALUES (?,?,?,?,?,?, 'completed',NULL,?)
            """,
            (ref, int(order["total_centavos"]) / 100, order["payment_method"], int(order["received_cash_centavos"]) / 100, 0.0, total_qty, f"Order {order['order_ref']}"),
        )
        transaction_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for row in items:
            subtotal = int(row["unit_price_centavos"]) * int(row["quantity_ordered"]) / 100
            db.execute(
                "INSERT INTO transaction_items (transaction_id,inventory_id,brand,quantity,unit_price,subtotal) VALUES (?,?,?,?,?,?)",
                (transaction_id, row["inventory_id"], row["brand"], row["quantity_ordered"], int(row["unit_price_centavos"]) / 100, subtotal),
            )
        return int(transaction_id)

    def _audit(self, db, order_id: int, event_type: str, from_state: Optional[str], to_state: Optional[str], actor: str, detail: Dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO order_audit_events (order_id,event_type,from_state,to_state,actor,detail_json) VALUES (?,?,?,?,?,?)",
            (order_id, event_type, from_state, to_state, actor, _json(detail)),
        )


def order_service() -> OrderService:
    """Flask-friendly factory; no serial device is opened here."""
    return OrderService()
