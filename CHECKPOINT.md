# MendoVendo hardware/payment integration checkpoint

This file is append-only for phase records and decisions. It is the hand-off
document for resuming the integration without assuming that unmeasured
hardware behavior is safe.

## Resume here

- Current phase: **R0 audit record complete; R1 firmware remediation awaiting
  user approval**
- Current status: **software Phases 1–2 remediation required; real hardware
  remains disabled**
- Safe next action: review the R0 findings below and explicitly approve R1
  before any firmware behavior is changed. Physical work remains blocked until
  the worksheet below (TB identity/PHP sheet, continuity, DIP polarity, pulse
  captures, 0–5 V signals, and servo measurements) is completed.
- Cash and dispensing state: simulator events are enabled for tests only;
  real cash and real motion remain disabled and no Flask worker opens a serial
  device.
- User approval to continue software implementation: **previously approved in
  the 2026-08-03 user request because hardware is currently unavailable**;
  approval to begin R1 after this audit: **pending**.
- Physical Phase 0 completion approval: pending evidence and user review.

## Phase 0 — Baseline and hardware identity

- Status: blocked
- Manila date/time: 2026-08-03 13:05:10 PST (+0800)
- Branch: `experiment-march-1`
- Base commit: `41b2bbd` (working tree changes are not committed)

### Goal and acceptance criteria

Establish a reproducible software baseline and an auditable identity/evidence
record for the Allan coin acceptor, TOPVME TB bill acceptor, and rotor asset.
Phase 0 can complete only when the physical TB identity, PHP configuration,
harness continuity, DIP polarity, supported-denomination pulse counts, and
conditioned Arduino-side voltages are measured and recorded.

### Files/schema changed

- `CHECKPOINT.md` — created as the first implementation change.
- `hardware/README.md` — safety, wiring, calibration, and Phase-0 evidence
  worksheet.
- `hardware/references/README.md` — provenance and hashes for tracked copies.
- `hardware/references/` — tracked-copy location for the two manuals and STL.
- `pytest.ini` — scopes pytest to `testing/`, excluding archived binary
  artifacts from collection.
- `README.md` and `CLAUDE.md` — synchronized Phase-0 status and hand-off
  guidance.
- No database schema or runtime payment behavior has been changed.
- The supplied root-level reference files remain untouched; their tracked
  copies are under `hardware/references/`.

### Exact baseline commands and results

- `./.venv/bin/python -m unittest discover -s testing -p 'test_*.py' -q`
  — **92 tests, OK** (2026-08-03).
- `./.venv/bin/python -m pytest -q` — **92 passed, 52 subtests passed** in
  27.27 seconds after adding `pytest.ini` to scope discovery to `testing/`.
  Before that config, pytest discovered the archived binary-named file
  `_For-Mendo/testing/test_output.txt` and failed during collection; that was
  a test-discovery issue, not an application test failure.

### Hardware measurements, photos, pulse captures, and calibration values

- Allan reference: `allan coinslot calibration.pdf`, four pages, dated
  2020-08-27. It describes six coin programs (old/new ₱1, ₱5, and ₱10),
  calibration samples, and standard sensitivity `F=8`; the supplied plan
  selects `H=20`, `P=1/5/10`.
- TB reference: `tb_series.pdf`, 24 pages. It documents generic TB74/TB77
  dimensions, 12 V ±10% supply, pulse/RS232/ccTalk/ID003 interfaces, and the
  WEL-R7U02 harness. It does **not** identify the connected unit’s exact model,
  PHP firmware label, currency DIP sheet, or observed pulse mapping.
- WEL-R7U02 colors documented by the manual: red `+12 V`, orange `GND`, blue
  `METER+`, purple `METER-`, yellow `INHIBIT+`, green `INHIBIT-`.
  Continuity has not yet been measured on the physical harness.
- No physical photos, pulse-width captures, pulse-gap captures, denomination
  trials, DIP-bank readings, or conditioned 0–5 V measurements are available
  in this workspace.
- Rotor source: `rotor_9pocket_35x20_recommended_clearance.stl` is preserved;
  the plan describes it as a watertight 172 × 172 × 16 mm rotor. No hardware
  cycle or loaded-dispense measurement has been performed.

### Decisions or deviations

- The application remains cash-disabled until physical evidence passes the
  Phase-0 gate.
