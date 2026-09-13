# TB74-PH6 bill validator — protocol reverse-engineering analysis

Date: 2026-08-03. Status: **desk analysis complete, bench verification pending.**

This answers the V1 reverse-engineering brief. It does not authorize powered
cash. The `hardware/README.md` Phase-0 worksheet still governs.

---

## 0. Executive summary

Three findings, in order of importance.

1. **The protocol is Pulse, not RS232.** Settled by the 4-way DIP bank, which
   is already on its correct factory default. Hypothesis 1 in the brief is
   dead.
2. **The DIP switches are wrong. ₱50 and ₱100 are currently set to REJECT.**
   Only ₱20 is enabled. Two switches need to move: **SW7 and SW8 on the 10-way
   bank → ON.**
3. **The ₱50 note was never accepted, so no credit pulse was ever emitted.**
   Every pulse count recorded so far (122, 79, 30, 19, 1, 77/26/3) is motor and
   EMI noise from the acceptor pulling the note in, scanning it, and returning
   it. The timing proves this independently of the DIP finding.

---

## 1. The timing proof — why every measurement so far is noise

The TB74 pulse output has exactly two speed settings, selected by SW4 of the
10-way bank:

| SW4 | Mode | LOW (active) | HIGH (idle) | Falling-edge period |
| --- | --- | ---: | ---: | ---: |
| ON | Fast | 50 ms | 100 ms | **150 ms** |
| OFF | Slow (default) | 50 ms | 300 ms | **350 ms** |

The sibling ICT PHP6 sheets offer at most four options, the fastest being
`30 ms LO / 50 ms HI` = **80 ms period**. A TB74 Taiwan build uses 75/75 and
150/150.

**Across every documented configuration of this device class, the shortest
possible interval between two credit pulses is 80 ms. Our unit, on SW4=ON, is
150 ms.**

The brief records measured gaps of **~8 ms, ~10 ms, ~20 ms**.

That is one to two orders of magnitude too fast. No DIP setting, no currency
build, and no firmware revision of this acceptor emits credit pulses at that
rate. Therefore **none of the recorded edges were credit pulses.** The
observation that activity appears only while the transport motor runs, and
stops when idle, is consistent with brushed-motor commutation noise coupling
into a high-impedance input.

This also explains the "results varied dramatically" problem. The counts were
never measuring the device — each diagnostic sketch was measuring its own
debounce constant against a noise floor. A sketch with no debounce reported
122; one with a 50 ms debounce collapsed the same burst to 1.

Two contributing electrical factors:

- The input is on `INPUT_PULLUP` (internal, ~20–50 kΩ). The manual's pulse
  interface (printed page 13 / PDF page 16) is an opto-isolated open-collector
  **Credit O/P** and specifies an external **4.7 kΩ** pull-up. At 20–50 kΩ the
  node is 4–10× more susceptible to injected noise and has slow edges.
- Slow edges through a non-Schmitt AVR interrupt pin can retrigger. This is
  secondary here — it produces sub-millisecond bursts, not 8–20 ms ones — but
  it compounds the problem.

---

## 1a. Bench measurement, 2026-08-03 — the wiring is wrong upstream of the DIPs

Measured live on the connected Uno with `hardware/firmware/line_check`.
No note inserted, machine idle:

| Pin | Pull-up ON | Pull-up OFF | Reading |
| --- | --- | --- | --- |
| **D2 / INT0** | **0 % high**, ~14 glitches/400 ms, min run 8 µs | **0 % high, 0 transitions** | **HELD LOW** |
| **D3 / INT1** | 100 % high, 0 transitions | 100 % high, 0 transitions | HIGH and quiet |

`bill_live_diag` on the same wiring reported **~8,000 raw edges per second on
D2, continuously, with no note anywhere near the machine**, and `clean pulses
= 0` on every single burst. D3 never triggered at all.

**D2 cannot be METER+.** The TB74 pulse output is an opto-isolated
open-collector Credit O/P: idle means the transistor is off, the collector is
open, and a pull-up must lift the node HIGH. The Uno's internal pull-up cannot
lift D2 at all, and with the pull-up removed the pin is flat LOW with zero
transitions. That is a low-impedance path to ground — a **ground wire on the
wrong pin**, not a credit output.

This sits upstream of the DIP finding and explains the entire measurement
history in the brief: the counts were never wrong readings of the credit
output, they were readings of something that was never the credit output.

