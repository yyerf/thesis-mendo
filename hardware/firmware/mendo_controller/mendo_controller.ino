/*
 * MendoVendo controller firmware.
 *
 * One source tree targets Arduino Uno and Mega. D0/D1 remain USB serial;
 * board selection changes only compile-time capacity. The host protocol is a
 * bounded ASCII frame with CRC16-CCITT. No Arduino String or JSON is used.
 *
 * Payment-only build: the measured D2/D3 pulse paths can credit a POS cash
 * session. Medicine motors remain compile-time disabled and this firmware
 * will reject every DISPENSE_ONE command.
 */

#include <Arduino.h>
#include <EEPROM.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <Wire.h>

#if defined(ARDUINO_AVR_UNO)
static const uint8_t EEPROM_RING_SLOTS = 8;
static const uint8_t JOB_RING_SLOTS = 8;
#elif defined(ARDUINO_AVR_MEGA2560)
static const uint8_t EEPROM_RING_SLOTS = 24;
static const uint8_t JOB_RING_SLOTS = 24;
#else
static const uint8_t EEPROM_RING_SLOTS = 8;
static const uint8_t JOB_RING_SLOTS = 8;
#endif

static const uint8_t PIN_COIN = 2;          // INT0
static const uint8_t PIN_BILL = 3;          // INT1
static const uint8_t PIN_BILL_INHIBIT = 4;
static const uint8_t PIN_COIN_POWER = 5;
static const uint8_t PIN_CHUTE_RESERVED = 6;
static const uint8_t PIN_PCA_OE = 7;        // active low
static const uint8_t PIN_INTERLOCK = 8;
static const uint8_t PCA9685_ADDR = 0x40;
static const uint16_t FRAME_LIMIT = 240;
static const uint32_t HEARTBEAT_TIMEOUT_MS = 3000UL;

// ---------------------------------------------------------------------------
// Cash pulse discrimination.
//
// TB74 bill geometry is MEASURED, not assumed: 2026-08-03 bench captures gave
// LOW 50 ms, HIGH 100 ms, period 150 ms (Fast, 10-way SW4 = ON) for PHP
// 20/50/100 at 2/5/10 pulses. See
// docs/architecture/tb74-pulse-protocol-analysis.md.
//
// The same captures showed why raw edge counting cannot be used: one accepted
// PHP 50 note carried 12,871 raw interrupt edges around its 5 real pulses, a
// 2574:1 noise ratio. Counting raw edges would have credited PHP 128,710.
// Six rejected notes produced 23,064 raw edges and must credit exactly zero.
//
// Every pulse therefore has to survive three independent checks: a level
// stability (glitch) filter, a LOW-width window, and a minimum period. The
// fastest credit pulse anywhere in this device family is an 80 ms period, so
// anything quicker is provably not payment.
// ---------------------------------------------------------------------------
static const uint16_t BILL_GLITCH_MS     = 20;   // level must hold to count
static const uint16_t BILL_MIN_LOW_MS    = 25;   // measured 50 ms
static const uint16_t BILL_MAX_LOW_MS    = 400;
static const uint16_t BILL_MIN_PERIOD_MS = 80;   // family minimum
static const uint16_t BILL_GAP_MS        = 500;  // > 350 ms slow-mode gap
static const uint16_t BILL_MAX_PULSES    = 120;  // PHP 1000 = 100; cap runaway

// Allan coin acceptor, MEASURED 2026-08-04 after calibration:
//   LOW 69-77 ms (mostly 70), period 162-171 ms (mostly 170).
//   PHP 1 -> 1 pulse (6 samples), PHP 5 -> 5 pulses (3 samples).
// Slower than the bill line, so the filter can be just as strict.
//
// Coin value is LINEAR: 1 pulse = PHP 1 at every denomination. A rapid burst
// of coins merges into one train (110 pulses observed in a single 19 s train),
// so the host must scale by pulse count rather than look up a denomination.
// These are the exact loose discovery filters from the sketch used for the
// successful all-coin test. They accept the measured ~70 ms LOW / ~170 ms
// period while preserving the tested D2 behavior.
static const uint16_t COIN_GLITCH_MS     = 3;
static const uint16_t COIN_MIN_LOW_MS    = 4;
static const uint16_t COIN_MAX_LOW_MS    = 400;
static const uint16_t COIN_MIN_PERIOD_MS = 12;
static const uint16_t COIN_GAP_MS        = 400;
static const uint16_t COIN_MAX_PULSES    = 200;  // PHP 200 ceiling per train
static const uint16_t EEPROM_EVENT_BASE = 16;
static const uint16_t EEPROM_JOB_BASE = EEPROM_EVENT_BASE + EEPROM_RING_SLOTS * 8;
static const uint8_t EEPROM_JOB_RECORD_SIZE = 44;
static const uint8_t EEPROM_JOB_MARKER = 0xA6;
static const uint8_t JOB_STARTED = 1;
static const uint8_t JOB_DONE = 2;
// Cash and motion have separate gates. D2/D3 pulse acceptance is now enabled
// from the completed bench trials; actuator calibration is still absent, so
// no command can energize a medicine motor.
static const bool CASH_INPUTS_CONFIRMED = true;
static const bool MEDICINE_MOTORS_ENABLED = false;

