"""Compatibility bridge facade with explicit simulator/real modes."""

from __future__ import annotations

import os
from typing import Any, Dict

from .daemon import UnixHardwareClient
from .interface import HardwareFault
from .simulator import SimulatedHardware


class VendoBridge:
    """Use the simulator by default; real mode talks only to the daemon socket."""

    def __init__(self, mode: str | None = None, socket_path: str | None = None):
        self.mode = (mode or os.environ.get("MENDO_HARDWARE_MODE", "simulator")).lower()
        if self.mode == "simulator":
            self.backend = SimulatedHardware()
        elif self.mode == "real":
            self.backend = UnixHardwareClient(socket_path or os.environ.get("MENDO_HARDWARE_SOCKET", "/run/mendo/hardware.sock"))
        else:
            raise ValueError("MENDO_HARDWARE_MODE must be simulator or real")

    @property
    def simulator(self) -> bool:
        return self.mode == "simulator"

    def status(self) -> Dict[str, Any]:
        try:
            status = self.backend.status()
            status["mode"] = self.mode
            status["simulator"] = self.simulator
            status.setdefault("physical_evidence_required", not self.simulator)
            status.setdefault("configuration_valid", self.simulator)
            return status
        except Exception as exc:
            return {
                "mode": self.mode,
                "simulator": self.simulator,
                "connected": False,
                "healthy": False,
                "acceptors_inhibited": True,
                "coin_power_enabled": False,
                "pca_outputs_enabled": False,
                "fault_code": str(exc),
                "physical_evidence_required": True,
                "configuration_valid": False,
            }

    def start_payment(self, session_ref: str, amount_due_centavos: int) -> Dict[str, Any]:
        return self.backend.start_payment(session_ref, amount_due_centavos)

    def stop_payment(self, session_ref: str) -> Dict[str, Any]:
        return self.backend.stop_payment(session_ref)

    def dispense_one(self, job_id: str, slot: int, profile_version: str) -> Dict[str, Any]:
        return self.backend.dispense_one(job_id, slot, profile_version)

    def heartbeat(self) -> Dict[str, Any]:
        return self.backend.heartbeat()

    def job_status(self, job_id: str) -> Dict[str, Any] | None:
        method = getattr(self.backend, "job_status", None)
        return method(job_id) if method else None

    def poll_event(self) -> Dict[str, Any] | None:
        method = getattr(self.backend, "poll_event", None)
        return method() if method else None

    def ack_cash_event(self, boot_id: str, sequence_no: int, source: str) -> Dict[str, Any]:
        method = getattr(self.backend, "ack_cash_event", None)
        if not method:
            return {"ok": True}
        return method(boot_id, sequence_no, source)

    def insert_cash(self, source: str, centavos: int) -> Dict[str, Any]:
        method = getattr(self.backend, "insert_cash", None)
        if not method:
            raise HardwareFault("Cash injection is simulator-only")
        return method(source, centavos)
