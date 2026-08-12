"""Executable entry point for the dedicated hardware daemon.

Run with ``MENDO_HARDWARE_MODE=simulator`` for development or ``real`` on the
host that owns the udev-created serial device.  Flask is a socket client and
must not run this module inside a web worker.
"""

from __future__ import annotations

import os
import signal
import time

from .daemon import HardwareDaemon
from .real_backend import SerialHardwareBackend
from .simulator import SimulatedHardware


def main() -> None:
    mode = os.environ.get("MENDO_HARDWARE_MODE", "simulator").lower()
    socket_path = os.environ.get("MENDO_HARDWARE_SOCKET", "/run/mendo/hardware.sock")
    if mode == "real":
        backend = SerialHardwareBackend(
            os.environ.get("MENDO_SERIAL_DEVICE", "/dev/mendo-uno"),
            baudrate=int(os.environ.get("MENDO_SERIAL_BAUD", "115200")),
        )
    elif mode == "simulator":
        backend = SimulatedHardware()
    else:
        raise SystemExit("MENDO_HARDWARE_MODE must be simulator or real")

    daemon = HardwareDaemon(backend, socket_path=socket_path).start()
    stop = {"value": False}

    def request_stop(_signum, _frame):
        stop["value"] = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while not stop["value"]:
            time.sleep(0.5)
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()
