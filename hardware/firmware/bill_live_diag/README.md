# Live bench diagnostics

Two read-only Arduino Uno sketches. Neither drives inhibit, coin power,
PCA9685 OE, or a servo. Neither can credit an order. They are bench
instruments; the Phase-0 gate in `hardware/README.md` still governs.

## `bill_live_diag` — is this a credit pulse or noise?

Watches **both** D2/INT0 and D3/INT1, so it works regardless of which pin
METER+ landed on. For every burst of line activity it prints raw edge count
next to clean pulse count:

- **raw edges** — unfiltered interrupt count, i.e. the noise floor
- **clean pulses** — survivors of a 20 ms glitch filter, i.e. real credit

The gap between those two numbers is the whole diagnosis. `raw=4000,
clean=0` means the line is busy but nothing was ever paid.

It also reports LOW width, pulse period, whether the timing matches TB74 Fast
(50/100) or Slow (50/300), and maps clean pulse counts to pesos at the
documented 1 pulse = ₱10 scaling:

| pulses | 2 | 5 | 10 | 20 | 50 | 100 |
| --- | --- | --- | --- | --- | --- | --- |
| value | ₱20 | ₱50 | ₱100 | ₱200 | ₱500 | ₱1000 |

Any interval under 80 ms is counted separately as `sub-80ms events` — the
fastest credit pulse in this whole device family is 80 ms, so those are
provably not payment.

## `line_check` — what is physically attached to this pin?

Samples D2 and D3 with the internal pull-up ON and OFF and reports duty
cycle, transition count and rate. That separates:

| Result | Meaning |
| --- | --- |
| `HELD LOW` | low-impedance path to GND — the pull-up cannot lift it. An idle METER+ reads HIGH, so this pin is **not** METER+ |
| `HIGH and quiet` | idle METER+ (correct), or an open pin — insert a note to tell them apart |
| `FLOATING` | nothing driving it |
| `OSCILLATING` | active noise source, unusable as-is |

## Running them

```bash
# build + flash
arduino --upload --board arduino:avr:uno --port /dev/ttyACM0 \
  hardware/firmware/bill_live_diag/bill_live_diag.ino

# watch (Ctrl-] to quit)
python3 -m serial.tools.miniterm /dev/ttyACM0 115200
```

Serial is **115200**. If you use the Arduino IDE's Serial Monitor instead,
set the baud rate to match or you will see garbage.

`USE_INTERNAL_PULLUP` at the top of `bill_live_diag.ino` defaults to `1` so
the sketch runs on the existing wiring. Set it to `0` once the external
4.7 kΩ pull-up to Uno 5 V is fitted — that is the value the TB manual's pulse
interface actually specifies (printed page 13 / PDF page 16).