- Reference documents are treated as wiring/calibration guidance, not proof of
  the installed acceptor’s identity or behavior.
- No TB Philippine DIP settings are inferred from a TP-series document.
- The existing 92-test suite is the baseline; the new hardware/payment suite
  must be additive.
- Test discovery is scoped to the live `testing/` suite so future hardware
  tests can run with the same command without reading archived artifacts.

### Known risks and rollback/recovery

- Wrong TB model, DIP polarity, or pulse mapping could credit the wrong amount
  or fail to inhibit on reset. Keep the acceptors physically disconnected or
  inhibited until measured.
- The Allan COIN signal voltage is unknown; never connect it directly to Uno
  D2. Use the specified 12 V-rated optocoupler interface and verify its output
  is 0–5 V first.
- If a later phase is unsafe, disable the daemon/acceptor power controls and
  retain the SQLite event/job evidence for manual review. No financial refund
  may restore physical stock without an explicit return-to-stock action.

### Documentation updated

- The checkpoint, hardware guide, README, and `CLAUDE.md` are synchronized for
  the current evidence state. Physical measurements are still required before
  this phase can be marked complete.

### User approval

- Phase 0 completion approval: pending physical evidence and user review.
- Approval to begin Phase 1: pending.
- Clarification recorded 2026-08-03: the user approved simulator/software
  continuation while physical Phase 0 remains incomplete; this does not
  approve real hardware enablement.

## Append-only decision log

### D-0001 — 2026-08-03, Phase 0

Use the repository’s supported unittest discovery command as the baseline:
92/92 tests pass. Raw pytest discovery is not an acceptance command until it
is scoped away from the archived `_For-Mendo` artifacts.

### D-0002 — 2026-08-03, Phase 0

The supplied TB installation guide is insufficient to authorize PHP cash
acceptance. Exact model/firmware, currency DIP sheet, polarity, pulse mapping,
and voltage measurements remain physical acceptance evidence requirements.

### D-0003 — 2026-08-03, Phase 0

The root-level supplied manuals and STL are preserved as originals. Tracked
copies may be placed under `hardware/references/` with provenance and hashes;
the originals must not be deleted or overwritten.

### D-0004 — 2026-08-03, Phase 0

Scope pytest discovery to `testing/` with `pytest.ini`. The live suite now
passes under both the supported unittest command and `./.venv/bin/python -m
pytest -q` (92 tests; 52 subtests reported by pytest).

## Phase 1 — order and inventory foundation (software-only)

- Status: **complete for simulator/software scope; physical acceptance pending**
- Manila date/time: 2026-08-03 14:08:37 PST (+0800)
- Branch: `experiment-march-1`
- Commit: `41b2bbd` base; implementation is currently an uncommitted working
  tree and must be reviewed before commit.

### Goal and acceptance criteria

Add a recoverable additive order layer without deleting historical
transactions: integer-centavo totals, ten-slot catalog snapshots,
`stock_quantity - reserved_quantity` availability, exactly-once cash events,
sequential per-unit dispense jobs, idempotent final receipts, cashbox
reconciliation, legal transitions, timeout handling, and explicit recovery
actions.

### Files/schema changed

- `mendo_core/money.py` — Decimal-to-centavo conversion and PHP formatting.
- `pos/db.py` — additive orders, order items, cash sessions/events, payment
  attempts, motion profiles, dispense jobs, cashbox sessions, audit events,
  reserved inventory, cashbox assignment, and restock audit fields.
- `pos/order_service.py` — transactional lifecycle and recovery service.
- `pos/routes_checkout.py`, `pos/routes_shop.py`, `pos/routes_admin.py` — kiosk,
  cashier, Xendit, hardware, audit, cashbox, and staff-recovery APIs.
- `web/static/js/pos.js`, `web/static/js/kiosk-checkout.js`, checkout/shop/admin
  templates — centavo-aware status and payment/dispensing UI.

### Exact test/build commands and results

- `./.venv/bin/python -m unittest discover -s testing -p 'test_*.py' -q` —
  baseline recorded before implementation: **92 tests, OK**.
- `./.venv/bin/python -m pytest -q testing/test_hardware_payment.py` —
  **19 passed**.
- `./.venv/bin/python -m pytest -q` — **111 passed, 52 subtests passed** in
  33.35 seconds.
- `./.venv/bin/python -m compileall -q mendo_core pos hardware testing` —
  **exit 0**.

