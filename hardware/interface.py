"""Hardware backend contracts used by Flask, the daemon, and tests."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Protocol


class HardwareFault(RuntimeError):
    pass


@dataclass
class HardwareHealth:
    mode: str
    connected: bool
    healthy: bool
    simulator: bool
    firmware_identity: str
    protocol_version: str
    last_heartbeat: str | None
    acceptors_inhibited: bool
    coin_power_enabled: bool
    pca_outputs_enabled: bool
    fault_code: str | None = None
    physical_evidence_required: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HardwareController(Protocol):
    def status(self) -> Dict[str, Any]: ...
    def start_payment(self, session_ref: str, amount_due_centavos: int) -> Dict[str, Any]: ...
    def stop_payment(self, session_ref: str) -> Dict[str, Any]: ...
    def dispense_one(self, job_id: str, slot: int, profile_version: str) -> Dict[str, Any]: ...
    def heartbeat(self) -> Dict[str, Any]: ...
