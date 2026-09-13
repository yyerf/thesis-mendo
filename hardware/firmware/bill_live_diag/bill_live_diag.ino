/*
 * MendoVendo - TB74 live pulse diagnostic (READ ONLY)
 *
 * Purpose: tell you, out loud, whether the TB74 METER line is emitting real
 * credit pulses or just transport-motor noise. Built from the vendor DIP sheet
 * geometry documented in docs/architecture/tb74-pulse-protocol-analysis.md.
 *
 *   TB74 Fast (10-way SW4 = ON) : 50 ms LOW / 100 ms HIGH -> 150 ms period
 *   TB74 Slow (10-way SW4 = OFF): 50 ms LOW / 300 ms HIGH -> 350 ms period
 *   Fastest option anywhere in this device family: 30/50 -> 80 ms period
 *
 * So anything repeating faster than 80 ms CANNOT be a credit pulse. This
 * sketch counts raw edges and clean pulses side by side and prints both, which
 * is what separates "the acceptor paid me" from "the motor made noise".
 *
 * SAFETY: input-only. Never drives inhibit, coin power, PCA9685 OE, or a
 * servo. It cannot credit an order. It is a bench instrument, not a
 * controller.
 *
 * WIRING: watches BOTH Uno interrupt pins, so it works whether METER+ landed
 * on D2 or D3.
 *   TB pin 7 BLUE  METER+ -> D2 or D3
 *   TB pin 8 PURPLE METER- -> Arduino GND
 *   TB pin 5 RED   +12V   -> separate fused 12 V supply (NEVER an Uno pin)
 *   TB pin 9 ORANGE GND   -> that supply's return
 */

#include <Arduino.h>
#include "channel.h"

// Set to 0 once the external 4.7 kOhm pull-up to Uno 5 V is fitted (the value
// the TB manual's pulse interface actually specifies, printed page 13).
// Leave at 1 to run right now on the internal pull-up.
#define USE_INTERNAL_PULLUP 1

static const uint8_t PIN_A = 2;  // INT0
static const uint8_t PIN_B = 3;  // INT1

static const uint16_t GLITCH_MS      = 20;   // level must hold this long to count
static const uint16_t MIN_LOW_MS     = 25;   // real credit LOW is >= 30 ms
static const uint16_t MAX_LOW_MS     = 400;
static const uint16_t MIN_PERIOD_MS  = 80;   // faster than this cannot be credit
static const uint16_t TRAIN_QUIET_MS = 500;  // > 350 ms slow-mode gap
static const uint32_t IDLE_REPORT_MS = 10000UL;

volatile uint16_t rawEdgesA = 0;
volatile uint16_t rawEdgesB = 0;

void isrA() { rawEdgesA++; }
void isrB() { rawEdgesB++; }

Channel chA, chB;
uint32_t lastIdleReportMs = 0;
uint32_t totalCentavos = 0;

void resetTrain(Channel &c) {
  c.trainActive = false;
  c.pulses = 0;
  c.prevLowStartMs = 0;
  c.lowOpen = false;
  c.lowMin = 0xFFFF; c.lowMax = 0; c.lowSum = 0;
  c.perMin = 0xFFFF; c.perMax = 0; c.perSum = 0; c.perCount = 0;
  c.fastRejects = 0;
}

void initChannel(Channel &c, uint8_t pin, const __FlashStringHelper *name,
                 volatile uint16_t *rawEdges) {
  c.pin = pin;
  c.name = name;
  c.rawEdges = rawEdges;
  c.rawLevel = digitalRead(pin);
  c.stableLevel = c.rawLevel;
  c.lastRawChangeMs = millis();
  c.rawAtTrainStart = 0;
  c.lastActivityMs = millis();
  resetTrain(c);
}

// 1 pulse = PHP 10 (the GCD base unit), per the TB74/PHP6 vendor sheets.
uint32_t centavosForPulses(uint16_t pulses) {
  switch (pulses) {
    case 2:   return 2000UL;    // PHP 20
    case 5:   return 5000UL;    // PHP 50
    case 10:  return 10000UL;   // PHP 100
    case 20:  return 20000UL;   // PHP 200
    case 50:  return 50000UL;   // PHP 500
    case 100: return 100000UL;  // PHP 1000
    default:  return 0;
  }
}

void printPeso(uint32_t centavos) {
  Serial.print(F("PHP "));
  Serial.print(centavos / 100UL);
  Serial.print('.');
  uint8_t c = (uint8_t)(centavos % 100UL);
  if (c < 10) Serial.print('0');
  Serial.print(c);
}