### Hardware measurements and calibration values

None are available. The ₱20/₱50/₱100 bill pulse fixture `{2: 2000, 5: 5000,
10: 10000}` and the ten `1500/1900 µs` motion profiles are explicitly marked
simulator/unmeasured and are not evidence about the installed hardware.

### Decisions or deviations

- The user authorized continuing with software and simulator work because the
  hardware cannot currently be used.
- Real refunds do not restore physical stock. Reservations for undispensed
  units are released; physical stock rises only through an explicit staff
  return-to-stock action.
- The legacy transaction table remains a receipt projection for compatibility;
  the new order tables are the financial source of truth.

### Known risks and rollback/recovery instructions

- Do not infer TB PHP DIP settings or pulse mappings from the reference PDF.
- If a software regression appears, run the baseline unittest command and
  preserve the SQLite order/cash/job rows for review; do not delete or reset
  the database as a recovery shortcut.
- Set `MENDO_HARDWARE_MODE=simulator` for development. Never clear the real
  firmware/configuration evidence gate to bypass missing measurements.

### Documentation updated

`README.md`, `CLAUDE.md`, `hardware/README.md`,
`docs/architecture/cash-order-integration.md`, and this checkpoint were
synchronized. User-facing fulfillment wording is `dispensed_unverified` /
“actuator acknowledged” until a shared chute sensor exists.

### Next safe action

Continue Phase 2 software validation; no physical connection is required.
When hardware becomes available, resume Phase 0 evidence capture before any
real cash session.

### User approval

- Simulator/software continuation: **approved by the user on 2026-08-03**.
- Physical Phase 0 completion: pending.

## Phase 2 — hardware interface and simulator (software-only)

- Status: **complete for socket/simulator/real-daemon source; bench acceptance
  deferred**
- Manila date/time: 2026-08-03 14:08:37 PST (+0800)
- Branch: `experiment-march-1`
- Commit: `41b2bbd` base; implementation is uncommitted and must be reviewed
  before commit.

### Goal and acceptance criteria

Provide one bounded protocol and one serial owner, with explicit simulator and
real modes, fail-safe health, CRC16 frames, a Unix-domain Flask boundary,
firmware identity/protocol/configuration checks, heartbeat behavior, job
idempotency, and fault-injection coverage without opening a real serial device
in tests.

### Files changed

- `hardware/protocol.py`, `pulses.py`, `interface.py`, `simulator.py` — bounded
  ASCII frames, CRC, pulse grouping, contracts, and deterministic faults.
- `hardware/daemon.py`, `real_backend.py`, `daemon_main.py`, `serial_bridge.py`,
  `service.py` — Unix socket daemon, pyserial-owned real backend, client, and
  Flask service boundary.
- `hardware/firmware/mendo_controller/mendo_controller.ino` and
  `hardware/firmware/platformio.ini` — shared Uno/Mega source, fail-safe pins,
  interrupts, pulse finalization, CRC validation, EEPROM evidence/job rings,
  A→B→A job identity protection, heartbeat, and PCA OE control.
- `hardware/udev/99-mendo-uno.rules`, `hardware/systemd/mendo-hardware.service`,
  and `hardware/config.example.toml` — restricted daemon deployment examples.
- `testing/test_hardware_payment.py` — 19 simulator/payment/daemon tests.

### Exact test/build commands and results

- `./.venv/bin/python -m pytest -q testing/test_hardware_payment.py` —
  **19 passed**.
- `./.venv/bin/python -m pytest -q` — **111 passed, 52 subtests passed**.
- `./.venv/bin/python -m compileall -q mendo_core pos hardware testing` —
  **exit 0**.
- PlatformIO/Arduino hardware compilation and PTY Arduino integration were
  **not run**: the board is unavailable and PlatformIO is not installed in
  this environment. The Unix-socket simulator round trip did pass.

### Hardware measurements and calibration values

No physical measurements, photos, pulse captures, loaded servo trials, or
flash/SRAM reports are available. The firmware constant
`PHYSICAL_EVIDENCE_CONFIRMED` remains false. Real mode therefore refuses cash
until measured configuration is reported by the controller and the service
health gate passes.

### Decisions or deviations

- Simulator mode is intentionally visible in every order/status response and
  says that events are synthetic.
- The planned PTY-based Arduino test is deferred; the current automated
  boundary test uses a Unix socket with the same framed protocol.
