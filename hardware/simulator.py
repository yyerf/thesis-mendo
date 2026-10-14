"""Deterministic cash/servo simulator with fault injection.

The simulator is intentionally visible in every status response. It is useful
for automated checkout and recovery tests, but it never represents physical
hardware acceptance evidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import uuid

from .interface import HardwareFault
from .pulses import PulseMapping


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class SimulatedHardware:
    mode = "simulator"

    def __init__(self, *, bill_pulses: Optional[Dict[int, int]] = None):
        # The bill mapping is an explicit simulator fixture, not a claim about
        # the unmeasured TB unit. It can be replaced by a captured calibration.
        self.mapping = PulseMapping(
            coins={1: 100, 5: 500, 10: 1000},
            bills=bill_pulses or {2: 2000, 5: 5000, 10: 10000},
        )
        self.boot_id = uuid.uuid4().hex[:12]
        self.sequence = 0
        self.connected = True
        self.healthy = True
        self.fault_code: Optional[str] = None
        self.last_heartbeat = datetime.now()
        self.payment_session: Optional[str] = None
        self.acceptors_inhibited = True
        self.coin_power_enabled = False
        self.pca_outputs_enabled = False
        self.job_results: Dict[str, Dict[str, Any]] = {}
        self.motion_history: list[Dict[str, Any]] = []
        self.active_servo_slot: Optional[int] = None
        self.fail_next_dispense = False
        self.fail_next_as = "unexecuted"
        self.lose_next_ack = False
        self.unknown_next_pulse = False
        # Receipt printer emulation of the controller's single EEPROM job.
        self.printer_present = True
        self.print_job: Dict[str, Any] = {"fingerprint": "", "state": 0, "length": 0, "received": 0}
        self.printed_jobs: list[bytes] = []
        self._print_buffer = bytearray()
        self.interrupt_print_after: Optional[int] = None

    def status(self) -> Dict[str, Any]:
        return {
            "mode": "simulator",
            "connected": self.connected,
            "healthy": self.healthy,
            "simulator": True,
            "firmware_identity": "mendo-simulator-v1",
            "protocol_version": "1",
            "last_heartbeat": self.last_heartbeat.strftime("%Y-%m-%d %H:%M:%S"),
            "acceptors_inhibited": self.acceptors_inhibited,
            "coin_power_enabled": self.coin_power_enabled,
            "pca_outputs_enabled": self.pca_outputs_enabled,
            "fault_code": self.fault_code,
            "boot_id": self.boot_id,
            "physical_evidence_required": True,
            "configured_coin_centavos": list(self.mapping.supported_centavos("coin")),
            "configured_bill_centavos": list(self.mapping.supported_centavos("bill")),
            "motion_count": len(self.motion_history),
        }

    def heartbeat(self) -> Dict[str, Any]:
        if not self.connected:
            raise HardwareFault("SERIAL_DISCONNECTED")
        self.last_heartbeat = datetime.now()
        return self.status()

    def start_payment(self, session_ref: str, amount_due_centavos: int) -> Dict[str, Any]:
        if not self.healthy or not self.connected:
            raise HardwareFault(self.fault_code or "HARDWARE_UNHEALTHY")
        if self.payment_session and self.payment_session != session_ref:
            raise HardwareFault("CASH_SESSION_BUSY")
        self.payment_session = session_ref
        self.acceptors_inhibited = False
        self.coin_power_enabled = True
        return self.status()

    def stop_payment(self, session_ref: str) -> Dict[str, Any]:
        if self.payment_session and self.payment_session != session_ref:
            raise HardwareFault("CASH_SESSION_MISMATCH")
        self.payment_session = None
        self.acceptors_inhibited = True
        self.coin_power_enabled = False
        return self.status()

    def insert_cash(self, source: str, centavos: int) -> Dict[str, Any]:
        if not self.payment_session or self.acceptors_inhibited or not self.connected or not self.healthy:
            raise HardwareFault("ACCEPTORS_INHIBITED")
        pulses = self.mapping.pulses_for(source, centavos)
        if self.unknown_next_pulse:
            self.unknown_next_pulse = False
            pulses = 99
        if pulses is None:
            raise HardwareFault("DENOMINATION_NOT_CONFIGURED")
        self.sequence += 1
        return {
            "event_id": f"{self.boot_id}-{self.sequence}",
            "session_ref": self.payment_session,
            "source": source,
            "raw_pulses": pulses,
            "mapped_centavos": self.mapping.map(source, pulses) or 0,
            "boot_id": self.boot_id,
            "sequence_no": self.sequence,
            "pulse_started_at": _now(),
        }

    def inject_raw_pulses(self, source: str, raw_pulses: int) -> Dict[str, Any]:
        if not self.payment_session or self.acceptors_inhibited:
            raise HardwareFault("ACCEPTORS_INHIBITED")
        self.sequence += 1
        return {
            "event_id": f"{self.boot_id}-{self.sequence}",
            "session_ref": self.payment_session,
            "source": source,
            "raw_pulses": int(raw_pulses),
            "mapped_centavos": self.mapping.map(source, raw_pulses) or 0,
            "boot_id": self.boot_id,
            "sequence_no": self.sequence,
            "pulse_started_at": _now(),
        }

    def cash_diagnostics(self) -> Dict[str, Any]:
        return {
            "coin_raw": 0,
            "bill_raw": 0,
            "coin_level": 1,
            "bill_level": 1,
            "coin_clean": 0,
            "bill_clean": 0,
            "coin_train": 0,
            "bill_train": 0,
            "coin_suspect": 0,
            "bill_suspect": 0,
            "event_sequence": self.sequence,
            "acceptors_enabled": int(not self.acceptors_inhibited),
        }

    def cash_evidence(self, slot: int) -> Dict[str, Any]:
        return {"slot": int(slot), "present": 0}

    def dispense_one(self, job_id: str, slot: int, profile_version: str) -> Dict[str, Any]:
        if job_id in self.job_results:
            result = dict(self.job_results[job_id])
            result["duplicate_request"] = True
            return result
        if not self.connected or not self.healthy:
            result = {"job_id": job_id, "event": "DISPENSE_FAILED", "error_code": self.fault_code or "HARDWARE_UNHEALTHY", "controller_result": "unknown"}
            self.job_results[job_id] = result
            return result
        if self.active_servo_slot is not None:
            raise HardwareFault("SERVO_BUSY")
        self.active_servo_slot = int(slot)
        self.pca_outputs_enabled = True
        self.motion_history.append({"job_id": job_id, "slot": int(slot), "profile_version": profile_version, "started_at": _now()})
        if self.fail_next_dispense:
            self.fail_next_dispense = False
            result = {"job_id": job_id, "event": "DISPENSE_FAILED", "error_code": "SIMULATED_JAM", "controller_result": self.fail_next_as}
            self.active_servo_slot = None
            self.pca_outputs_enabled = False
            self.job_results[job_id] = result
            return result
        result = {
            "job_id": job_id,
            "event": "DISPENSE_DONE_UNVERIFIED",
            "slot": int(slot),
            "profile_version": profile_version,
            "controller_result": "executed",
            "ack_lost": self.lose_next_ack,
        }
        self.lose_next_ack = False
        self.active_servo_slot = None
        self.pca_outputs_enabled = False
        self.job_results[job_id] = result
        return result

    def job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        result = self.job_results.get(job_id)
        return dict(result) if result else None

    def printer_command(self, name: str, **fields: Any) -> Dict[str, Any]:
        """Same observable contract as the controller's PRINT_* commands."""
        fingerprint = str(fields.get("fingerprint", "")).lower()
        job = self.print_job
        mine = bool(fingerprint) and job["state"] != 0 and job["fingerprint"] == fingerprint

        def status() -> Dict[str, Any]:
            ready = int(
                self.printer_present and self.healthy and self.connected
                and self.acceptors_inhibited
            )
            base = {"ready": ready, "dtr_level": 0 if self.printer_present else 1}
            if mine or (name == "PRINT_BEGIN" and job["fingerprint"] == fingerprint):
                return {"known": 1, **base, "state": job["state"], "received": job["received"], "length": job["length"]}
            return {"known": 0, **base, "state": 0, "received": 0, "length": 0}

        if name == "PRINTER_STATUS":
            return status()
        if name == "PRINT_CLEAR":
            if not mine:
                raise HardwareFault("PRINT_CLEAR_REJECTED")
            self.print_job = {"fingerprint": "", "state": 0, "length": 0, "received": 0}
            self._print_buffer = bytearray()
            return {"known": 0, "ready": 1, "dtr_level": 0, "state": 0, "received": 0, "length": 0}
        if name == "PRINT_BEGIN":
            try:
                length = int(fields.get("length", 0))
                valid = len(fingerprint) == 16 and int(fingerprint, 16) != 0
            except ValueError:
                valid = False
            if not valid or not 0 < length <= 4096:
                raise HardwareFault("BAD_PRINT_REQUEST")
            if mine:
                return status()
            if job["state"] in (1, 3):
                raise HardwareFault("PRIOR_PRINT_AMBIGUOUS")
            if not status()["ready"]:
                raise HardwareFault("PRINTER_NOT_READY")
            self.print_job = {"fingerprint": fingerprint, "state": 1, "length": length, "received": 0}
            self._print_buffer = bytearray()
            job = self.print_job
            mine = True
            return status()
        if name == "PRINT_CHUNK":
            if not mine or job["state"] != 1:
                raise HardwareFault("PRINT_JOB_NOT_ACTIVE")
            if int(fields.get("offset", -1)) != job["received"]:
                raise HardwareFault("PRINT_OFFSET_MISMATCH")
            try:
                chunk = bytes.fromhex(str(fields.get("hex", "")))
            except ValueError:
                raise HardwareFault("BAD_PRINT_CHUNK") from None
            if not chunk or job["received"] + len(chunk) > job["length"]:
                raise HardwareFault("BAD_PRINT_CHUNK")
            for byte in chunk:
                if not self.printer_present or (
                    self.interrupt_print_after is not None
                    and job["received"] >= self.interrupt_print_after
                ):
                    self.interrupt_print_after = None
                    job["state"] = 3
                    raise HardwareFault("PRINTER_INTERRUPTED")
                self._print_buffer.append(byte)
                job["received"] += 1
            return status()
        if name == "PRINT_END":
            if mine and job["state"] == 2:
                return status()
            if not mine or job["state"] != 1 or int(fields.get("length", -1)) != job["length"] or job["received"] != job["length"]:
                raise HardwareFault("PRINT_LENGTH_MISMATCH")
            job["state"] = 2
            self.printed_jobs.append(bytes(self._print_buffer))
            return status()
        raise HardwareFault("UNSUPPORTED_PRINTER_COMMAND")

    # Fault injection is intentionally explicit and test-only friendly.
    def disconnect(self) -> None:
        self.connected = False
        self.healthy = False
        self.fault_code = "SERIAL_DISCONNECTED"
        self._fail_safe()

    def reconnect(self) -> None:
        self.connected = True
        self.healthy = True
        self.fault_code = None
        self.last_heartbeat = datetime.now()
        self._fail_safe()

    def reset(self) -> None:
        if self.print_job["state"] == 1:
            # The controller cannot know how much reached the paper.
            self.print_job["state"] = 3
        self.boot_id = uuid.uuid4().hex[:12]
        self.sequence = 0
        self.payment_session = None
        self.last_heartbeat = datetime.now()
        self._fail_safe()

    def tick(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        current = now or datetime.now()
        if current - self.last_heartbeat > timedelta(seconds=3):
            self.healthy = False
            self.fault_code = "HEARTBEAT_TIMEOUT"
            self._fail_safe()
        return self.status()

    def _fail_safe(self) -> None:
        self.acceptors_inhibited = True
        self.coin_power_enabled = False
        self.pca_outputs_enabled = False
        self.active_servo_slot = None
