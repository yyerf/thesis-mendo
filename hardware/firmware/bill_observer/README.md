# TB bill-only observer

`bill_observer.ino` is an observe-only Arduino Uno sketch for the TB
WEL-R7U02 METER output. It captures `CHANGE` edges on D3/INT1 and prints raw
pulse count, every edge timestamp, pulse width, inter-pulse gap, train
duration, and the unverified V1 candidate mapping:

- 2 pulses → candidate ₱20.00
- 5 pulses → candidate ₱50.00
- 10 pulses → candidate ₱100.00

The mapping and 250 ms train gap are hypotheses only. The sketch never credits
an order, drives D4/TB inhibit, powers a coin acceptor, accesses the PCA9685,
or moves a servo.

Serial is 115200 baud. Send `ARM` before a pulse trial; use `STATUS`, `HELP`,
or `DISARM` as needed. Keep the TB inhibit pair disconnected from the Uno
until the exact TB PHP/DIP polarity has been measured. This is not a
production cash controller.
