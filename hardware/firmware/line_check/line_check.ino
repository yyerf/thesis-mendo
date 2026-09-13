/*
 * MendoVendo - METER line electrical characteriser (READ ONLY)
 *
 * Answers one question: what is actually attached to D2 and D3?
 *
 * For each pin it samples the raw port at high speed in two configurations,
 * internal pull-up ON and OFF, and reports duty cycle, transition rate and
 * dominant frequency. That is enough to separate the three cases:
 *
 *   floating / open        pull-up ON -> steady HIGH ; pull-up OFF -> noisy
 *   held low (short/GND)   pull-up ON -> steady LOW  ; pull-up OFF -> steady LOW
 *   driven / oscillating   both configurations show the same activity
 *
 * Input-only. Drives nothing.
 */

#include <Arduino.h>

static const uint16_t SAMPLE_MS = 400;

// D2 = PIND bit 2, D3 = PIND bit 3.
struct Result {
  uint32_t samples;
  uint32_t highSamples;
  uint32_t transitions;
  uint16_t minRunUs;
  uint16_t maxRunUs;
};

Result measure(uint8_t mask) {
  Result r;
  r.samples = 0; r.highSamples = 0; r.transitions = 0;
  r.minRunUs = 0xFFFF; r.maxRunUs = 0;

  uint32_t endMs = millis() + SAMPLE_MS;
  uint8_t last = (PIND & mask) ? 1 : 0;
  uint32_t lastChangeUs = micros();

  while (millis() < endMs) {
    uint8_t now = (PIND & mask) ? 1 : 0;
    r.samples++;
    if (now) r.highSamples++;
    if (now != last) {
      uint32_t nowUs = micros();
      uint32_t run = nowUs - lastChangeUs;
      if (r.transitions) {  // skip the first, its start is arbitrary
        if (run < r.minRunUs) r.minRunUs = (uint16_t)min(run, 65535UL);
        if (run > r.maxRunUs) r.maxRunUs = (uint16_t)min(run, 65535UL);
      }
      lastChangeUs = nowUs;
      r.transitions++;
      last = now;
    }
  }
  return r;
}

void report(const __FlashStringHelper *label, Result r) {
  Serial.print(label);
  uint32_t pctHigh = (r.samples) ? (r.highSamples * 100UL / r.samples) : 0;
  Serial.print(F("  high="));
  if (pctHigh < 10) Serial.print(' ');
  if (pctHigh < 100) Serial.print(' ');
  Serial.print(pctHigh); Serial.print(F("%"));

  Serial.print(F("  transitions="));
  Serial.print(r.transitions);

  Serial.print(F("  rate="));
  uint32_t hz = r.transitions * 1000UL / SAMPLE_MS / 2UL;  // full cycles/sec
  Serial.print(hz); Serial.print(F(" Hz"));

  if (r.transitions > 1) {
    Serial.print(F("  run(us) min="));
    Serial.print(r.minRunUs);
    Serial.print(F(" max="));
    Serial.print(r.maxRunUs);
  }
  Serial.println();
}

void verdict(const __FlashStringHelper *pin, Result up, Result down) {
  Serial.print(F("  -> "));
  Serial.print(pin);
  Serial.print(F(" : "));

  uint32_t upHighPct   = up.samples   ? (up.highSamples   * 100UL / up.samples)   : 0;
  uint32_t downHighPct = down.samples ? (down.highSamples * 100UL / down.samples) : 0;
  bool upQuiet   = up.transitions   <= 2;
  bool downQuiet = down.transitions <= 2;

  // Duty cycle decides first. A pin the pull-up cannot lift is tied low no
  // matter how many microsecond glitches ride on it, so test that before
  // looking at transition counts.
  if (upHighPct < 10 && downHighPct < 10) {
    Serial.println(F("HELD LOW - low-impedance path to GND."));
    Serial.println(F("       The internal pull-up cannot lift it. An idle"));
    Serial.println(F("       METER+ must read HIGH, so this is NOT METER+:"));
    Serial.println(F("       most likely a ground wire on the wrong pin."));
  } else if (upHighPct > 90 && upQuiet) {
    if (downQuiet && downHighPct > 90) {
      Serial.println(F("HIGH and quiet - either an idle METER+ (correct) or"));
      Serial.println(F("       an open pin. Insert a note to tell them apart."));
    } else {
      Serial.println(F("FLOATING - nothing driving it; needs the pull-up."));
    }
  } else {
    Serial.println(F("OSCILLATING - active noise source. NOT usable as-is."));
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }
  delay(300);

  Serial.println();
  Serial.println(F("=================================================="));
  Serial.println(F("  METER line electrical characteriser"));
  Serial.println(F("  READ ONLY - drives nothing"));
  Serial.println(F("=================================================="));
  Serial.print(F("  sample window per config: "));
  Serial.print(SAMPLE_MS); Serial.println(F(" ms"));
  Serial.println();
}

void loop() {
  Serial.println(F("---------------- D2 / INT0 ----------------"));
  pinMode(2, INPUT_PULLUP); delay(50);
  Result d2up = measure(_BV(2));
  report(F("  pull-up ON :"), d2up);
  pinMode(2, INPUT); delay(50);
  Result d2dn = measure(_BV(2));
  report(F("  pull-up OFF:"), d2dn);
  verdict(F("D2"), d2up, d2dn);
  Serial.println();

  Serial.println(F("---------------- D3 / INT1 ----------------"));
  pinMode(3, INPUT_PULLUP); delay(50);
  Result d3up = measure(_BV(3));
  report(F("  pull-up ON :"), d3up);
  pinMode(3, INPUT); delay(50);
  Result d3dn = measure(_BV(3));
  report(F("  pull-up OFF:"), d3dn);
  verdict(F("D3"), d3up, d3dn);

  Serial.println();
  Serial.println(F("=================================================="));
  Serial.println();
  delay(3000);
}
