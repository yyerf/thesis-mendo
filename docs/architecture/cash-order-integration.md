# Cash order and dispenser architecture

Status: payment-only real cash path implemented for supervised POS testing;
medicine-motor dispatch is intentionally disabled.

## Durable boundary

The browser cart is only a pre-order view. `OrderService` creates the durable
order, snapshots each catalog line and centavo price, and reserves stock under
SQLite `BEGIN IMMEDIATE`. Availability is `stock_quantity - reserved_quantity`.
The order reference and idempotency key are the recovery handles; browser
sessions are not the payment source of truth.

Cash events carry the payment session, source, raw pulse count, mapped
centavos, controller boot id, and sequence number. The unique event id and
boot/sequence/source constraint make replay safe. Unknown pulse trains credit
nothing and put the order into manual review. When payment reaches the due
amount, overpayment is stored separately from medicine revenue and acceptors
are stopped.

In the current payment-only rollout, reaching the amount due calls
`finalize_payment_only_sale`. It deducts all reserved quantities, releases the
reservations, writes stock logs, creates the receipt, and stamps
`completion_mode=payment_only` in one SQLite write transaction. Replaying that
transition returns the same receipt and cannot deduct stock again. No dispense
job is created and no item is labelled physically dispensed.

The older sequential dispense state machine remains isolated for future motor
work, but checkout does not invoke it in this phase.

Polling an already-paid order is also a recovery trigger after a Flask restart:
it re-enters the idempotent stock/receipt commit and never contacts a motor.

## Hardware process boundary

Flask uses `HardwareService` and a short-lived Unix-socket client. A dedicated
`hardware.daemon` owns the socket and, in real mode, the only `/dev/mendo-uno`
serial descriptor through `SerialHardwareBackend`. Frames are bounded,
newline-delimited ASCII with request ids and CRC16-CCITT. The simulator is the
default development mode and is labelled in every status/order response.

Real cash requires the expected firmware identity, protocol-version match,
recent heartbeat, healthy connection, and the measured cash-input gate. The
controller sends `session`; the serial owner normalizes it to `session_ref` and
maps clean pulse counts through `PulseMapping`. Events are peeked until the POS
commits and ACKs them, so a burst is not destructively drained. Motion stays
behind the separate false compile-time gate.

## Recovery ownership

| Evidence/state | Durable owner | Recovery rule |
| --- | --- | --- |
| Cash pulse | `cash_events` + controller EEPROM | Commit, then ACK; replay is duplicate-safe |
| Payment amount | `orders` | Integer centavos; overpayment is separate |
| Stock reservation | `inventory.reserved_quantity` + `order_items` | Release only undispensed units |
| Physical attempt | `dispense_jobs` + controller job ring | Never retry an unknown physical result |
| Receipt | legacy `transactions` projection | Create once with the payment-only stock commit |
| Drawer count | `cashbox_sessions` | Reconcile only events assigned to that drawer session |

The physical acceptance evidence remains a later action: exact TB model and
PHP sheet, harness continuity, DIP polarity, coin/bill pulse captures,
0–5 V conditioned signals, servo profiles, current/voltage measurements, and
the required repeated trial counts.

The authenticated admin boundary exposes the same durable evidence through
hardware health, payment-event, dispense-job, accounting, cashbox, profile,
and manual-recovery endpoints. Sales revenue is reported separately from
received tender and overpayment.
