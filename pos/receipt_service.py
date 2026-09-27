"""Durable paper receipts for completed sales.

A completed sale queues copy 1 inside the same transaction that commits stock
(``OrderService._create_final_transaction_locked``). Printing happens after
that commit, over the hardware boundary:

``pending``  queued, never attempted
``printing`` claimed by one request (a stale claim is reclaimed)
``printed``  the controller reported the job complete
``failed``   nothing of this copy is on paper or the job can resume; retried
``ambiguous`` the printer stopped mid-receipt; staff must look at the paper
``cancelled`` staff superseded an ambiguous copy with a reprint

A failed print never touches the sale: payment and stock are already final.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import uuid
from typing import Any, Dict, List, Optional

from hardware.printer import (
    AMBIGUOUS,
    PRINTED,
    PrintOutcome,
    RESUMABLE,
    make_fingerprint,
    print_job,
)
from hardware.receipt import render_receipt, render_test_slip

from .order_service import OrderError, OrderService, _immediate, _now


log = logging.getLogger("mendo.receipts")

CLAIM_STALE_SECONDS = 30
AUTO_RETRY_LIMIT = 5
AUTO_RETRY_INTERVAL_SECONDS = 3
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class ReceiptError(OrderError):
    pass


def queue_receipt_locked(
    db, order_id: int, transaction_ref: str, *, copy_no: int, requested_by: str = "system"
) -> None:
    """Insert one print job; the caller owns the transaction."""
    # A random component keeps fingerprints unique even if the database is
    # recreated and transaction numbers repeat against the same controller.
    fingerprint = make_fingerprint(f"receipt|{transaction_ref}|{copy_no}|{uuid.uuid4().hex}")
    db.execute(
        """
        INSERT OR IGNORE INTO receipt_prints
            (print_ref, order_id, copy_no, fingerprint, requested_by)
        VALUES (?,?,?,?,?)
        """,
        (f"PR-{transaction_ref}-{copy_no}", order_id, copy_no, fingerprint, requested_by),
    )


def _row_dict(row) -> Dict[str, Any]:
    return dict(row) if row else {}


class ReceiptPrintService:
    def __init__(self, db, hardware):
        self.db = db
        self.hardware = hardware
        self.orders = OrderService(db)

    # ── reads ─────────────────────────────────────────────────────────────

    def list_for_order(self, order_id: int) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM receipt_prints WHERE order_id=? ORDER BY copy_no", (order_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def summary_for_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """The customer-facing state: the newest copy that is not superseded."""
        rows = [r for r in self.list_for_order(order_id) if r["state"] != "cancelled"]
        if not rows:
            return None
        latest = rows[-1]
        return {
            key: latest[key]
            for key in ("print_ref", "copy_no", "state", "attempts", "last_error", "printed_at", "printer_mode")
        }

    def list_attention(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT p.*, o.order_ref FROM receipt_prints p JOIN orders o ON o.id=p.order_id
            WHERE p.state IN ('pending','printing','failed','ambiguous')
            ORDER BY p.id DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── printing ──────────────────────────────────────────────────────────

    def print_pending_for_order(self, order_ref: str) -> Optional[Dict[str, Any]]:
        """Attempt every printable copy of one order; returns the summary."""
        order = self.orders.get_order(order_ref)
        now = datetime.now()
        for row in self.list_for_order(order["id"]):
            if self._due(row, now):
                self.run(row["id"])
        return self.summary_for_order(order["id"])

    def _due(self, row: Dict[str, Any], now: datetime) -> bool:
        state = row["state"]
        if state == "pending":
            return True
        stamp = row.get("claimed_at") if state == "printing" else row.get("updated_at")
        try:
            age = now - datetime.strptime(str(stamp), _TIME_FORMAT)
        except (TypeError, ValueError):
            age = timedelta(days=1)
        if state == "printing":
            return age >= timedelta(seconds=CLAIM_STALE_SECONDS)
        if state == "failed":
            return (
                int(row["attempts"]) < AUTO_RETRY_LIMIT
                and age >= timedelta(seconds=AUTO_RETRY_INTERVAL_SECONDS)
            )
        return False

    def run(self, print_id: int, *, force: bool = False) -> Dict[str, Any]:
        """Claim one copy and print it. Only one caller can hold the claim."""
        db = self.db
        stale = (datetime.now() - timedelta(seconds=CLAIM_STALE_SECONDS)).strftime(_TIME_FORMAT)
        with _immediate(db):
            claimed = db.execute(
                """
                UPDATE receipt_prints
                SET state='printing', claimed_at=?, attempts=attempts+1, updated_at=?
                WHERE id=? AND (
                    state='pending'
                    OR (state='failed' AND (? OR attempts < ?))
                    OR (state='printing' AND claimed_at <= ?)
                )
                """,
                (_now(), _now(), print_id, int(force), AUTO_RETRY_LIMIT, stale),
            ).rowcount
        row = _row_dict(db.execute("SELECT * FROM receipt_prints WHERE id=?", (print_id,)).fetchone())
        if not claimed:
            return row
        order = self.orders.get_order_by_id(int(row["order_id"]))
        copy_label = "REPRINT" if int(row["copy_no"]) > 1 else None
        data = render_receipt(order, copy_label=copy_label)
        mode = self._mode()
        try:
            outcome = print_job(self.hardware.printer_command, row["fingerprint"], data)
        except Exception as exc:  # never let a printer fault escape the sale
            log.warning("Receipt %s print failed", row["print_ref"], exc_info=True)
            outcome = PrintOutcome(RESUMABLE, str(exc), 0, len(data))
        state = {PRINTED: "printed", AMBIGUOUS: "ambiguous"}.get(outcome.result, "failed")
        with _immediate(db):
            db.execute(
                """
                UPDATE receipt_prints
                SET state=?, last_error=?, bytes_total=?, bytes_sent=?, printer_mode=?,
                    printed_at=CASE WHEN ?='printed' THEN ? ELSE printed_at END,
                    updated_at=?
                WHERE id=?
                """,
                (
                    state, outcome.fault_code, len(data), outcome.received, mode,
                    state, _now(), _now(), print_id,
                ),
            )
            self.orders._audit(
                db, int(row["order_id"]), f"RECEIPT_{state.upper()}", row["state"], state,
                "receipt-printer",
                {
                    "print_ref": row["print_ref"], "copy_no": row["copy_no"],
                    "result": outcome.result, "fault_code": outcome.fault_code,
                    "bytes_sent": outcome.received, "bytes_total": len(data),
                    "printer_mode": mode,
                },
            )
        return _row_dict(db.execute("SELECT * FROM receipt_prints WHERE id=?", (print_id,)).fetchone())

    def reprint(self, order_ref: str, *, actor: str) -> Dict[str, Any]:
        order = self.orders.get_order(order_ref)
        if order.get("fulfillment_state") != "completed" or not order.get("transaction_ref"):
            raise ReceiptError("Only a completed sale has a receipt to reprint")
        with _immediate(self.db):
            copy_no = self._next_copy_locked(order["id"])
            queue_receipt_locked(self.db, order["id"], order["transaction_ref"], copy_no=copy_no, requested_by=actor)
        row = self.db.execute(
            "SELECT id FROM receipt_prints WHERE order_id=? AND copy_no=?", (order["id"], copy_no)
        ).fetchone()
        return self.run(row["id"])

    def retry(self, print_ref: str) -> Dict[str, Any]:
        row = self._by_ref(print_ref)
        if row["state"] != "failed":
            raise ReceiptError(f"Receipt {print_ref} is {row['state']}, not failed")
        return self.run(row["id"], force=True)

    def resolve_ambiguous(self, print_ref: str, *, action: str, actor: str) -> Dict[str, Any]:
        """Staff looked at the paper. Release the controller's job record.

        ``mark_printed``: the receipt came out whole enough to hand over.
        ``reprint``: supersede it with a new, labelled copy.
        """
        row = self._by_ref(print_ref)
        if row["state"] != "ambiguous":
            raise ReceiptError(f"Receipt {print_ref} is {row['state']}, not ambiguous")
        if action not in {"mark_printed", "reprint"}:
            raise ReceiptError("action must be mark_printed or reprint")
        self._clear_controller(row["fingerprint"])
        new_state = "printed" if action == "mark_printed" else "cancelled"
        with _immediate(self.db):
            self.db.execute(
                "UPDATE receipt_prints SET state=?, resolved_by=?, updated_at=? WHERE id=?",
                (new_state, actor, _now(), row["id"]),
            )
            self.orders._audit(
                self.db, int(row["order_id"]), "RECEIPT_AMBIGUITY_RESOLVED", "ambiguous", new_state,
                actor, {"print_ref": print_ref, "action": action},
            )
        if action == "reprint":
            order_ref = self.db.execute("SELECT order_ref FROM orders WHERE id=?", (row["order_id"],)).fetchone()[0]
            return self.reprint(order_ref, actor=actor)
        return _row_dict(self.db.execute("SELECT * FROM receipt_prints WHERE id=?", (row["id"],)).fetchone())

    def printer_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {"mode": self._mode()}
        try:
            status.update(self.hardware.printer_command("PRINTER_STATUS"))
            status["reachable"] = True
        except Exception as exc:
            status.update(reachable=False, fault_code=str(exc))
        blocking = self.db.execute(
            "SELECT print_ref FROM receipt_prints WHERE state='ambiguous' ORDER BY id LIMIT 1"
        ).fetchone()
        status["blocked_by"] = blocking["print_ref"] if blocking else None
        return status

    def test_print(self, *, actor: str) -> Dict[str, Any]:
        fingerprint = make_fingerprint(f"test|{actor}|{uuid.uuid4().hex}")
        outcome = print_job(self.hardware.printer_command, fingerprint, render_test_slip())
        if outcome.result == AMBIGUOUS:
            # A half-printed test slip harms nobody; never let it block sales.
            self._clear_controller(fingerprint)
        return {
            "result": outcome.result, "fault_code": outcome.fault_code,
            "bytes_sent": outcome.received, "bytes_total": outcome.length,
            "mode": self._mode(),
        }

    # ── helpers ───────────────────────────────────────────────────────────

    def _by_ref(self, print_ref: str) -> Dict[str, Any]:
        row = self.db.execute("SELECT * FROM receipt_prints WHERE print_ref=?", (print_ref,)).fetchone()
        if not row:
            raise ReceiptError(f"Receipt print {print_ref} not found")
        return dict(row)

    def _next_copy_locked(self, order_id: int) -> int:
        row = self.db.execute(
            "SELECT COALESCE(MAX(copy_no),0) AS n FROM receipt_prints WHERE order_id=?", (order_id,)
        ).fetchone()
        return int(row["n"]) + 1

    def _clear_controller(self, fingerprint: str) -> None:
        try:
            self.hardware.printer_command("PRINT_CLEAR", fingerprint=fingerprint)
        except Exception as exc:
            if str(exc) != "PRINT_CLEAR_REJECTED":  # already gone is fine
                raise ReceiptError(f"Printer controller did not release the job: {exc}") from exc

    def _mode(self) -> str:
        bridge = getattr(self.hardware, "bridge", None)
        return getattr(bridge, "mode", "unknown")


def receipt_service() -> ReceiptPrintService:
    """Flask-request factory, matching ``order_service()``."""
    from hardware.service import get_hardware_service

    from .db import get_db

    return ReceiptPrintService(get_db(), get_hardware_service())


def print_receipts_safely(order_ref: str) -> Optional[Dict[str, Any]]:
    """Print any due copy of a completed order; never raises into a sale."""
    try:
        return receipt_service().print_pending_for_order(order_ref)
    except Exception:
        log.warning("Receipt printing for %s failed", order_ref, exc_info=True)
        return None