// Source index: 0 = coin, 1 = bill. Parallel arrays rather than a struct so
// the Arduino 1.x auto-prototype pass cannot break the build.
static const uint8_t SRC_COIN = 0;
static const uint8_t SRC_BILL = 1;
const uint8_t  srcPin[2]       = {PIN_COIN, PIN_BILL};
const uint16_t srcGlitchMs[2]  = {COIN_GLITCH_MS, BILL_GLITCH_MS};
const uint16_t srcMinLowMs[2]  = {COIN_MIN_LOW_MS, BILL_MIN_LOW_MS};
const uint16_t srcMaxLowMs[2]  = {COIN_MAX_LOW_MS, BILL_MAX_LOW_MS};
const uint16_t srcMinPerMs[2]  = {COIN_MIN_PERIOD_MS, BILL_MIN_PERIOD_MS};
const uint16_t srcGapMs[2]     = {COIN_GAP_MS, BILL_GAP_MS};
const uint16_t srcMaxPulses[2] = {COIN_MAX_PULSES, BILL_MAX_PULSES};

// Raw edge counters are evidence only. They are never credited.
volatile uint16_t rawEdges[2] = {0, 0};

uint8_t  rawLevel[2], stableLevel[2], lowOpen[2], trainActive[2], suspect[2];
uint8_t  drainAfterStop[2] = {0, 0};
uint32_t lastRawChangeMs[2], trainStartMs[2], lastActivityMs[2];
uint32_t lowStartMs[2], prevLowStartMs[2];
uint16_t cleanPulses[2], rawAtTrainStart[2];

bool acceptorsEnabled = false;
bool controllerHealthy = false;
uint32_t lastHeartbeatMs = 0;
uint32_t bootSequence = 0;
uint16_t eventSequence = 0;
uint8_t jobRingIndex = 0;
char activeSession[40] = "";
char rxFrame[FRAME_LIMIT + 1];
uint16_t rxLength = 0;

struct SlotProfile {
  uint16_t positionA;
  uint16_t positionB;
  uint16_t travelMs;
  uint16_t dwellMs;
  uint16_t settleMs;
  uint16_t cooldownMs;
  const char *version;
};

SlotProfile profiles[10] = {
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"},
  {1500,1900,500,250,300,500,"v1-unmeasured"}
};