- No production override was added for missing hardware evidence.

### Known risks and rollback/recovery instructions

- Do not run `MENDO_HARDWARE_MODE=real` without the udev identity, dedicated
  daemon account, exact harness verification, and measured fail-safe polarity.
- To roll back hardware behavior, stop `mendo-hardware.service`, use simulator
  mode, and leave acceptors/PCA OE physically disabled.
- A lost dispense ACK must be resolved with `JOB_STATUS`/staff review; never
  issue a second physical command solely because an ACK was lost.

### Documentation updated

`hardware/README.md`, firmware README/configuration, systemd/udev examples,
`README.md`, `CLAUDE.md`, `docs/architecture/cash-order-integration.md`, and
this checkpoint were synchronized.

### Next safe action

Keep automated development in simulator mode. When hardware becomes available,
finish Phase 0, then compile the identical firmware for Uno and Mega, capture
flash/SRAM usage, and run pulse-generator tests before powering either
acceptor.

### User approval

- Simulator/software continuation: **approved by the user on 2026-08-03**.
- Real hardware enablement: pending Phase-0 evidence and explicit review.

## Resume here — physical work only

1. Identify the exact TB model, PHP firmware label, harness continuity, DIP
   banks, and inhibit polarity.
2. Capture Allan coin and TB bill pulse width/gap/count evidence with the
   conditioned Arduino-side signals verified at 0–5 V.
3. Record the evidence files/photos under `hardware/evidence/` and update the
   Phase-0 worksheet and decision log.
4. Only after review, replace simulator/unmeasured mappings, compile Uno and
   Mega, and begin one-device-at-a-time bench tests.

## Append-only decision log (continued)

### D-0005 — 2026-08-03, software continuation

The user explicitly authorized implementation to continue while the physical
hardware is unavailable. Software and simulator phases may proceed, but this
does not approve real cash, real dispensing, inferred TB settings, or a
physical Phase-0 completion.

### D-0006 — 2026-08-03, hardware safety gate

The shared firmware source keeps `PHYSICAL_EVIDENCE_CONFIRMED=false`, starts
with acceptors inhibited and PCA OE disabled, and reports the missing
configuration/evidence gate. Development uses only the visibly labelled
simulator until the worksheet is reviewed.

### D-0007 — 2026-08-03, recovery semantics

An unknown controller result is never retried automatically. Staff may retry
only a job explicitly marked `unexecuted`; a financial refund never restores
physical stock, and return-to-stock is a separate staff-confirmed action.

## Software consistency addendum — 2026-08-03

- Status: **complete for simulator/software scope; physical acceptance remains blocked**
- Manila date/time: 2026-08-03 14:41:17 PST (+0800)
- Branch: `experiment-march-1`
- Commit: `41b2bbd` base; working tree remains uncommitted.

### Goal and acceptance criteria

Keep the compatibility lifecycle field `orders.fulfillment_state` while adding
an explicit actuator-result field. Completed servo acknowledgments must be
reported as `dispensed_unverified`; cancellations, manual review, refund,
retry, and migration paths must not lose that distinction. Existing databases
must migrate additively.

### Files/schema changed

- `pos/db.py` — additive `orders.fulfillment_result` field and migration.
- `pos/order_service.py` — fulfillment-result projection and state updates.
- `testing/test_hardware_payment.py` — migrated-database and unverified-result
  assertions.

### Exact test/build commands and results

- `./.venv/bin/python -m pytest testing/test_hardware_payment.py -q` —
  **20 passed**.
- `./.venv/bin/python -m pytest -q` — **rerun required after this addendum**;
  the preceding full run was **111 passed, 52 subtests passed**.
- Physical firmware compilation, PTY Arduino integration, and hardware trials
  remain deferred because the hardware is unavailable.

### Hardware measurements, photos, pulse captures, and calibration values

None. This addendum changes no physical mapping. Simulator bill mappings and
unmeasured servo profiles remain synthetic and gated.

### Decisions or deviations

`fulfillment_state=completed` remains for historical/API compatibility, while
`fulfillment_result=dispensed_unverified` is the authoritative prototype
verification label. A future chute sensor may introduce a verified result
without rewriting historical orders.

### Known risks and rollback/recovery instructions