D3 reading a steady HIGH is consistent with either a correctly-landed idle
METER+ or an open pin — 400 ms is not long enough for AVR pin capacitance to
decay, so the two cannot be separated without inserting a note. Note that D3
is also what `hardware/README.md` locks METER+ to.

**Resolve before re-testing:** confirm by continuity which harness conductor
is on D2 and which is on D3. TB pin 7 BLUE (METER+) belongs on **D3**; TB pin 8
PURPLE (METER-) belongs on **Arduino GND**, not on an input pin.

## 1b. CONFIRMED — first successful credit read, 2026-08-03 23:09:16

After moving METER+ to D3 and fitting the external 4.7 kΩ pull-up, a ₱50 note
was inserted and **kept (stacked)**. Captured on D3/INT1:

```
channel        : D3 / INT1
raw edges      : 2317   (unfiltered)
clean pulses   : 5      (real credit)
LOW width      : 50 / 50 / 50    ms  (min/avg/max)
pulse period   : 150 / 150 / 151 ms  (min/avg/max)
VERDICT        : CREDIT PULSE TRAIN (timing valid)
timing profile : TB74 FAST (50/100, SW4=ON)
MONEY          : PHP 50.00
```

Every predicted value reproduced exactly:

| Predicted | Measured | |
| --- | --- | --- |
| Pulse protocol, not RS232 | pulses on METER, no serial | ✅ |
| LOW width 50 ms | 50 / 50 / 50 ms, zero jitter | ✅ |
| Period 150 ms (Fast, SW4=ON) | 150 / 150 / 151 ms | ✅ |
| 1 pulse = ₱10 | ₱50 note → 5 pulses | ✅ |
| METER+ belongs on D3 | clean train on D3 | ✅ |

The `raw edges = 2317` against `clean pulses = 5` in the same window is the
other half of the result: transport-motor noise **is** present on the line and
coexists with the credit train. A 20 ms glitch filter separates them cleanly.
Any firmware that counts raw edges will massively over-credit.

Supporting evidence from the same session: the legacy `Bill_Acceptor.ino` was
left running on the mis-wired input for ~13 minutes and accumulated
**₱16,130 of credit that was never inserted**. That is the concrete
demonstration of why the V1 sketch is unsafe as a cash controller.

Also observed: with `USE_INTERNAL_PULLUP 0`, the unconnected D2 floated and
reported a phantom train at `period 150/150/151 ms` — identical to the real D3
train — at the same instant. That is capacitive crosstalk from the adjacent
pin, not a signal. Unwatched interrupt pins must be tied off with
`INPUT_PULLUP`, which `bill_ide_paste` now does.

### Full denomination set, 2026-08-03 23:23 (D2 tied off, totals trustworthy)

| Time | Note | Clean pulses | LOW width | Period | Read as |
| --- | --- | ---: | --- | --- | --- |
| 23:23:16 | ₱20 | **2** | 50/50/51 ms | 151/151/151 ms | PHP 20.00 |
| 23:23:21 | ₱50 | **5** | 50/50/51 ms | 150/150/151 ms | PHP 50.00 |
| 23:23:24 | ₱100 | **10** | 50/50/51 ms | 150/150/151 ms | PHP 100.00 |

**Session total ₱170.00 = ₱20 + ₱50 + ₱100, exact.** Zero phantom credits.
2/5/10 pulses at 1 pulse/₱10 across the whole enabled set, all at 50 ms LOW
and a 150 ms period.

### Noise rejection under load — the safety-critical result

The same run included six failed/rejected insertion attempts before the ₱20
succeeded. Raw versus clean, every event:

| Event | Raw edges | Clean pulses | Credited |
| --- | ---: | ---: | --- |
| 6 rejected attempts | 792, 1704, 2749, 5146, 5969, 6704 | **0 each** | ₱0 ✅ |
| ₱20 accepted | 4,924 | 2 | ₱20 ✅ |
| ₱50 accepted | **12,871** | 5 | ₱50 ✅ |
| ₱100 accepted | 3,263 | 10 | ₱100 ✅ |

Two properties matter here and both hold:

1. **No false credit on rejection.** 23,064 raw edges across six rejected
   attempts produced ₱0. A rejected note never pays.
