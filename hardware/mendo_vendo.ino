/*
 * ═══════════════════════════════════════════════════════════
 *  MENDO VENDO — Spring-Type Medicine Vending Machine
 *  Arduino Uno + 2 Servos (1 servo per medicine slot)
 * ═══════════════════════════════════════════════════════════
 *
 * HARDWARE SETUP:
 *   Servo 1 (Slot 1) → Pin 9
 *   Servo 2 (Slot 2) → Pin 10
 *   Status LED        → Pin 13 (built-in)
 *
 * SERIAL PROTOCOL (9600 baud):
 *   Command (from PC):   "DISPENSE:<slot>\n"       e.g. "DISPENSE:1\n"
 *   Batch command:        "BATCH:<s>=<q>,<s>=<q>\n" e.g. "BATCH:1=2,2=3\n"
 *     → All slots spin simultaneously
 *     → Duration = quantity × SPIN_PER_QTY_MS (5 sec default)
 *   Response (to PC):    "OK:<slot>\n"              on single dispense
 *                        "BATCH_OK:<s>=<q>,...\n"    on batch
 *                        "ERR:<message>\n"           on failure
 *   Heartbeat:           "PING\n" → "PONG\n"
 *   Status:              "STATUS\n" → "READY:2\n"
 *
 * SPRING MECHANISM:
 *   - Servo rotates from 0° → DISPENSE_ANGLE (e.g. 180°) to push spring
 *   - Holds for duration proportional to quantity
 *   - Returns to 0° (rest position)
 */

#include <Servo.h>

// ─── Configuration ───────────────────────────────────
#define NUM_SLOTS       2
#define BAUD_RATE       9600
#define STATUS_LED      13

// How long the servo spins per 1 quantity (milliseconds)
// 1 qty = 5000ms, 2 qty = 10000ms, 3 qty = 15000ms, etc.
#define SPIN_PER_QTY_MS 5000

// Max items in a single BATCH command
#define MAX_BATCH       4

// Servo pins (Arduino Uno PWM pins)
const int SERVO_PINS[NUM_SLOTS] = { 9, 10 };

// Dispense settings per slot (adjustable per spring tension)
const int DISPENSE_ANGLE[NUM_SLOTS] = { 180, 180 };  // degrees to rotate
const int REST_ANGLE[NUM_SLOTS]     = { 0, 0 };       // rest position

// ─── Globals ─────────────────────────────────────────
Servo servos[NUM_SLOTS];
bool  slotBusy[NUM_SLOTS] = { false, false };
String inputBuffer = "";

// ─── Setup ───────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);
  pinMode(STATUS_LED, OUTPUT);
  
  // Attach servos and set to rest position
  for (int i = 0; i < NUM_SLOTS; i++) {
    servos[i].attach(SERVO_PINS[i]);
    servos[i].write(REST_ANGLE[i]);
    delay(100);
  }
  
  // Ready indicator: blink LED 3 times
  for (int i = 0; i < 3; i++) {
    digitalWrite(STATUS_LED, HIGH);
    delay(150);
    digitalWrite(STATUS_LED, LOW);
    delay(150);
  }
  
  Serial.println("MENDO_VENDO:READY");
  Serial.println("SLOTS:" + String(NUM_SLOTS));
}

// ─── Main Loop ───────────────────────────────────────
void loop() {
  // Read serial commands
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
      // Prevent buffer overflow
      if (inputBuffer.length() > 64) {
        inputBuffer = "";
        Serial.println("ERR:BUFFER_OVERFLOW");
      }
    }
  }
}

