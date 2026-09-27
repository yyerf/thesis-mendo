"""Receipt printing: ESC/POS layout, controller job protocol, and POS flow."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from hardware.daemon import HardwareDaemon, UnixHardwareClient
from hardware.printer import (
    AMBIGUOUS,
    BLOCKED,
    CHUNK_BYTES,
    NOT_PRINTED,
    PRINTED,
    make_fingerprint,
    print_job,
)
from hardware.protocol import command
from hardware.receipt import WIDTH, render_receipt, render_test_slip
from hardware.serial_bridge import VendoBridge
from hardware.service import HardwareService
from hardware.simulator import SimulatedHardware
from pos import receipt_service as receipt_module
from pos.receipt_service import ReceiptPrintService

from testing.test_hardware_payment import TemporaryOrderCase


ESC_SEQUENCE = re.compile(rb"\x1b[@]|\x1b[aE!d]..?|\x1dV.")


def printed_lines(data: bytes) -> list[str]:
    """Text as it lands on paper, with ESC/POS control sequences removed."""
    text = re.sub(rb"\x1b@|\x1b7...|\x1b[aE!d].|\x1dV.", b"", data, flags=re.S)
    return text.decode("ascii").split("\n")


SAMPLE_ORDER = {
    "order_ref": "ORD-20260928-ABC",
    "transaction_ref": "TXN-20260928-0001",
    "payment_method": "cash",
    "completed_at": "2026-09-28 14:03:11",
    "total_centavos": 1500,
    "received_cash_centavos": 2000,
    "overpayment_centavos": 500,
    "items": [
        {"brand": "Biogesic Paracetamol 500mg Tablet (Para sa lagnat at sakit ng ulo)", "quantity_ordered": 2, "unit_price_centavos": 500},
        {"brand": "Kremil-S Niño ₱", "quantity_ordered": 1, "unit_price_centavos": 500},
    ],
}


class ReceiptLayoutTests(unittest.TestCase):
    def test_every_printed_line_fits_58mm_and_is_ascii(self):
        data = render_receipt(SAMPLE_ORDER)
        data.decode("ascii")  # raises on anything the code page cannot print
        for line in printed_lines(data):
            if line == "MENDO VENDO":
                continue  # double-width title: 11 chars = 22 columns
            self.assertLessEqual(len(line), WIDTH, line)

    def test_receipt_carries_sale_facts(self):
        text = "\n".join(printed_lines(render_receipt(SAMPLE_ORDER)))
        self.assertIn("TXN-20260928-0001", text)
        self.assertIn("ORD-20260928-ABC", text)
        self.assertIn("PHP 15.00", text)
        self.assertIn("Cash received", text)
        self.assertIn("Excess (no change)", text)
        self.assertIn("Kremil-S Nino", text)  # accents folded, peso sign dropped
        self.assertIn("not an official receipt", text)

    def test_receipt_limits_peak_heat_and_avoids_solid_rules(self):
        data = render_receipt(SAMPLE_ORDER)
        self.assertTrue(data.startswith(b"\x1b@\x1b7\x03\x50\x02"))
        self.assertNotIn(b"-" * 3, data)  # solid rules browned the printer out

    def test_receipt_ends_with_tear_feed_and_reprint_is_labelled(self):
        data = render_receipt(SAMPLE_ORDER, copy_label="REPRINT")
        self.assertTrue(data.endswith(b"\x1bd\x06\x1dV\x01"))
        self.assertIn(b"*** REPRINT ***", data)

    def test_fingerprint_is_valid_on_original_firmware(self):
        fingerprint = make_fingerprint("receipt|TXN-1|1")
        self.assertRegex(fingerprint, r"^[0-9a-f]{16}$")
        self.assertGreaterEqual(int(fingerprint[:2], 16), 0x80)  # first 32 bits nonzero
        self.assertEqual(fingerprint, make_fingerprint("receipt|TXN-1|1"))
        self.assertNotEqual(fingerprint[:8], make_fingerprint("receipt|TXN-1|2")[:8])

    def test_chunk_frame_fits_the_uno_receive_buffer(self):
        frame = command(
            "R0123456789", "PRINT_CHUNK", fingerprint="f" * 16, offset=4000,
            hex=(b"\xff" * CHUNK_BYTES).hex(),
        )
        self.assertLessEqual(len(frame) - 1, 240)  # firmware FRAME_LIMIT


class PrintProtocolTests(unittest.TestCase):
    def setUp(self):
        self.printer = SimulatedHardware()
        self.data = render_test_slip("protocol test")

    def test_job_prints_exactly_once_even_when_repeated(self):
        fingerprint = make_fingerprint("once")
        self.assertEqual(print_job(self.printer.printer_command, fingerprint, self.data).result, PRINTED)
        self.assertEqual(print_job(self.printer.printer_command, fingerprint, self.data).result, PRINTED)
        self.assertEqual(self.printer.printed_jobs, [self.data])

    def test_printer_absent_or_cash_session_open_prints_nothing(self):
        self.printer.printer_present = False
        outcome = print_job(self.printer.printer_command, make_fingerprint("absent"), self.data)
        self.assertEqual((outcome.result, outcome.fault_code), (NOT_PRINTED, "PRINTER_NOT_READY"))
        self.printer.printer_present = True
        self.printer.start_payment("CASH-1", 1000)
        outcome = print_job(self.printer.printer_command, make_fingerprint("cash-open"), self.data)
        self.assertEqual(outcome.result, NOT_PRINTED)
        self.assertEqual(self.printer.printed_jobs, [])

    def test_lost_reply_resyncs_from_controller_offset(self):
        calls = {"chunks": 0}

        def flaky(name, **fields):
            result = self.printer.printer_command(name, **fields)
            if name == "PRINT_CHUNK":
                calls["chunks"] += 1
                if calls["chunks"] == 2:
                    raise ConnectionError("reply lost after the controller printed")
            return result

        outcome = print_job(flaky, make_fingerprint("flaky"), self.data)
        self.assertEqual(outcome.result, PRINTED)
        self.assertEqual(self.printer.printed_jobs, [self.data])  # no byte repeated

    def test_interrupted_job_is_ambiguous_and_blocks_until_cleared(self):
        self.printer.interrupt_print_after = 70
        first = make_fingerprint("interrupted")
        outcome = print_job(self.printer.printer_command, first, self.data)
        self.assertEqual((outcome.result, outcome.received), (AMBIGUOUS, 70))
        # Retrying the same job must not print the rest of a half receipt.
        self.assertEqual(print_job(self.printer.printer_command, first, self.data).result, AMBIGUOUS)
        blocked = print_job(self.printer.printer_command, make_fingerprint("next"), self.data)
        self.assertEqual((blocked.result, blocked.fault_code), (BLOCKED, "PRIOR_PRINT_AMBIGUOUS"))
        self.printer.printer_command("PRINT_CLEAR", fingerprint=first)
        self.assertEqual(print_job(self.printer.printer_command, make_fingerprint("next"), self.data).result, PRINTED)

    def test_controller_reset_mid_job_is_ambiguous(self):
        fingerprint = make_fingerprint("reset")
        self.printer.printer_command("PRINT_BEGIN", fingerprint=fingerprint, length=len(self.data))
        self.printer.printer_command("PRINT_CHUNK", fingerprint=fingerprint, offset=0, hex=self.data[:10].hex())
        self.printer.reset()
        self.assertEqual(print_job(self.printer.printer_command, fingerprint, self.data).result, AMBIGUOUS)

    def test_print_job_through_the_unix_daemon(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "hardware.sock")
            backend = SimulatedHardware()
            daemon = HardwareDaemon(backend, socket_path=path).start()
            try:
                client = UnixHardwareClient(path)
                receipt = render_receipt(SAMPLE_ORDER)
                outcome = print_job(client.printer_command, make_fingerprint("socket"), receipt)
                self.assertEqual(outcome.result, PRINTED)
                self.assertEqual(backend.printed_jobs, [receipt])
                with self.assertRaises(Exception) as caught:
                    client.printer_command("PRINT_CLEAR", fingerprint=make_fingerprint("unknown"))
                self.assertIn("PRINT_CLEAR_REJECTED", str(caught.exception))
            finally:
                daemon.stop()


class DaemonStatusFrameTests(unittest.TestCase):
    def test_faulted_real_status_still_fits_one_frame(self):
        """A fault used to push the 243-byte status past 256 bytes, so the POS
        saw "disconnected" instead of the fault (2026-09-28 live test)."""
        from hardware.protocol import decode_frame

        class Backend:
            def status(self):
                return {
                    "mode": "real", "connected": False, "healthy": False, "simulator": False,
                    "firmware_identity": "mendo-controller-v1", "protocol_version": "1",
                    "last_heartbeat": "2026-09-28 01:50:00", "acceptors_inhibited": True,
                    "physical_evidence_required": False, "configuration_valid": True,
                    "fault_code": "SerialTimeoutException: Write timeout", "protocol_errors": 4,
                }

        daemon = HardwareDaemon(Backend(), socket_path="/nonexistent")
        fields = decode_frame(daemon._status_response("R0123456789", "HEARTBEAT")).fields
        self.assertTrue(fields["fault_code"].startswith("SerialTimeout"))
        self.assertEqual(fields["healthy"], "0")


class ReceiptFlowTests(TemporaryOrderCase):
    def setUp(self):
        super().setUp()
        from pos.routes_checkout import checkout_bp

        self.app.secret_key = "receipt-flow-test"
        self.app.register_blueprint(checkout_bp)
        self.hardware = HardwareService(VendoBridge(mode="simulator"))
        self.app.extensions["mendo_hardware"] = self.hardware
        self.sim = self.hardware.bridge.backend
        self.client = self.app.test_client()

    def pay_order(self) -> dict:
        item = self.item(8)
        order = self.service.create_order(
            [{"inventory_id": item["id"], "quantity": 1}],
            idempotency_key=f"receipt-{len(self.sim.printed_jobs)}-{id(self)}",
            payment_method="cash",
        )
        started = self.client.post(
            f"/checkout/api/orders/{order['order_ref']}/cash/start",
            json={"no_change_consent": True},
        )
        self.assertEqual(started.status_code, 200)
        paid = self.client.post(
            f"/checkout/api/orders/{order['order_ref']}/cash/simulate",
            json={"source": "bill", "centavos": 10000},
        )
        self.assertEqual(paid.status_code, 200)
        return paid.get_json()

    def test_completed_sale_prints_one_receipt(self):
        completed = self.pay_order()
        self.assertEqual(completed["fulfillment_state"], "completed")
        self.assertEqual(completed["receipt_print"]["state"], "printed")
        self.assertEqual(completed["receipt_print"]["printer_mode"], "simulator")
        self.assertEqual(len(self.sim.printed_jobs), 1)
        self.assertIn(completed["transaction_ref"].encode(), self.sim.printed_jobs[0])
        # Polling the finished order must never print it again.
        polled = self.client.get(f"/checkout/api/orders/{completed['order_ref']}").get_json()
        self.assertEqual(polled["receipt_print"]["state"], "printed")
        self.assertEqual(len(self.sim.printed_jobs), 1)

    def test_printer_fault_never_undoes_the_sale_and_is_retried(self):
        self.sim.printer_present = False
        completed = self.pay_order()
        self.assertEqual(completed["payment_state"], "paid")
        self.assertEqual(completed["fulfillment_state"], "completed")
        self.assertEqual(completed["receipt_print"]["state"], "failed")
        self.assertEqual(completed["receipt_print"]["last_error"], "PRINTER_NOT_READY")

        self.sim.printer_present = True
        original = receipt_module.AUTO_RETRY_INTERVAL_SECONDS
        receipt_module.AUTO_RETRY_INTERVAL_SECONDS = 0
        try:
            polled = self.client.get(f"/checkout/api/orders/{completed['order_ref']}").get_json()
        finally:
            receipt_module.AUTO_RETRY_INTERVAL_SECONDS = original
        self.assertEqual(polled["receipt_print"]["state"], "printed")
        self.assertEqual(len(self.sim.printed_jobs), 1)

    def test_staff_resolve_half_printed_receipt_with_labelled_reprint(self):
        self.sim.interrupt_print_after = 40
        completed = self.pay_order()
        self.assertEqual(completed["receipt_print"]["state"], "ambiguous")
        receipts = ReceiptPrintService(self.db, self.hardware)
        row = receipts.list_for_order(completed["id"])[0]

        # While ambiguous, the controller refuses every other job.
        self.assertEqual(receipts.test_print(actor="staff:1")["result"], BLOCKED)

        reprinted = receipts.resolve_ambiguous(row["print_ref"], action="reprint", actor="staff:1")
        self.assertEqual((reprinted["copy_no"], reprinted["state"]), (2, "printed"))
        self.assertIn(b"*** REPRINT ***", self.sim.printed_jobs[-1])
        states = [r["state"] for r in receipts.list_for_order(completed["id"])]
        self.assertEqual(states, ["cancelled", "printed"])

    def test_mark_printed_releases_the_controller(self):
        self.sim.interrupt_print_after = 40
        completed = self.pay_order()
        receipts = ReceiptPrintService(self.db, self.hardware)
        row = receipts.list_for_order(completed["id"])[0]
        resolved = receipts.resolve_ambiguous(row["print_ref"], action="mark_printed", actor="staff:1")
        self.assertEqual(resolved["state"], "printed")
        self.assertEqual(receipts.test_print(actor="staff:1")["result"], PRINTED)


if __name__ == "__main__":
    unittest.main()
