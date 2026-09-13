"""Serial-owned backend used only by the hardware daemon.

Flask workers never instantiate this class.  The daemon owns the one serial
descriptor, performs the firmware handshake, and keeps the acceptors in the
fail-safe state until the controller reports a verified configuration.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
import threading
import time
from typing import Any, Deque, Dict, Optional
import uuid

from .interface import HardwareFault
from .pulses import PulseMapping
from .protocol import ProtocolError, command, decode_frame


class SerialHardwareBackend:
    """Bounded request/response bridge for the Arduino controller."""

    mode = "real"

    def __init__(
        self,
        port: str = "/dev/mendo-uno",
        *,
        baudrate: int = 115200,
        timeout: float = 0.25,
        heartbeat_seconds: float = 1.0,
        boot_delay_seconds: float = 2.2,
    ):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.heartbeat_seconds = float(heartbeat_seconds)
        self.boot_delay_seconds = max(0.0, float(boot_delay_seconds))
        self._serial = None
        self._lock = threading.RLock()
        self._events: Deque[Dict[str, Any]] = deque(maxlen=32)
        self._pulse_mapping = PulseMapping()
        self._status: Dict[str, Any] = {
            "mode": "real",
            "connected": False,
            "healthy": False,
            "simulator": False,
            "firmware_identity": "",
            "protocol_version": "",
            "last_heartbeat": None,
            "acceptors_inhibited": True,
            "coin_power_enabled": False,
            "pca_outputs_enabled": False,
            "physical_evidence_required": True,
            "configuration_valid": False,
            "fault_code": "NOT_STARTED",
        }
        self._stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None

    def start(self) -> "SerialHardwareBackend":
        try:
            import serial  # pyserial is a production dependency

            self._stop.clear()
            self._serial = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            # Opening an Uno CDC serial port toggles DTR and resets the board.
            # Bytes written while the Optiboot bootloader is still active are
            # discarded, which previously made the very first HELLO time out
            # even though the correct firmware was installed.
            if self.boot_delay_seconds:
                time.sleep(self.boot_delay_seconds)
            self._serial.reset_input_buffer()
            self._status.update({"connected": True, "fault_code": None})
            hello = self._request("HELLO")
            self._apply_status(hello)
            if self._status.get("firmware_identity") != "mendo-controller-v1":
                raise HardwareFault("FIRMWARE_IDENTITY_MISMATCH")
            if str(self._status.get("protocol_version", "")) != "1":
                raise HardwareFault("PROTOCOL_VERSION_MISMATCH")
            # Establish health immediately. Waiting for the background loop's
            # first tick creates a race where the POS reports a healthy serial
            # controller as unavailable for roughly one second after startup.
            self.heartbeat()
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name="mendo-controller-heartbeat",
                daemon=True,
            )
            self._heartbeat_thread.start()
            return self
        except Exception as exc:
            self._set_fault(str(exc))
            self.close()
            raise HardwareFault(str(exc)) from exc

    def close(self) -> None:
        self._stop.set()
        if self._heartbeat_thread and self._heartbeat_thread is not threading.current_thread():
            self._heartbeat_thread.join(timeout=1.0)
        self._heartbeat_thread = None
        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                finally:
                    self._serial = None
            self._status.update(
                connected=False,
                healthy=False,
                acceptors_inhibited=True,
                coin_power_enabled=False,
                pca_outputs_enabled=False,
                fault_code="SERIAL_DISCONNECTED",
            )

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def heartbeat(self) -> Dict[str, Any]:
        result = self._request("HEARTBEAT", enable=0)
        self._apply_status(result)
        self._status["last_heartbeat"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.status()

    def start_payment(self, session_ref: str, amount_due_centavos: int) -> Dict[str, Any]:
        result = self._request("PAY_START", session=session_ref, due=int(amount_due_centavos))
        self._apply_status(result)
        self._status.update(acceptors_inhibited=False, coin_power_enabled=True)
        return self.status()

    def stop_payment(self, session_ref: str) -> Dict[str, Any]:
        result = self._request("PAY_STOP", session=session_ref)
        self._apply_status(result)
        self._status.update(acceptors_inhibited=True, coin_power_enabled=False)
        return self.status()

    def dispense_one(self, job_id: str, slot: int, profile_version: str) -> Dict[str, Any]:
        result = self._request("DISPENSE_ONE", job_id=job_id, slot=int(slot), profile=profile_version)
        self._apply_status(result)
        return {"job_id": job_id, **result}

    def job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        result = self._request("JOB_STATUS", job_id=job_id)
        if result.get("known") in {"0", 0, False}:
            # Preserve an explicit controller-negative result. The caller may
            # release and retry only after this answer; a transport exception
            # remains an unknown physical result and is never retried.
            return {"known": 0, "job_id": job_id}
        return result

    def drain_events(self) -> list[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    def poll_event(self) -> Optional[Dict[str, Any]]:
        """Peek until ACK, pulling the controller's EEPROM fallback if needed."""
        with self._lock:
            if self._events:
                return dict(self._events[0])
        # Cash events are normally received asynchronously while a heartbeat
        # request is reading serial. CASH_POLL closes the loss window: the AVR
        # keeps the validated pulse record in EEPROM and returns it until the
        # database commit is followed by CASH_ACK.
        result = self._request("CASH_POLL")
        if str(result.get("has_event", "0")) == "1":
            self._capture_cash_event(result)
        with self._lock:
            return dict(self._events[0]) if self._events else None

    def ack_cash_event(self, boot_id: str, sequence_no: int, source: str) -> Dict[str, Any]:
        result = self._request(
            "CASH_ACK", boot_id=boot_id, sequence_no=int(sequence_no), source=source
        )
        with self._lock:
            for index, event in enumerate(self._events):
                if (
                    str(event.get("boot_id")) == str(boot_id)
                    and int(event.get("sequence_no", -1)) == int(sequence_no)
                    and str(event.get("source")) == str(source)
                ):
                    del self._events[index]
                    break
        return result

    def cash_diagnostics(self) -> Dict[str, Any]:
        return dict(self._request("CASH_DIAG"))

    def cash_evidence(self, slot: int) -> Dict[str, Any]:
        return dict(self._request("CASH_EVIDENCE", slot=int(slot)))

    def _capture_cash_event(self, fields: Dict[str, str]) -> None:
        """Normalize the AVR evidence frame into the POS cash contract.

        Firmware owns pulse timing validation. The host owns denomination
        policy, so ``mapped_centavos=0;requires_mapping=1`` is expected on the
        wire and is converted from the calibrated clean-pulse count here.
        """
        source = str(fields.get("source", ""))
        try:
            pulses = int(fields.get("raw_pulses", "0"))
            sequence = int(fields.get("sequence_no", "0"))
        except (TypeError, ValueError):
            self._set_fault("MALFORMED_CASH_EVENT")
            return
        if source not in {"coin", "bill"} or pulses <= 0 or sequence <= 0:
            self._set_fault("MALFORMED_CASH_EVENT")
            return
        boot_id = str(fields.get("boot_id", ""))
        session_ref = str(fields.get("session_ref") or fields.get("session") or "")
        mapped = self._pulse_mapping.map(source, pulses) or 0
        event = {
            "event": "CASH_EVENT",
            "event_id": f"{boot_id}-{source}-{sequence}",
            "session_ref": session_ref,
            "source": source,
            # Protocol name retained for compatibility: these are validated
            # clean pulses, never the noisy ISR edge counter.
            "raw_pulses": pulses,
            "mapped_centavos": mapped,
            "boot_id": boot_id,
            "sequence_no": sequence,
            "quality": str(fields.get("quality", "ok")),
        }
        if fields.get("pulse_started_ms") is not None:
            event["pulse_started_at"] = fields["pulse_started_ms"]
        if not session_ref or not boot_id:
            self._set_fault("MALFORMED_CASH_EVENT")
            return
        with self._lock:
            identity = (boot_id, source, sequence)
            if not any(
                (str(item.get("boot_id")), str(item.get("source")), int(item.get("sequence_no", -1)))
                == identity
                for item in self._events
            ):
                self._events.append(event)

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self.heartbeat_seconds):
            try:
                self.heartbeat()
            except Exception as exc:
                self._set_fault(str(exc))

    def _request(self, name: str, **fields: object) -> Dict[str, str]:
        with self._lock:
            if self._serial is None:
                raise HardwareFault("SERIAL_NOT_OPEN")
            request_id = f"R{uuid.uuid4().hex[:10]}"
            self._serial.write(command(request_id, name, **fields))
            self._serial.flush()
            deadline = time.monotonic() + max(1.0, self.timeout * 8)
            while time.monotonic() < deadline:
                raw = self._serial.readline(256)
                if not raw:
                    continue
                try:
                    frame = decode_frame(raw)
                except ProtocolError:
                    self._set_fault("PROTOCOL_ERROR")
                    continue
                if frame.kind == "EVT":
                    if frame.command == "CASH_EVENT":
                        self._capture_cash_event(frame.fields)
                    continue
                if frame.request_id != request_id:
                    continue
                if frame.fields.get("ok") == "0":
                    raise HardwareFault(frame.fields.get("fault_code", "CONTROLLER_REJECTED"))
                return frame.fields
            raise HardwareFault("CONTROLLER_TIMEOUT")

    def _apply_status(self, status: Dict[str, Any]) -> None:
        with self._lock:
            for key in (
                "firmware_identity", "protocol_version", "last_heartbeat",
                "fault_code", "mode",
            ):
                if key in status:
                    self._status[key] = status[key] or None
            for key in (
                "connected", "healthy", "acceptors_inhibited", "coin_power_enabled",
                "pca_outputs_enabled", "physical_evidence_required", "configuration_valid",
            ):
                if key in status:
                    value = status[key]
                    self._status[key] = str(value).lower() in {"1", "true", "yes"}
            self._status["connected"] = True

    def _set_fault(self, fault: str) -> None:
        with self._lock:
            self._status.update(
                connected=False,
                healthy=False,
                acceptors_inhibited=True,
                coin_power_enabled=False,
                pca_outputs_enabled=False,
                fault_code=fault,
            )