2. **Correct extraction under the worst noise.** The ₱50 read carried a
   2574:1 noise-to-signal ratio and still yielded exactly 5 pulses. Naive
   raw-edge counting at ₱10/pulse would have credited **₱128,710** for that
   single ₱50 note.

This is the empirical justification for the 20 ms glitch filter and for
treating raw interrupt counts as unusable in any cash path.

### Polymer banknotes are rejected — acceptor firmware limitation, 2026-08-03

The new **polymer ₱100 is consistently rejected** while paper ₱100 reads
correctly at 10 pulses. This is not a wiring, DIP, or software fault, and no
change on our side can fix it.

Bangko Sentral ng Pilipinas released the polymer ₱500/₱100/₱50 (First
Philippine Polymer Banknote Series) on **23 December 2024**, nationwide from
January 2025. The polymer ₱1000 preceded it in 2022. Our unit's currency
dataset is labelled `10PH6003` and the supplied TB-Series guide is dated
May 2022 — the templates predate the polymer series by roughly two years.

A validator authenticates against stored optical/UV/IR templates. Polymer
substrate has entirely different signatures and thickness from abaca paper, so
an older dataset cannot match it. DIP switches only enable or disable
denominations that already exist in the dataset; they cannot add one.

**Fix:** reload the currency dataset with the G-BOX programmer. The TB-Series
guide §5-3 ("Software download") directs users to the local agent or
`service@topvme.com.tw`. Request a PH6 dataset that includes the polymer
series, then re-run the Phase-0 trials for every denomination.

**Until then the behaviour is safe, not silently wrong.** A polymer note is
drawn in, examined, and returned; the acceptor emits no credit pulses and the
filter reports `clean=0`. The customer keeps their money and receives nothing.
That is the correct failure direction — but it is an acceptance-rate and
usability limitation that grows as polymer notes displace paper, and it must
be declared rather than hidden. Paper notes remain legal tender and still
circulate, so the kiosk is usable in the interim.

### Allan coin acceptor — misclassification observed, 2026-08-04

After calibration the coin geometry is consistent and the linear model holds:
**1 pulse = ₱1** at every denomination, ~70 ms LOW, ~170 ms period.

| Coin | Pulses | Samples |
| --- | ---: | ---: |
| ₱1 | 1 | 6 |
| ₱5 | 5 | 3 |
| ₱10 | 10 | 1 |
| ₱20 | 20 | 1 |

**But two ₱10 coins dropped in one session produced 1 pulse and 10 pulses —
₱11 credited for ₱20 inserted.** The 1-pulse event (raw 893, span 472 ms,
LOW 69 ms) is byte-for-byte the signature of a genuine ₱1 drop, and its span
matches a single clean pulse rather than a truncated train. The acceptor
emitted exactly one pulse: it **classified a ₱10 coin as a ₱1**.

This is a coin-recognition failure inside the Allan unit. No firmware or host
logic can detect it, because both 1 and 10 are legitimate pulse counts. The
pulse train is perfectly formed; only its *value* is wrong.

**Why it is worse than it looks.** The error is symmetric. A ₱10 read as ₱1
shortchanges the customer by ₱9; a ₱1 read as ₱10 shortchanges the operator by
the same amount. The linear coin model cannot reject either, and a strict
lookup table would not help — 1 and 10 are both valid entries.

Contrast with bills: the TB74 carries a manufacturer currency dataset and
encodes denomination in the pulse count, so a wrong count is detectable and
gets rejected. Coin discrimination is only as good as the samples taught into
the unit, and the host has no way to audit it.

**Probable cause.** Philippine coins exist in old and NGC (2018-) variants
with different diameters and alloys. Programming one slot per denomination
(E=4) leaves no room to teach both variants, so a coin of the untaught variety
can fall into a neighbouring program's tolerance band. The original six-program
plan in `hardware/README.md` (old/new for ₱1/₱5/₱10) exists precisely to avoid
this; trading those variant slots for a fourth denomination is what opened the
gap.

**Remediation, in order:**

1. Re-teach with `H = 20` samples per program using a deliberate mix of old
   and NGC coins of that denomination.
2. Prefer `E = 6` with variant coverage over `E = 4` with an extra
   denomination, unless ₱20 acceptance is worth more than accuracy.
3. Tighten `F` and re-test; record the direction that helps, since the
   supplied sheet does not state it.
4. Measure a **misclassification rate**: 20 drops per denomination, recording
   the pulse count for each. Anything above zero is a money defect.

