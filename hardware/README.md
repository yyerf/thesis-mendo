# MendoVendo hardware guide

Status: **payment-only POS integration with receipt printing; medicine motors disabled.**
2026-09-28: bill path (D3) verified; **coin path (D2) signal is faulty and the
TB74 inhibit is not wired** — see [Open hardware issues](#open-hardware-issues-2026-09-28).

The controller now carries the same D2 coin and D3 TB74 timing filters used by
the successful bench sketch. The host maps validated pulses, binds them to one
active payment session, persists them before ACK, and retains every queued
event in a burst. When the amount due is reached, inventory and the receipt are
committed atomically. `DISPENSE_ONE` remains rejected at the firmware boundary,
and PCA9685 OE is held HIGH (disabled).

This enables the requested supervised POS payment test. It does not establish
production readiness: keep medicine motors disconnected, keep the collection
box supervised, and retain the simulator label as the software-only fallback.
The supplied legacy sketches remain under [`references/legacy/`](references/legacy/)
and are not the integrated controller.

## Run a payment-only test

1. Upload `hardware/firmware/mendo_controller/` (Arduino IDE, or
   `arduino-cli upload --fqbn arduino:avr:uno -p /dev/ttyACM0 hardware/firmware/mendo_controller`
   after `arduino-cli compile`). Close Serial Monitor afterward; the daemon
   needs exclusive access at **115200 baud**. The last known-good image from
   before the rebuild is in `firmware/backup/`.
2. Start the hardware daemon (replace `/dev/ttyACM0` if the Uno has another
   stable path):

   ```bash
   MENDO_HARDWARE_MODE=real \
   MENDO_HARDWARE_SOCKET=/tmp/mendo-hardware.sock \
   MENDO_SERIAL_DEVICE=/dev/ttyACM0 \
   ./.venv/bin/python -m hardware.daemon_main
   ```

3. In a second terminal, start the POS against the same socket:

   ```bash
   MENDO_HARDWARE_MODE=real \
   MENDO_HARDWARE_SOCKET=/tmp/mendo-hardware.sock \
   ./.venv/bin/python app.py
   ```

4. Open `/shop`, add medicine, select **Start Cash Payment**, and insert cash.
   The live dialog shows due, inserted, and remaining values. On success, verify
   `/admin/inventory`, the receipt, and stock logs. No motor job should exist.

## Receipt printer (KMP26, 58 mm)

Wiring: printer RX ← Uno **D9**, printer "TX" wire → Uno **D10**, printer GND →
Arduino GND, printer 12 V from the TB74's 12 V supply (WEL-R7U02 harness).
Both signal leads go through a series resistor (1–10 kΩ, unverified). The
printer's DTR pin is not connected.

- **D10 behaves as a busy output, not serial data.** Measured: LOW and fully
  steady at idle (0 changes in 45,263 samples); HIGH for ~400 ms only when the
  head draws peak current. Firmware waits while it is HIGH (max 3 s per chunk,
  then the job is marked interrupted).
- **No cutter.** GS V 0/1/66, ESC i and ESC m were all ignored. Receipts end
  with a 6-line feed so the text clears the tear bar; tear by hand.
- **Brown-out on solid rules (root cause of missing receipt text).** A
  full-width solid `----` rule made the printer go busy ~400 ms and lose the
  text already in its buffer (photos 2026-09-28). Receipts therefore use spaced
  dashes and start with `ESC 7 3 80 2` (at most 32 dots heated at once), which
  printed the same rule fully dark with 0 ms busy and nothing lost. A dedicated
  or heavier 12 V supply for the printer is still recommended.

Protocol (host → Uno, one ESC/POS job at a time, see `hardware/printer.py`):
`PRINT_BEGIN fingerprint,length` · `PRINT_CHUNK fingerprint,offset,hex` (≤ 96
bytes; host sends 64) · `PRINT_END fingerprint,length` · `PRINT_CLEAR
fingerprint` (staff) · `PRINTER_STATUS [fingerprint]`. Job states: 0 idle,
1 receiving, 2 printed, 3 interrupted. The single job record lives in EEPROM,
so a retry after a lost reply resumes at the controller's byte count and never
prints twice; a job interrupted mid-paper blocks all printing until staff
resolve it on **Admin → Hardware** (`PRINTER_STATUS` always reports the
blocking `job` fingerprint, so it can be cleared even if the host lost it).

POS side: every completed sale queues copy 1 in `receipt_prints` inside the
sale's transaction; printing runs after commit and can never undo a sale
(`pos/receipt_service.py`). Admin → Hardware shows printer state, a test-slip
button, retry, reprint, and the "paper is complete / reprint" decision for an
interrupted receipt.

## Bench diagnostics

Stop the daemon first (it owns the port), then:

```bash
.venv/bin/python -m hardware.probe HEARTBEAT PRINTER_STATUS CASH_DIAG
.venv/bin/python -m hardware.probe CASH_TRAIN:index=0 CASH_TRAIN:index=1
.venv/bin/python -m hardware.probe PRINTER_LINE_SCAN:ms=500
```

- `CASH_DIAG` — raw edge counters, current levels, open trains.
- `CASH_TRAIN index=N` — the last 8 finished coin/bill pulse trains (0 =
  oldest): validated pulses, settled LOWs, min/max LOW width and period, and
  the suspect flag. Recorded even when no payment is active, so a coin or bill
  can be characterised without crediting it. Also reachable through the
  daemon (`UnixHardwareClient.cash_train`).
- `PRINTER_LINE_SCAN ms=N` — samples D10 for N ms and counts level changes.

## Open hardware issues (2026-09-28)

1. **Bill inhibit not wired.** Yellow `INHIBIT+`/green `INHIBIT-` are not
   connected, so the TB74 accepted a ₱50 note while the Uno was inhibiting it.
   Money inserted outside an active payment is taken but never credited.
2. **Coin slot not switched by D5.** A coin was accepted with D5 (coin power)
   off, so the coin acceptor is powered directly. Same consequence as (1).
3. **Coin signal on D2 is unreliable.** Wiring: coin COUNTER → ~10 kΩ → D2 with
   only the Uno's ~35 kΩ internal pull-up. Observed: idle level alternating
   between LOW (with ~2,000 noise edges/s) and HIGH; ₱5 counted as 3 or 4
   pulses (flagged suspect); a ₱10+₱20 sequence produced ~7 pulse-shaped LOWs
   with 0.4–1.3 s irregular gaps and fragments instead of the August train
   (70 ms LOW / ~170 ms period, 1 pulse per peso). Check the Allan NO/NC
   switch, then use 1 kΩ series + 4.7 kΩ pull-up to 5 V (never a pull-up with
   the 10 kΩ still in series) or, better, a PC817 optocoupler; add ~100 nF to
   GND at D2.
4. **Both input lines carry bursts of thousands of sub-ms spikes per second**
   (bill ≈3,500/s) with nothing running. The firmware now ignores them for
   train timing (previously they could hold a train open so no cash event
   fired), but the source — likely shared 12 V/ground — should be fixed.

The bill path itself is healthy: a ₱50 note measured exactly 5 × 50 ms LOW at a
150 ms period.

## Reference files

Tracked copies and provenance are listed in
[`hardware/references/README.md`](references/README.md). The original supplied
files remain at the repository root while this integration is being audited.

The TB-to-Uno bench wiring is documented in the
[editable wiring diagram](tb-arduino-uno-wiring.svg) and its
[connection guide](tb-arduino-uno-wiring.md). Neither authorizes physical
power-up; the Phase-0 identity, polarity, voltage, and pulse-evidence gate
must be cleared first.

## Locked hardware mapping

| Arduino connection | Function |
| --- | --- |
| D0/D1 | USB serial only; no peripherals |
| D2 / INT0 | conditioned Allan coin pulse input |
| D3 / INT1 | conditioned TB METER pulse input |
| D4 | TB inhibit transistor control |
| D5 | fail-off coin-acceptor power relay/load switch |
| D6 | reserved for future shared chute sensor |
| D7 | PCA9685 active-low OE safety control |
| D8 | enclosure interlock input (pull-up; LOW = fail-safe). Empty on the 2026-09 kiosk |
| D9 | thermal printer RX — bit-banged 9600 8N1, idle HIGH |
| D10 | thermal printer busy line (the wire labelled "TX"; LOW = ready, HIGH ≈ busy) |
| A4/A5 | PCA9685 SDA/SCL (not linked in the payment+printer build) |
| PCA channels 0–9 | hardware slots 1–10 |

Uno and Mega builds must share one source tree. Board selection is a
compile-time target detail only; slot numbering, protocol frames, and database
mapping do not change.

## Power and safety gate

- Power the Arduino from host USB. Never put the acceptor’s 12 V rail on an
  Arduino input.
- Use a separately fused regulated 12 V supply for the TB and Allan devices.
  The TB guide states 12 V DC ±10%, with up to 1.2 A maximum operation.
- Use the external fused 5 V servo supply for the PCA9685 servo rail. Never
  power an MG996R from the Uno 5 V pin. Only one servo may be active at a time.
- Tie Arduino ground, PCA9685 logic ground, and servo-supply ground together
  at the documented logic boundary; keep the 12 V cash-device side isolated
  through the optocoupler/load-control interfaces.
- A hardware pull-up on PCA9685 OE must leave outputs disabled during reset,
  boot, serial loss, and firmware failure.
- Fit a master disconnect, branch fuses sized from measured current, terminal
  blocks, strain relief, and a locked collection enclosure.
- Before attaching the Uno, perform continuity and voltage tests. Every
  conditioned Arduino-side signal must measure 0–5 V in all expected states.

## TB bill acceptor bench wiring

The supplied guide documents WEL-R7U02 as follows. Verify every conductor with
continuity; do not trust color alone.

| Harness color | Function |
| --- | --- |
| Red | +12 V DC |
| Orange | 12 V ground |
| Blue | METER+ |
| Purple | METER- |
| Yellow | INHIBIT+ |
| Green | INHIBIT- |

Use the manual’s isolated customer-side pulse circuit: 4.7 kΩ pull-up to
Arduino 5 V, METER+ to D3, and METER- to Arduino logic ground. Drive the
inhibit pair through the documented NPN interface with a base resistor and
hardware pull-down. Select and prove a polarity where boot, reset, missing
heartbeat, disconnected USB, and daemon failure inhibit the acceptor.

The exact TB model (TB74/TB77 variant), PHP firmware label, DIP banks, currency
sheet, pulse protocol, and pulse counts are **not yet recorded**. Do not copy
settings from a TP-series Philippine sheet. Record twenty consecutive correct
trials for each enabled ₱20/₱50/₱100 denomination and rejection trials for
₱200/₱500/₱1000 before enabling cash.

## Allan coin acceptor bench calibration

Use a 12 V-rated optocoupler input module. The unknown-voltage COIN wire must
not connect directly to D2. The optocoupler’s 5 V-side collector connects to
D2 with an external pull-up. Control acceptor power through the fail-off relay
or rated high-side load switch on D5 so an inactive order cannot swallow a
coin.

The selected six programs are:

| Program | Coin sample | H | P | F |
| --- | --- | ---: | ---: | ---: |
| 1 | old/current ₱1 | 20 | 1 | 8 |
| 2 | other ₱1 variant | 20 | 1 | 8 |
| 3 | old/current ₱5 | 20 | 5 | 8 |
| 4 | other ₱5 variant | 20 | 5 | 8 |
| 5 | old/current ₱10 | 20 | 10 | 8 |
| 6 | other ₱10 variant | 20 | 10 | 8 |

Use actual circulating coins in acceptable condition. Start at medium pulse
speed. For each accepted sample, capture pulse width, inter-pulse gap, total
train duration, idle level, and the conditioned D2 voltage. Firmware constants
must be derived from those captures. Unknown trains disable both acceptors and
route the order to manual review.

## Servo and rotor safety

PCA channels 0–9 map to slots 1–10. Each persisted profile must include
`position_a_us`, `position_b_us`, travel time, B dwell, return settle, cooldown,
and profile version. Pulse widths must be calibrated and range-checked; do not
assume 0°/180° endpoints. A `DISPENSE_ONE` job executes A → B → A, disables
the channel’s PWM, and reports only `dispensed_done_unverified` until the
future shared chute sensor is installed.

Phase 4 evidence must include 100 unloaded cycles and 20 loaded trials per
slot, with current draw, voltage droop, resets, jams, and wear recorded. A
successful servo acknowledgment is not evidence that medicine physically
reached the customer.

## Phase 0 evidence worksheet

Complete this table from the physical bench and attach photos or capture files
under `hardware/evidence/` (do not commit secrets or customer data).

| Evidence | Result | File/photo/capture |
| --- | --- | --- |
| TB exact model and variant | TB74-PH60Ni (label TB7441123 / 10PH6003 / B444) | operator-reported |
| TB PHP firmware label | PH6 — ₱20/50/100/200/500/1000 | vendor sheets in `references/vendor-dip-sheets/` |
| TB harness continuity | **pending** | pending |
| TB DIP banks and inhibit polarity | Pulse mode, 1 pulse/₱10, Fast, inhibit Active High; SW6+SW7 enable ₱20/₱50/₱100 | `docs/architecture/tb74-pulse-protocol-analysis.md` §1b |
| TB ₱20 pulse count/width/gap | **2 pulses**, 50 ms LOW, 151 ms period | 2026-08-03 23:23:16 capture |
| TB ₱50 pulse count/width/gap | **5 pulses**, 50 ms LOW, 150 ms period | 2026-08-03 23:23:21 capture |
| TB ₱100 pulse count/width/gap | **10 pulses**, 50 ms LOW, 150 ms period | 2026-08-03 23:23:24 capture |
| Higher-bill rejection | **pending** — ₱200/₱500/₱1000 disabled at DIP, not yet trialled | pending |
| Rejected-note zero-credit | 6 rejections, 23,064 raw edges, ₱0 credited | 2026-08-03 23:23 capture |
| Allan coin pulse captures | **pending** | pending |
| Arduino-side D2/D3 levels | **pending** | pending |
| 12 V and servo-rail measurements | **pending** | pending |
| Hardware photos | **pending** | pending |

Until every required row has evidence, the production gate remains closed.

## Software-only integration

The durable workflow lives in `pos/order_service.py`. It reserves stock using
`stock_quantity - reserved_quantity`, records integer-centavo payment events
exactly once, creates one immutable dispense job per unit, and projects one
legacy receipt only after every actuator job is acknowledged as
`done_unverified`. A successful controller motion is never presented as proof
that medicine reached the chute.

After a Flask restart, polling a paid order resumes the durable dispatcher. It
queries any `started` job by immutable controller ID before sending another
command. Only a controller-negative `known=0` answer can release a job for a
staff retry; a missing or ambiguous answer remains manual review.

The hardware boundary is split into three processes/roles:

- `hardware.simulator.SimulatedHardware` is the deterministic development
  backend. Its status always says `mode=simulator` and
  `physical_evidence_required=true`.
- `hardware.daemon` owns the Unix socket and, in real deployments, the only
  serial descriptor. Flask workers use `UnixHardwareClient`; they never open a
  TTY. The sample systemd unit runs the daemon as `mendo-hardware:dialout`.
- `hardware.real_backend.SerialHardwareBackend` performs the bounded CRC
  handshake and heartbeat when the daemon is explicitly started in real mode.
  The firmware and service still require the physical-evidence/configuration
  gate to be cleared before cash can start.

Development commands:

```text
./.venv/bin/python -m pytest -q
MENDO_HARDWARE_MODE=simulator ./.venv/bin/python -m hardware.daemon_main
```

Do not set `MENDO_HARDWARE_MODE=real` until the Phase-0 worksheet is complete
and the R1–R4 remediation checkpoints have been approved. The current daemon
and firmware sources are not a release authorization for powered hardware.
The sample udev rule grants access to the dedicated daemon identity through
`dialout`; it does not recommend `chmod 666`.
