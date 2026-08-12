# Uno/Mega controller firmware

`mendo_controller.ino` is the payment-only controller for the tested D2 coin
and D3 TB74 pulse paths. It is a single Arduino IDE sketch and also shares Uno
and Mega build definitions through `platformio.ini`:

```text
pio run -d hardware/firmware -e uno
pio run -d hardware/firmware -e mega
```

The cash gate is enabled from the completed pulse trials. Firmware reports
validated counts only; the Python host owns the peso mapping. The Uno build is
verified at 10,526 bytes flash and 1,407 bytes globals (641 bytes free), and frame transmission
streams its CRC instead of allocating a second large buffer on the stack.

Medicine motion is a separate gate and remains disabled. `DISPENSE_ONE` is
always rejected, PCA9685 OE is HIGH during boot/fail-safe/payment, and the
placeholder motion profiles must not be treated as calibration. Keep servos
disconnected during this phase. Cash-event replay after a daemon/controller
restart still needs a supervised fault test before production use.