**Open design question.** The kiosk sells ~₱9.50 items and already accepts
₱20/₱50/₱100 notes reliably. If the misclassification rate cannot be driven to
zero, running bills-only is a defensible configuration: it removes an
unauditable money error at the cost of some convenience. Coin credit must stay
gated until step 4 produces a clean result.

### Denomination switch assignment — two candidates, unresolved

The only 10-way change made was **SW7 OFF → ON**; SW8/9/10 verified still OFF.
Both ₱50 and ₱100 are accepted now. Two readings fit that equally well:

| | SW6 | SW7 | SW8 | SW9 | SW10 |
| --- | --- | --- | --- | --- | --- |
| **A** (from MXP6 sheet shape) | ₱20 | **₱50 & ₱100** | ₱200 | ₱500 | ₱1000 |
| **B** (operator-reported) | **₱20 & ₱50** | ₱100 | ₱200 | ₱500 | ₱1000 |

Both predict today's observed behaviour with SW6+SW7 ON. They differ on one
point only: **with SW7 OFF, is ₱50 accepted?** A says no, B says yes.

Weak evidence for B: the original V1 brief reported a ₱50 being accepted under
the factory config (SW6 ON, SW7 OFF). That observation predates the wiring fix
and could not distinguish stacking from rejection, so it is not decisive.

**Discriminating test (~1 minute):** set SW7 OFF, power-cycle, insert ₱50.
Accepted → B. Returned → A. Restore SW7 ON afterwards.

Either way the current configuration is correct and safe: ₱20/₱50/₱100
enabled, ₱200/₱500/₱1000 refused. The ambiguity affects documentation only,
not behaviour.

This falsifies the per-denomination reading taken from the Mexican MXP6 sheet.
On this PH6 build, **SW7 = ₱50 & ₱100 as one group**. Grouping is normal in
this device family — the MXP6 sheet groups ₱500 & ₱1000 on SW10, and the ICT
TAO-A.V PHP6 sheet groups ₱100 & ₱200 — the PH build simply groups a different
pair. Six denominations across five switches requires exactly one such pair.

Bank state as measured:

| SW | Function | State | Effect | Basis |
| --- | --- | --- | --- | --- |
| 1,2,3 | scaling | OFF/OFF/OFF | 1 pulse / ₱10 | ✅ measured |
| 4 | speed | ON | Fast 50/100 | ✅ measured |
| 5 | inhibit level | OFF | Active High | vendor sheet |
| 6 | ₱20 | ON | accepted | inferred, **untested** |
| 7 | **₱50 & ₱100** | **ON** | both accepted | ✅ measured |
| 8 | ₱200 | OFF | rejected | inferred, untested |
| 9 | ₱500 | OFF | rejected | inferred, untested |
| 10 | ₱1000 | OFF | rejected | inferred, untested |

**This is already the target configuration.** ₱20/₱50/₱100 are enabled and
₱200/₱500/₱1000 are refused at the acceptor, which is the correct policy for a
kiosk that gives no change. No further DIP changes are required; SW8/9/10 must
stay OFF.

Untested gaps: ₱20 acceptance (SW6), and rejection of ₱200/₱500/₱1000. All
three switches being OFF is the fail-safe direction, so the residual risk is
low, but the rejection trials still belong in the Phase-0 worksheet.

## 2. The DIP switch map (this is the answer to "are my dips correct")

Source: genuine TOPVME **TB74** sheet for MXP6 (`20/50/100/200/500/1000`),
the same six-bill structure as PHP6, on the same 10-way + 4-way banks.
See `hardware/references/vendor-dip-sheets/`.

### DIP SW SETTING 1 — the 10-way bank (CTS195-10)

| SW | Function | Your setting | Verdict |
| --- | --- | --- | --- |
| 1,2,3 | Pulse scaling (see table below) | OFF/OFF/OFF = **1 pulse / ₱10** | correct (default) |
| 4 | ON = Fast 50/100 ms · OFF = Slow 50/300 ms | **ON** = Fast | good — keep |
| 5 | ON = Inhibit Active Low · OFF = Active High | OFF = Active High | correct (default) |
| 6 | ON = Accept ₱20 | **ON** | correct |
| 7 | ON = Accept **₱50 & ₱100** | **ON** (after fix) | correct — see §1b |
| 8 | ON = Accept ₱200 | OFF | correct for this project |
| 9 | ON = Accept ₱500 | OFF | correct for this project |
| 10 | ON = Accept ₱1000 | OFF | correct for this project |