Do not interpret a completed actuator job as proof of a physical drop. If the
migration or state projection regresses, preserve the order/job/cash evidence,
run the full test command, and keep real mode disabled; do not delete or reset
the production SQLite database.

### Documentation updated

This checkpoint and the existing architecture/hardware hand-off documents
remain synchronized with the deferred physical gate.

### Next safe action

Run the final full software checks. When hardware becomes available, resume
the physical Phase-0 worksheet before clearing `PHYSICAL_EVIDENCE_CONFIRMED`.

### User approval

- Software continuation: **approved by the user on 2026-08-03**.
- Physical enablement: pending measurements and explicit review.

### D-0008 — 2026-08-03, actuator-result vocabulary

Use `dispensed_unverified` for the initial fulfillment result. The legacy
`completed` lifecycle state is retained only as a compatibility projection;
the system must never claim a chute drop until a shared chute sensor is
installed and validated.

## Final software verification — 2026-08-03

- Status: **complete for the authorized simulator/software scope**
- Manila date/time: 2026-08-03 (final verification after the consistency addendum)
- Branch: `experiment-march-1`
- Commit: `41b2bbd` base; no commit was created by this implementation pass.
- Exact results:
  - `./.venv/bin/python -m pytest -q` — **112 passed, 52 subtests passed**.
  - `./.venv/bin/python -m compileall -q mendo_core pos hardware testing` — **exit 0**.
  - `node --check web/static/js/kiosk-checkout.js && node --check web/static/js/pos.js` — **exit 0**.
  - `git diff --check` — **clean**.
- Hardware measurements/photos/pulse captures/calibration: **not available**;
  physical Phase 0 remains blocked and no real-device acceptance claim is made.
- Next safe action: preserve simulator mode, then resume the physical worksheet
  and review this checkpoint when the hardware is available.
- User approval: software continuation approved; real hardware enablement
  remains pending evidence and explicit review.

## Final software verification continuation — 2026-08-03

- Status: **complete for the authorized simulator/software scope**
- Files changed since the preceding verification: `pos/order_service.py`,
  `pos/routes_checkout.py`, `pos/routes_admin.py`, `hardware/real_backend.py`,
  `testing/test_hardware_payment.py`, and synchronized architecture/hardware/
  assistant documentation.
- Exact results:
  - `./.venv/bin/python -m pytest -q` — **113 passed, 52 subtests passed**.
  - `./.venv/bin/python -m compileall -q mendo_core pos hardware testing` — **exit 0**.
  - `node --check web/static/js/kiosk-checkout.js && node --check web/static/js/pos.js` — **exit 0**.
  - `git diff --check` — **clean**.
- Recovery acceptance: a lost dispense response is reconciled by immutable
  job ID; the simulator test confirms one physical-motion record and one stock
  deduction. No hardware acceptance evidence exists.
- Known risk/rollback: real firmware compilation and bench tests remain
  unavailable; keep `MENDO_HARDWARE_MODE=simulator` and the physical evidence
  gate closed. Stop the daemon and preserve SQLite evidence if a future bench
  test fails.
- Next safe action: physical Phase 0 worksheet, then Uno/Mega compilation and
  pulse-generator tests when the user has the hardware.
- User approval: software continuation approved; physical enablement pending.

### End-to-end simulator smoke verification

Using a temporary SQLite database with seeded stock and
`MENDO_HARDWARE_MODE=simulator`, the public flow returned:

- `POST /checkout/api/orders` → **201**, due `₱9.50`.
- `POST /checkout/api/orders/<ref>/cash/start` with consent → **200**,
  `awaiting_cash`.
- `POST /checkout/api/orders/<ref>/cash/simulate` with ₱10 → **200**, `paid`,
  `dispensed_unverified`, overpayment `₱0.50`.
- Polling `GET /checkout/api/orders/<ref>` → **200**,
  `dispensed_unverified`.
- Unknown order → **404**; no fingerprint route registered.


## TB-to-Arduino Uno wiring diagram addendum — 2026-08-03 17:04 PST

- Status: **complete for the documentation artifact; physical Phase 0 remains blocked**.
- Manila date/time: 2026-08-03 17:04 PST (+0800)
- Branch: `experiment-march-1`
- Commit: no commit created by this addendum.
- Goal and acceptance criteria: provide an editable, print-ready bench diagram
  for the TB WEL-R7U02 harness, isolated METER input, NPN inhibit interface,
  Arduino D3/D4/GND connections, and separate 12 V/5 V domains. The diagram
  explicitly gates power-up on continuity, exact PHP DIP/polarity, and 0–5 V
  measurements.
