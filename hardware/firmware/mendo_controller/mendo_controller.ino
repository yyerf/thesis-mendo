/*
 * MendoVendo controller firmware.
 *
 * One source tree targets Arduino Uno and Mega. D0/D1 remain USB serial;
 * board selection changes only compile-time capacity. The host protocol is a
 * bounded ASCII frame with CRC16-CCITT. No Arduino String or JSON is used.
 *
 * Payment + receipt build: the measured D2/D3 pulse paths can credit a POS
 * cash session and the KMP26 thermal printer on D9/D10 prints receipts.
 * Medicine motors remain disabled: this build does not link the PCA9685/I2C
 * code at all (it is in git history for the motion phase), holds PCA OE HIGH,
 * and rejects every DISPENSE_ONE command.
 *
 * Rebuilt 2026-09-28 from the recovered protocol of the working printer image
 * (hardware/firmware/backup/uno_working_2026-09-28.hex), whose source was lost.
 * Protocol-compatible with that image except that print fingerprints compare all
 * 64 bits (the lost build compared only the first 32).
 */

#include <Arduino.h>
#include <EEPROM.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
static const uint8_t PIN_INTERLOCK = 8;      // empty on the 2026-09 kiosk; pull-up keeps it HIGH
// KMP26 58 mm printer, 9600 8N1 TTL. D9 drives the printer's RX. The
// printer's TX returns on D10; it idles LOW while the printer is powered and
// connected, so a HIGH (pull-up) level means absent or busy. Both leads go
// through a series resistor. The printer's DTR is not connected.
static const uint8_t PIN_PRINTER_TX = 9;
static const uint8_t PIN_PRINTER_LINE = 10;
static const uint16_t FRAME_LIMIT = 240;        // receive buffer
static const uint16_t FRAME_TX_LIMIT = 250;     // host reads 256 incl. CRC and CRLF
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
static const uint8_t EEPROM_JOB_RECORD_SIZE = 44;  // area reserved for the motion build
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
char activeSession[40] = "";
char rxFrame[FRAME_LIMIT + 1];
uint16_t rxLength = 0;

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
  if ((uint16_t)(bodyLength + 5) > FRAME_TX_LIMIT) return;
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

static const char STATUS_FMT[] PROGMEM =
  "healthy=%u;firmware_identity=mendo-controller-v1;protocol_version=1;acceptors_inhibited=%u;coin_power_enabled=%u;pca_outputs_enabled=0;physical_evidence_required=%u;configuration_valid=%u;fault_code=%s";

void sendStatus(const char *requestId) {
  // 203 characters with FAIL_SAFE. The lost build used a 200-byte buffer and
  // cut the fault code to "FAIL_".
  char payload[212];
  snprintf_P(payload, sizeof(payload), STATUS_FMT,
             controllerHealthy ? 1 : 0, acceptorsEnabled ? 0 : 1,
             acceptorsEnabled ? 1 : 0,
             CASH_INPUTS_CONFIRMED ? 0 : 1,
             CASH_INPUTS_CONFIRMED ? 1 : 0,
             controllerHealthy ? "" : "FAIL_SAFE");
  sendFrame("RSP", requestId, "STATUS", payload);
}