The SW6–SW10 denomination assignment above is the **measured PH6 mapping**, not
the Mexican MXP6 sheet's. The MXP6 sheet assigns one note per switch for
SW6–SW9 and groups ₱500 & ₱1000 on SW10; the PH6 build instead groups
₱50 & ₱100 on SW7. Bench evidence in §1b overrides the sheet here.

Pulse scaling options (SW1/SW2/SW3):

| SW1 | SW2 | SW3 | Scaling |
| --- | --- | --- | --- |
| OFF | OFF | OFF | **1 pulse / ₱10** ← default, and what you have |
| OFF | OFF | ON | 2 pulses / ₱10 |
| OFF | ON | OFF | 3 pulses / ₱10 |
| OFF | ON | ON | 4 pulses / ₱10 |
| ON | OFF | OFF | 5 pulses / ₱10 |
| ON | OFF | ON | 10 pulses / ₱10 |
| ON | ON | OFF | 20 pulses / ₱10 |
| ON | ON | ON | 100 pulses / ₱10 |

### DIP SW SETTING 2 — the 4-way bank (CTS208-4)

| SW | Function | Your setting | Verdict |
| --- | --- | --- | --- |
| 1 | ON = Pulse Normal **High** (NO) · OFF = Normal Low (NC) | **ON** | correct — matches your observed idle-HIGH |
| 2 | ON = **Pulse Protocol** · OFF = RS232 Protocol | **ON** | correct — **this is the protocol answer** |
| 3 | Reserved | OFF | correct (default) |
| 4 | Reserved | OFF | correct (default) |

**The whole 4-way bank is already exactly right.** You are in Pulse mode,
normally-high, and that is why counting FALLING edges is the correct approach.

### The change required

Move **SW7 → ON** on the 10-way bank. Nothing else — that single switch
enables both ₱50 and ₱100. **Done and verified**; see §1b.

Then **power-cycle the acceptor** — the vendor sheet states "Please reset the
bill acceptor after any changes on Dip switch." A DIP change without a reset
does not take effect, which is a plausible reason earlier switch experiments
appeared to do nothing.

Leaving SW9 and SW10 OFF is deliberate and correct: it makes the acceptor
physically refuse ₱200/₱500/₱1000, which is the right policy for a kiosk that
gives no change and already caps carts at 3 units/item and 5 distinct items.

### Cross-check available right now, before any wiring change

The TB manual's troubleshooting table (printed page 17) states:

> Red LED, 2 flashes → **Disable** → "Check if the DIP switch setting is correct"

Insert a ₱50 and watch the LED and the note. If the note is drawn in, paused,
and **returned**, it was rejected — which is what the DIP map predicts. If it
is **stacked and kept**, then the note was genuinely accepted and the bank
mapping needs re-derivation from the bench instead.

---

## 3. PHP denomination decoding

PH6 = the six circulating Philippine notes: **₱20, ₱50, ₱100, ₱200, ₱500,
₱1000**. Confirmed by two independent PHP6 currency sheets.

The pulse base unit is **₱10** — the GCD of the six denominations. This is why
₱10 appears in the scaling table even though no ₱10 note exists.

At your current `1 pulse / ₱10` scaling and SW4=Fast (150 ms period):

| Note | Expected pulses | Expected train duration | Enabled by |
| --- | ---: | ---: | --- |
| ₱20 | **2** | ~0.30 s | SW6 (ON now) |
| ₱50 | **5** | ~0.75 s | SW7 (needs ON) |
| ₱100 | **10** | ~1.50 s | SW8 (needs ON) |
| ₱200 | 20 | ~3.0 s | SW9 — intentionally OFF |
| ₱500 | 50 | ~7.5 s | SW10 — intentionally OFF |
| ₱1000 | 100 | ~15 s | SW10 — intentionally OFF |

Note how badly Slow mode scales: on SW4=OFF the period is 350 ms, so ₱100
would take 3.5 s and ₱1000 would take 35 s. **Keep SW4 = ON.**

This vindicates the V1 sketch's `billValuePerPulse = 10`. That constant was
right; the DIP configuration and the signal conditioning were not.

---

## 4. Repository trace — answers to the brief's ten questions