- Files changed: `hardware/tb-arduino-uno-wiring.svg`,
  `hardware/tb-arduino-uno-wiring.md`, and `hardware/README.md`.
- Exact validation commands and results:
  - `google-chrome --headless --no-sandbox --disable-gpu --hide-scrollbars --window-size=1600,1400 --screenshot=/tmp/mendo-tb-uno-wiring-final.png file:///home/yyerf/school/mendo-testing/hardware/tb-arduino-uno-wiring.svg` — rendered and visually inspected.
  - `./.venv/bin/python -m pytest -q` — prior synchronized software result:
    **113 passed, 52 subtests passed**; this documentation-only addendum does
    not change runtime code.
  - `git diff --check` — **clean**.
- Hardware measurements, photos, pulse captures, and calibration values:
  **none**. The diagram is based on the supplied manual only; it is not a
  substitute for identifying the connected unit or measuring its signals.
- Decisions/deviations: exact TB model, PHP firmware/DIP sheet, inhibit
  polarity, R3/R4 values, and pulse mapping remain bench evidence gates.
  Higher bills remain disabled by the application configuration.
- Known risks and rollback/recovery: do not connect the TB 12 V rail to the
  Uno. If the physical bench test disagrees with the diagram, keep real mode
  disabled, record the measured harness/polarity, and correct the diagram and
  checkpoint before powering the interface.
- Documentation updated: `hardware/README.md`, the editable SVG diagram, and
  the companion connection guide.
- Next safe action: when hardware is available, complete the Phase-0 worksheet
  and verify the exact TB harness, PHP DIP sheet, fail-safe inhibit state, and
  conditioned 0–5 V signals before any application checkout.
- User approval: diagram delivered; physical enablement still requires the
  user's measurements and explicit review.

## Phase R0 — Correct the audit record — 2026-08-03 18:27:15 PST (+0800)

- Status: **complete for the audit/documentation record; remediation required**.
- Branch: `experiment-march-1`.
- Base commit: `41b2bbd`; working tree is intentionally uncommitted and dirty
  from the prior software implementation plus this R0 record.
- Goal and acceptance criteria: classify the supplied V1 bill sketch as
  unverified legacy evidence, record every release-blocking finding, correct
  the Phase 1–2 status, capture the current compile/test baseline, and keep
  real cash, coin power, PCA outputs, and `PHYSICAL_EVIDENCE_CONFIRMED`
  disabled.

### R0 files and evidence changed

- Moved the supplied `Bill_Acceptor.ino` into
  `hardware/references/legacy/Bill_Acceptor.ino` with an audit warning. It is
  not the integrated controller and must never be flashed.
- Added `hardware/references/legacy/README.md` and updated
  `hardware/references/README.md` with provenance and the unverified mapping.
- Synchronized `README.md`, `CLAUDE.md`, `hardware/README.md`,
  `hardware/firmware/README.md`, and
  `docs/architecture/cash-order-integration.md` so they no longer imply that
  the current simulator foundation is release-ready.
- No runtime firmware, database, daemon, or POS behavior was changed in R0.

### V1 bill sketch classification

The sketch is **unverified legacy evidence**. Its `1 pulse = ₱10` hypothesis
predicts ₱20 = 2 pulses, ₱50 = 5 pulses, and ₱100 = 10 pulses. It has no
inhibit control, payment-session binding, replay/idempotency protocol, safe
atomic shared-state handling, or measured external 4.7 kΩ interface/timing.
Its 50 ms debounce and 250 ms train gap are not calibration evidence.

### Release-blocking findings recorded for R1–R4

1. `hardware/firmware/mendo_controller/mendo_controller.ino` currently writes
   active-low PCA OE with the unsafe polarity: fail-safe LOW enables outputs,
   while movement HIGH disables them. Do not connect powered servos.
2. PCA9685 sleep/prescale/restart initialization and readback at calibrated
   50 Hz are absent.
3. Firmware emits `mapped_centavos=0`, while the current checkout ingestion
   path expects a supplied session/mapping; real bill events cannot safely
   credit an order.
4. `SerialHardwareBackend.drain_events()` destructively drains the queue and
   `HardwareDaemon` returns only its first event, so queued events can be lost.
