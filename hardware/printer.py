"""Receipt printing over the controller's PRINT_* commands.

The KMP26 58 mm thermal printer is wired to the Uno, not to the host: Uno D9
drives the printer's RX at 9600 baud and the printer's TX comes back on D10,
where the firmware treats a LOW idle line as "printer present". The host sends
already-rendered ESC/POS bytes in hex chunks:

    PRINT_BEGIN   fingerprint, length   -> open (or re-report) one job
    PRINT_CHUNK   fingerprint, offset, hex
    PRINT_END     fingerprint, length   -> job complete (state 2)
    PRINT_CLEAR   fingerprint           -> staff-only: forget a job
    PRINTER_STATUS [fingerprint]

Every reply is a ``PRINT_STATUS`` frame with ``known, ready, dtr_level,
state, received, length``. Controller job states: 0 idle, 1 receiving,
2 printed, 3 interrupted (the controller reset or the printer stalled mid-job,
so some of the receipt may already be on paper).

The controller keeps exactly one job record in EEPROM. The fingerprint makes a
repeated request idempotent: re-sending the same job after a lost reply either
resumes at the controller's ``received`` offset or reports it done; it never
prints the receipt twice. A state-3 job blocks every other job until staff
decide whether it printed (``PRINT_CLEAR``), because only a person can look at
the paper.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Dict, Optional

from .interface import HardwareFault


CHUNK_BYTES = 64          # 128 hex chars keeps the frame well under 240 bytes
MAX_JOB_BYTES = 4096      # measured limit of the original printer firmware

STATE_IDLE = 0
STATE_RECEIVING = 1
STATE_PRINTED = 2
STATE_INTERRUPTED = 3

# Outcomes reported to the POS.
PRINTED = "printed"            # this call (or an earlier one) finished the job
NOT_PRINTED = "not_printed"    # nothing of this job reached paper; safe to retry
RESUMABLE = "resumable"        # job open on the controller; retry resumes it
BLOCKED = "blocked"            # another job is interrupted; staff must clear it
AMBIGUOUS = "ambiguous"        # this job was interrupted mid-paper; staff decide

Send = Callable[..., Dict[str, Any]]


def make_fingerprint(key: str) -> str:
    """Return the 16-hex job identity for ``key``.

    The top bit is forced on. The original controller build parses only the
    first 32 bits and rejects zero, so this keeps fingerprints valid on both
    the recovered and the rebuilt firmware.
    """
    digest = bytearray(hashlib.sha256(key.encode("utf-8")).digest()[:8])
    digest[0] |= 0x80
    return digest.hex()


@dataclass
class PrintOutcome:
    result: str
    fault_code: Optional[str] = None
    received: int = 0
    length: int = 0

    @property
    def printed(self) -> bool:
        return self.result == PRINTED


def _int(fields: Dict[str, Any], key: str) -> int:
    try:
        return int(fields.get(key, 0))
    except (TypeError, ValueError):
        return 0


def _outcome_for(status: Dict[str, Any], length: int) -> Optional[PrintOutcome]:
    """Classify a job status; ``None`` means "still receiving, keep sending"."""
    state = _int(status, "state")
    received = _int(status, "received")
    if str(status.get("known", "0")) != "1":
        return PrintOutcome(NOT_PRINTED, "PRINT_JOB_UNKNOWN", received, length)
    if _int(status, "length") != length:
        # Only possible on the original 32-bit-fingerprint firmware when two
        # different receipts collide. Never stream into someone else's job.
        return PrintOutcome(BLOCKED, "PRINT_FINGERPRINT_COLLISION", received, length)
    if state == STATE_PRINTED:
        return PrintOutcome(PRINTED, None, received, length)
    if state == STATE_INTERRUPTED:
        return PrintOutcome(AMBIGUOUS, "PRINTER_INTERRUPTED", received, length)
    if state != STATE_RECEIVING:
        return PrintOutcome(NOT_PRINTED, f"PRINT_STATE_{state}", received, length)
    return None


def print_job(send: Send, fingerprint: str, data: bytes) -> PrintOutcome:
    """Stream one ESC/POS job through ``send(command, **fields)``.

    ``send`` raises :class:`HardwareFault` carrying the controller fault code
    when the controller answers ``ok=0``; any other exception is a transport
    failure whose effect is unknown until the controller is asked again.
    """
    length = len(data)
    if not 0 < length <= MAX_JOB_BYTES:
        raise ValueError(f"Print job must be 1..{MAX_JOB_BYTES} bytes")

    try:
        status = send("PRINT_BEGIN", fingerprint=fingerprint, length=length)
    except HardwareFault as exc:
        code = str(exc)
        if code == "PRIOR_PRINT_AMBIGUOUS":
            return PrintOutcome(BLOCKED, code, 0, length)
        return PrintOutcome(NOT_PRINTED, code, 0, length)
    except Exception as exc:
        # BEGIN is idempotent and sends nothing to the paper, so a lost reply
        # is resolved by the next attempt's BEGIN.
        return PrintOutcome(RESUMABLE, f"TRANSPORT:{exc}", 0, length)

    resyncs = 0
    while True:
        outcome = _outcome_for(status, length)
        if outcome is not None:
            return outcome
        offset = _int(status, "received")
        try:
            if offset >= length:
                status = send("PRINT_END", fingerprint=fingerprint, length=length)
            else:
                chunk = data[offset:offset + CHUNK_BYTES]
                status = send(
                    "PRINT_CHUNK", fingerprint=fingerprint, offset=offset, hex=chunk.hex()
                )
            continue
        except HardwareFault as exc:
            fault = str(exc)
        except Exception as exc:
            fault = f"TRANSPORT:{exc}"
        # The controller knows exactly how many bytes it passed to the
        # printer. Ask it rather than guessing, then continue from there.
        resyncs += 1
        try:
            status = send("PRINTER_STATUS", fingerprint=fingerprint)
        except Exception:
            return PrintOutcome(RESUMABLE, fault, offset, length)
        if resyncs > 3 and _int(status, "state") == STATE_RECEIVING:
            return PrintOutcome(RESUMABLE, fault, _int(status, "received"), length)
