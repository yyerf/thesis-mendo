# Legacy hardware evidence

`Bill_Acceptor.ino` is the V1 sketch supplied for audit. It is retained here
as unverified legacy evidence and must never be flashed as the integrated
controller.

Its `1 pulse = ₱10` mapping predicts 2 pulses for ₱20, 5 for ₱50, and 10 for
₱100, but those values are only hypotheses until the exact TB PHP unit is
measured. The sketch has no inhibit control, payment-session binding,
replay/idempotency protocol, or measured pulse calibration. The integrated
firmware under `hardware/firmware/mendo_controller/` is a separate source tree
and remains physically gated.