An exhaustive keyword sweep (`attachInterrupt`, `pulseIn`, `Serial.begin`,
`SoftwareSerial`, `ccTalk`, `ID003`, `TB74`, `TOPVME`, denomination literals,
checksum/frame markers) across every tree including the archived `_For-Mendo/`
v1/v2 system returned matches in only these files:

```
Bill_Acceptor.ino                                (41 lines, root)
hardware/references/legacy/Bill_Acceptor.ino     (same file, archived)
hardware/firmware/bill_observer/bill_observer.ino
hardware/firmware/mendo_controller/mendo_controller.ino
hardware/firmware/bench_safe/bench_safe.ino
hardware/{README,tb-arduino-uno-wiring}.md, .svg
CHECKPOINT.md
```

**`_For-Mendo/` contains no bill-validator code at all.** There is no hidden
protocol parser, no packet decoder, no lookup table, and no second serial port
anywhere in this repository.

| # | Question | Answer |
| --- | --- | --- |
| 1 | Pulse, RS232, ccTalk or ID003? | **Pulse.** DIP2 SW2=ON. No serial parser exists in any tree. |
| 2 | Where is bill acceptance handled? | `Bill_Acceptor.ino` only — a 41-line ISR counter. Nothing else predates this project. |
| 3 | How is denomination determined? | It is not. The V1 sketch multiplies a raw count by ₱10 and accumulates a single `credit` integer. No per-note identification. |
| 4 | Packet decoding? | **None.** No checksum, frame, header, or byte-marker logic exists. |
| 5 | Pulse counting? | Yes — `attachInterrupt(digitalPinToInterrupt(2), billPulseISR, FALLING)` with a 50 ms ISR debounce and a 250 ms train-settle in `loop()`. |
| 6 | PHP denomination lookup table? | Not in V1. The current repo has one: `hardware/config.example.toml` → `{2:2000, 5:5000, 10:10000}` centavos, mirrored in `hardware/simulator.py:30`. **This analysis confirms those three values are correct.** |
| 7 | Undocumented TB74 constants? | Only `billValuePerPulse = 10`. Now explained: it is the ₱10 pulse base unit. |
| 8 | Which Arduino pins? | V1 used **D2/INT0**. The current locked mapping uses **D3/INT1** for the TB meter and reserves D2/INT0 for the Allan coin acceptor (`hardware/README.md`). |
| 9 | Baud rate? | `9600` in V1 — that is the **USB debug console only**, not a validator link. Current firmware uses `115200`, also host-side only. There is no serial connection to the acceptor. |
| 10 | Hidden protocol parser? | No. |

### Execution path (V1, as-built)

```
Bill inserted
  → TB74 validates, and IF the denomination is enabled, stacks the note
  → opto-isolated Credit O/P pulls METER+ LOW, N times, 50 ms LOW / 100 ms HIGH
  → D2 FALLING interrupt → billPulseISR() → pulseCount++ (50 ms debounce)
  → loop(): 250 ms of quiet → credit += pulseCount * 10 → Serial.print
  → (no vending logic — the sketch ends here)
```

There is no session binding, no idempotency, no inhibit control, and no
acknowledgement. Everything downstream of "credit" was never implemented in
V1; the durable order/dispense state machine in `pos/order_service.py` and
`hardware/` is new work in this project.

### Hardware pins and ports

| Signal | TB pin | Harness colour | Arduino | Notes |
| --- | --- | --- | --- | --- |
| +12 V | 5 | Red | — | separate fused supply, never an Uno pin |
| 12 V GND | 9 | Orange | — | supply return only |
| METER+ | 7 | Blue | **D3 / INT1** | needs external 4.7 kΩ pull-up to Uno 5 V |
| METER- | 8 | Purple | Uno logic GND | |
| INHIBIT+ | 1 | Yellow | via 1 kΩ to 5 V | Active **High** (SW5=OFF) |
| INHIBIT- | 2 | Green | NPN collector from D4 | |

Serial ports in use: **one** — the Uno USB CDC to the host, 115200 baud. The
acceptor is not on any UART.

---

## 5. Firmware constants that are wrong for this device

Not applied — the brief asked for understanding before rewriting. Recorded
here so the changes are deliberate.