5. EEPROM cash replay after reboot is documented but not implemented; stored
   evidence lacks the payment session required for valid replay.
6. The public cash-event route accepts caller-supplied money and can forge a
   payment; it must be removed before any network demonstration.
7. Cash-session expiry is not scheduled by a worker; an abandoned browser can
   leave acceptors active.
8. `PAY_STOP` can discard a pulse train already captured by the ISR instead of
   inhibiting and finalizing it safely.
9. Database/admin motion profiles are not sent to firmware; hardcoded
   `1500/1900 µs` values are used.
10. Multi-unit failure recovery can release unrelated reservations instead of
    only the affected undispensed unit.
11. `return_dispensed_to_stock()` calls the undefined `_set_order_states`.
12. Real cashier checkout can return before real dispensing is completed.
13. Admin recovery, profile, cashbox, refund, and reconciliation controls are
    not exposed as a complete authenticated workflow.
14. Earlier Phase 1–2 checkpoint entries are superseded: they are now
    **implemented foundation; remediation required**, not release acceptance.

### Current compile and test baseline

- `./.venv/bin/python -m pytest -q testing/test_hardware_payment.py` —
  **21 passed in 5.64s**.
- `arduino-builder -compile -hardware /usr/share/arduino/hardware -tools
  /usr/share/arduino/tools -tools /usr/share/arduino/hardware/tools
  -built-in-libraries /usr/share/arduino/hardware/arduino/avr/libraries
  -fqbn arduino:avr:uno .../hardware/firmware/mendo_controller/mendo_controller.ino`
  — **9,178 bytes flash; 1,371 bytes globals; 677 bytes free SRAM**.
- The same builder command with `-fqbn
  arduino:avr:mega:cpu=atmega2560` — **10,222 bytes flash; 1,383 bytes
  globals; 6,809 bytes free SRAM**.
- The legacy sketch built as Uno — **2,242 bytes flash; 234 bytes globals**.
- Post-R0 `./.venv/bin/python -m pytest -q` — **113 passed, 52 subtests
  passed in 38.17s**; R0 changed documentation and evidence placement only.
- Post-R0 `./.venv/bin/python -m compileall -q mendo_core pos hardware testing`
  — **exit 0**; both JavaScript `node --check` commands — **exit 0**.
- `git diff --check` — **clean** after the R0 edits.

### Hardware gate and risks

- Hardware measurements, photos, pulse captures, inhibit-polarity evidence,
  and calibration values: **none available**.
- `PHYSICAL_EVIDENCE_CONFIRMED` remains false. Real cash, coin power, PCA
  outputs, and real-mode checkout remain disabled. The Uno's reported 677-byte
  free-SRAM compile result is not accepted as a production margin; R1 must
  measure a runtime stack watermark or move to Mega.
- Rollback/recovery: preserve the legacy sketch under
  `hardware/references/legacy/`; if R1 work regresses, keep real mode disabled,
  rerun the recorded build/tests, and do not flash or power the current
  integrated firmware.

### Documentation and next action

- Synchronized: `CHECKPOINT.md`, `hardware/README.md`,
  `hardware/firmware/README.md`, `README.md`, `CLAUDE.md`,
  `docs/architecture/cash-order-integration.md`, and the legacy-reference
  notes.
- Next safe action: present this R0 evidence and obtain explicit user approval
  before beginning **R1 — Firmware safety**. No R1 code has been changed.
- User approval: **pending**.

### D-0009 — 2026-08-03, V1 bill sketch classification

The supplied root `Bill_Acceptor.ino` is unverified legacy evidence. Its
₱10-per-pulse mapping and timing constants are hypotheses only. It is retained
under `hardware/references/legacy/` and must never be flashed as the integrated
controller or used to authorize the installed TB unit.

## USB controller inspection — 2026-08-03 18:48:48 PST (+0800)

- Status: **diagnostic complete; no firmware write performed**.
- Detected board: Arduino Uno R3, USB VID/PID `2341:0043`, ATmega328P
  signature `0x1e950f`.
- Stable device path:
  `/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_751363233373514071E2-if00`
  → `/dev/ttyACM0`.
- Read-only flash inspection found the strings `MENDO_VENDO_V2:READY`,
  `SLOTS:`, `DISPENSE:`, and `System Ready`. This is an older self-test/legacy
  image, not the current integrated `mendo_controller.ino` image.