void printStat(const __FlashStringHelper *label, uint16_t mn, uint16_t mx,
               uint32_t sum, uint16_t n) {
  Serial.print(label);
  if (!n) { Serial.println(F("  (no samples)")); return; }
  Serial.print(mn); Serial.print(F(" / "));
  Serial.print((uint16_t)(sum / n)); Serial.print(F(" / "));
  Serial.print(mx); Serial.println(F("  ms  (min/avg/max)"));
}

void reportTrain(Channel &c, uint32_t now) {
  noInterrupts();
  uint16_t rawNow = *c.rawEdges;
  interrupts();
  uint16_t rawInTrain = rawNow - c.rawAtTrainStart;

  Serial.println();
  Serial.println(F("=================== BILL EVENT ==================="));
  Serial.print(F("  channel          : ")); Serial.println(c.name);
  Serial.print(F("  raw edges        : ")); Serial.print(rawInTrain);
  Serial.println(F("   (unfiltered interrupts)"));
  Serial.print(F("  clean pulses     : ")); Serial.print(c.pulses);
  Serial.print(F("   (survived the "));
  Serial.print(GLITCH_MS); Serial.println(F(" ms glitch filter)"));
  Serial.print(F("  window           : "));
  Serial.print(now - c.trainStartMs); Serial.println(F(" ms"));

  printStat(F("  LOW width        : "), c.lowMin, c.lowMax, c.lowSum, c.pulses);
  printStat(F("  pulse period     : "), c.perMin, c.perMax, c.perSum, c.perCount);

  if (c.fastRejects) {
    Serial.print(F("  sub-80ms events  : "));
    Serial.print(c.fastRejects);
    Serial.println(F("   <-- impossible for real credit"));
  }

  Serial.print(F("  VERDICT          : "));
  if (c.pulses == 0) {
    Serial.println(F("NOISE ONLY - no credit pulses"));
    Serial.println(F("  meaning          : the note was NOT accepted, or the"));
    Serial.println(F("                     line is picking up motor noise."));
    Serial.println(F("  check            : did the note get STACKED or RETURNED?"));
    Serial.println(F("                     red LED x2 = DIP disable (manual p.17)"));
  } else {
    bool clean = (c.perCount == 0) || (c.perMin >= MIN_PERIOD_MS);
    if (clean) Serial.println(F("CREDIT PULSE TRAIN (timing valid)"));
    else       Serial.println(F("MIXED - some intervals too fast, suspect"));

    if (c.perCount) {
      Serial.print(F("  timing profile   : "));
      uint16_t avg = (uint16_t)(c.perSum / c.perCount);
      if (avg >= 110 && avg <= 200)      Serial.println(F("TB74 FAST (50/100, SW4=ON)"));
      else if (avg >= 300 && avg <= 400) Serial.println(F("TB74 SLOW (50/300, SW4=OFF)"));
      else                               Serial.println(F("unrecognised - record it"));
    }

    uint32_t cents = centavosForPulses(c.pulses);
    Serial.print(F("  MONEY            : "));
    if (cents) {
      printPeso(cents);
      if (clean) {
        totalCentavos += cents;
        Serial.print(F("     [session total "));
        printPeso(totalCentavos);
        Serial.print(F("]"));
      }
      Serial.println();
    } else {
      Serial.print(F("UNMAPPED ("));
      Serial.print(c.pulses);
      Serial.println(F(" pulses) - expected 2/5/10/20/50/100"));
    }
  }
  Serial.println(F("=================================================="));
  Serial.println();
}

void onStableEdge(Channel &c, uint8_t level, uint32_t at) {
  if (level == LOW) {
    c.lowStartMs = at;
    c.lowOpen = true;
    return;
  }
  if (!c.lowOpen) return;
  c.lowOpen = false;

  uint32_t width = at - c.lowStartMs;
  if (width < MIN_LOW_MS || width > MAX_LOW_MS) return;  // not a credit LOW

  if (c.prevLowStartMs) {
    uint32_t period = c.lowStartMs - c.prevLowStartMs;
    if (period < MIN_PERIOD_MS) {
      c.fastRejects++;
    } else {
      if (period < c.perMin) c.perMin = (uint16_t)period;
      if (period > c.perMax) c.perMax = (uint16_t)period;
      c.perSum += period;
      c.perCount++;
    }
  }
  c.prevLowStartMs = c.lowStartMs;

  if (width < c.lowMin) c.lowMin = (uint16_t)width;
  if (width > c.lowMax) c.lowMax = (uint16_t)width;
  c.lowSum += width;
  c.pulses++;
}

