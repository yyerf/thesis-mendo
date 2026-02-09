/*
 * ═══════════════════════════════════════════════════════════
 *  MENDO VENDO v2 — Servo + DC Motor (Relay)
 *  Arduino Uno + 1 Servo + 1 DC Motor (via relay)
 * ═══════════════════════════════════════════════════════════
 *
 * SLOT MAP:
 *   Slot 1 = Servo (SG90) → Pin 9
 *   Slot 2 = DC Motor (Dynamo) via Relay → Pin 8
 *
 * SERIAL PROTOCOL (9600 baud):
 *   DISPENSE:1          -> servo spins for SPIN_PER_QTY_MS (1 unit)
 *   DISPENSE:2          -> motor ON for SPIN_PER_QTY_MS (1 unit)
 *   BATCH:1=2,2=3       -> servo 10s + motor 15s simultaneously
 *     → Duration = quantity × SPIN_PER_QTY_MS (5 sec default)
 *   STATUS              -> READY:2
 *   PING                -> PONG
 */

#include <Servo.h>

#define NUM_SLOTS 2
#define BAUD_RATE 9600
#define STATUS_LED 13

// How long each actuator runs per 1 quantity (milliseconds)
// 1 qty = 5000ms, 2 qty = 10000ms, 3 qty = 15000ms, etc.
#define SPIN_PER_QTY_MS 5000

// Max items in a single BATCH command
#define MAX_BATCH 4

// Slot 1 (Servo)
const int SERVO_PIN = 9;
const int SERVO_REST = 0;
const int SERVO_DISPENSE = 180;

// Slot 2 (DC Motor via Relay)
const int RELAY_PIN = 8;      // IN pin on relay module
const bool RELAY_ACTIVE_HIGH = true; // set false if your relay is active LOW

Servo servo1;
bool slotBusy[NUM_SLOTS] = { false, false };
String inputBuffer = "";

void setup() {
  Serial.begin(BAUD_RATE);
  pinMode(STATUS_LED, OUTPUT);

  // Servo setup
  servo1.attach(SERVO_PIN);
  servo1.write(SERVO_REST);

  // Relay setup
  pinMode(RELAY_PIN, OUTPUT);
  relayOff();

  // Ready blink
  for (int i = 0; i < 3; i++) {
    digitalWrite(STATUS_LED, HIGH);
    delay(150);
    digitalWrite(STATUS_LED, LOW);
    delay(150);
  }

  Serial.println("MENDO_VENDO_V2:READY");
  Serial.println("SLOTS:" + String(NUM_SLOTS));
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
      if (inputBuffer.length() > 64) {
        inputBuffer = "";
        Serial.println("ERR:BUFFER_OVERFLOW");
      }
    }
  }
}

void processCommand(String cmd) {
  cmd.toUpperCase();

  if (cmd == "PING") {
    Serial.println("PONG");
    return;
  }

  if (cmd == "STATUS") {
    Serial.println("READY:" + String(NUM_SLOTS));
    return;
  }

  // ── BATCH:<slot>=<qty>,<slot>=<qty>  (simultaneous dispense) ──
  if (cmd.startsWith("BATCH:")) {
    String payload = cmd.substring(6);
    processBatch(payload);
    return;
  }

  // ── TEST:<slot>  (brief actuator test — no product dispensed) ──
  if (cmd.startsWith("TEST:")) {
    int slot = cmd.substring(5).toInt();
    if (slot < 1 || slot > NUM_SLOTS) {
      Serial.println("ERR:INVALID_SLOT_" + String(slot));
      return;
    }
    if (slot == 1) {
      // Servo: small jiggle (0→45→0)
      servo1.write(45);
      delay(400);
      servo1.write(SERVO_REST);
    } else {
      // DC Motor: brief relay pulse
      relayOn();
      delay(400);
      relayOff();
    }
    Serial.println("TEST_OK:" + String(slot));
    return;
  }

  // ── DISPENSE:<slot>  (single unit) ──
  if (cmd.startsWith("DISPENSE:")) {
    int slot = cmd.substring(9).toInt();
    if (slot < 1 || slot > NUM_SLOTS) {
      Serial.println("ERR:INVALID_SLOT_" + String(slot));
      return;
    }

    int idx = slot - 1;
    if (slotBusy[idx]) {
      Serial.println("ERR:SLOT_BUSY_" + String(slot));
      return;
    }

    unsigned long duration = SPIN_PER_QTY_MS;

    if (slot == 1) {
      dispenseServo(duration);
    } else {
      dispenseMotor(duration);
    }
    Serial.println("OK:" + String(slot));
    return;
  }

  if (cmd == "RESET") {
    servo1.write(SERVO_REST);
    relayOff();
    slotBusy[0] = slotBusy[1] = false;
    Serial.println("RESET_OK");
    return;
  }

  Serial.println("ERR:UNKNOWN_CMD");
}

