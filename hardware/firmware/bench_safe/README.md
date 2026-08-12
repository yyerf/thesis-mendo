# USB-only bench diagnostic

`bench_safe.ino` is a temporary diagnostic image for board identification and
serial testing while the cash acceptors, PCA9685, and servos are disconnected.
It does not capture cash, drive the TB inhibit pair, access I2C, or move a
servo. It holds coin power off and PCA9685 OE high (disabled).

This is not the integrated controller and is not a cash-acceptance test.
