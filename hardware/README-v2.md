# Mendo Vendo v2 — Servo + DC Motor (Relay)

## Overview

This version supports **1 servo (SG90)** and **1 DC motor (dynamo)** driven via a **relay module**.

- **Slot 1** → Servo (Pin 9)
- **Slot 2** → DC Motor via Relay (Pin 8)

---

## Wiring

### Servo (Slot 1)
- Servo Signal → **Pin 9**
- Servo VCC → **External 5V**
- Servo GND → **External GND**

### Relay + DC Motor (Slot 2)
- Relay **IN** → **Pin 8**
- Relay **VCC** → **5V** (Arduino 5V or external 5V depending on relay module)
- Relay **GND** → **Arduino GND**

**Motor Power:**
- External motor supply **+** → Relay COM
- Relay NO → Motor **+**
- Motor **-** → External motor supply **-**
- **Common ground**: External motor supply GND must connect to Arduino GND

> Add a flyback diode across the motor terminals (if not built into relay module) to protect from voltage spikes.

---

## Serial Protocol (9600 baud)

| Command | Response | Action |
|--------|----------|--------|
| `PING` | `PONG` | Heartbeat |
| `STATUS` | `READY:2` | Status |
| `DISPENSE:1` | `OK:1` | Servo dispense |
| `DISPENSE:2` | `OK:2` | Motor dispense |
| `RESET` | `RESET_OK` | Reset |

---

## Firmware File

Use: **hardware/mendo_vendo_v2.ino**

### Adjustable Parameters (in code)

```cpp
const int SERVO_DISPENSE = 180;
const int SERVO_HOLD_MS = 800;

const int MOTOR_RUN_MS = 1200;
const bool RELAY_ACTIVE_HIGH = true; // set false if relay is active LOW
```

---

## Notes

- DC motor must have its **own power supply**.
- Never power the motor from Arduino 5V pin.
- Always connect grounds together.
