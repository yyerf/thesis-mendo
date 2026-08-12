"""Software-only acceptance tests for the recoverable payment/dispenser path."""

from __future__ import annotations

from datetime import datetime, timedelta
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from flask import Flask

from hardware.daemon import HardwareDaemon, UnixHardwareClient
from hardware.interface import HardwareFault
from hardware.protocol import ProtocolError, command, decode_frame
from hardware.pulses import PulseMapping, group_edges
from hardware.real_backend import SerialHardwareBackend
from hardware.serial_bridge import VendoBridge
from hardware.service import HardwareService
from hardware.simulator import SimulatedHardware
from mendo_core.money import format_php, to_centavos
from pos import db as pos_db
from pos.order_service import (
    ConsentRequired,
    HardwareJobUnknown,
    IdempotencyConflict,
    InvalidTransition,
    OrderService,
)


class TemporaryOrderCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db_path = pos_db.DB_PATH
        pos_db.DB_PATH = str(Path(self.tmp.name) / "pos.sqlite")
        self.app = Flask("hardware-test")
        self.ctx = self.app.app_context()
        self.ctx.push()
        pos_db.init_db()
        self.db = pos_db.get_db()
        self.db.execute("UPDATE inventory SET stock_quantity=50,reserved_quantity=0")
        self.db.commit()
        self.service = OrderService(self.db)

    def tearDown(self):
        pos_db.close_db()
        self.ctx.pop()
        pos_db.DB_PATH = self.original_db_path
        self.tmp.cleanup()

    def item(self, slot: int):
        return self.db.execute("SELECT id,brand FROM inventory WHERE hardware_slot=?", (slot,)).fetchone()


class MoneyAndProtocolTests(unittest.TestCase):
    def test_centavos_preserve_nine_peso_fifty(self):
        self.assertEqual(to_centavos("9.50"), 950)
        self.assertEqual(format_php(950, centavos=True), "₱9.50")

    def test_crc_and_bounded_ascii_frame(self):
        raw = command("R1", "STATUS", slot=8)
        self.assertEqual(decode_frame(raw).fields["slot"], "8")
        with self.assertRaises(ProtocolError):
            decode_frame(raw.replace(b"slot=8", b"slot=9"))
        with self.assertRaises(ProtocolError):
            decode_frame(raw[:-1])

    def test_source_specific_pulse_grouping_and_bounce_rejection(self):
        trains = group_edges("coin", [0, 1, 40, 150, 151], gap_ms=80, debounce_ms=3)
        self.assertEqual([train.pulse_count for train in trains], [2, 1])
        mapping = PulseMapping(coins={1: 100, 5: 500}, bills={2: 2000})
        self.assertEqual(mapping.map("coin", 2), None)
        self.assertEqual(mapping.map("bill", 2), 2000)