void sendFault(const char *requestId, const char *command, PGM_P faultCode) {
  char payload[48];
  snprintf_P(payload, sizeof(payload), PSTR("ok=0;fault_code=%S"), faultCode);
  sendFrame("RSP", requestId, command, payload);
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

// Per-train evidence (bench diagnostics only; never used for credit).
uint8_t trainLows[2];
uint16_t trainMinLow[2], trainMaxLow[2], trainMinPer[2], trainMaxPer[2];

void resetTrain(uint8_t s) {
  trainActive[s] = 0;
  cleanPulses[s] = 0;
  prevLowStartMs[s] = 0;
  lowOpen[s] = 0;
  suspect[s] = 0;
  trainLows[s] = 0;
  trainMinLow[s] = trainMinPer[s] = 0xFFFF;
  trainMaxLow[s] = trainMaxPer[s] = 0;
}

// Ring of the last TRAIN_LOG_SIZE finished trains that had at least one
// settled LOW, recorded whether or not a payment was active.
static const uint8_t TRAIN_LOG_SIZE = 8;
struct TrainRecord {
  uint8_t source;
  uint8_t pulses;
  uint8_t lows;
  uint8_t suspect;
  uint16_t minLow, maxLow, minPer, maxPer, durationMs;
};
TrainRecord trainLog[TRAIN_LOG_SIZE];
uint8_t trainLogHead = 0;
uint8_t trainLogCount = 0;

void recordTrain(uint8_t s, uint16_t pulses, uint8_t bad, uint32_t startedMs, uint32_t now) {
  if (!trainLows[s]) return;          // pure noise: nothing settled
  TrainRecord &r = trainLog[trainLogHead];
  r.source = s;
  r.pulses = pulses > 255 ? 255 : (uint8_t)pulses;
  r.lows = trainLows[s];
  r.suspect = bad;
  r.minLow = trainMinLow[s]; r.maxLow = trainMaxLow[s];
  r.minPer = trainMinPer[s]; r.maxPer = trainMaxPer[s];
  uint32_t duration = now - startedMs;
  r.durationMs = duration > 0xFFFF ? 0xFFFF : (uint16_t)duration;
  trainLogHead = (uint8_t)((trainLogHead + 1) % TRAIN_LOG_SIZE);
  if (trainLogCount < TRAIN_LOG_SIZE) trainLogCount++;
}

void sendTrainLog(const char *requestId, uint8_t index) {
  // One finished train per frame, index 0 = oldest retained.
  if (index >= trainLogCount) {
    char empty[24];
    snprintf_P(empty, sizeof(empty), PSTR("count=%u;present=0"), trainLogCount);
    sendFrame("RSP", requestId, "CASH_TRAIN", empty);
    return;
  }
  TrainRecord &r = trainLog[(trainLogHead + TRAIN_LOG_SIZE - trainLogCount + index) % TRAIN_LOG_SIZE];
  char payload[160];
  snprintf_P(payload, sizeof(payload),
             PSTR("count=%u;present=1;source=%s;pulses=%u;lows=%u;suspect=%u;low_min=%u;low_max=%u;period_min=%u;period_max=%u;duration_ms=%u"),
             trainLogCount, r.source == SRC_BILL ? "bill" : "coin", r.pulses, r.lows, r.suspect,
             r.minLow == 0xFFFF ? 0 : r.minLow, r.maxLow,
             r.minPer == 0xFFFF ? 0 : r.minPer, r.maxPer, r.durationMs);
  sendFrame("RSP", requestId, "CASH_TRAIN", payload);
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
  if (trainLows[s] < 255) trainLows[s]++;
  if (width < trainMinLow[s]) trainMinLow[s] = (uint16_t)min(width, (uint32_t)0xFFFE);
  if (width > trainMaxLow[s]) trainMaxLow[s] = (uint16_t)min(width, (uint32_t)0xFFFE);
  if (prevLowStartMs[s]) {
    uint32_t seen = lowStartMs[s] - prevLowStartMs[s];
    if (seen < trainMinPer[s]) trainMinPer[s] = (uint16_t)min(seen, (uint32_t)0xFFFE);
    if (seen > trainMaxPer[s]) trainMaxPer[s] = (uint16_t)min(seen, (uint32_t)0xFFFE);
  }
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
      lastActivityMs[s] = now;
      noInterrupts();
      rawAtTrainStart[s] = rawEdges[s];
      interrupts();
    }
    // Raw glitches no longer extend the train. Both lines carried thousands
    // of sub-millisecond spikes per second on the 2026-09-28 bench, which
    // could hold a train open indefinitely so its cash event never fired.
    // Only settled transitions below count as activity.
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
    recordTrain(s, pulses, bad, startedMs, lastActivityMs[s]);
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

// ---------------------------------------------------------------------------
// Receipt printer.
//
// The host renders ESC/POS and streams it here in hex chunks; the firmware
// only moves bytes and keeps one durable job record so a lost reply or a
// reset can never print a receipt twice. Job states: 0 idle, 1 receiving,
// 2 printed, 3 interrupted (reset or stalled printer mid-job: part of the
// receipt may be on paper, so only staff may clear it).
// ---------------------------------------------------------------------------
static const uint32_t PRINTER_BAUD = 9600UL;
static const uint16_t PRINTER_BIT_US = (uint16_t)(1000000UL / PRINTER_BAUD);
static const uint16_t PRINT_MAX_LENGTH = 4096;
static const uint8_t PRINT_CHUNK_MAX = 96;
static const uint16_t PRINTER_WAIT_MS = 3000;   // busy this long within one chunk = stalled
static const uint8_t PRINT_IDLE = 0;
static const uint8_t PRINT_RECEIVING = 1;
static const uint8_t PRINT_DONE = 2;
static const uint8_t PRINT_INTERRUPTED = 3;
// 16-byte record after the (unused) motion-job ring:
// marker, state, fingerprint[8], length(2), received(2), checksum, layout.
static const uint16_t EEPROM_PRINT_BASE =
  EEPROM_JOB_BASE + JOB_RING_SLOTS * EEPROM_JOB_RECORD_SIZE + 16;
static const uint8_t EEPROM_PRINT_MARKER = 0xB7;
static const uint8_t EEPROM_PRINT_LAYOUT = 0x01;

volatile uint8_t *printerTxPort;
uint8_t printerTxMask;
uint8_t printFingerprint[8];
uint8_t printState = PRINT_IDLE;
uint16_t printLength = 0;
uint16_t printReceived = 0;
// How often and how long the printer held its busy line during this job
// (RAM only). Evidence for flow-control tuning, not part of the job record.
uint16_t printBusyWaits = 0;
uint16_t printBusyMs = 0;
uint16_t printBusyMaxMs = 0;

static const char PRINT_STATUS_FMT[] PROGMEM =
  "known=%u;ready=%u;dtr_level=%u;state=%u;received=%u;length=%u;busy_waits=%u;busy_ms=%u;busy_max_ms=%u;acceptors_inhibited=%u;coin_power_enabled=%u;job=%s;job_state=%u";

uint8_t printRecordChecksum() {
  uint8_t sum = printState ^ (uint8_t)printLength ^ (uint8_t)(printLength >> 8) ^
                (uint8_t)printReceived ^ (uint8_t)(printReceived >> 8);
  for (uint8_t i = 0; i < 8; i++) sum ^= printFingerprint[i];
  return (uint8_t)(sum ^ 0x5A);
}

void savePrintRecord() {
  int a = EEPROM_PRINT_BASE;
  EEPROM.update(a, EEPROM_PRINT_MARKER);
  EEPROM.update(a + 1, printState);
  for (uint8_t i = 0; i < 8; i++) EEPROM.update(a + 2 + i, printFingerprint[i]);
  EEPROM.update(a + 10, (uint8_t)printLength);
  EEPROM.update(a + 11, (uint8_t)(printLength >> 8));
  EEPROM.update(a + 12, (uint8_t)printReceived);
  EEPROM.update(a + 13, (uint8_t)(printReceived >> 8));
  EEPROM.update(a + 14, printRecordChecksum());
  EEPROM.update(a + 15, EEPROM_PRINT_LAYOUT);
}

void clearPrintRecord() {
  printState = PRINT_IDLE;
  printLength = printReceived = 0;
  memset(printFingerprint, 0, sizeof(printFingerprint));
  savePrintRecord();
}

void loadPrintRecord() {
  int a = EEPROM_PRINT_BASE;
  // Bytes left by an earlier firmware are far likelier than a torn write, so
  // only a record with the marker, this layout version, and a valid checksum
  // is trusted.
  if (EEPROM.read(a) != EEPROM_PRINT_MARKER || EEPROM.read(a + 15) != EEPROM_PRINT_LAYOUT) {
    clearPrintRecord();
    return;
  }
  printState = EEPROM.read(a + 1);
  for (uint8_t i = 0; i < 8; i++) printFingerprint[i] = EEPROM.read(a + 2 + i);
  printLength = (uint16_t)EEPROM.read(a + 10) | ((uint16_t)EEPROM.read(a + 11) << 8);
  printReceived = (uint16_t)EEPROM.read(a + 12) | ((uint16_t)EEPROM.read(a + 13) << 8);
  if (EEPROM.read(a + 14) != printRecordChecksum() || printState > PRINT_INTERRUPTED) {
    clearPrintRecord();
    return;
  }
  // A job that was still receiving cannot know how much reached the paper.
  // Never resume it automatically.
  if (printState == PRINT_RECEIVING) {
    printState = PRINT_INTERRUPTED;
    savePrintRecord();
  }
}

bool printerLineIdle() { return digitalRead(PIN_PRINTER_LINE) == LOW; }

bool printerReady() {
  return controllerHealthy && !acceptorsEnabled && !drainAfterStop[0] &&
         !drainAfterStop[1] && printerLineIdle();
}

// Bit-banged 8N1, transmit only (no SoftwareSerial, so no pin-change ISRs
// compete with the D2/D3 cash interrupts). Interrupts are held off for one
// byte (~1 ms); the host is waiting for this reply, so no USB bytes arrive.
void printerWriteByte(uint8_t value) {
  uint8_t oldSreg = SREG;
  cli();
  *printerTxPort &= (uint8_t)~printerTxMask;             // start bit
  delayMicroseconds(PRINTER_BIT_US);
  for (uint8_t bit = 0; bit < 8; bit++) {
    if (value & 0x01) *printerTxPort |= printerTxMask;
    else *printerTxPort &= (uint8_t)~printerTxMask;
    value >>= 1;
    delayMicroseconds(PRINTER_BIT_US);
  }
  *printerTxPort |= printerTxMask;                         // stop bit
  delayMicroseconds(PRINTER_BIT_US);
  SREG = oldSreg;
}

// Copies `key`'s value (key must start the payload or follow ';').
bool payloadField(const char *payload, const char *key, char *out, uint8_t size) {
  uint8_t keyLength = (uint8_t)strlen(key);
  const char *p = payload;
  while (p && *p) {
    if (!strncmp(p, key, keyLength) && p[keyLength] == '=') {
      p += keyLength + 1;
      uint8_t i = 0;
      while (*p && *p != ';') {
        if (i >= size - 1) return false;
        out[i++] = *p++;
      }
      out[i] = '\0';
      return true;
    }
    p = strchr(p, ';');
    if (p) p++;
  }
  return false;
}

int8_t hexNibble(char c) {
  if (c >= '0' && c <= '9') return (int8_t)(c - '0');
  if (c >= 'a' && c <= 'f') return (int8_t)(c - 'a' + 10);
  if (c >= 'A' && c <= 'F') return (int8_t)(c - 'A' + 10);
  return -1;
}

bool parseFingerprint(const char *payload, uint8_t *out) {
  char text[20];
  if (!payloadField(payload, "fingerprint", text, sizeof(text)) || strlen(text) != 16) return false;
  uint8_t any = 0;
  for (uint8_t i = 0; i < 8; i++) {
    int8_t high = hexNibble(text[2 * i]);
    int8_t low = hexNibble(text[2 * i + 1]);
    if (high < 0 || low < 0) return false;
    out[i] = (uint8_t)((high << 4) | low);
    any |= out[i];
  }
  return any != 0;
}

bool parseUnsigned(const char *payload, const char *key, uint16_t &value) {
  char text[8];
  if (!payloadField(payload, key, text, sizeof(text)) || !text[0]) return false;
  char *end = NULL;
  unsigned long parsed = strtoul(text, &end, 10);
  if (!end || *end || parsed > 65535UL) return false;
  value = (uint16_t)parsed;
  return true;
}

bool isCurrentJob(const uint8_t *fingerprint) {
  return printState != PRINT_IDLE && !memcmp(fingerprint, printFingerprint, 8);
}

void sendPrintStatus(const char *requestId, bool known) {
  // `job` always names the controller's current record, so staff can clear
  // an interrupted job even when the host has lost its fingerprint.
  char job[17];
  for (uint8_t i = 0; i < 8; i++) {
    snprintf_P(job + 2 * i, 3, PSTR("%02x"), printFingerprint[i]);
  }
  // Longest possible payload is 186 characters; the Uno has ~700 B of stack,
  // and a 224-byte buffer here overflowed it once the train log was added.
  char payload[192];
  snprintf_P(payload, sizeof(payload), PRINT_STATUS_FMT,
             known ? 1 : 0, printerReady() ? 1 : 0, printerLineIdle() ? 0 : 1,
             known ? printState : 0, known ? printReceived : 0,
             known ? printLength : 0, known ? printBusyWaits : 0,
             known ? printBusyMs : 0, known ? printBusyMaxMs : 0,
             acceptorsEnabled ? 0 : 1, acceptorsEnabled ? 1 : 0,
             printState == PRINT_IDLE ? "" : job, printState);
  sendFrame("RSP", requestId, "PRINT_STATUS", payload);
}

// Bench diagnostic: poll the printer line for `ms` (max 1000) and report
// level changes, so a busy level (few changes) can be told apart from serial
// data or noise (many). Bounded and interrupt-free; it never prints.
void sendPrinterLineScan(const char *requestId, uint16_t ms) {
  if (ms == 0 || ms > 1000) ms = 200;
  uint32_t start = millis();
  uint32_t samples = 0, highSamples = 0, changes = 0;
  uint8_t last = digitalRead(PIN_PRINTER_LINE);
  while ((uint32_t)(millis() - start) < ms) {
    uint8_t level = digitalRead(PIN_PRINTER_LINE);
    samples++;
    if (level) highSamples++;
    if (level != last) { changes++; last = level; }
  }
  char payload[96];
  snprintf_P(payload, sizeof(payload), PSTR("ms=%u;samples=%lu;high_samples=%lu;changes=%lu;level_now=%u"),
             ms, samples, highSamples, changes, last);
  sendFrame("RSP", requestId, "PRINTER_LINE_SCAN", payload);
}

void handlePrinterCommand(const char *requestId, const char *command, const char *payload) {
  uint8_t fingerprint[8];
  bool hasFingerprint = parseFingerprint(payload, fingerprint);

  if (!strcmp(command, "PRINTER_LINE_SCAN")) {
    uint16_t ms = 200;
    parseUnsigned(payload, "ms", ms);
    sendPrinterLineScan(requestId, ms);
    return;
  }

  if (!strcmp(command, "PRINTER_STATUS")) {
    sendPrintStatus(requestId, hasFingerprint && isCurrentJob(fingerprint));
    return;
  }

  if (!strcmp(command, "PRINT_CLEAR")) {
    // Staff decision after looking at the paper. Only the named job.
    if (!hasFingerprint || !isCurrentJob(fingerprint)) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINT_CLEAR_REJECTED"));
      return;
    }
    clearPrintRecord();
    sendPrintStatus(requestId, false);
    return;
  }

  if (!strcmp(command, "PRINT_BEGIN")) {
    uint16_t length = 0;
    if (!hasFingerprint || !parseUnsigned(payload, "length", length) ||
        length == 0 || length > PRINT_MAX_LENGTH) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINTER_NOT_READY"));
      return;
    }
    if (isCurrentJob(fingerprint)) {        // idempotent: report, never restart
      sendPrintStatus(requestId, true);
      return;
    }
    if (printState == PRINT_RECEIVING || printState == PRINT_INTERRUPTED) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRIOR_PRINT_AMBIGUOUS"));
      return;
    }
    if (!printerReady()) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINTER_NOT_READY"));
      return;
    }
    memcpy(printFingerprint, fingerprint, 8);
    printLength = length;
    printReceived = 0;
    printBusyWaits = printBusyMs = printBusyMaxMs = 0;
    printState = PRINT_RECEIVING;
    savePrintRecord();
    sendPrintStatus(requestId, true);
    return;
  }

  if (!strcmp(command, "PRINT_CHUNK")) {
    if (!hasFingerprint || !isCurrentJob(fingerprint) || printState != PRINT_RECEIVING) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINT_JOB_NOT_ACTIVE"));
      return;
    }
    uint16_t offset = 0;
    if (!parseUnsigned(payload, "offset", offset) || offset != printReceived) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINT_OFFSET_MISMATCH"));
      return;
    }
    // Validate the whole chunk before a single byte reaches the paper.
    const char *hex = NULL;
    for (const char *p = payload; p && *p; ) {
      if (!strncmp(p, "hex=", 4)) { hex = p + 4; break; }
      p = strchr(p, ';');
      if (p) p++;
    }
    uint8_t hexLength = 0;
    if (hex) {
      while (hex[hexLength] && hex[hexLength] != ';') {
        if (hexNibble(hex[hexLength]) < 0 || hexLength >= PRINT_CHUNK_MAX * 2) { hex = NULL; break; }
        hexLength++;
      }
    }
    if (!hex || hexLength == 0 || (hexLength & 1)) {
      sendFault(requestId, "PRINT_STATUS", PSTR("BAD_PRINT_CHUNK"));
      return;
    }
    uint8_t count = hexLength / 2;
    if ((uint32_t)printReceived + count > printLength) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINT_LENGTH_MISMATCH"));
      return;
    }
    if (acceptorsEnabled) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINTER_NOT_READY"));
      return;
    }
    // The busy budget covers the whole chunk so one reply always arrives
    // well inside the host's request timeout.
    uint32_t chunkBusyMs = 0;
    for (uint8_t i = 0; i < count; i++) {
      if (!printerLineIdle()) {
        uint32_t waitStart = millis();
        printBusyWaits++;
        while (!printerLineIdle()) {
          if (chunkBusyMs + (uint32_t)(millis() - waitStart) >= PRINTER_WAIT_MS) {
            printBusyMs += (uint16_t)(millis() - waitStart);
            printState = PRINT_INTERRUPTED;
            savePrintRecord();
            sendFault(requestId, "PRINT_STATUS", PSTR("PRINTER_INTERRUPTED"));
            return;
          }
        }
        uint32_t waited = millis() - waitStart;
        chunkBusyMs += waited;
        printBusyMs += (uint16_t)waited;
        if (waited > printBusyMaxMs) printBusyMaxMs = (uint16_t)waited;
      }
      printerWriteByte((uint8_t)((hexNibble(hex[2 * i]) << 4) | hexNibble(hex[2 * i + 1])));
      printReceived++;
    }
    savePrintRecord();
    sendPrintStatus(requestId, true);
    return;
  }

  if (!strcmp(command, "PRINT_END")) {
    uint16_t length = 0;
    if (hasFingerprint && isCurrentJob(fingerprint) && printState == PRINT_DONE) {
      sendPrintStatus(requestId, true);         // idempotent after a lost reply
      return;
    }
    if (!hasFingerprint || !isCurrentJob(fingerprint) || printState != PRINT_RECEIVING ||
        !parseUnsigned(payload, "length", length) || length != printLength ||
        printReceived != printLength) {
      sendFault(requestId, "PRINT_STATUS", PSTR("PRINT_LENGTH_MISMATCH"));
      return;
    }
    printState = PRINT_DONE;
    savePrintRecord();
    sendPrintStatus(requestId, true);
    return;
  }

  sendFault(requestId, "PRINT_STATUS", PSTR("UNSUPPORTED_PRINT_COMMAND"));
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
    sendFrame("RSP", requestId, "ACK", "ok=0;fault_code=MEDICINE_MOTORS_DISABLED");
  } else if (!strcmp(command, "JOB_STATUS")) {
    // No motion job can exist in this build.
    sendFrame("RSP", requestId, "JOB_STATUS", "known=0");
  } else if (!strncmp(command, "PRINT", 5)) {
    handlePrinterCommand(requestId, command, payload);
  } else if (!strcmp(command, "CASH_DIAG")) {
    sendCashDiagnostics(requestId);
  } else if (!strcmp(command, "CASH_EVIDENCE")) {
    char *slotText = strstr(payload, "slot=");
    if (!slotText) {
      sendFrame("RSP", requestId, "CASH_EVIDENCE", "ok=0;fault_code=BAD_EVIDENCE_SLOT");
      return;
    }
    sendCashEvidence(requestId, (uint8_t)atoi(slotText + 5));
  } else if (!strcmp(command, "CASH_TRAIN")) {
    char *indexText = strstr(payload, "index=");
    sendTrainLog(requestId, indexText ? (uint8_t)atoi(indexText + 6) : 0);
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
  pinMode(PIN_PRINTER_TX, OUTPUT);
  pinMode(PIN_PRINTER_LINE, INPUT_PULLUP);
  // Keep every motor output disabled throughout the payment-only test.
  digitalWrite(PIN_PCA_OE, HIGH);
  digitalWrite(PIN_BILL_INHIBIT, LOW);
  digitalWrite(PIN_COIN_POWER, LOW);
  digitalWrite(PIN_PRINTER_TX, HIGH);       // UART idle (mark)
  printerTxPort = portOutputRegister(digitalPinToPort(PIN_PRINTER_TX));
  printerTxMask = digitalPinToBitMask(PIN_PRINTER_TX);
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
  loadPrintRecord();
  failSafe();
  lastHeartbeatMs = millis();
}

void loop() {
  readSerialFrames();
  finalizePulseTrains();
  if (millis() - lastHeartbeatMs > HEARTBEAT_TIMEOUT_MS) failSafe();
  if (digitalRead(PIN_INTERLOCK) == LOW) failSafe();
}
