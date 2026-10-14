# Uno firmware backup — 2026-09-28

Read-only dump of the working, integrated Arduino Uno R3 controller (coin slot,
TB bill acceptor, thermal printer) taken after the source `.ino` was lost with
the old SSD. **No source for the printer build exists in git** — this binary is
the only copy until the sketch is reconstructed.

| File | Contents | SHA-256 |
|------|----------|---------|
| `uno_working_2026-09-28.hex` | full 32 KiB flash (app + Optiboot), Intel HEX | `369ab96e9547ddcfdc8726c7c83ed7c19adae28ac8a99a221a03889a6ec98447` |
| `uno_working_2026-09-28.eeprom.hex` | **not EEPROM** — see note below | `53ee9dd199628c6df95ce5f64ef3ae91a3695376ad35ef359b93604529f27e11` |

**Correction (same day):** the "EEPROM" file holds the first 1 KiB of *flash*
(its bytes are the interrupt vector table and format strings). The Uno's
Optiboot bootloader does not implement EEPROM reads and silently returned flash.
The real EEPROM contents were never captured; reading them needs an ISP
programmer. The flash backup is unaffected and was verified.

Board: Uno R3 `2341:0043`, ATmega328P `0x1e950f`, USB serial
`751363233373514071E2`. Dump verified byte-for-byte against the chip
(`avrdude -U flash:v`, 32768 bytes). Fuses are not readable through Optiboot.

## Identity (live probe at 115200 baud, `MENDO/1` protocol)

- `firmware_identity=mendo-controller-v1`, `protocol_version=1`,
  `configuration_valid=1`, `pca_outputs_enabled=0` — i.e. the payment-only
  `mendo_controller.ino` **plus a printer extension** (~13.6 KB app vs 10.5 KB
  for the repo sketch).
- Printer commands present only in this image: `PRINTER_STATUS`,
  `PRINT_BEGIN`, `PRINT_CHUNK` (`offset=`, `hex=`), `PRINT_END`, `PRINT_CLEAR`;
  response `PRINT_STATUS` (`known, ready, dtr_level, state, received, length,
  stack_headroom`); faults `PRINTER_NOT_READY`, `PRINTER_INTERRUPTED`,
  `PRINT_JOB_NOT_ACTIVE`, `PRINT_OFFSET_MISMATCH`, `PRINT_LENGTH_MISMATCH`,
  `BAD_PRINT_CHUNK`, `PRIOR_PRINT_AMBIGUOUS`, `PRINT_CLEAR_REJECTED`.
- Idle printer probe: `ready=1; dtr_level=0; state=0`.

## Restore

```
avrdude -p m328p -c arduino -P /dev/ttyACM0 -b 115200 \
  -U flash:w:uno_working_2026-09-28.hex:i
```

EEPROM cannot be read or written through Optiboot. Firmware that reuses it
(boot counter, cash-evidence ring, print record) must validate what it finds.
