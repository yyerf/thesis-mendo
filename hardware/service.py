"""Flask integration for the dedicated hardware daemon or explicit simulator."""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import current_app

from .serial_bridge import VendoBridge


class HardwareService:
    def __init__(self, bridge: VendoBridge):
        self.bridge = bridge

    @classmethod
    def from_environment(cls) -> "HardwareService":
        return cls(VendoBridge())

    def status(self) -> Dict[str, Any]:
        return self.bridge.status()

    def ready_for_cash(self) -> bool:
        status = self.status()
        def truthy(value: Any) -> bool:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        if not truthy(status.get("healthy")) or not truthy(status.get("connected")):
            return False
        if status.get("mode") == "real":
            # A healthy serial link is not enough to authorize money. The
            # daemon must prove the expected firmware/protocol and explicitly
            # report that the physical calibration/evidence gate is closed.
            if status.get("firmware_identity") != "mendo-controller-v1":
                return False
            if str(status.get("protocol_version", "")) != "1":
                return False
            if not status.get("last_heartbeat") or status.get("fault_code"):
                return False
            if truthy(status.get("physical_evidence_required", True)):
                return False
            if str(status.get("configuration_valid", "0")).lower() not in {"1", "true", "yes"}:
                return False
        return True

    def start_cash(self, session_ref: str, amount_due_centavos: int) -> Dict[str, Any]:
        return self.bridge.start_payment(session_ref, amount_due_centavos)

    def stop_cash(self, session_ref: str) -> Dict[str, Any]:
        return self.bridge.stop_payment(session_ref)

    def dispense(self, job_id: str, slot: int, profile_version: str) -> Dict[str, Any]:
        return self.bridge.dispense_one(job_id, slot, profile_version)

    def inject_cash(self, source: str, centavos: int) -> Dict[str, Any]:
        if not self.bridge.simulator:
            raise RuntimeError("Cash injection is disabled outside simulator mode")
        return self.bridge.insert_cash(source, centavos)

    def poll_event(self) -> Dict[str, Any] | None:
        return self.bridge.poll_event()

    def ack_cash_event(self, boot_id: str, sequence_no: int, source: str) -> Dict[str, Any]:
        return self.bridge.ack_cash_event(boot_id, sequence_no, source)


def get_hardware_service() -> HardwareService:
    service = current_app.extensions.get("mendo_hardware")
    if service is None:
        service = HardwareService.from_environment()
        current_app.extensions["mendo_hardware"] = service
    return service
