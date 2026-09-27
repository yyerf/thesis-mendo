"""Send protocol commands straight to the controller for bench checks.

    python -m hardware.probe HEARTBEAT PRINTER_STATUS CASH_DIAG
    python -m hardware.probe PRINTER_STATUS:fingerprint=8a1b2c3d4e5f6071

Each argument is ``COMMAND[:key=value,key=value]``. A HEARTBEAT is sent
before each command so health-gated commands see a live host. Opening the
port resets the Uno. Stop the hardware daemon first: it owns the port.
"""

from __future__ import annotations

import os
import sys
import time

from .protocol import command, decode_frame

DEFAULT_PORT = "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_751363233373514071E2-if00"


def _exchange(port, request_id: str, name: str, fields: dict, wait: float = 1.0) -> list[str]:
    port.write(command(request_id, name, **fields))
    deadline, raw = time.monotonic() + wait, b""
    while time.monotonic() < deadline:
        raw += port.read(512)
        if any(
            line.split(b"|")[2:3] == [request_id.encode()]
            for line in raw.split(b"\n")[:-1]  # complete lines only
        ):
            break
    return [line.decode("ascii", "replace") for line in raw.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    import serial

    if not argv:
        print(__doc__)
        return 2
    port = serial.Serial(os.environ.get("MENDO_SERIAL_DEVICE", DEFAULT_PORT), 115200, timeout=0.1)
    time.sleep(2.5)  # Optiboot runs after the DTR reset
    port.reset_input_buffer()
    for index, arg in enumerate(argv):
        name, _, rest = arg.partition(":")
        fields = dict(pair.split("=", 1) for pair in rest.split(",") if pair)
        if name != "HEARTBEAT":
            _exchange(port, f"h{index}", "HEARTBEAT", {}, wait=0.3)
        for line in _exchange(port, f"p{index}", name, fields):
            try:
                frame = decode_frame((line.rstrip("\r") + "\n").encode())
                print(f"{name}: {frame.command} {frame.fields}")
            except Exception:
                print(f"{name}: (unparsed) {line}")
    port.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
