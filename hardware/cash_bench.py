"""Bench cash session: enable the acceptors and log every validated train.

    python -m hardware.cash_bench --minutes 5

Opens a controller payment session that the POS knows nothing about, so the
real firmware reports each coin/bill exactly as it would during a sale, but
nothing is credited to any order. Every event is printed with the time it
arrived, the validated pulse count, the host's peso mapping and the quality
flag, then acknowledged. Stops the session on exit (Ctrl-C or timeout).
Needs the hardware daemon running; stop the POS from polling orders meanwhile.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import os
import time

from .daemon import UnixHardwareClient
from .pulses import PulseMapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=5.0)
    parser.add_argument("--session", default=f"BENCH-{datetime.now():%H%M%S}")
    args = parser.parse_args()
    client = UnixHardwareClient(os.environ.get("MENDO_HARDWARE_SOCKET", "/tmp/mendo-hardware.sock"))
    mapping = PulseMapping()
    client.start_payment(args.session, 10_000_00)
    print(f"{datetime.now():%H:%M:%S} bench session {args.session} open; acceptors enabled", flush=True)
    deadline = time.monotonic() + args.minutes * 60
    try:
        while time.monotonic() < deadline:
            event = client.poll_event()
            if not event:
                time.sleep(0.3)
                continue
            pulses = int(event.get("raw_pulses", 0))
            source = str(event.get("source", ""))
            pesos = (mapping.map(source, pulses) or 0) / 100
            print(
                f"{datetime.now():%H:%M:%S}  {source:4}  pulses={pulses:<3}  "
                f"maps_to=PHP {pesos:<6.2f}  quality={event.get('quality', '?')}  "
                f"seq={event.get('sequence_no')}",
                flush=True,
            )
            client.ack_cash_event(str(event.get("boot_id", "")), int(event.get("sequence_no", 0)), source)
    except KeyboardInterrupt:
        pass
    finally:
        client.stop_payment(args.session)
        print(f"{datetime.now():%H:%M:%S} bench session closed; acceptors inhibited", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
