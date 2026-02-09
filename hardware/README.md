# Mendo Vendo — Hardware Setup Guide

## Overview

Spring-type medicine vending machine controlled by **Arduino Uno** with **2 servo motors**.  
Each servo pushes a spring coil to dispense one type of medicine.

---

## Hardware Components

| Component         | Quantity | Notes                          |
|--------------------|----------|--------------------------------|
| Arduino Uno R3     | 1        | USB-B connection to PC         |
| Servo Motor (SG90) | 2        | Or MG996R for heavier springs  |
| 5V Power Supply    | 1        | External supply for servos     |
| Spring Coils       | 2        | One per medicine slot          |
| USB Cable          | 1        | Arduino to PC                  |
| Jumper Wires       | ~12      | Signal, VCC, GND               |

---

## Wiring Diagram

```
                    ┌─────────────────────┐
                    │    ARDUINO UNO      │
                    │                     │
    Servo 1 ◄──────┤ Pin 9  (PWM)        │
    Servo 2 ◄──────┤ Pin 10 (PWM)        │
                    │                     │
    Status LED ◄───┤ Pin 13 (built-in)   │
                    │                     │
                    │ 5V ────────────┐    │
                    │ GND ───────────┤    │
                    └────────────────┤────┘
                                     │
                           ┌─────────┴─────────┐
                           │  EXTERNAL 5V PSU   │
                           │  (for servos)      │
                           └───────────────────-┘
```

### Pin Connections

| Arduino Pin | Component     | Wire Color (suggested) |
|-------------|---------------|------------------------|
| Pin 9       | Servo 1 Signal| Orange/Yellow          |
| Pin 10      | Servo 2 Signal| Orange/Yellow          |
| Pin 13      | Built-in LED  | (on board)             |
| 5V          | Servo VCC     | Red                    |
| GND         | Servo GND     | Brown/Black            |

### ⚠️ Important: External Power for Servos

**Do NOT power the servos from the Arduino 5V pin!**  
Use an external 5V power supply (≥2A) and connect:
- External 5V → Servo VCC (both servos)
- External GND → Servo GND (both servos) **AND** Arduino GND (common ground!)
- Arduino pins 9/10 → Servo signal wires only

---

## Slot Mapping

Edit `config.json` to map medicine brands to physical slots:

```json
{
  "port": "/dev/ttyACM0",
  "baud": 9600,
  "slots": {
    "Decolgen": 1,
    "Biogesic": 2
  }
}
```

- **`port`**: Set to `null` for auto-detect, or specify manually:
  - Linux: `"/dev/ttyUSB0"` or `"/dev/ttyACM0"`
  - Windows: `"COM3"`, `"COM4"`, etc.
  - Mac: `"/dev/cu.usbmodem14101"`
- **`baud`**: Must match Arduino sketch (default `9600`)
- **`slots`**: Maps brand name → servo number (1 or 2)

---

## Arduino Firmware Upload

1. Open `mendo_vendo.ino` in Arduino IDE
2. Select **Board**: Arduino Uno
3. Select the correct **Port**
4. Click **Upload** (→)
5. Open Serial Monitor (9600 baud) — you should see:
   ```
   MENDO_VENDO:READY
  SLOTS:2
   ```

### Adjusting Dispense Settings

In `mendo_vendo.ino`, adjust these per slot if needed:

```cpp
const int DISPENSE_ANGLE[NUM_SLOTS] = { 180, 180 };  // rotation degrees
const int REST_ANGLE[NUM_SLOTS]     = { 0, 0 };       // rest position  
const int HOLD_TIME_MS[NUM_SLOTS]   = { 800, 800 };   // hold time (ms)
```

- **DISPENSE_ANGLE**: How far the servo rotates (increase if spring doesn't push enough)
- **HOLD_TIME_MS**: How long to hold (increase if medicine needs more time to fall)

---

## Serial Protocol

| Command (PC → Arduino) | Response (Arduino → PC) | Description            |
|-------------------------|------------------------|------------------------|
| `PING\n`                | `PONG\n`               | Heartbeat check        |
| `STATUS\n`              | `READY:2\n`            | Get status             |
| `DISPENSE:1\n`          | `OK:1\n`               | Dispense from slot 1   |
| `DISPENSE:2\n`          | `OK:2\n`               | Dispense from slot 2   |
| `TEST:1\n`              | `TEST_OK:1\n`          | Test servo 1 (small move) |
| `RESET\n`               | `RESET_OK\n`           | Return all to rest     |

Error responses: `ERR:INVALID_SLOT_N`, `ERR:SLOT_BUSY_N`, `ERR:UNKNOWN_CMD`

---

## Python Bridge Test

```bash
# Install pyserial
pip install pyserial

# Run interactive test
python hardware/serial_bridge.py
```

This will:
1. Auto-detect the Arduino port
2. Test PING/PONG
3. Enter interactive mode (type `1`, `2` to dispense, `t1` to test)

---

## Integration Flow

```
User clicks "Buy & Dispense" on recommendation card
        │
        ▼
  Flask /api/vend endpoint
        │
        ├── 1. Check stock (POS database)
        ├── 2. Create transaction (deduct stock)
        ├── 3. Send DISPENSE:N to Arduino
        │       via serial_bridge.py
        └── 4. Return success + receipt
        │
        ▼
  Arduino rotates servo → spring pushes medicine → medicine drops
```

---

## Troubleshooting

| Problem                  | Solution                                           |
|--------------------------|-----------------------------------------------------|
| Port not detected        | Check USB cable, install CH340 drivers if needed     |
| Permission denied (Linux)| `sudo chmod 666 /dev/ttyUSB0` or add user to `dialout` group |
| Servo jitters            | Use external 5V power supply, add capacitor         |
| Medicine doesn't drop    | Increase `DISPENSE_ANGLE` or `HOLD_TIME_MS`         |
| Serial timeout           | Check baud rate matches (9600), reset Arduino        |
| Multiple Arduino boards  | Set `port` explicitly in `config.json`               |
