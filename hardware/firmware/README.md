# Uno/Mega controller firmware

`mendo_controller/mendo_controller.ino` is the payment + receipt controller:
D2 coin and D3 TB74 pulse inputs, the KMP26 printer on D9 (TX) / D10 (busy),
and no medicine motion. It is a single Arduino IDE sketch that also builds for
the Mega:

```text
arduino-cli compile --fqbn arduino:avr:uno  hardware/firmware/mendo_controller
arduino-cli upload  --fqbn arduino:avr:uno -p /dev/ttyACM0 hardware/firmware/mendo_controller
pio run -d hardware/firmware -e uno      # PlatformIO alternative
```

Uno build (2026-09-28): **15,690 bytes flash, 1,373 bytes globals, 675 bytes
free SRAM**. Keep an eye on free SRAM: an earlier variant with 555 bytes free
overflowed the stack on `PRINTER_STATUS` and streamed garbage. Soak-test every
command after changing buffers (300/300 clean on the current build).

History: the working printer build's source was lost with an SSD on
2026-09-28. This sketch was rebuilt from the repository's payment-only
controller plus the printer protocol recovered from the backed-up image
(`backup/`). It is protocol-compatible with that image except that print
fingerprints compare all 64 bits (the lost build compared only 32) and the
`STATUS` payload is no longer truncated (`FAIL_` → `FAIL_SAFE`).

Firmware reports validated pulse counts only; the Python host owns the peso
mapping. Pulse trains end after 400 ms (coin) / 500 ms (bill) without a
*settled* level change; raw sub-millisecond spikes no longer extend a train.

Medicine motion stays disabled: the PCA9685/I2C code is not linked (see git
history before 2026-09-28 for the motion build), `DISPENSE_ONE` is always
rejected, and PCA OE (D7) is held HIGH. Keep servos disconnected.

Other sketches in this folder are bench diagnostics from August 2026.