- Exact command results: `avrdude -n` identified the ATmega328P successfully;
  read-only flash dump completed successfully. No TB, coin acceptor, PCA9685,
  or servo wiring was validated by this inspection.
- Safety decision: do not flash the current integrated firmware because the R0
  audit found the PCA9685 OE polarity unsafe. The next write must be either an
  approved R1-remediated controller or a deliberately USB-only safe diagnostic
  image.
- Next safe action: obtain explicit direction on the image to flash; real cash,
  coin power, PCA outputs, and `PHYSICAL_EVIDENCE_CONFIRMED` remain disabled.

## USB-only diagnostic upload — 2026-08-03 18:53 PST (+0800)

- Status: **complete; diagnostic image only; R1 integrated firmware not started**.
- Target: Arduino Uno R3 / ATmega328P at the stable `/dev/serial/by-id/`
  path recorded above.
- Files added: `hardware/firmware/bench_safe/bench_safe.ino` and its README.
- Build result: `arduino-builder` Uno compile succeeded with **2,836 bytes
  flash and 237 bytes globals**.
- Upload result: `avrdude` wrote and verified **2,836 bytes** successfully.
- Serial command/result: at 115200 baud, `PING` returned `PONG`; startup and
  status output reported `MODE=USB_ONLY`, `ACCEPTORS=DISABLED`,
  `D5=LOW_COIN_POWER_OFF`, `D7=HIGH_PCA_OE_DISABLED`, `I2C=PCA_NOT_ACCESSED`,
  and `DISPENSING=NOT_IMPLEMENTED`.
- Safety condition: keep the TB, Allan acceptor, PCA9685, and servos
  disconnected. This image leaves D4 as `INPUT_INHIBIT_NOT_DRIVEN`; it is not
  a bill-inhibit controller and must not be used with a powered TB.
- No cash, pulse, voltage, inhibit-polarity, or servo measurement was made.
- Next safe action: approve and implement R1 before uploading any integrated
  controller. Real cash/motion and `PHYSICAL_EVIDENCE_CONFIRMED` remain off.

## Payment-only POS integration — 2026-08-05

- Status: **implemented and software-verified; ready for a supervised cash/POS
  trial; medicine motors remain disabled**.
- User evidence: the supplied combined D2/D3 diagnostic was reported working
  across the coin set. Earlier TB74 captures establish the D3 2/5/10 pulse map
  for PHP 20/50/100. The integrated controller now uses the diagnostic's tested
  D2 filters and the measured D3 filters.
- Controller gate split: `CASH_INPUTS_CONFIRMED=true` and
  `MEDICINE_MOTORS_ENABLED=false`. `DISPENSE_ONE` is rejected, and active-low
  PCA9685 OE is held HIGH during boot, fail-safe, and payment.
- Boundary fixes: controller `session` is normalized to `session_ref`; the host
  maps validated pulse counts instead of treating `mapped_centavos=0` as an
  unknown payment; queued events are retained until database commit and ACK,
  so a burst no longer loses every event after the first.
- POS behavior: both kiosk checkout and authenticated `/shop` Cashier start a
  durable cash session. On reaching the amount due,
  `finalize_payment_only_sale` deducts reserved inventory, clears reservations,
  writes sale logs, creates one receipt, and records
  `completion_mode=payment_only` in one `BEGIN IMMEDIATE` transaction. Replay
  returns the same receipt and does not deduct again. No dispense job is made.
- Verification: focused hardware/payment suite **39 passed** and the full suite
  **131 passed with 52 subtests**; simulator browser
  flow moved a PHP 10 order from `awaiting_cash` to `paid/completed`, reduced
  stock 10 → 9, left reserved stock at 0, and created a receipt; Python
  compileall, both JavaScript syntax checks, and `git diff --check` passed.
- Arduino Uno verification: **10,526 bytes flash (32%)**, **1,407 bytes globals
  (68%)**, **641 bytes free SRAM**. Frame CRC output is streamed to avoid a
  second 241-byte stack buffer during cash-event emission.
- Remaining prototype risks: controller EEPROM cash replay across a hard reset,
  acceptor-control polarity, conditioned voltage limits, and long-run/noise
  trials still require physical fault testing. `PAY_STOP` now inhibits new
  money while draining a pulse train that had already begun. Keep the trial
  supervised and do not attach medicine motors.
