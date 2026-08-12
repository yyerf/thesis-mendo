# TB bill acceptor to Arduino Uno wiring

See the companion [editable wiring diagram](tb-arduino-uno-wiring.svg).

This is a **bench/reference schematic**, not physical acceptance evidence. It
uses the supplied TOPVME WEL-R7U02 harness mapping and the TB manual's isolated
customer-side interfaces. The exact connected TB model, PHP firmware label,
DIP sheet, and inhibit polarity are still pending.

## Connections shown

| TB harness | Connect to | Notes |
| --- | --- | --- |
| Pin 5, red, `+12 V DC` | Fused regulated 12 V positive | TB power domain only |
| Pin 9, orange, `12 V GND` | 12 V supply return | Do not route this to an Uno input |
| Pin 7, blue, `METER+` | Arduino D3 / INT1 and the R1 node | Isolated open-collector pulse output |
| Pin 8, purple, `METER-` | Arduino logic GND | Customer-side meter return |
| Pin 1, yellow, `INHIBIT+` | R2 1 kΩ, then Arduino 5 V logic | Verify polarity on the exact unit |
| Pin 2, green, `INHIBIT-` | Q1 NPN collector | Q1 emitter returns to Arduino logic GND |

The METER node gets an external **R1 = 4.7 kΩ pull-up to Arduino 5 V**. The
Arduino counts the conditioned pulse signal on D3; firmware must use the
measured source-specific pulse gap and calibrated pulse-count mapping.

The inhibit driver uses the manual's NPN open-collector arrangement. The
diagram shows **R3 = 2.2 kΩ** from D4 to the transistor base and **R4 = 100
kΩ** as a base pulldown. These are interface-design starting values, not
bench-validated values. Confirm base current, transistor ratings, the TB DIP
polarity, and the required inactive level before enabling cash.

## Common wiring mistakes

1. **Putting the pull-up in series.** R1 is a *pull-up*: it goes between the
   Arduino 5 V pin and the METER+ signal node. It does not go in line between
   METER+ and the Arduino input. The TB credit output is an opto-isolated open
   collector — it can only pull down, so without a pull-up the pin has no
   defined idle level.
2. **Bonding pin 9 (orange, 12 V GND) to Arduino ground.** This defeats the
   optocoupler, which is the entire reason it is fitted. Motor current up to
   1.2 A then shares a return path with your logic reference and injects noise
   directly into the signal. Pin 9 belongs to the 12 V supply return only.
   Pin 8 (purple, METER-) is the customer-side emitter and *is* the conductor
   that goes to Arduino logic ground.
3. **Landing a ground conductor on an input pin.** A pin the internal pull-up
   cannot lift is tied to ground; an idle METER+ must read HIGH. Use
   `hardware/firmware/line_check` to check this before trusting any counts.

Only two conductors touch the Arduino: **blue (pin 7) to D3**, and **purple
(pin 8) to Arduino GND**. Red and orange go to the fused 12 V supply and
nowhere else.

Optional noise filter: 100 nF from the signal node to Arduino GND. With
R1 = 4.7 kΩ that is a ~470 µs time constant, roughly 100x faster than the
50 ms credit pulse, so it removes microsecond glitches without distorting the
signal. Use 1 µF only if noise persists.

## Do not power until all are true

1. Continuity identifies every WEL-R7U02 conductor and the exact TB model.
2. The exact Philippine currency/DIP sheet for that TB unit is available; do
   not substitute a TP-series sheet.
3. Reset, USB loss, daemon failure, and missing heartbeat produce **bill
   inhibited** at the physical unit.
4. The 12 V rail is isolated from the Uno, and every conditioned Uno-side
   signal measures 0–5 V in all expected states.
5. The 12 V supply is fused/current-limited, with a master disconnect. The
   Arduino is powered from USB; no acceptor load is powered from an Uno pin.

The enabled denominations remain ₱20, ₱50, and ₱100. Higher denominations are
not enabled by this drawing. Record twenty correct trials per enabled
denomination and rejection trials for ₱200/₱500/₱1000 before clearing the
physical Phase-0 gate.

Source: the supplied TB installation guide, printed page 13 (PDF page 16) for
the pulse/inhibit interfaces and printed page 10 for the WEL-R7U02 harness.
