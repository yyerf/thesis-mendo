"""Print the controller's last coin/bill pulse trains with wall-clock times.

    python -m hardware.cash_log            # show the log
    python -m hardware.cash_log --clear    # empty it before a bench run

Talks to the running hardware daemon (``MENDO_HARDWARE_SOCKET``, default
``/tmp/mendo-hardware.sock``). Trains are logged even when no payment is
active, so coins can be characterised without being credited. Expected
counts: coins 1 pulse per peso; bills 1 pulse per ₱10.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import os
import sys

from .daemon import UnixHardwareClient


def main(argv: list[str]) -> int:
    client = UnixHardwareClient(os.environ.get("MENDO_HARDWARE_SOCKET", "/tmp/mendo-hardware.sock"))
    first = client.cash_train(0, clear="--clear" in argv)
    if "--clear" in argv:
        print(f"Train log cleared at {datetime.now():%H:%M:%S}.")
        return 0
    count = int(first.get("count", 0))
    if not count:
        print("No pulse trains logged.")
        return 0
    print(f"{'#':>2}  {'time':8}  {'src':4}  {'pulses':>6}  {'lows':>4}  {'suspect':7}  "
          f"{'LOW ms':>9}  {'period ms':>9}  {'length':>7}")
    for index in range(count):
        t = first if index == 0 else client.cash_train(index)
        # Asked for "now" and "started" in one reply, so the age is exact
        # to within the reply's transit time.
        age_ms = (int(t["now_ms"]) - int(t["started_ms"])) & 0xFFFFFFFF
        when = datetime.now() - timedelta(milliseconds=age_ms)
        print(f"{index:>2}  {when:%H:%M:%S}  {t['source']:4}  {t['pulses']:>6}  {t['lows']:>4}  "
              f"{'YES' if t['suspect'] == '1' else 'no':7}  "
              f"{t['low_min'] + '-' + t['low_max']:>9}  {t['period_min'] + '-' + t['period_max']:>9}  "
              f"{int(t['duration_ms']) / 1000:>6.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
