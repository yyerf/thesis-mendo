"""Dedicated local hardware daemon and Unix-socket frame server."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from collections import deque
import socket
import socketserver
import threading
import uuid
from typing import Any, Dict, Optional

from .interface import HardwareFault
from .protocol import Frame, ProtocolError, command, decode_frame, response
from .simulator import SimulatedHardware


class HardwareDaemon:
    """Own one backend and expose only bounded protocol frames over a socket."""

    def __init__(self, backend=None, *, socket_path: str = "/tmp/mendo-hardware.sock"):
        self.backend = backend or SimulatedHardware()
        self.socket_path = Path(socket_path)
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._pending_events = deque()

    def handle(self, frame: Frame) -> bytes:
        try:
            fields = frame.fields
            if frame.command in {"HELLO", "STATUS"}:
                return response(frame.request_id, "STATUS", **self._compact_status())
            if frame.command == "HEARTBEAT":
                self.backend.heartbeat()
                return response(frame.request_id, "HEARTBEAT", **self._compact_status())
            if frame.command == "PAY_START":
                self.backend.start_payment(fields.get("session", ""), int(fields.get("due", "0")))
                return response(frame.request_id, "ACK", ok=1, command=frame.command)
            if frame.command == "PAY_STOP":
                self.backend.stop_payment(fields.get("session", ""))
                return response(frame.request_id, "ACK", ok=1, command=frame.command)
            if frame.command == "DISPENSE_ONE":
                result = self.backend.dispense_one(fields["job_id"], int(fields["slot"]), fields["profile"])
                return response(frame.request_id, "ACK", ok=1, command=frame.command, **result)
            if frame.command == "JOB_STATUS":
                result = self.backend.job_status(fields["job_id"]) or {"known": 0}
                return response(frame.request_id, "JOB_STATUS", **result)
            if frame.command == "POLL_EVENT":
                poll = getattr(self.backend, "poll_event", None)
                event = poll() if poll else None
                if event:
                    return response(frame.request_id, "CASH_EVENT", has_event=1, **event)
                if not self._pending_events:
                    drain = getattr(self.backend, "drain_events", None)
                    self._pending_events.extend(drain() if drain else [])
                if self._pending_events:
                    return response(
                        frame.request_id, "CASH_EVENT", has_event=1,
                        **self._pending_events[0],
                    )
                return response(frame.request_id, "CASH_EVENT", has_event=0)
            if frame.command == "CASH_ACK":
                acknowledge = getattr(self.backend, "ack_cash_event", None)
                if acknowledge:
                    acknowledge(fields.get("boot_id", ""), int(fields.get("sequence_no", "0")), fields.get("source", ""))
                if self._pending_events:
                    candidate = self._pending_events[0]
                    if (
                        str(candidate.get("boot_id", "")) == fields.get("boot_id", "")
                        and str(candidate.get("sequence_no", "")) == fields.get("sequence_no", "")
                        and str(candidate.get("source", "")) == fields.get("source", "")
                    ):
                        self._pending_events.popleft()
                return response(frame.request_id, "ACK", ok=1, command=frame.command)
            if frame.command == "CASH_DIAG":
                diagnostic = getattr(self.backend, "cash_diagnostics", None)
                if not diagnostic:
                    raise ProtocolError("CASH_DIAG_UNSUPPORTED")
                return response(frame.request_id, "CASH_DIAG", **diagnostic())
            if frame.command == "CASH_EVIDENCE":
                evidence = getattr(self.backend, "cash_evidence", None)
                if not evidence:
                    raise ProtocolError("CASH_EVIDENCE_UNSUPPORTED")
                return response(
                    frame.request_id,
                    "CASH_EVIDENCE",
                    **evidence(int(fields.get("slot", "0"))),
                )
            if frame.command == "SIM_INSERT":
                result = self.backend.insert_cash(fields["source"], int(fields["centavos"]))
                return response(frame.request_id, "CASH_EVENT", **result)
            raise ProtocolError(f"Unsupported command {frame.command}")
        except (KeyError, ValueError, HardwareFault, ProtocolError) as exc:
            return response(frame.request_id, "ACK", ok=0, command=frame.command, fault_code=str(exc))

    def _compact_status(self) -> Dict[str, Any]:
        """Keep every response within the Uno-sized 256-byte frame budget."""
        status = self.backend.status()
        keys = (
            "mode", "connected", "healthy", "simulator", "firmware_identity",
            "protocol_version", "last_heartbeat", "acceptors_inhibited",
            "physical_evidence_required", "configuration_valid",
        )
        compact: Dict[str, Any] = {}
        for key in keys:
            value = status.get(key, "")
            if isinstance(value, bool) and key != "simulator":
                value = 1 if value else 0
            if key == "last_heartbeat" and value:
                try:
                    value = int(datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").timestamp())
                except ValueError:
                    value = 1
            compact[key] = value
        if status.get("fault_code"):
            compact["fault_code"] = status["fault_code"]
        return compact

    def start(self) -> "HardwareDaemon":
        if self._server:
            return self
        starter = getattr(self.backend, "start", None)
        if starter:
            starter()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass
        daemon = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                while True:
                    raw = self.rfile.readline(256)
                    if not raw:
                        return
                    try:
                        frame = decode_frame(raw)
                        self.wfile.write(daemon.handle(frame))
                        self.wfile.flush()
                    except ProtocolError:
                        return

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = Server(str(self.socket_path), Handler)
        os.chmod(self.socket_path, 0o660)
        self._thread = threading.Thread(target=self._server.serve_forever, name="mendo-hardware-daemon", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass
        closer = getattr(self.backend, "close", None)
        if closer:
            closer()


class UnixHardwareClient:
    """Short-lived socket client; Flask never owns a serial file descriptor."""

    def __init__(self, socket_path: str = "/run/mendo/hardware.sock", timeout: float = 1.5):
        self.socket_path = socket_path
        self.timeout = timeout

    def request(self, name: str, **fields: object) -> Dict[str, str]:
        request_id = f"R{uuid.uuid4().hex[:10]}"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.sendall(command(request_id, name, **fields))
            raw = b""
            while not raw.endswith(b"\n") and len(raw) < 256:
                chunk = sock.recv(256 - len(raw))
                if not chunk:
                    break
                raw += chunk
        frame = decode_frame(raw)
        if frame.fields.get("ok") == "0":
            raise HardwareFault(frame.fields.get("fault_code", "HARDWARE_REQUEST_FAILED"))
        return frame.fields

    def status(self) -> Dict[str, Any]:
        return dict(self.request("STATUS"))

    def start_payment(self, session_ref: str, amount_due_centavos: int) -> Dict[str, Any]:
        return dict(self.request("PAY_START", session=session_ref, due=amount_due_centavos))

    def stop_payment(self, session_ref: str) -> Dict[str, Any]:
        return dict(self.request("PAY_STOP", session=session_ref))

    def dispense_one(self, job_id: str, slot: int, profile_version: str) -> Dict[str, Any]:
        return dict(self.request("DISPENSE_ONE", job_id=job_id, slot=slot, profile=profile_version))

    def heartbeat(self) -> Dict[str, Any]:
        return dict(self.request("HEARTBEAT"))

    def job_status(self, job_id: str) -> Dict[str, Any]:
        return dict(self.request("JOB_STATUS", job_id=job_id))

    def poll_event(self) -> Optional[Dict[str, Any]]:
        result = self.request("POLL_EVENT")
        if str(result.get("has_event", "0")) != "1":
            return None
        return result

    def ack_cash_event(self, boot_id: str, sequence_no: int, source: str) -> Dict[str, Any]:
        return dict(self.request("CASH_ACK", boot_id=boot_id, sequence_no=sequence_no, source=source))

    def cash_diagnostics(self) -> Dict[str, Any]:
        return dict(self.request("CASH_DIAG"))

    def cash_evidence(self, slot: int) -> Dict[str, Any]:
        return dict(self.request("CASH_EVIDENCE", slot=int(slot)))