class MigrationTests(unittest.TestCase):
    def test_order_schema_additions_migrate_existing_database(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        # These are deliberately old-shaped tables: the additive migration
        # must not require a destructive rebuild or erase existing rows.
        db.executescript(
            """
            CREATE TABLE orders (id INTEGER PRIMARY KEY, order_ref TEXT);
            CREATE TABLE cash_events (id INTEGER PRIMARY KEY);
            CREATE TABLE dispense_jobs (id INTEGER PRIMARY KEY);
            INSERT INTO orders (id, order_ref) VALUES (7, 'ORD-OLD');
            """
        )
        pos_db._migrate_order_schema(db)
        order_columns = {row["name"] for row in db.execute("PRAGMA table_info(orders)")}
        cash_columns = {row["name"] for row in db.execute("PRAGMA table_info(cash_events)")}
        job_columns = {row["name"] for row in db.execute("PRAGMA table_info(dispense_jobs)")}
        self.assertIn("fulfillment_result", order_columns)
        self.assertIn("completion_mode", order_columns)
        self.assertIn("stock_committed_at", order_columns)
        self.assertIn("cashbox_session_id", cash_columns)
        self.assertIn("restocked_at", job_columns)
        self.assertEqual(db.execute("SELECT fulfillment_result FROM orders WHERE id=7").fetchone()[0], "reserved")
        db.close()


class OrderLifecycleTests(TemporaryOrderCase):
    def create(self, slot=8, quantity=1, key="k1", payment_method="cash"):
        row = self.item(slot)
        return self.service.create_order(
            [{"inventory_id": row["id"], "quantity": quantity}],
            idempotency_key=key,
            payment_method=payment_method,
        )

    def test_reservation_idempotency_and_conflict(self):
        order = self.create(key="same")
        self.assertEqual(self.service.create_order([{"inventory_id": self.item(8)["id"], "quantity": 1}], idempotency_key="same")["order_ref"], order["order_ref"])
        with self.assertRaises(IdempotencyConflict):
            self.service.create_order([{"inventory_id": self.item(8)["id"], "quantity": 2}], idempotency_key="same")
        row = self.item(8)
        self.assertEqual(self.db.execute("SELECT reserved_quantity FROM inventory WHERE id=?", (row["id"],)).fetchone()[0], 1)

    def test_no_change_consent_is_required(self):
        order = self.create()
        with self.assertRaises(ConsentRequired):
            self.service.start_cash(order["order_ref"], no_change_consent=False)

    def test_duplicate_cash_event_credits_once_and_records_overpayment(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        event = dict(session_ref=cash["session_ref"], event_id="evt-1", source="coin", raw_pulses=20, mapped_centavos=2000, boot_id="boot", sequence_no=1)
        first = self.service.record_cash_event(order["order_ref"], **event)
        duplicate = self.service.record_cash_event(order["order_ref"], **event)
        self.assertTrue(first["payment_complete"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.service.get_order(order["order_ref"])["received_cash_centavos"], 2000)
        self.assertEqual(self.service.get_order(order["order_ref"])["overpayment_centavos"], 1000)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cash_events").fetchone()[0], 1)

    def test_payment_only_completion_deducts_stock_once_without_motor_job(self):
        order = self.create(key="payment-only-stock")
        item = self.item(8)
        before = self.db.execute(
            "SELECT stock_quantity FROM inventory WHERE id=?", (item["id"],)
        ).fetchone()[0]
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        paid = self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"],
            event_id="payment-only-paid", source="coin", raw_pulses=10,
            mapped_centavos=0, boot_id="boot-payment-only", sequence_no=1,
        )
        self.assertTrue(paid["payment_complete"])

        first = self.service.finalize_payment_only_sale(order["order_ref"])
        replay = self.service.finalize_payment_only_sale(order["order_ref"])
        inventory = self.db.execute(
            "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?",
            (item["id"],),
        ).fetchone()
        self.assertEqual(inventory["stock_quantity"], before - 1)
        self.assertEqual(inventory["reserved_quantity"], 0)
        self.assertEqual(first["fulfillment_state"], "completed")
        self.assertEqual(first["completion_mode"], "payment_only")
        self.assertIsNotNone(first["stock_committed_at"])
        self.assertEqual(first["transaction_ref"], replay["transaction_ref"])
        self.assertEqual(first["items"][0]["quantity_dispensed"], 0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM dispense_jobs WHERE order_id=?", (first["id"],)
        ).fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM stock_logs WHERE reference LIKE 'PAYMENT_ONLY:%'"
        ).fetchone()[0], 1)

    def test_host_maps_validated_pulses_when_controller_sends_zero_money(self):
        order = self.create(key="host-maps-zero")
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        result = self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"],
            event_id="host-map-bill", source="bill", raw_pulses=5,
            mapped_centavos=0, boot_id="host-map", sequence_no=1,
        )
        self.assertTrue(result["credited"])
        self.assertEqual(result["order"]["received_cash_centavos"], 5000)

    def test_unknown_pulses_enter_manual_review_without_credit(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        result = self.service.record_cash_event(order["order_ref"], session_ref=cash["session_ref"], event_id="unknown", source="bill", raw_pulses=77, mapped_centavos=0, boot_id="boot", sequence_no=1)
        self.assertTrue(result["manual_review"])
        self.assertEqual(result["order"]["received_cash_centavos"], 0)
        self.assertEqual(result["order"]["payment_state"], "manual_review")

    def test_every_price_is_a_whole_peso(self):
        # Policy: no centavos. The smallest currency the kiosk can physically
        # accept is PHP 1 (one coin pulse), so a sub-peso price is unpayable in
        # exact change and forces overpayment on a machine that gives none.
        # Storage stays integer centavos -- this constrains the values, not the
        # representation.
        rows = self.db.execute(
            "SELECT brand, unit_price_centavos FROM inventory WHERE is_active=1"
        ).fetchall()
        self.assertTrue(rows, "inventory seed is empty")
        offenders = [
            f"{r['brand']} = {r['unit_price_centavos'] / 100:.2f}"
            for r in rows
            if int(r["unit_price_centavos"]) % 100 != 0
        ]
        self.assertEqual(offenders, [], f"prices with centavos: {offenders}")

    def test_catalog_defaults_are_whole_pesos(self):
        # Guard the seed source too, or a fresh database reintroduces centavos.
        from mendo_core.medicine_catalog import MEDICINE_CATALOG

        offenders = [
            f"{item.brand} = {item.default_price}"
            for item in MEDICINE_CATALOG
            if to_centavos(item.default_price) % 100 != 0
        ]
        self.assertEqual(offenders, [], f"catalog defaults with centavos: {offenders}")

    def _pay(self, order, cash, *, source, pulses, centavos, seq, event_id):
        return self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"], event_id=event_id,
            source=source, raw_pulses=pulses, mapped_centavos=centavos,
            boot_id="boot", sequence_no=seq,
        )

    def test_mixed_bill_and_coin_payment_reaches_exact_total(self):
        # PHP 22 due, paid as one PHP 20 note plus two PHP 1 coins -- the
        # everyday case for whole-peso pricing with no change given.
        self.db.execute("UPDATE inventory SET unit_price_centavos=2200 WHERE hardware_slot=8")
        self.db.commit()
        order = self.create()
        self.assertEqual(order["total_centavos"], 2200)
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)

        first = self._pay(order, cash, source="bill", pulses=2, centavos=2000, seq=1, event_id="m-bill")
        self.assertFalse(first.get("payment_complete"))
        self.assertEqual(first["order"]["received_cash_centavos"], 2000)

        self._pay(order, cash, source="coin", pulses=1, centavos=100, seq=2, event_id="m-c1")
        last = self._pay(order, cash, source="coin", pulses=1, centavos=100, seq=3, event_id="m-c2")

        self.assertTrue(last["payment_complete"])
        self.assertEqual(last["order"]["received_cash_centavos"], 2200)
        self.assertEqual(last["order"]["overpayment_centavos"], 0)
        self.assertEqual(last["order"]["payment_state"], "paid")

    def test_coin_landing_after_payment_completes_is_banked_as_overpayment(self):
        # Inhibit cannot recall a coin already inside the mechanism. The money
        # is physically in the drawer, so it must be accounted for or the
        # cashbox reconciles short.
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        paid = self._pay(order, cash, source="bill", pulses=2, centavos=2000, seq=1, event_id="late-bill")
        self.assertTrue(paid["payment_complete"])
        due = paid["order"]["total_centavos"]

        late = self._pay(order, cash, source="coin", pulses=5, centavos=500, seq=2, event_id="late-coin")
        self.assertFalse(late["credited"])
        self.assertTrue(late.get("overpaid"))
        self.assertFalse(late["manual_review"])
        self.assertEqual(late["order"]["payment_state"], "paid")
        self.assertEqual(late["order"]["received_cash_centavos"], 2500)
        self.assertEqual(late["order"]["overpayment_centavos"], 2500 - due)

        # The drawer must be able to account for every peso taken.
        banked = self.db.execute(
            "SELECT COALESCE(SUM(mapped_centavos),0) FROM cash_events WHERE event_state='accepted'"
        ).fetchone()[0]
        self.assertEqual(banked, 2500)

    def test_cash_on_a_cancelled_order_is_banked_and_audited_not_dropped(self):
        # 'cancelled' is terminal, so a stray coin must not resurrect the order.
        # It still physically entered the drawer, so it has to stay countable
        # and leave an audit trail for staff.
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self.service.cancel_order(order["order_ref"])
        stray = self._pay(order, cash, source="coin", pulses=10, centavos=1000, seq=1, event_id="stray")
        self.assertFalse(stray["credited"])
        self.assertEqual(stray["order"]["payment_state"], "cancelled")
        banked = self.db.execute(
            "SELECT COALESCE(SUM(mapped_centavos),0) FROM cash_events WHERE event_state='accepted'"
        ).fetchone()[0]
        self.assertEqual(banked, 1000)
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM order_audit_events WHERE event_type='CASH_ON_CLOSED_ORDER'"
            ).fetchone()[0],
            1,
        )

    def test_cash_after_timeout_review_stays_in_review(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self._pay(order, cash, source="coin", pulses=1, centavos=100, seq=1, event_id="partial")
        self.db.execute(
            "UPDATE cash_payment_sessions SET last_activity_at=? WHERE session_ref=?",
            ((datetime.now() - timedelta(seconds=400)).strftime("%Y-%m-%d %H:%M:%S"), cash["session_ref"]),
        )
        self.db.commit()
        self.service.expire_cash_sessions()
        late = self._pay(order, cash, source="coin", pulses=5, centavos=500, seq=2, event_id="after-timeout")
        self.assertFalse(late["credited"])
        self.assertEqual(late["order"]["payment_state"], "manual_review")
        banked = self.db.execute(
            "SELECT COALESCE(SUM(mapped_centavos),0) FROM cash_events WHERE event_state='accepted'"
        ).fetchone()[0]
        self.assertEqual(banked, 600)

    def test_coin_pulses_are_linear_one_peso_each(self):
        # Measured 2026-08-04 after Allan calibration: PHP 1 -> 1 pulse,
        # PHP 5 -> 5, PHP 20 -> 20, all at ~70 ms LOW / 170 ms period.
        mapping = PulseMapping()
        for pulses, centavos in ((1, 100), (5, 500), (10, 1000), (20, 2000)):
            self.assertEqual(mapping.map("coin", pulses), centavos)
        # Coins fed rapidly merge into one train; 110 pulses was observed in a
        # single 19 s train and must credit PHP 110, not route to review.
        self.assertEqual(mapping.map("coin", 110), 11000)
        # Junk trains still credit nothing.
        self.assertIsNone(mapping.map("coin", 0))
        self.assertIsNone(mapping.map("coin", 201))

    def test_explicit_coin_table_opts_back_into_strict_lookup(self):
        mapping = PulseMapping(coins={1: 100, 5: 500})
        self.assertEqual(mapping.map("coin", 5), 500)
        self.assertIsNone(mapping.map("coin", 2))

    def test_merged_coin_train_credits_its_full_value(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        result = self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"], event_id="coin-merged",
            source="coin", raw_pulses=110, mapped_centavos=11000, boot_id="boot",
            sequence_no=1,
        )
        self.assertTrue(result["credited"])
        self.assertEqual(result["order"]["received_cash_centavos"], 11000)

    def test_partial_peso_coin_value_is_rejected(self):
        # Coins are whole pesos. A fractional value means the mapping or the
        # pulse count is wrong, so it must not credit.
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        result = self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"], event_id="coin-odd",
            source="coin", raw_pulses=3, mapped_centavos=350, boot_id="boot",
            sequence_no=1,
        )
        self.assertTrue(result["manual_review"])
        self.assertEqual(result["order"]["received_cash_centavos"], 0)

    def test_suspect_train_never_credits_even_at_a_valid_denomination(self):
        # A noise burst can coincidentally total 5 pulses, which maps to a real
        # PHP 50. The controller flags impossible timing as quality=suspect and
        # that must override the mapping. Bench evidence: one accepted PHP 50
        # carried 12,871 raw edges around its 5 real pulses.
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        result = self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"], event_id="suspect-1",
            source="bill", raw_pulses=5, mapped_centavos=5000, boot_id="boot",
            sequence_no=1, quality="suspect",
        )
        self.assertTrue(result["manual_review"])
        self.assertFalse(result["credited"])
        self.assertEqual(result["order"]["received_cash_centavos"], 0)
        self.assertEqual(result["order"]["payment_state"], "manual_review")
        row = self.db.execute("SELECT event_state,mapped_centavos FROM cash_events WHERE event_id='suspect-1'").fetchone()
        self.assertEqual(row["event_state"], "unknown")
        self.assertEqual(row["mapped_centavos"], 0)

    def test_ok_quality_train_still_credits_normally(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        result = self.service.record_cash_event(
            order["order_ref"], session_ref=cash["session_ref"], event_id="ok-1",
            source="bill", raw_pulses=5, mapped_centavos=5000, boot_id="boot",
            sequence_no=2, quality="ok",
        )
        self.assertTrue(result["credited"])
        self.assertEqual(result["order"]["received_cash_centavos"], 5000)

    def test_measured_bill_mapping_is_the_default(self):
        # PHP 20/50/100 at 1 pulse / PHP 10, measured 2026-08-03.
        mapping = PulseMapping()
        self.assertEqual(mapping.map("bill", 2), 2000)
        self.assertEqual(mapping.map("bill", 5), 5000)
        self.assertEqual(mapping.map("bill", 10), 10000)
        # Denominations disabled at the acceptor stay unmapped so they route to
        # manual review rather than crediting.
        for pulses in (20, 50, 100):
            self.assertIsNone(mapping.map("bill", pulses))

    def test_timeout_zero_credit_cancels_and_releases_reservation(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self.db.execute("UPDATE cash_payment_sessions SET last_activity_at=? WHERE session_ref=?", ((datetime.now() - timedelta(seconds=400)).strftime("%Y-%m-%d %H:%M:%S"), cash["session_ref"]))
        self.db.commit()
        self.assertEqual(self.service.expire_cash_sessions(), [order["order_ref"]])
        current = self.service.get_order(order["order_ref"])
        self.assertEqual(current["payment_state"], "cancelled")
        self.assertEqual(self.db.execute("SELECT reserved_quantity FROM inventory WHERE hardware_slot=8").fetchone()[0], 0)

    def test_partial_timeout_becomes_review_and_keeps_received_cash_evidence(self):
        order = self.create()
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self.service.record_cash_event(order["order_ref"], session_ref=cash["session_ref"], event_id="partial", source="coin", raw_pulses=1, mapped_centavos=100, boot_id="boot", sequence_no=1)
        self.db.execute("UPDATE cash_payment_sessions SET last_activity_at=? WHERE session_ref=?", ((datetime.now() - timedelta(seconds=400)).strftime("%Y-%m-%d %H:%M:%S"), cash["session_ref"]))
        self.db.commit()
        self.service.expire_cash_sessions()
        current = self.service.get_order(order["order_ref"])
        self.assertEqual(current["payment_state"], "manual_review")
        self.assertEqual(current["received_cash_centavos"], 100)
        self.assertEqual(self.db.execute("SELECT reserved_quantity FROM inventory WHERE hardware_slot=8").fetchone()[0], 0)

    def test_unknown_timeout_keeps_reservation_for_staff_review(self):
        order = self.create(key="unknown-timeout")
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self.service.record_cash_event(order["order_ref"], session_ref=cash["session_ref"], event_id="unknown-timeout-event", source="bill", raw_pulses=77, mapped_centavos=0, boot_id="boot-unknown", sequence_no=1)
        self.db.execute("UPDATE cash_payment_sessions SET last_activity_at=? WHERE session_ref=?", ((datetime.now() - timedelta(seconds=400)).strftime("%Y-%m-%d %H:%M:%S"), cash["session_ref"]))
        self.db.commit()
        self.service.expire_cash_sessions()
        current = self.service.get_order(order["order_ref"])
        self.assertEqual(current["payment_state"], "manual_review")
        self.assertEqual(self.db.execute("SELECT reserved_quantity FROM inventory WHERE hardware_slot=8").fetchone()[0], 1)

    def test_sequential_dispense_lost_ack_is_not_repeated(self):
        order = self.create(slot=8, quantity=2)
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self.service.record_cash_event(order["order_ref"], session_ref=cash["session_ref"], event_id="paid", source="bill", raw_pulses=2, mapped_centavos=2000, boot_id="boot", sequence_no=1)
        self.service.enqueue_dispense_jobs(order["order_ref"])
        jobs = self.db.execute("SELECT job_id FROM dispense_jobs WHERE order_id=? ORDER BY unit_sequence", (self.db.execute("SELECT id FROM orders WHERE order_ref=?", (order["order_ref"],)).fetchone()[0],)).fetchall()
        self.service.claim_dispense_job(jobs[0]["job_id"])
        self.service.record_dispense_event(jobs[0]["job_id"], "DISPENSE_DONE_UNVERIFIED", ack_result="ack_lost", controller_result="executed")
        self.assertEqual(self.service.next_dispense_job(order["order_ref"])["job_id"], jobs[1]["job_id"])
        duplicate = self.service.record_dispense_event(jobs[0]["job_id"], "DISPENSE_DONE_UNVERIFIED")
        self.assertEqual(duplicate["items"][0]["quantity_dispensed"], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM stock_logs WHERE reference LIKE ?", (f"DISPENSE:{jobs[0]['job_id']}%",)).fetchone()[0], 1)

    def test_refund_does_not_restore_physical_stock(self):
        order = self.create()
        current = self.service.record_cashier_payment(order["order_ref"], received_centavos=1000)
        self.service.enqueue_dispense_jobs(order["order_ref"])
        job = self.service.next_dispense_job(order["order_ref"])
        self.service.claim_dispense_job(job["job_id"])
        self.service.record_dispense_event(job["job_id"], "DISPENSE_DONE_UNVERIFIED")
        before = self.db.execute("SELECT stock_quantity FROM inventory WHERE hardware_slot=8").fetchone()[0]
        self.service.refund_order(order["order_ref"])
        self.assertEqual(self.db.execute("SELECT stock_quantity FROM inventory WHERE hardware_slot=8").fetchone()[0], before)

    def test_refund_releases_undispensed_reservation(self):
        order = self.create(key="refund-reservation")
        self.service.record_cashier_payment(order["order_ref"], received_centavos=1000)
        self.service.refund_order(order["order_ref"])
        current = self.service.get_order(order["order_ref"])
        self.assertEqual(current["payment_state"], "refunded")
        self.assertEqual(current["fulfillment_state"], "cancelled")
        self.assertEqual(self.db.execute("SELECT reserved_quantity FROM inventory WHERE hardware_slot=8").fetchone()[0], 0)

    def test_only_unexecuted_job_can_be_retried(self):
        order = self.create(key="retry-unexecuted")
        self.service.record_cashier_payment(order["order_ref"], received_centavos=1000)
        self.service.enqueue_dispense_jobs(order["order_ref"])
        job = self.service.next_dispense_job(order["order_ref"])
        self.service.claim_dispense_job(job["job_id"])
        self.service.fail_dispense_job(job["job_id"], error_code="SERIAL_LOST", error_detail="ack missing", controller_result="unexecuted")
        retried = self.service.retry_unexecuted_dispense(job["job_id"], actor="7")
        self.assertEqual(retried["dispense_jobs"][0]["state"], "queued")
        self.service.claim_dispense_job(job["job_id"])
        completed = self.service.record_dispense_event(job["job_id"], "DISPENSE_DONE_UNVERIFIED")
        self.assertEqual(completed["fulfillment_state"], "completed")
        self.assertEqual(completed["fulfillment_verification"], "dispensed_unverified")

    def test_unknown_controller_result_is_not_retryable(self):
        order = self.create(key="retry-unknown")
        self.service.record_cashier_payment(order["order_ref"], received_centavos=1000)
        self.service.enqueue_dispense_jobs(order["order_ref"])
        job = self.service.next_dispense_job(order["order_ref"])
        self.service.fail_dispense_job(job["job_id"], error_code="POWER_LOSS", error_detail="unknown", controller_result="unknown")
        with self.assertRaises(HardwareJobUnknown):
            self.service.retry_unexecuted_dispense(job["job_id"])

    def test_cashbox_reconciliation_is_session_scoped(self):
        box = self.service.open_cashbox(staff_id=1)
        order = self.create(key="box-one")
        cash = self.service.start_cash(order["order_ref"], no_change_consent=True)
        self.service.record_cash_event(order["order_ref"], session_ref=cash["session_ref"], event_id="box-event-1", source="coin", raw_pulses=10, mapped_centavos=1000, boot_id="box", sequence_no=1)
        closed = self.service.close_cashbox(box["session_ref"], staff_id=1, counted_total_centavos=1000)
        self.assertEqual(closed["expected_total_centavos"], 1000)
        summary = self.service.accounting_summary()
        self.assertEqual(summary["received_cash_centavos"], 1000)
        self.assertEqual(summary["overpayment_centavos"], 0)
        self.assertEqual(summary["expected_cashbox_centavos"], 1000)
        next_box = self.service.open_cashbox(staff_id=1)
        order2 = self.create(key="box-two")
        cash2 = self.service.start_cash(order2["order_ref"], no_change_consent=True)
        self.service.record_cash_event(order2["order_ref"], session_ref=cash2["session_ref"], event_id="box-event-2", source="coin", raw_pulses=10, mapped_centavos=1000, boot_id="box", sequence_no=2)
        closed2 = self.service.close_cashbox(next_box["session_ref"], staff_id=1, counted_total_centavos=1000)
        self.assertEqual(closed2["expected_total_centavos"], 1000)

    def test_lost_dispatch_response_reconciles_before_any_retry(self):
        from pos.routes_checkout import _dispatch_order

        class LostResponseHardware(SimulatedHardware):
            def dispense_one(self, job_id, slot, profile_version):
                super().dispense_one(job_id, slot, profile_version)
                raise HardwareFault("ACK_LOST_AFTER_MOTION")

        bridge = VendoBridge(mode="simulator")
        backend = LostResponseHardware()
        bridge.backend = backend
        self.app.extensions["mendo_hardware"] = HardwareService(bridge)
        order = self.create(key="lost-dispatch-response")
        self.service.record_cashier_payment(order["order_ref"], received_centavos=1000)
        result = _dispatch_order(order["order_ref"])
        self.assertEqual(result["fulfillment_verification"], "dispensed_unverified")
        self.assertEqual(len(backend.motion_history), 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM stock_logs WHERE reference LIKE 'DISPENSE:%:UNVERIFIED'").fetchone()[0], 1)

    def test_xendit_duplicate_callback_is_one_payment(self):
        order = self.create(payment_method="xendit_cashless")
        self.service.ensure_xendit_attempt(order["order_ref"], external_id="MENDO-" + order["order_ref"], amount_centavos=order["total_centavos"])
        self.service.complete_xendit_payment(order["order_ref"], external_id="MENDO-" + order["order_ref"], provider_payment_id="inv-1", amount_centavos=order["total_centavos"], currency="PHP")
        self.service.complete_xendit_payment(order["order_ref"], external_id="MENDO-" + order["order_ref"], provider_payment_id="inv-1", amount_centavos=order["total_centavos"], currency="PHP")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM payment_attempts WHERE order_id=?", (self.db.execute("SELECT id FROM orders WHERE order_ref=?", (order["order_ref"],)).fetchone()[0],)).fetchone()[0], 1)
        self.assertEqual(self.service.get_order(order["order_ref"])["payment_state"], "paid")


class CashierPaymentRouteTests(TemporaryOrderCase):
    def setUp(self):
        super().setUp()
        from pos.routes_checkout import checkout_bp
        from pos.routes_shop import shop_bp

        self.app.secret_key = "cashier-flow-test"
        self.app.register_blueprint(shop_bp)
        self.app.register_blueprint(checkout_bp)
        self.app.extensions["mendo_hardware"] = HardwareService(
            VendoBridge(mode="simulator")
        )
        self.client = self.app.test_client()
        with self.client.session_transaction() as browser_session:
            browser_session["pos_user_id"] = 1

    def test_new_cash_start_expires_abandoned_zero_cash_session(self):
        item = self.item(8)
        old_order = self.service.create_order(
            [{"inventory_id": item["id"], "quantity": 1}],
            idempotency_key="abandoned-cash-order",
            payment_method="cash",
        )
        old_cash = self.service.start_cash(
            old_order["order_ref"], no_change_consent=True
        )
        hardware = self.app.extensions["mendo_hardware"]
        hardware.start_cash(old_cash["session_ref"], old_order["total_centavos"])
        self.db.execute(
            "UPDATE cash_payment_sessions SET last_activity_at=? WHERE session_ref=?",
            (
                (datetime.now() - timedelta(seconds=400)).strftime("%Y-%m-%d %H:%M:%S"),
                old_cash["session_ref"],
            ),
        )
        self.db.commit()

        new_order = self.service.create_order(
            [{"inventory_id": item["id"], "quantity": 1}],
            idempotency_key="replacement-cash-order",
            payment_method="cash",
        )
        response = self.client.post(
            f"/checkout/api/orders/{new_order['order_ref']}/cash/start",
            json={"no_change_consent": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.get_order(old_order["order_ref"])["payment_state"], "cancelled")
        started = response.get_json()
        self.assertEqual(started["payment_state"], "awaiting_cash")
        self.assertEqual(
            hardware.bridge.backend.payment_session,
            started["cash_session"]["session_ref"],
        )

    def test_main_cashier_payment_updates_stock_without_dispense(self):
        item = self.item(8)
        before = self.db.execute(
            "SELECT stock_quantity FROM inventory WHERE id=?", (item["id"],)
        ).fetchone()[0]
        added = self.client.post(
            "/shop/api/cart/add",
            json={"inventory_id": item["id"], "quantity": 1},
        )
        self.assertEqual(added.status_code, 200)
        started = self.client.post(
            "/shop/api/checkout",
            json={"no_change_consent": True},
            headers={"Idempotency-Key": "cashier-browser-flow"},
        )
        self.assertEqual(started.status_code, 200)
        order = started.get_json()["order"]
        self.assertEqual(order["payment_state"], "awaiting_cash")

        paid = self.client.post(
            f"/checkout/api/orders/{order['order_ref']}/cash/simulate",
            json={"source": "bill", "centavos": 2000},
        )
        self.assertEqual(paid.status_code, 200)
        completed = paid.get_json()
        self.assertEqual(completed["payment_state"], "paid")
        self.assertEqual(completed["fulfillment_state"], "completed")
        self.assertEqual(completed["completion_mode"], "payment_only")
        self.assertEqual(completed["dispense_jobs"], [])
        stock = self.db.execute(
            "SELECT stock_quantity,reserved_quantity FROM inventory WHERE id=?",
            (item["id"],),
        ).fetchone()
        self.assertEqual(stock["stock_quantity"], before - 1)
        self.assertEqual(stock["reserved_quantity"], 0)


class HardwareBoundaryTests(unittest.TestCase):
    def test_simulator_starts_in_fail_safe_and_has_explicit_identity(self):
        backend = SimulatedHardware()
        status = backend.status()
        self.assertTrue(status["simulator"])
        self.assertTrue(status["acceptors_inhibited"])
        self.assertTrue(status["physical_evidence_required"])

    def test_unix_daemon_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "hardware.sock")
            daemon = HardwareDaemon(SimulatedHardware(), socket_path=path).start()
            try:
                client = UnixHardwareClient(path)
                status = client.status()
                self.assertEqual(status["firmware_identity"], "mendo-simulator-v1")
                self.assertEqual(status["simulator"], "True")
                client.start_payment("session-1", 1000)
                event = client.request("SIM_INSERT", source="coin", centavos=100)
                self.assertEqual(event["mapped_centavos"], "100")
                diagnostics = client.cash_diagnostics()
                self.assertEqual(diagnostics["bill_level"], "1")
                self.assertEqual(client.cash_evidence(0)["present"], "0")
                client.stop_payment("session-1")
                job = client.dispense_one("job-1", 1, "v1-unmeasured")
                self.assertEqual(job["job_id"], "job-1")
                self.assertEqual(client.job_status("job-1")["event"], "DISPENSE_DONE_UNVERIFIED")
            finally:
                daemon.stop()

    def test_real_controller_cash_event_is_normalized_and_mapped(self):
        backend = SerialHardwareBackend(port="unused")
        backend._capture_cash_event({
            "session": "CASH-123",
            "source": "coin",
            "raw_pulses": "20",
            "mapped_centavos": "0",
            "requires_mapping": "1",
            "boot_id": "42",
            "sequence_no": "7",
            "pulse_started_ms": "12345",
            "quality": "ok",
        })
        event = backend.poll_event()
        self.assertEqual(event["session_ref"], "CASH-123")
        self.assertEqual(event["mapped_centavos"], 2000)
        self.assertEqual(event["event_id"], "42-coin-7")
        self.assertEqual(event["pulse_started_at"], "12345")
        backend._request = lambda *_args, **_kwargs: {"ok": "1"}
        backend.ack_cash_event("42", 7, "coin")
        self.assertIsNone(backend.poll_event())

    def test_real_controller_pulls_persistent_bill_event_when_async_frame_is_lost(self):
        backend = SerialHardwareBackend(port="unused")
        requests = []

        def recovered_request(name, **_fields):
            requests.append(name)
            return {
                "has_event": "1",
                "session": "CASH-BILL-RECOVERY",
                "source": "bill",
                "raw_pulses": "5",
                "mapped_centavos": "0",
                "boot_id": "23",
                "sequence_no": "9",
                "quality": "ok",
            }

        backend._request = recovered_request
        event = backend.poll_event()

        self.assertEqual(requests, ["CASH_POLL"])
        self.assertEqual(event["session_ref"], "CASH-BILL-RECOVERY")
        self.assertEqual(event["source"], "bill")
        self.assertEqual(event["mapped_centavos"], 5000)
        self.assertEqual(event["event_id"], "23-bill-9")

    def test_daemon_keeps_burst_events_until_each_is_acked(self):
        class BurstBackend:
            def __init__(self):
                self.drained = False

            def status(self):
                return SimulatedHardware().status()

            def drain_events(self):
                if self.drained:
                    return []
                self.drained = True
                return [
                    {"boot_id": "b", "sequence_no": 1, "source": "coin", "session_ref": "s", "raw_pulses": 1, "mapped_centavos": 100},
                    {"boot_id": "b", "sequence_no": 2, "source": "coin", "session_ref": "s", "raw_pulses": 5, "mapped_centavos": 500},
                ]

            def ack_cash_event(self, *_args):
                return {"ok": True}

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "burst.sock")
            daemon = HardwareDaemon(BurstBackend(), socket_path=path).start()
            try:
                client = UnixHardwareClient(path)
                first = client.poll_event()
                replay = client.poll_event()
                self.assertEqual(first["sequence_no"], "1")
                self.assertEqual(replay["sequence_no"], "1")
                client.ack_cash_event("b", 1, "coin")
                second = client.poll_event()
                self.assertEqual(second["sequence_no"], "2")
            finally:
                daemon.stop()


if __name__ == "__main__":
    unittest.main()
