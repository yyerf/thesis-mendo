#!/usr/bin/env python3
"""End-to-end proof: measured TB74 pulse trains -> paid order -> inventory.

Drives the real `pos.order_service.OrderService` against a throwaway database
using the pulse counts MEASURED on the 2026-08-03 bench:

    PHP 20 = 2 pulses    PHP 50 = 5 pulses    PHP 100 = 10 pulses
    (1 pulse / PHP 10, 50 ms LOW, 150 ms period, TB74 Fast)

No hardware is touched and no physical gate is opened. This exercises the same
service methods the Flask routes call, so a pass here means the calibration
reaches inventory correctly through the production code path.

Run:  ./.venv/bin/python testing/verify_bill_to_inventory.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask  # noqa: E402

from hardware.pulses import PulseMapping  # noqa: E402
from mendo_core.money import format_php  # noqa: E402
from pos import db as pos_db  # noqa: E402
from pos.order_service import OrderService  # noqa: E402

MEASURED_TRAINS = {"PHP 20": 2, "PHP 50": 5, "PHP 100": 10}
FAILURES: list[str] = []


def check(label: str, actual, expected) -> None:
    ok = actual == expected
    print(f"    {'PASS' if ok else 'FAIL'}  {label}: {actual!r}"
          + ("" if ok else f"  (expected {expected!r})"))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    mapping = PulseMapping()

    print("=" * 66)
    print("  Measured pulse map (hardware/pulses.py defaults)")
    print("=" * 66)
    for label, pulses in MEASURED_TRAINS.items():
        cents = mapping.map("bill", pulses)
        print(f"    {pulses:>3} pulses -> {format_php(cents, centavos=True) if cents else 'UNMAPPED'}   ({label})")
    print("    disabled at the DIP bank, must stay unmapped:")
    for pulses in (20, 50, 100):
        check(f"{pulses} pulses unmapped", mapping.map("bill", pulses), None)

    tmp = tempfile.TemporaryDirectory()
    original = pos_db.DB_PATH
    pos_db.DB_PATH = str(Path(tmp.name) / "pos.sqlite")
    app = Flask("verify-bill-to-inventory")
    ctx = app.app_context()
    ctx.push()
    try:
        pos_db.init_db()
        db = pos_db.get_db()
        db.execute("UPDATE inventory SET stock_quantity=50,reserved_quantity=0")
        db.commit()
        service = OrderService(db)

        item = db.execute(
            "SELECT id,brand,unit_price_centavos,hardware_slot FROM inventory WHERE hardware_slot=8"
        ).fetchone()
        before = db.execute(
            "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?", (item["id"],)
        ).fetchone()

        print()
        print("=" * 66)
        print(f"  Order: 1 x {item['brand']} (slot {item['hardware_slot']})")
        print("=" * 66)
        print(f"    stock before      : {before['stock_quantity']} "
              f"(reserved {before['reserved_quantity']})")

        order = service.create_order(
            [{"inventory_id": item["id"], "quantity": 1}],
            idempotency_key="verify-1",
            payment_method="cash",
        )
        due = order["total_centavos"]
        print(f"    order_ref         : {order['order_ref']}")
        print(f"    amount due        : {format_php(due, centavos=True)}")

        reserved = db.execute(
            "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?", (item["id"],)
        ).fetchone()
        print(f"    after reserve     : stock {reserved['stock_quantity']}, "
              f"reserved {reserved['reserved_quantity']}")
        check("reservation held", reserved["reserved_quantity"], before["reserved_quantity"] + 1)
        check("stock not yet decremented", reserved["stock_quantity"], before["stock_quantity"])

        # Choose the smallest measured note that covers the amount due.
        pulses = next(
            (p for p in sorted(MEASURED_TRAINS.values())
             if (mapping.map("bill", p) or 0) >= due),
            max(MEASURED_TRAINS.values()),
        )
        cents = mapping.map("bill", pulses)

        print()
        print("-" * 66)
        print(f"  Inserting a {format_php(cents, centavos=True)} note -> {pulses} pulses on D3")
        print("-" * 66)

        cash = service.start_cash(order["order_ref"], no_change_consent=True)
        result = service.record_cash_event(
            order["order_ref"],
            session_ref=cash["session_ref"],
            event_id="verify-evt-1",
            source="bill",
            raw_pulses=pulses,
            mapped_centavos=cents,
            boot_id="verify-boot",
            sequence_no=1,
            quality="ok",
        )
        paid = service.get_order(order["order_ref"])
        print(f"    credited          : {result.get('credited')}")
        print(f"    received          : {format_php(paid['received_cash_centavos'], centavos=True)}")
        print(f"    overpayment       : {format_php(paid['overpayment_centavos'], centavos=True)}")
        print(f"    payment_state     : {paid['payment_state']}")
        check("payment credited", result.get("credited"), True)
        check("cash recorded exactly", paid["received_cash_centavos"], cents)
        check("overpayment tracked", paid["overpayment_centavos"], cents - due)

        print()
        print("-" * 66)
        print("  Payment-only inventory commit (motors disabled)")
        print("-" * 66)
        service.finalize_payment_only_sale(order["order_ref"])

        final_order = service.get_order(order["order_ref"])
        final = db.execute(
            "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?", (item["id"],)
        ).fetchone()
        print(f"    stock after       : {final['stock_quantity']} "
              f"(reserved {final['reserved_quantity']})")
        print(f"    order fulfillment : {final_order['fulfillment_state']}")
        print(f"    completion mode   : {final_order['completion_mode']}")
        check("stock decremented once", final["stock_quantity"], before["stock_quantity"] - 1)
        check("reservation released", final["reserved_quantity"], before["reserved_quantity"])
        check("payment-only completion", final_order["completion_mode"], "payment_only")
        check(
            "no motor job created",
            db.execute(
                "SELECT COUNT(*) FROM dispense_jobs WHERE order_id=?",
                (final_order["id"],),
            ).fetchone()[0],
            0,
        )

        # A suspect train, on its own order, at a denomination that WOULD map.
        # Noise can coincidentally total a valid pulse count, so the quality
        # flag has to override the mapping.
        print()
        print("-" * 66)
        print("  Suspect train (impossible timing) at a valid denomination")
        print("-" * 66)
        order_b = service.create_order(
            [{"inventory_id": item["id"], "quantity": 1}],
            idempotency_key="verify-2",
            payment_method="cash",
        )
        cash_b = service.start_cash(order_b["order_ref"], no_change_consent=True)
        suspect = service.record_cash_event(
            order_b["order_ref"],
            session_ref=cash_b["session_ref"],
            event_id="verify-evt-suspect",
            source="bill",
            raw_pulses=pulses,
            mapped_centavos=cents,
            boot_id="verify-boot",
            sequence_no=2,
            quality="suspect",
        )
        after = service.get_order(order_b["order_ref"])
        stock_b = db.execute(
            "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?", (item["id"],)
        ).fetchone()
        print(f"    would have mapped : {format_php(cents, centavos=True)} ({pulses} pulses)")
        print(f"    credited          : {suspect.get('credited')}")
        print(f"    received          : {format_php(after['received_cash_centavos'], centavos=True)}")
        print(f"    payment_state     : {after['payment_state']}")
        print(f"    stock             : {stock_b['stock_quantity']} "
              f"(reserved {stock_b['reserved_quantity']})")
        check("suspect not credited", suspect.get("credited"), False)
        check("suspect routed to review", after["payment_state"], "manual_review")
        check("suspect banked nothing", after["received_cash_centavos"], 0)
        check("suspect deducted nothing",
              stock_b["stock_quantity"], before["stock_quantity"] - 1)
    finally:
        pos_db.close_db()
        ctx.pop()
        pos_db.DB_PATH = original
        tmp.cleanup()

    print()
    print("=" * 66)
    if FAILURES:
        print(f"  {len(FAILURES)} CHECK(S) FAILED: {', '.join(FAILURES)}")
        print("=" * 66)
        return 1
    print("  ALL CHECKS PASSED")
    print("  Measured bill calibration reaches the payment-only inventory")
    print("  path. No medicine-motor job was created.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