// ─── Batch Dispense (simultaneous) ──────────────────
// Parse "1=2,2=3" → start servo + motor at same time,
// each runs for qty × SPIN_PER_QTY_MS
void processBatch(String payload) {
  int batchSlots[MAX_BATCH];    // 0-indexed slot
  int batchQty[MAX_BATCH];
  int batchCount = 0;

  // Parse comma-separated pairs
  int start = 0;
  while (start < (int)payload.length() && batchCount < MAX_BATCH) {
    int comma = payload.indexOf(',', start);
    String pair;
    if (comma == -1) {
      pair = payload.substring(start);
      start = payload.length();
    } else {
      pair = payload.substring(start, comma);
      start = comma + 1;
    }
    pair.trim();
    int eq = pair.indexOf('=');
    if (eq == -1) {
      Serial.println("ERR:BAD_BATCH_FORMAT");
      return;
    }
    int s = pair.substring(0, eq).toInt();
    int q = pair.substring(eq + 1).toInt();
    if (s < 1 || s > NUM_SLOTS) {
      Serial.println("ERR:INVALID_SLOT_" + String(s));
      return;
    }
    if (q < 1 || q > 10) {
      Serial.println("ERR:INVALID_QTY_" + String(q));
      return;
    }
    int idx = s - 1;
    if (slotBusy[idx]) {
      Serial.println("ERR:SLOT_BUSY_" + String(s));
      return;
    }
    batchSlots[batchCount] = idx;
    batchQty[batchCount] = q;
    batchCount++;
  }

  if (batchCount == 0) {
    Serial.println("ERR:EMPTY_BATCH");
    return;
  }

  // Mark all busy
  for (int i = 0; i < batchCount; i++) {
    slotBusy[batchSlots[i]] = true;
  }
  digitalWrite(STATUS_LED, HIGH);

  // Calculate per-slot duration
  unsigned long durations[MAX_BATCH];
  unsigned long maxDuration = 0;
  for (int i = 0; i < batchCount; i++) {
    durations[i] = (unsigned long)batchQty[i] * SPIN_PER_QTY_MS;
    if (durations[i] > maxDuration) maxDuration = durations[i];
  }

  // Start ALL actuators simultaneously
  int servoIndex = -1;
  for (int i = 0; i < batchCount; i++) {
    if (batchSlots[i] == 0) {
      servo1.write(SERVO_DISPENSE);  // Servo ON
      servoIndex = i;
    } else {
      relayOn();                      // Motor ON
    }
  }

  // Non-blocking timing: check each slot's duration
  unsigned long startTime = millis();
  bool running[MAX_BATCH];
  for (int i = 0; i < batchCount; i++) running[i] = true;

  bool servoPos = false;
  unsigned long lastServoToggle = millis();
  while (millis() - startTime < maxDuration + 500) {
    unsigned long elapsed = millis() - startTime;
    // Keep servo oscillating while its slot is still running
    if (servoIndex >= 0 && running[servoIndex]) {
      if (millis() - lastServoToggle >= 250) {
        servo1.write(servoPos ? SERVO_DISPENSE : SERVO_REST);
        servoPos = !servoPos;
        lastServoToggle = millis();
      }
    }
    for (int i = 0; i < batchCount; i++) {
      if (running[i] && elapsed >= durations[i]) {
        // This slot is done — stop its actuator
        if (batchSlots[i] == 0) {
          servo1.write(SERVO_REST);
        } else {
          relayOff();
        }
        running[i] = false;
      }
    }
    delay(50);
  }

  // Ensure everything is off
  servo1.write(SERVO_REST);
  relayOff();
  for (int i = 0; i < batchCount; i++) {
    slotBusy[batchSlots[i]] = false;
  }
  delay(300);
  digitalWrite(STATUS_LED, LOW);

  // Build response: "BATCH_OK:1=2,2=3"
  String resp = "BATCH_OK:";
  for (int i = 0; i < batchCount; i++) {
    if (i > 0) resp += ",";
    resp += String(batchSlots[i] + 1) + "=" + String(batchQty[i]);
  }
  Serial.println(resp);
}

// ─── Single Dispense (duration-based) ───────────────
void dispenseServo(unsigned long duration) {
  slotBusy[0] = true;
  digitalWrite(STATUS_LED, HIGH);
  // Oscillate servo during duration for a visible continuous motion
  unsigned long startTime = millis();
  bool pos = false;
  while (millis() - startTime < duration) {
    servo1.write(pos ? SERVO_DISPENSE : SERVO_REST);
    pos = !pos;
    delay(250);
  }
  servo1.write(SERVO_REST);
  delay(500);
  digitalWrite(STATUS_LED, LOW);
  slotBusy[0] = false;
}

void dispenseMotor(unsigned long duration) {
  slotBusy[1] = true;
  digitalWrite(STATUS_LED, HIGH);
  relayOn();
  delay(duration);
  relayOff();
  delay(300);
  digitalWrite(STATUS_LED, LOW);
  slotBusy[1] = false;
}

void relayOn() {
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_HIGH ? HIGH : LOW);
}

void relayOff() {
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_HIGH ? LOW : HIGH);
}