// ─── Command Processor ──────────────────────────────
void processCommand(String cmd) {
  cmd.toUpperCase();
  
  // PING — heartbeat check
  if (cmd == "PING") {
    Serial.println("PONG");
    return;
  }
  
  // STATUS — report ready state
  if (cmd == "STATUS") {
    Serial.println("READY:" + String(NUM_SLOTS));
    return;
  }
  
  // ── BATCH:<slot>=<qty>,<slot>=<qty>  (simultaneous dispense) ──
  // e.g. "BATCH:1=2,2=3"  → slot 1 spins 10s, slot 2 spins 15s, both at once
  if (cmd.startsWith("BATCH:")) {
    String payload = cmd.substring(6);
    processBatch(payload);
    return;
  }

  // DISPENSE:<slot>  (1-indexed, single unit)
  if (cmd.startsWith("DISPENSE:")) {
    String slotStr = cmd.substring(9);
    int slot = slotStr.toInt();
    
    if (slot < 1 || slot > NUM_SLOTS) {
      Serial.println("ERR:INVALID_SLOT_" + String(slot));
      return;
    }
    
    int idx = slot - 1;  // Convert to 0-indexed
    
    if (slotBusy[idx]) {
      Serial.println("ERR:SLOT_BUSY_" + String(slot));
      return;
    }
    
    dispenseSlot(idx, 1);
    Serial.println("OK:" + String(slot));
    return;
  }
  
  // TEST:<slot> — test servo without full dispense cycle
  if (cmd.startsWith("TEST:")) {
    String slotStr = cmd.substring(5);
    int slot = slotStr.toInt();
    
    if (slot < 1 || slot > NUM_SLOTS) {
      Serial.println("ERR:INVALID_SLOT_" + String(slot));
      return;
    }
    
    int idx = slot - 1;
    // Quick test: move to 45° and back
    servos[idx].write(45);
    delay(300);
    servos[idx].write(REST_ANGLE[idx]);
    delay(200);
    Serial.println("TEST_OK:" + String(slot));
    return;
  }
  
  // RESET — return all servos to rest
  if (cmd == "RESET") {
    for (int i = 0; i < NUM_SLOTS; i++) {
      servos[i].write(REST_ANGLE[i]);
      slotBusy[i] = false;
    }
    delay(300);
    Serial.println("RESET_OK");
    return;
  }
  
  // Unknown command
  Serial.println("ERR:UNKNOWN_CMD");
}

// ─── Batch Dispense (simultaneous) ──────────────────
// Parse "1=2,2=3" → start all servos at once, each runs qty × SPIN_PER_QTY_MS
void processBatch(String payload) {
  int batchSlots[MAX_BATCH];
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

  // Start ALL servos simultaneously → dispense angle
  for (int i = 0; i < batchCount; i++) {
    servos[batchSlots[i]].write(DISPENSE_ANGLE[batchSlots[i]]);
  }

  // Non-blocking timing: check each slot's duration
  unsigned long startTime = millis();
  bool running[MAX_BATCH];
  for (int i = 0; i < batchCount; i++) running[i] = true;

  while (millis() - startTime < maxDuration + 500) {
    unsigned long elapsed = millis() - startTime;
    for (int i = 0; i < batchCount; i++) {
      if (running[i] && elapsed >= durations[i]) {
        // This slot is done — return servo to rest
        servos[batchSlots[i]].write(REST_ANGLE[batchSlots[i]]);
        running[i] = false;
      }
    }
    delay(50);  // small tick
  }

  // Ensure all returned to rest
  for (int i = 0; i < batchCount; i++) {
    servos[batchSlots[i]].write(REST_ANGLE[batchSlots[i]]);
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

// ─── Single Dispense ────────────────────────────────
void dispenseSlot(int idx, int qty) {
  slotBusy[idx] = true;
  digitalWrite(STATUS_LED, HIGH);
  
  unsigned long duration = (unsigned long)qty * SPIN_PER_QTY_MS;

  // Rotate servo to push the spring coil
  servos[idx].write(DISPENSE_ANGLE[idx]);
  
  // Hold for quantity-proportional duration
  delay(duration);
  
  // Return servo to rest position
  servos[idx].write(REST_ANGLE[idx]);
  
  // Wait for servo to return fully
  delay(500);
  
  slotBusy[idx] = false;
  digitalWrite(STATUS_LED, LOW);
}