void pollChannel(Channel &c, uint32_t now) {
  uint8_t raw = digitalRead(c.pin);

  if (raw != c.rawLevel) {
    c.rawLevel = raw;
    c.lastRawChangeMs = now;
    if (!c.trainActive) {
      c.trainActive = true;
      c.trainStartMs = now;
      noInterrupts();
      c.rawAtTrainStart = *c.rawEdges;
      interrupts();
      c.pulses = 0;
      c.prevLowStartMs = 0;
      c.lowOpen = false;
      c.lowMin = 0xFFFF; c.lowMax = 0; c.lowSum = 0;
      c.perMin = 0xFFFF; c.perMax = 0; c.perSum = 0; c.perCount = 0;
      c.fastRejects = 0;
      Serial.print(F("[activity on "));
      Serial.print(c.name);
      Serial.println(F(" ...]"));
    }
    c.lastActivityMs = now;
  } else if (c.stableLevel != raw && (now - c.lastRawChangeMs) >= GLITCH_MS) {
    c.stableLevel = raw;
    onStableEdge(c, raw, c.lastRawChangeMs);
    c.lastActivityMs = now;
  }

  if (c.trainActive && (now - c.lastActivityMs) >= TRAIN_QUIET_MS) {
    reportTrain(c, now);
    resetTrain(c);
    lastIdleReportMs = now;
  }
}

void setup() {
#if USE_INTERNAL_PULLUP
  pinMode(PIN_A, INPUT_PULLUP);
  pinMode(PIN_B, INPUT_PULLUP);
#else
  pinMode(PIN_A, INPUT);
  pinMode(PIN_B, INPUT);
#endif

  Serial.begin(115200);
  while (!Serial) { ; }
  delay(200);

  initChannel(chA, PIN_A, F("D2 / INT0"), &rawEdgesA);
  initChannel(chB, PIN_B, F("D3 / INT1"), &rawEdgesB);

  attachInterrupt(digitalPinToInterrupt(PIN_A), isrA, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_B), isrB, CHANGE);

  Serial.println();
  Serial.println(F("=================================================="));
  Serial.println(F("  MendoVendo TB74 live pulse diagnostic"));
  Serial.println(F("  READ ONLY - cannot credit an order or move a servo"));
  Serial.println(F("=================================================="));
  Serial.print(F("  pull-up          : "));
#if USE_INTERNAL_PULLUP
  Serial.println(F("INTERNAL (~20-50k) - fit external 4.7k"));
#else
  Serial.println(F("EXTERNAL 4.7k expected"));
#endif
  Serial.print(F("  glitch filter    : ")); Serial.print(GLITCH_MS); Serial.println(F(" ms"));
  Serial.print(F("  train ends after : ")); Serial.print(TRAIN_QUIET_MS); Serial.println(F(" ms quiet"));
  Serial.println(F("  expected @ 1 pulse / PHP 10:"));
  Serial.println(F("     PHP  20 ->   2 pulses      PHP  200 ->  20"));
  Serial.println(F("     PHP  50 ->   5 pulses      PHP  500 ->  50"));
  Serial.println(F("     PHP 100 ->  10 pulses      PHP 1000 -> 100"));
  Serial.print(F("  idle level D2    : "));
  Serial.println(digitalRead(PIN_A) ? F("HIGH (good)") : F("LOW  (check wiring)"));
  Serial.print(F("  idle level D3    : "));
  Serial.println(digitalRead(PIN_B) ? F("HIGH (good)") : F("LOW  (check wiring)"));
  Serial.println(F("--------------------------------------------------"));
  Serial.println(F("  Insert one note. Watch whether it is kept or returned."));
  Serial.println();
  lastIdleReportMs = millis();
}

void loop() {
  uint32_t now = millis();
  pollChannel(chA, now);
  pollChannel(chB, now);

  if (!chA.trainActive && !chB.trainActive &&
      (now - lastIdleReportMs) >= IDLE_REPORT_MS) {
    lastIdleReportMs = now;
    noInterrupts();
    uint16_t ra = rawEdgesA, rb = rawEdgesB;
    interrupts();
    Serial.print(F("[idle  t=")); Serial.print(now / 1000); Serial.print(F("s"));
    Serial.print(F("  D2=")); Serial.print(digitalRead(PIN_A) ? F("HI") : F("LO"));
    Serial.print(F("  D3=")); Serial.print(digitalRead(PIN_B) ? F("HI") : F("LO"));
    Serial.print(F("  rawA=")); Serial.print(ra);
    Serial.print(F("  rawB=")); Serial.print(rb);
    Serial.print(F("  total=")); printPeso(totalCentavos);
    Serial.println(F("]"));
  }
}