uint16_t crc16Ccitt(const uint8_t *data, uint16_t length) {
  uint16_t crc = 0xFFFF;
  for (uint16_t i = 0; i < length; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

uint16_t crc16Append(uint16_t crc, const char *text) {
  while (*text) {
    crc ^= (uint16_t)(uint8_t)*text++ << 8;
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

void failSafe() {
  acceptorsEnabled = false;
  controllerHealthy = false;
  drainAfterStop[0] = drainAfterStop[1] = 0;
  activeSession[0] = '\0';
  digitalWrite(PIN_BILL_INHIBIT, LOW);
  digitalWrite(PIN_COIN_POWER, LOW);
  digitalWrite(PIN_PCA_OE, HIGH); // PCA9685 OE is active LOW: HIGH is disabled
}

void inhibitAcceptors() {
  acceptorsEnabled = false;
  digitalWrite(PIN_BILL_INHIBIT, LOW);
  digitalWrite(PIN_COIN_POWER, LOW);
  digitalWrite(PIN_PCA_OE, HIGH);
}

void enableAcceptors() {
  if (!controllerHealthy || !CASH_INPUTS_CONFIRMED) return;
  // Activity seen while the inputs were inhibited cannot belong to this
  // payment. Start both debouncers from the actual idle level so powered-off
  // D2 noise or an old D3 transition cannot contaminate the first tender.
  uint32_t now = millis();
  for (uint8_t s = 0; s < 2; s++) {
    resetTrain(s);
    rawLevel[s] = digitalRead(srcPin[s]);
    stableLevel[s] = rawLevel[s];
    lastRawChangeMs[s] = now;
    lastActivityMs[s] = now;
  }
  digitalWrite(PIN_BILL_INHIBIT, HIGH);
  digitalWrite(PIN_COIN_POWER, HIGH);
  acceptorsEnabled = true;
}

void sendFrame(const char *kind, const char *requestId, const char *command,
               const char *payload) {
  // Stream the body while computing its CRC. Building a second 241-byte body
  // beside a ~180-byte cash payload used most of the Uno's remaining stack.
  // This keeps peak SRAM bounded during the exact moment cash is reported.
  uint16_t bodyLength = 11 + strlen(kind) + strlen(requestId) +
                        strlen(command) + strlen(payload);
  if ((uint16_t)(bodyLength + 6) > FRAME_LIMIT) return;
  uint16_t crc = 0xFFFF;
  crc = crc16Append(crc, "MENDO/1|");
  crc = crc16Append(crc, kind);
  crc = crc16Append(crc, "|");
  crc = crc16Append(crc, requestId);
  crc = crc16Append(crc, "|");
  crc = crc16Append(crc, command);
  crc = crc16Append(crc, "|");
  crc = crc16Append(crc, payload);
  Serial.print(F("MENDO/1|"));
  Serial.print(kind); Serial.print('|');
  Serial.print(requestId); Serial.print('|');
  Serial.print(command); Serial.print('|');
  Serial.print(payload);
  Serial.print('|');
  if (crc < 0x1000) Serial.print('0');
  if (crc < 0x0100) Serial.print('0');
  if (crc < 0x0010) Serial.print('0');
  Serial.println(crc, HEX);
}

bool validateFrameCrc(char *line) {
  // The final pipe separates the CRC from the exact body that was sent.
  // Validate before strtok() mutates the receive buffer.
  char *crcSeparator = strrchr(line, '|');
  if (!crcSeparator || strlen(crcSeparator + 1) != 4) return false;
  char *end = NULL;
  unsigned long expected = strtoul(crcSeparator + 1, &end, 16);
  if (!end || *end != '\0' || expected > 0xFFFFUL) return false;
  *crcSeparator = '\0';
  uint16_t actual = crc16Ccitt((const uint8_t *)line, (uint16_t)strlen(line));
  *crcSeparator = '|';
  return actual == (uint16_t)expected;
}

void sendStatus(const char *requestId) {
  char payload[200];
  snprintf(payload, sizeof(payload),
           "mode=real;healthy=%u;connected=1;simulator=0;firmware_identity=mendo-controller-v1;protocol_version=1;acceptors_inhibited=%u;physical_evidence_required=%u;configuration_valid=%u;fault_code=%s",
           controllerHealthy ? 1 : 0, acceptorsEnabled ? 0 : 1,
           CASH_INPUTS_CONFIRMED ? 0 : 1,
           CASH_INPUTS_CONFIRMED ? 1 : 0,
           controllerHealthy ? "" : "FAIL_SAFE");
  sendFrame("RSP", requestId, "STATUS", payload);
}

void recordEventEvidence(uint8_t source, uint16_t pulses, uint8_t bad) {
  // Wear-levelled evidence marker. A later host ACK marks the slot clear.
  // Bytes 6-7 bind the record to this controller boot so an old note can
  // never be replayed into a new payment session after a reset.
  uint8_t slot = (uint8_t)(eventSequence % EEPROM_RING_SLOTS);
  int address = EEPROM_EVENT_BASE + (int)slot * 8;
  EEPROM.update(address, 0xA5);
  EEPROM.update(address + 1, (uint8_t)(source | (bad ? 0x80 : 0x00)));
  EEPROM.update(address + 2, (uint8_t)(pulses & 0xFF));
  EEPROM.update(address + 3, (uint8_t)(pulses >> 8));
  EEPROM.update(address + 4, (uint8_t)(eventSequence & 0xFF));
  EEPROM.update(address + 5, (uint8_t)(eventSequence >> 8));
  EEPROM.update(address + 6, (uint8_t)(bootSequence & 0xFF));
  EEPROM.update(address + 7, (uint8_t)((bootSequence >> 8) & 0xFF));
}

void acknowledgeEventEvidence(uint8_t source, uint16_t sequence) {
  for (uint8_t slot = 0; slot < EEPROM_RING_SLOTS; slot++) {
    int address = EEPROM_EVENT_BASE + (int)slot * 8;
    if (EEPROM.read(address) != 0xA5) continue;
    uint8_t storedSource = (uint8_t)(EEPROM.read(address + 1) & 0x01);
    uint16_t storedSequence = (uint16_t)EEPROM.read(address + 4) | ((uint16_t)EEPROM.read(address + 5) << 8);
    if (storedSource == source && storedSequence == sequence) {
      EEPROM.update(address, 0x00);
      return;
    }
  }
}

static const char CASH_DIAG_FMT[] PROGMEM =
  "coin_raw=%u;bill_raw=%u;coin_level=%u;bill_level=%u;coin_clean=%u;bill_clean=%u;coin_train=%u;bill_train=%u;coin_suspect=%u;bill_suspect=%u;event_sequence=%u;acceptors_enabled=%u";
static const char CASH_EVIDENCE_FMT[] PROGMEM =
  "slot=%u;present=1;source=%s;raw_pulses=%u;sequence_no=%u;boot_id=%u;quality=%s";
static const char CASH_POLL_FMT[] PROGMEM =
  "has_event=1;session=%s;source=%s;raw_pulses=%u;mapped_centavos=0;boot_id=%u;sequence_no=%u;requires_mapping=1;quality=%s";

void sendCashDiagnostics(const char *requestId) {
  uint16_t coinRaw, billRaw;
  noInterrupts();
  coinRaw = rawEdges[SRC_COIN];
  billRaw = rawEdges[SRC_BILL];
  interrupts();
  char payload[190];
  snprintf_P(payload, sizeof(payload), CASH_DIAG_FMT,
           coinRaw, billRaw,
           digitalRead(PIN_COIN) == HIGH ? 1 : 0,
           digitalRead(PIN_BILL) == HIGH ? 1 : 0,
           cleanPulses[SRC_COIN], cleanPulses[SRC_BILL],
           trainActive[SRC_COIN], trainActive[SRC_BILL],
           suspect[SRC_COIN], suspect[SRC_BILL],
           eventSequence, acceptorsEnabled ? 1 : 0);
  sendFrame("RSP", requestId, "CASH_DIAG", payload);
}

void sendCashEvidence(const char *requestId, uint8_t slot) {
  if (slot >= EEPROM_RING_SLOTS) {
    sendFrame("RSP", requestId, "CASH_EVIDENCE", "ok=0;fault_code=BAD_EVIDENCE_SLOT");
    return;
  }
  int address = EEPROM_EVENT_BASE + (int)slot * 8;
  if (EEPROM.read(address) != 0xA5) {
    char emptyPayload[32];
    snprintf(emptyPayload, sizeof(emptyPayload), "slot=%u;present=0", slot);
    sendFrame("RSP", requestId, "CASH_EVIDENCE", emptyPayload);
    return;
  }
  uint8_t sourceAndQuality = EEPROM.read(address + 1);
  uint8_t source = (uint8_t)(sourceAndQuality & 0x01);
  uint16_t pulses = (uint16_t)EEPROM.read(address + 2) |
                    ((uint16_t)EEPROM.read(address + 3) << 8);
  uint16_t sequence = (uint16_t)EEPROM.read(address + 4) |
                      ((uint16_t)EEPROM.read(address + 5) << 8);
  uint16_t storedBoot = (uint16_t)EEPROM.read(address + 6) |
                        ((uint16_t)EEPROM.read(address + 7) << 8);
  char payload[112];
  snprintf_P(payload, sizeof(payload), CASH_EVIDENCE_FMT,
           slot, source == SRC_BILL ? "bill" : "coin", pulses, sequence,
           storedBoot, (sourceAndQuality & 0x80) ? "suspect" : "ok");
  sendFrame("RSP", requestId, "CASH_EVIDENCE", payload);
}

void sendPendingCashEvent(const char *requestId) {
  uint16_t currentBoot = (uint16_t)bootSequence;
  if (!activeSession[0]) {
    sendFrame("RSP", requestId, "CASH_POLL", "has_event=0");
    return;
  }
  for (uint8_t slot = 0; slot < EEPROM_RING_SLOTS; slot++) {
    int address = EEPROM_EVENT_BASE + (int)slot * 8;
    if (EEPROM.read(address) != 0xA5) continue;
    uint16_t storedBoot = (uint16_t)EEPROM.read(address + 6) |
                          ((uint16_t)EEPROM.read(address + 7) << 8);
    if (storedBoot != currentBoot) continue;
    uint8_t sourceAndQuality = EEPROM.read(address + 1);
    uint8_t source = (uint8_t)(sourceAndQuality & 0x01);
    uint16_t pulses = (uint16_t)EEPROM.read(address + 2) |
                      ((uint16_t)EEPROM.read(address + 3) << 8);
    uint16_t sequence = (uint16_t)EEPROM.read(address + 4) |
                        ((uint16_t)EEPROM.read(address + 5) << 8);
    char payload[180];
    snprintf_P(payload, sizeof(payload), CASH_POLL_FMT,
               activeSession, source == SRC_BILL ? "bill" : "coin", pulses,
               storedBoot, sequence,
               (sourceAndQuality & 0x80) ? "suspect" : "ok");
    sendFrame("RSP", requestId, "CASH_POLL", payload);
    return;
  }
  sendFrame("RSP", requestId, "CASH_POLL", "has_event=0");
}

bool findJobRecord(const char *jobId, uint8_t &state, uint8_t &slot) {
  char stored[40];
  for (uint8_t index = 0; index < JOB_RING_SLOTS; index++) {
    int address = EEPROM_JOB_BASE + (int)index * EEPROM_JOB_RECORD_SIZE;
    if (EEPROM.read(address) != EEPROM_JOB_MARKER) continue;
    for (uint8_t i = 0; i < sizeof(stored) - 1; i++) {
      stored[i] = (char)EEPROM.read(address + 4 + i);
    }
    stored[sizeof(stored) - 1] = '\0';
    if (!strcmp(stored, jobId)) {
      state = EEPROM.read(address + 1);
      slot = EEPROM.read(address + 2);
      return true;
    }
  }
  return false;
}

void recordJob(const char *jobId, uint8_t state, uint8_t slot) {
  int address = -1;
  bool reused = false;
  uint8_t existingState = 0;
  uint8_t existingSlot = 0;
  if (findJobRecord(jobId, existingState, existingSlot)) {
    char stored[40];
    for (uint8_t index = 0; index < JOB_RING_SLOTS; index++) {
      int candidate = EEPROM_JOB_BASE + (int)index * EEPROM_JOB_RECORD_SIZE;
      if (EEPROM.read(candidate) != EEPROM_JOB_MARKER) continue;
      for (uint8_t i = 0; i < sizeof(stored) - 1; i++) stored[i] = (char)EEPROM.read(candidate + 4 + i);
      stored[sizeof(stored) - 1] = '\0';
      if (!strcmp(stored, jobId)) { address = candidate; reused = true; break; }
    }
  }
  if (address < 0) address = EEPROM_JOB_BASE + (int)jobRingIndex * EEPROM_JOB_RECORD_SIZE;
  // Clear the marker first so a reset during the write cannot create a
  // falsely completed job record.
  EEPROM.update(address, 0x00);
  EEPROM.update(address + 1, state);
  EEPROM.update(address + 2, slot);
  EEPROM.update(address + 3, 0x00);
  for (uint8_t i = 0; i < 39; i++) {
    char value = jobId[i];
    EEPROM.update(address + 4 + i, value);
    if (value == '\0') {
      for (uint8_t rest = i + 1; rest < 40; rest++) EEPROM.update(address + 4 + rest, 0x00);
      break;
    }
  }
  EEPROM.update(address, EEPROM_JOB_MARKER);
  if (!reused) {
    jobRingIndex = (uint8_t)((jobRingIndex + 1) % JOB_RING_SLOTS);
    EEPROM.update(2, jobRingIndex);
  }
}

// `pulses` is the VALIDATED count -- the host maps that to money. `bad` marks
// a train that contained physically impossible timing; the host must route
// those to manual review rather than credit them.
//
// Frame budget: sendFrame silently discards anything over FRAME_LIMIT, which
// for a cash event would mean money taken but never reported. The prefix
// "MENDO/1|EVT|EVENT|CASH_EVENT|" is 29 bytes, so the payload must stay under
// 211. Worst case below is 194 with a full 39-char session. Re-check this
// arithmetic before adding any field.
static const uint8_t CASH_PAYLOAD_MAX = 180;

// Format strings live in flash. On AVR a plain string literal is copied into
// SRAM at startup, and these two are ~300 bytes between them on a part with
// 2 KB total.
static const char CASH_FMT[] PROGMEM =
  "session=%s;source=%s;raw_pulses=%u;mapped_centavos=0;boot_id=%lu;sequence_no=%u;pulse_started_ms=%lu;requires_mapping=1;quality=%s";
static const char CASH_FMT_SHORT[] PROGMEM =
  "session=%s;source=%s;raw_pulses=%u;mapped_centavos=0;boot_id=%lu;sequence_no=%u;requires_mapping=1;quality=%s;truncated=1";

void emitCashEvent(uint8_t source, uint16_t pulses, uint32_t startedMs,
                   uint8_t bad) {
  if ((!acceptorsEnabled && !drainAfterStop[source]) || !controllerHealthy) return;
  eventSequence++;
  recordEventEvidence(source, pulses, bad);
  const char *src = (source == SRC_COIN) ? "coin" : "bill";
  const char *qual = bad ? "suspect" : "ok";
  char payload[CASH_PAYLOAD_MAX + 1];
  int n = snprintf_P(payload, sizeof(payload), CASH_FMT,
           activeSession, src, pulses, (unsigned long)bootSequence,
           eventSequence, (unsigned long)startedMs, qual);
  if (n <= 0 || n > (int)CASH_PAYLOAD_MAX) {
    // Defensive: never lose a cash event to a framing problem. Drop the
    // timestamp, which is diagnostic, and keep everything the host needs to
    // reconcile the payment.
    snprintf_P(payload, sizeof(payload), CASH_FMT_SHORT,
             activeSession, src, pulses, (unsigned long)bootSequence,
             eventSequence, qual);
  }
  sendFrame("EVT", "EVENT", "CASH_EVENT", payload);
}

// ISRs record raw electrical activity only. Nothing here can create credit.
void coinEdge() { rawEdges[SRC_COIN]++; }
void billEdge() { rawEdges[SRC_BILL]++; }

void resetTrain(uint8_t s) {
  trainActive[s] = 0;
  cleanPulses[s] = 0;
  prevLowStartMs[s] = 0;
  lowOpen[s] = 0;
  suspect[s] = 0;
}

// Called on a debounced (glitch-filtered) level transition.
void onStableEdge(uint8_t s, uint8_t level, uint32_t at) {
  if (level == LOW) {
    lowStartMs[s] = at;
    lowOpen[s] = 1;
    return;
  }
  if (!lowOpen[s]) return;
  lowOpen[s] = 0;

  uint32_t width = at - lowStartMs[s];
  if (width < srcMinLowMs[s] || width > srcMaxLowMs[s]) {
    // A LOW outside the credit-pulse window is noise, not a pulse. Flag the
    // train: a genuine acceptor never emits one.
    suspect[s] = 1;
    return;
  }

  if (prevLowStartMs[s]) {
    uint32_t period = lowStartMs[s] - prevLowStartMs[s];
    if (period < srcMinPerMs[s]) {
      // Physically impossible for this device family. Quarantine the train.
      suspect[s] = 1;
      return;
    }
  }
  prevLowStartMs[s] = lowStartMs[s];

  if (cleanPulses[s] >= srcMaxPulses[s]) {
    suspect[s] = 1;   // runaway: never wrap or over-credit
    return;
  }
  cleanPulses[s]++;
}

void pollCashSource(uint8_t s, uint32_t now) {
  uint8_t raw = digitalRead(srcPin[s]);

  if (raw != rawLevel[s]) {
    rawLevel[s] = raw;
    lastRawChangeMs[s] = now;
    if (!trainActive[s]) {
      resetTrain(s);
      trainActive[s] = 1;
      trainStartMs[s] = now;
      noInterrupts();
      rawAtTrainStart[s] = rawEdges[s];
      interrupts();
    }
    lastActivityMs[s] = now;
  } else if (stableLevel[s] != raw &&
             (uint32_t)(now - lastRawChangeMs[s]) >= srcGlitchMs[s]) {
    stableLevel[s] = raw;
    onStableEdge(s, raw, lastRawChangeMs[s]);
    lastActivityMs[s] = now;
  }

  if (trainActive[s] && (uint32_t)(now - lastActivityMs[s]) >= srcGapMs[s]) {
    uint16_t pulses = cleanPulses[s];
    uint8_t bad = suspect[s];
    uint32_t startedMs = trainStartMs[s];
    resetTrain(s);
    // A train with zero validated pulses is noise (a rejected note, or motor
    // interference). It must never reach the host as a cash event. On the
    // 2026-08-03 bench six rejected notes produced 23,064 raw edges between
    // them; all six must credit exactly zero.
    if (pulses) emitCashEvent(s, pulses, startedMs, bad);
    if (drainAfterStop[s]) {
      drainAfterStop[s] = 0;
      if (!drainAfterStop[0] && !drainAfterStop[1]) activeSession[0] = '\0';
    }
  }
}

void finalizePulseTrains() {
  uint32_t now = millis();
  pollCashSource(SRC_COIN, now);
  pollCashSource(SRC_BILL, now);
}

void pcaWrite(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

void pcaSetPulse(uint8_t channel, uint16_t microseconds) {
  // 50 Hz: 20,000 us frame, 4096 PCA counts.
  uint16_t ticks = (uint32_t)microseconds * 4096UL / 20000UL;
  uint8_t base = (uint8_t)(0x06 + 4 * channel);
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(base);
  Wire.write(0);
  Wire.write(0);
  Wire.write((uint8_t)(ticks & 0xFF));
  Wire.write((uint8_t)(ticks >> 8));
  Wire.endTransmission();
}

void pcaDisable(uint8_t channel) {
  uint8_t base = (uint8_t)(0x06 + 4 * channel);
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(base);
  Wire.write(0);
  Wire.write(0);
  Wire.write(0);
  Wire.write(0x10); // full-off bit; no idle PWM on inactive channels
  Wire.endTransmission();
}

bool dispenseOne(uint8_t slot, const char *jobId, const char *requestId) {
  if (!MEDICINE_MOTORS_ENABLED || !controllerHealthy || slot < 1 || slot > 10 || digitalRead(PIN_INTERLOCK) == LOW) return false;
  uint8_t knownState = 0;
  uint8_t knownSlot = 0;
  if (findJobRecord(jobId, knownState, knownSlot)) {
    if (knownState == JOB_DONE) {
      char done[96];
      snprintf(done, sizeof(done), "job_id=%s;slot=%u;result=done_unverified;duplicate=1", jobId, knownSlot);
      sendFrame("EVT", requestId, "DISPENSE_DONE_UNVERIFIED", done);
      return true;
    }
    // A reset during a started movement leaves the physical result unknown;
    // never repeat it automatically.
    return false;
  }
  SlotProfile &profile = profiles[slot - 1];
  if (profile.positionA < 500 || profile.positionA > 2500 ||
      profile.positionB < 500 || profile.positionB > 2500) return false;
  digitalWrite(PIN_PCA_OE, LOW);
  recordJob(jobId, JOB_STARTED, slot);
  char started[96];
  snprintf(started, sizeof(started), "job_id=%s;slot=%u;profile=%s", jobId, slot, profile.version);
  sendFrame("EVT", requestId, "DISPENSE_STARTED", started);
  pcaSetPulse(slot - 1, profile.positionA);
  delay(profile.travelMs);
  pcaSetPulse(slot - 1, profile.positionB);
  delay(profile.dwellMs);
  pcaSetPulse(slot - 1, profile.positionA);
  delay(profile.settleMs);
  pcaDisable(slot - 1);
  digitalWrite(PIN_PCA_OE, HIGH);
  delay(profile.cooldownMs);
  recordJob(jobId, JOB_DONE, slot);
  char done[96];
  snprintf(done, sizeof(done), "job_id=%s;slot=%u;profile=%s;result=done_unverified", jobId, slot, profile.version);
  sendFrame("EVT", requestId, "DISPENSE_DONE_UNVERIFIED", done);
  return true;
}

void handleCommand(char *line) {
  // The complete host parser is fixed-buffer and validates CRC before this
  // function. This compact bench handler extracts only required fields.
  char *kind = strtok(line, "|");
  char *frameKind = strtok(NULL, "|");
  char *requestId = strtok(NULL, "|");
  char *command = strtok(NULL, "|");
  char *payload = strtok(NULL, "|");
  char *crcText = strtok(NULL, "|");
  (void)kind; (void)frameKind; (void)crcText;
  if (!requestId || !command || !payload) return;
  if (!strcmp(command, "HELLO") || !strcmp(command, "STATUS")) {
    sendStatus(requestId);
  } else if (!strcmp(command, "HEARTBEAT")) {
    lastHeartbeatMs = millis();
    controllerHealthy = true;
    sendStatus(requestId);
    if (strstr(payload, "enable=1")) enableAcceptors();
  } else if (!strcmp(command, "PAY_START")) {
    if (!controllerHealthy || !CASH_INPUTS_CONFIRMED) {
      failSafe();
      sendFrame("RSP", requestId, "ACK", "ok=0;fault_code=PHYSICAL_EVIDENCE_REQUIRED");
    } else {
      char requestedSession[40] = "";
      char *session = strstr(payload, "session=");
      if (session) {
        session += 8;
        uint8_t i = 0;
        while (*session && *session != ';' && i < sizeof(requestedSession) - 1) requestedSession[i++] = *session++;
        requestedSession[i] = '\0';
      }
      if (!requestedSession[0]) {
        sendFrame("RSP", requestId, "ACK", "ok=0;fault_code=BAD_SESSION");
        return;
      }
      if (activeSession[0] && strcmp(activeSession, requestedSession)) {
        sendFrame("RSP", requestId, "ACK", "ok=0;fault_code=CASH_SESSION_BUSY");
        return;
      }
      strncpy(activeSession, requestedSession, sizeof(activeSession) - 1);
      activeSession[sizeof(activeSession) - 1] = '\0';
      drainAfterStop[0] = drainAfterStop[1] = 0;
      enableAcceptors();
      sendFrame("RSP", requestId, "ACK", "ok=1;command=PAY_START");
    }
  } else if (!strcmp(command, "PAY_STOP")) {
    // Inhibit new money immediately, but let a train that had already started
    // finish and be reported against the old session. A coin physically past
    // the gate cannot be recalled, and silently discarding it breaks drawer
    // reconciliation.
    drainAfterStop[0] = trainActive[0];
    drainAfterStop[1] = trainActive[1];
    inhibitAcceptors();
    if (!drainAfterStop[0] && !drainAfterStop[1]) activeSession[0] = '\0';
    sendFrame("RSP", requestId, "ACK", "ok=1;command=PAY_STOP");
  } else if (!strcmp(command, "DISPENSE_ONE")) {
    char *job = strstr(payload, "job_id=");
    char *slotText = strstr(payload, "slot=");
    if (!job || !slotText) { sendFrame("RSP", requestId, "ACK", "ok=0;fault_code=BAD_DISPENSE"); return; }
    job += 7;
    slotText += 5;
    char jobId[42];
    uint8_t i = 0;
    while (*job && *job != ';' && i < sizeof(jobId)-1) jobId[i++] = *job++;
    jobId[i] = '\0';
    uint8_t slot = (uint8_t)atoi(slotText);
    bool ok = dispenseOne(slot, jobId, requestId);
    sendFrame("RSP", requestId, "ACK", ok ? "ok=1;command=DISPENSE_ONE" : "ok=0;fault_code=DISPENSE_FAILED");
  } else if (!strcmp(command, "JOB_STATUS")) {
    char *job = strstr(payload, "job_id=");
    if (!job) { sendFrame("RSP", requestId, "JOB_STATUS", "known=0"); return; }
    job += 7;
    char jobId[40];
    uint8_t i = 0;
    while (*job && *job != ';' && i < sizeof(jobId)-1) jobId[i++] = *job++;
    jobId[i] = '\0';
    uint8_t state = 0;
    uint8_t slot = 0;
    if (findJobRecord(jobId, state, slot)) {
      char result[96];
      snprintf(result, sizeof(result), "known=1;job_id=%s;state=%u;slot=%u", jobId, state, slot);
      sendFrame("RSP", requestId, "JOB_STATUS", result);
    } else {
      sendFrame("RSP", requestId, "JOB_STATUS", "known=0");
    }
  } else if (!strcmp(command, "CASH_DIAG")) {
    sendCashDiagnostics(requestId);
  } else if (!strcmp(command, "CASH_EVIDENCE")) {
    char *slotText = strstr(payload, "slot=");
    if (!slotText) {
      sendFrame("RSP", requestId, "CASH_EVIDENCE", "ok=0;fault_code=BAD_EVIDENCE_SLOT");
      return;
    }
    sendCashEvidence(requestId, (uint8_t)atoi(slotText + 5));
  } else if (!strcmp(command, "CASH_POLL")) {
    sendPendingCashEvent(requestId);
  } else if (!strcmp(command, "CASH_ACK")) {
    char *sourceText = strstr(payload, "source=");
    char *sequenceText = strstr(payload, "sequence_no=");
    if (!sourceText || !sequenceText) {
      sendFrame("RSP", requestId, "ACK", "ok=0;fault_code=BAD_CASH_ACK");
      return;
    }
    sourceText += 7;
    sequenceText += 12;
    uint8_t source = (*sourceText == 'b') ? 1 : 0;
    acknowledgeEventEvidence(source, (uint16_t)atoi(sequenceText));
    sendFrame("RSP", requestId, "ACK", "ok=1;command=CASH_ACK");
  }
}

void readSerialFrames() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      rxFrame[rxLength] = '\0';
      if (rxLength > 0 && rxLength <= FRAME_LIMIT && validateFrameCrc(rxFrame)) {
        handleCommand(rxFrame);
      } else if (rxLength > 0) {
        // A malformed or tampered frame must not leave the acceptors enabled.
        failSafe();
      }
      rxLength = 0;
    } else if (rxLength < FRAME_LIMIT) {
      rxFrame[rxLength++] = c;
    } else {
      rxLength = 0;
      failSafe();
    }
  }
}

void setup() {
  // Cash inputs were previously left at their default (floating INPUT). A
  // floating interrupt pin is not inert: on the 2026-08-03 bench an
  // unconnected D2 capacitively coupled the real D3 credit train and produced
  // a phantom PHP 50 with identical 150 ms timing that passed every validity
  // check. Timing validation cannot catch that; only never floating can.
  // INPUT_PULLUP also fails safe if the external 4.7k pull-up is missing or
  // a harness conductor comes loose. With the 4.7k fitted the pair simply
  // parallel to ~4.2k, which is harmless.
  pinMode(PIN_COIN, INPUT_PULLUP);
  // The connected TB74 has the measured, vendor-specified external 4.7 kΩ
  // pull-up. Match the successful diagnostic image exactly on D3 rather than
  // adding the AVR's weak internal pull-up in parallel.
  pinMode(PIN_BILL, INPUT);

  pinMode(PIN_BILL_INHIBIT, OUTPUT);
  pinMode(PIN_COIN_POWER, OUTPUT);
  pinMode(PIN_PCA_OE, OUTPUT);
  pinMode(PIN_CHUTE_RESERVED, INPUT_PULLUP);
  pinMode(PIN_INTERLOCK, INPUT_PULLUP);
  // Keep every motor output disabled throughout the payment-only test.
  digitalWrite(PIN_PCA_OE, HIGH);
  digitalWrite(PIN_BILL_INHIBIT, LOW);
  digitalWrite(PIN_COIN_POWER, LOW);
  Wire.begin();
  Serial.begin(115200);
  for (uint8_t s = 0; s < 2; s++) {
    rawLevel[s] = digitalRead(srcPin[s]);
    stableLevel[s] = rawLevel[s];
    lastRawChangeMs[s] = millis();
    lastActivityMs[s] = millis();
    rawAtTrainStart[s] = 0;
    resetTrain(s);
  }
  // CHANGE, not FALLING: the raw counter is an evidence channel and must see
  // the whole noise picture. Credit comes from the polled, validated path.
  attachInterrupt(digitalPinToInterrupt(PIN_COIN), coinEdge, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_BILL), billEdge, CHANGE);
  bootSequence = (uint32_t)EEPROM.read(0) | ((uint32_t)EEPROM.read(1) << 8);
  bootSequence++;
  EEPROM.update(0, (uint8_t)(bootSequence & 0xFF));
  EEPROM.update(1, (uint8_t)(bootSequence >> 8));
  jobRingIndex = EEPROM.read(2);
  if (jobRingIndex >= JOB_RING_SLOTS) jobRingIndex = 0;
  failSafe();
  lastHeartbeatMs = millis();
}

void loop() {
  readSerialFrames();
  finalizePulseTrains();
  if (millis() - lastHeartbeatMs > HEARTBEAT_TIMEOUT_MS) failSafe();
  if (digitalRead(PIN_INTERLOCK) == LOW) failSafe();
}