| Location | Constant | Problem | Suggested |
| --- | --- | --- | --- |
| `mendo_controller.ino:42` | `BILL_GAP_MS = 180` | Below the 350 ms Slow-mode period. If SW4 is ever OFF, every single pulse is emitted as its own event — a ₱100 note becomes ten ₱10 credits. Only 30 ms of margin even in Fast mode. | **500** |
| `mendo_controller.ino:279` | `billEdge()` bounce filter `< 3` ms | Passes the entire 8–20 ms motor-noise band straight into the counter. Real minimum period is 150 ms. | **25** ms |
| `bill_observer.ino` | `TRAIN_GAP_US = 250000` | Same Slow-mode splitting problem. | **500000** |
| `hardware/pulses.py` | `PulseMapping(bills=...)` defaults to `{}` | Bill mapping is empty by default while coins are pre-populated; a real bill train would map to `None`. | seed `{2:2000, 5:5000, 10:10000}` |
| `bill_observer.ino` | `candidateCentavos()` marked `UNVERIFIED_V1_HYPOTHESIS` | The 2/5/10 → ₱20/₱50/₱100 mapping is now **documented from the vendor sheet**. Still needs bench trials, but it is no longer a guess. | reword to "vendor-documented, bench-pending" |

Electrical, before any re-test: fit the **4.7 kΩ pull-up from D3 to Uno 5 V**
and drop `INPUT_PULLUP` in favour of plain `INPUT`. `bill_observer.ino`
already assumes this; the root `Bill_Acceptor.ino` does not.

---

## 6. Recommended bench sequence

1. Set 10-way SW7 → ON, SW8 → ON. Leave everything else. **Power-cycle.**
2. Fit the external 4.7 kΩ pull-up on the METER node.
3. Flash `bill_observer.ino` (observe-only; drives no inhibit, no servo).
4. Send `ARM`, insert ₱20, ₱50, ₱100 one at a time.
5. Expect **2 / 5 / 10** falling edges, `PULSE_WIDTH_AVG_US ≈ 50000`,
   `INTERPULSE_GAP_AVG_US ≈ 150000`. Any gap under 80 ms is still noise —
   stop and fix conditioning before going further.
6. Confirm ₱200/₱500/₱1000 are returned, not stacked.
7. Twenty consecutive correct trials per enabled denomination, then fill in the
   `hardware/README.md` Phase-0 worksheet rows.

Until step 7 is complete and the R1–R4 remediation checkpoints are approved,
`MENDO_HARDWARE_MODE` stays `simulator`.

---

## 7. Confidence

| Claim | Confidence | Basis |
| --- | --- | --- |
| Protocol is Pulse, not RS232 | **Confirmed** | Measured credit train on METER; DIP2 SW2=ON; no serial parser in any tree |
| 1 pulse = ₱10 | **Confirmed** | ₱50 note produced exactly 5 pulses |
| Fast timing, 50 ms LOW / 150 ms period | **Confirmed** | Measured 50/50/50 and 150/150/151 |
| METER+ belongs on D3 with a 4.7 kΩ pull-up | **Confirmed** | Clean train only after the rewire |
| Sub-80 ms events are noise, not credit | **Confirmed** | 2317 raw edges vs 5 real pulses in one window |
| PHP6 = ₱20/50/100/200/500/1000 | **High** | Two independent PHP6 currency sheets |
| 10-way SW1-3 scaling, SW4 speed, SW5 inhibit | **High** | TB74 vendor sheet; SW1-3 and SW4 both verified by the measured result |
| SW6–SW10 are denominations, ON = accept | **Confirmed** | SW7 alone moved OFF→ON and denominations changed state |
| ₱20/₱50/₱100 = 2/5/10 pulses | **Confirmed** | All three trialled 23:23, session total exact at ₱170 |
| No false credit on a rejected note | **Confirmed** | 6 rejections, 23,064 raw edges, ₱0 credited |
| Which switch holds ₱50 (SW6 vs SW7) | **Unresolved** | Candidates A and B in §1b both fit; needs the SW7-OFF ₱50 test |
| SW8/9/10 = ₱200/₱500/₱1000 | **Medium** | Inferred; untested. All OFF is the fail-safe direction |

The protocol itself is fully measured. The per-switch assignment for SW6 and
SW8–SW10 remains inferred, but every one of those switches is OFF except SW6,
so the configuration is already the intended one and errors there cannot
enable an unwanted denomination.

Remaining Phase-0 coverage: ₱20 acceptance, twenty consecutive correct trials
per enabled denomination, and rejection trials for ₱200/₱500/₱1000 as notes
become available.
