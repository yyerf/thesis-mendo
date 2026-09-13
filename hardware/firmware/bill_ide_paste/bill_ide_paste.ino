/*
 * MendoVendo - TB74 bill diagnostic  (SINGLE FILE - paste into Arduino IDE)
 *
 * >>> SET THE SERIAL MONITOR TO 9600 BAUD <<<
 *
 * Watches BOTH D2 and D3, so it works whichever pin METER+ is on.
 * READ ONLY: drives no pin, cannot credit an order, cannot move a servo.
 *
 * WIRING
 *   4.7k resistor : Arduino 5V  ---> the signal junction
 *   TB pin 7 BLUE   METER+      ---> the signal junction ---> D3
 *   TB pin 8 PURPLE METER-      ---> Arduino GND
 *   TB pin 5 RED    +12V        ---> PSU +   (never the Arduino)
 *   TB pin 9 ORANGE GND         ---> PSU -   (never the Arduino)
 *
 * WHAT THE NUMBERS MEAN
 *   raw edges    = unfiltered electrical activity, i.e. the noise floor
 *   clean pulses = survivors of the 20 ms glitch filter, i.e. real credit
 *   A big raw count with 0 clean pulses means nothing was ever paid.
 *
 * TB74 credit pulse geometry, from the vendor DIP sheet:
 *   Fast (SW4 ON)  50 ms LOW / 100 ms HIGH -> 150 ms period
 *   Slow (SW4 OFF) 50 ms LOW / 300 ms HIGH -> 350 ms period
 * Nothing in this device family is faster than an 80 ms period, so anything
 * quicker than that is provably not payment.
 *
 * At 1 pulse / PHP 10:  2=P20  5=P50  10=P100  20=P200  50=P500  100=P1000
 */

// Set to 0 after you fit the external 4.7k pull-up to 5V. Leave at 1 to run
// on the Arduino's internal pull-up. Applies to the METER pin (D3) only.
#define USE_INTERNAL_PULLUP 0

// D2 = Allan coin acceptor, DISCOVERY mode. Its pulse geometry has never been
// measured, so this channel reports what the device actually does and never
// converts it to money.
//
// Set to 0 whenever nothing is wired to D2. An unwatched pin is held by its
// internal pull-up so it cannot float and act as an antenna: a floating D2
// picks up mains hum AND capacitively couples the real D3 train, producing
// convincing-looking but entirely fake events.
#define WATCH_D2 1

// At the current noise floor the per-event noise lines drown the results.
// They are counted either way; set to 1 only when chasing a wiring problem.
#define VERBOSE_NOISE 0

#define NCH 2

const uint8_t chEnabled[NCH] = {WATCH_D2, 1};

const uint8_t  chPin[NCH]        = {2, 3};
volatile uint16_t rawEdges[NCH]  = {0, 0};

uint8_t  rawLevel[NCH], stableLevel[NCH];
uint32_t lastRawChangeMs[NCH];
uint8_t  trainActive[NCH];
uint32_t trainStartMs[NCH], lastActivityMs[NCH];
uint16_t rawAtTrainStart[NCH];
uint32_t lowStartMs[NCH], prevLowStartMs[NCH];
uint8_t  lowOpen[NCH];
uint16_t pulses[NCH];
uint16_t lowMin[NCH], lowMax[NCH];
uint32_t lowSum[NCH];
uint16_t perMin[NCH], perMax[NCH];
uint32_t perSum[NCH];
uint16_t perCount[NCH];
uint16_t fastRejects[NCH];

// Per-channel filters.
//   D3 (bill) : MEASURED. TB74 = 50 ms LOW, 150 ms period.
//   D2 (coin) : UNKNOWN. Deliberately loose so a real coin pulse gets reported
//               instead of discarded against a guess. Coin acceptors run far
//               faster than bill validators, so the bill's 25 ms minimum LOW
//               and 80 ms minimum period would silently throw coin pulses away.
const uint16_t chGlitchMs[NCH]    = {3,   20};
const uint16_t chMinLowMs[NCH]    = {4,   25};
const uint16_t chMaxLowMs[NCH]    = {400, 400};
const uint16_t chMinPeriodMs[NCH] = {12,  80};
const uint16_t chQuietMs[NCH]     = {400, 500};
const uint32_t IDLE_REPORT_MS = 10000UL;

uint32_t lastIdleReportMs = 0;
uint32_t totalCentavos = 0;

// Phase-0 trial tally. Send 'r' in the Serial Monitor to zero it before a run.
uint16_t trialNo = 0;
uint16_t n20 = 0, n50 = 0, n100 = 0, nUnmapped = 0;
uint16_t nNoise = 0;

// Coin tally, bucketed by pulse count. 1 pulse = PHP 1 is measured, so the
// bucket IS the denomination. Drop 20 of one coin and every hit outside its
// bucket is a misclassification -- the rate this is built to measure.
uint16_t coinNo = 0;
uint16_t c1 = 0, c5 = 0, c10 = 0, c20 = 0, cOther = 0;
uint32_t coinTotalPesos = 0;

void isr0() { rawEdges[0]++; }
void isr1() { rawEdges[1]++; }

void printChName(uint8_t ch) {
  Serial.print(ch == 0 ? F("D2 / INT0") : F("D3 / INT1"));
}

void printPeso(uint32_t centavos) {
  Serial.print(F("PHP "));
  Serial.print(centavos / 100UL);
  Serial.print('.');
  uint8_t c = (uint8_t)(centavos % 100UL);
  if (c < 10) Serial.print('0');
  Serial.print(c);
}

uint32_t centavosForPulses(uint16_t p) {
  if (p == 2)   return 2000UL;
  if (p == 5)   return 5000UL;
  if (p == 10)  return 10000UL;
  if (p == 20)  return 20000UL;
  if (p == 50)  return 50000UL;
  if (p == 100) return 100000UL;
  return 0;
}

void clearStats(uint8_t ch) {
  pulses[ch] = 0;
  prevLowStartMs[ch] = 0;
  lowOpen[ch] = 0;
  lowMin[ch] = 0xFFFF; lowMax[ch] = 0; lowSum[ch] = 0;
  perMin[ch] = 0xFFFF; perMax[ch] = 0; perSum[ch] = 0; perCount[ch] = 0;
  fastRejects[ch] = 0;
}

void printStat(const __FlashStringHelper *label, uint16_t mn, uint16_t mx,
               uint32_t sum, uint16_t n) {
  Serial.print(label);
  if (!n) { Serial.println(F("  (no samples)")); return; }
  Serial.print(mn); Serial.print(F(" / "));
  Serial.print((uint16_t)(sum / n)); Serial.print(F(" / "));
  Serial.print(mx); Serial.println(F("  ms  (min/avg/max)"));
}

void printTally() {
  Serial.print(F("      tally: P20="));  Serial.print(n20);
  Serial.print(F("  P50="));             Serial.print(n50);
  Serial.print(F("  P100="));            Serial.print(n100);
  Serial.print(F("  | unmapped="));      Serial.print(nUnmapped);
  Serial.print(F("  noise="));           Serial.print(nNoise);
  Serial.print(F("  | total="));         printPeso(totalCentavos);
  Serial.println();
}

// A real payment mixes both acceptors: PHP 22 due, paid as a PHP 20 note plus
// two PHP 1 coins. The per-channel tallies alone never show that it added up,
// so every event ends with the combined figure.
void printGrandTotal() {
  uint32_t grand = totalCentavos + (coinTotalPesos * 100UL);
  Serial.print(F("  >>> SESSION TOTAL: ")); printPeso(grand);
  Serial.print(F("   (bills ")); printPeso(totalCentavos);
  Serial.print(F(" + coins ")); printPeso(coinTotalPesos * 100UL);
  Serial.println(F(")"));
}

void printCoinTally() {
  Serial.print(F("       coins: P1="));  Serial.print(c1);
  Serial.print(F("  P5="));              Serial.print(c5);
  Serial.print(F("  P10="));             Serial.print(c10);
  Serial.print(F("  P20="));             Serial.print(c20);
  Serial.print(F("  | other="));         Serial.print(cOther);
  Serial.print(F("  | PHP "));           Serial.print(coinTotalPesos);
  Serial.println();
}

void resetTally() {
  trialNo = 0; n20 = 0; n50 = 0; n100 = 0; nUnmapped = 0; nNoise = 0;
  totalCentavos = 0;
  coinNo = 0; c1 = 0; c5 = 0; c10 = 0; c20 = 0; cOther = 0; coinTotalPesos = 0;
  Serial.println(F("*** tally reset ***"));
}

void reportTrain(uint8_t ch, uint32_t now) {
  noInterrupts();
  uint16_t rawNow = rawEdges[ch];
  interrupts();
  uint16_t rawInTrain = rawNow - rawAtTrainStart[ch];

  // A train with no validated pulses is a rejected note or pure motor noise.
  // One line is enough; it is not a trial.
  if (pulses[ch] == 0) {
    nNoise++;
#if VERBOSE_NOISE
    Serial.print(F("[noise] "));  printChName(ch);
    Serial.print(F("  raw="));    Serial.print(rawInTrain);
    Serial.println(ch == 0 ? F("  clean=0  -> no coin pulse")
                           : F("  clean=0  -> nothing paid (note returned?)"));
#else
    (void)rawInTrain;
#endif
    return;
  }

  // D2 is the coin channel in DISCOVERY mode. Report the geometry; never
  // convert it to money. The constants for a real coin credit path have to be
  // derived from these captures first, exactly as the bill path was.
  if (ch == 0) {
    uint16_t p = pulses[ch];
    coinNo++;
    coinTotalPesos += p;              // measured: 1 pulse = PHP 1
    if      (p == 1)  c1++;
    else if (p == 5)  c5++;
    else if (p == 10) c10++;
    else if (p == 20) c20++;
    else              cOther++;

    Serial.print(F("[coin #")); Serial.print(coinNo); Serial.print(F("] pulses="));
    Serial.print(p);
    Serial.print(F("  -> PHP ")); Serial.print(p);
    Serial.print(F("   LOW="));   Serial.print((uint16_t)(lowSum[ch] / p));
    Serial.print(F("ms"));
    if (perCount[ch]) {
      Serial.print(F("  period="));
      Serial.print((uint16_t)(perSum[ch] / perCount[ch]));
      Serial.print(F("ms"));
    }
    Serial.print(F("  raw=")); Serial.print(rawInTrain);
    if (p != 1 && p != 5 && p != 10 && p != 20) {
      Serial.print(F("   <-- NOT a single denomination (merged, or misread)"));
    }
    Serial.println();
    printCoinTally();
    printGrandTotal();
    return;
  }

  uint8_t clean = (perCount[ch] == 0) || (perMin[ch] >= chMinPeriodMs[ch]);
  uint32_t cents = centavosForPulses(pulses[ch]);

  trialNo++;
  Serial.print(F("[#")); Serial.print(trialNo); Serial.print(F("] "));
  printChName(ch);
  Serial.print(F("  pulses=")); Serial.print(pulses[ch]);
  Serial.print(F("  LOW="));    Serial.print((uint16_t)(lowSum[ch] / pulses[ch]));
  Serial.print(F("ms"));
  if (perCount[ch]) {
    Serial.print(F("  period="));
    Serial.print((uint16_t)(perSum[ch] / perCount[ch]));
    Serial.print(F("ms"));
  }
  Serial.print(F("  raw=")); Serial.print(rawInTrain);
  Serial.print(F("  "));

  if (!clean) {
    Serial.print(F("SUSPECT ("));
    Serial.print(fastRejects[ch]);
    Serial.println(F(" sub-80ms) - DO NOT CREDIT"));
    nUnmapped++;
  } else if (cents) {
    totalCentavos += cents;
    if (cents == 2000UL) n20++;
    else if (cents == 5000UL) n50++;
    else if (cents == 10000UL) n100++;
    Serial.print(F("OK  ")); printPeso(cents); Serial.println();
  } else {
    nUnmapped++;
    Serial.print(F("UNMAPPED ("));
    Serial.print(pulses[ch]);
    Serial.println(F(" pulses) - expected 2/5/10"));
    // Anomaly: show the spread so it can be diagnosed.
    printStat(F("      LOW width  : "), lowMin[ch], lowMax[ch], lowSum[ch], pulses[ch]);
    printStat(F("      period     : "), perMin[ch], perMax[ch], perSum[ch], perCount[ch]);
  }
  printTally();
  printGrandTotal();
}

void onStableEdge(uint8_t ch, uint8_t level, uint32_t at) {
  if (level == LOW) { lowStartMs[ch] = at; lowOpen[ch] = 1; return; }
  if (!lowOpen[ch]) return;
  lowOpen[ch] = 0;

  uint32_t width = at - lowStartMs[ch];
  if (width < chMinLowMs[ch] || width > chMaxLowMs[ch]) return;

  if (prevLowStartMs[ch]) {
    uint32_t period = lowStartMs[ch] - prevLowStartMs[ch];
    if (period < chMinPeriodMs[ch]) {
      fastRejects[ch]++;
    } else {
      if (period < perMin[ch]) perMin[ch] = (uint16_t)period;
      if (period > perMax[ch]) perMax[ch] = (uint16_t)period;
      perSum[ch] += period;
      perCount[ch]++;
    }
  }
  prevLowStartMs[ch] = lowStartMs[ch];

  if (width < lowMin[ch]) lowMin[ch] = (uint16_t)width;
  if (width > lowMax[ch]) lowMax[ch] = (uint16_t)width;
  lowSum[ch] += width;
  pulses[ch]++;
}

void pollChannel(uint8_t ch, uint32_t now) {
  if (!chEnabled[ch]) return;
  uint8_t raw = digitalRead(chPin[ch]);

  if (raw != rawLevel[ch]) {
    rawLevel[ch] = raw;
    lastRawChangeMs[ch] = now;
    if (!trainActive[ch]) {
      trainActive[ch] = 1;
      trainStartMs[ch] = now;
      noInterrupts();
      rawAtTrainStart[ch] = rawEdges[ch];
      interrupts();
      clearStats(ch);
#if VERBOSE_NOISE
      Serial.print(F("[activity on ")); printChName(ch); Serial.println(F(" ...]"));
#endif
    }
    lastActivityMs[ch] = now;
  } else if (stableLevel[ch] != raw && (now - lastRawChangeMs[ch]) >= chGlitchMs[ch]) {
    stableLevel[ch] = raw;
    onStableEdge(ch, raw, lastRawChangeMs[ch]);
    lastActivityMs[ch] = now;
  }

  if (trainActive[ch] && (now - lastActivityMs[ch]) >= chQuietMs[ch]) {
    reportTrain(ch, now);
    trainActive[ch] = 0;
    clearStats(ch);
    lastIdleReportMs = now;
  }
}

void setup() {
  for (uint8_t ch = 0; ch < NCH; ch++) {
    if (!chEnabled[ch]) {
      // Unwatched: tie it off with the internal pull-up so it cannot float.
      pinMode(chPin[ch], INPUT_PULLUP);
      continue;
    }
#if USE_INTERNAL_PULLUP
    pinMode(chPin[ch], INPUT_PULLUP);
#else
    pinMode(chPin[ch], INPUT);
#endif
    rawLevel[ch] = digitalRead(chPin[ch]);
    stableLevel[ch] = rawLevel[ch];
    lastRawChangeMs[ch] = millis();
    lastActivityMs[ch] = millis();
    trainActive[ch] = 0;
    rawAtTrainStart[ch] = 0;
    clearStats(ch);
  }

  Serial.begin(9600);
  delay(300);

  if (chEnabled[0]) attachInterrupt(digitalPinToInterrupt(2), isr0, CHANGE);
  if (chEnabled[1]) attachInterrupt(digitalPinToInterrupt(3), isr1, CHANGE);

  Serial.println();
  Serial.println(F("=========================================="));
  Serial.println(F("  MendoVendo TB74 bill diagnostic"));
  Serial.println(F("  READ ONLY - cannot credit or move a servo"));
  Serial.println(F("=========================================="));
  Serial.print(F("  pull-up        : "));
#if USE_INTERNAL_PULLUP
  Serial.println(F("INTERNAL (fit the external 4.7k)"));
#else
  Serial.println(F("EXTERNAL 4.7k expected"));
#endif
  Serial.println(F("  expected pulses @ 1 pulse / PHP 10:"));
  Serial.println(F("     P20 = 2     P200 = 20"));
  Serial.println(F("     P50 = 5     P500 = 50"));
  Serial.println(F("     P100= 10    P1000= 100"));
  Serial.print(F("  D2 (coin)      : "));
  if (!chEnabled[0]) {
    Serial.println(F("not watched (tied off)"));
  } else {
    Serial.print(F("DISCOVERY, idle "));
    // Idle MUST be HIGH. A NO contact is open at rest, so the pull-up lifts
    // the line. LOW at rest means the pull-up is missing, the contact is
    // wired NC, or COIN is not the wire on D2.
    Serial.println(digitalRead(2) ? F("HIGH (good)")
                                  : F("LOW  <-- CHECK WIRING"));
  }
  Serial.print(F("  idle D3        : "));
  Serial.println(digitalRead(3) ? F("HIGH (good)") : F("LOW  <-- CHECK WIRING"));
  Serial.println(F("------------------------------------------"));
  Serial.println(F("  Insert ONE note at a time. Send 'r' to"));
  Serial.println(F("  reset the tally, 't' to reprint it."));
  Serial.println();
  lastIdleReportMs = millis();
}

void loop() {
  uint32_t now = millis();
  pollChannel(0, now);
  pollChannel(1, now);

  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == 'r' || c == 'R') resetTally();
    else if (c == 't' || c == 'T') {
      printTally(); printCoinTally(); printGrandTotal();
    }
  }

  if (!trainActive[0] && !trainActive[1] &&
      (now - lastIdleReportMs) >= IDLE_REPORT_MS) {
    lastIdleReportMs = now;
    noInterrupts();
    uint16_t r0 = rawEdges[0], r1 = rawEdges[1];
    interrupts();
    Serial.print(F("[idle t=")); Serial.print(now / 1000); Serial.print(F("s"));
    Serial.print(F("  D3=")); Serial.print(digitalRead(3) ? F("HI") : F("LO"));
    Serial.print(F("  rawD3=")); Serial.print(r1);
    if (chEnabled[0]) {
      Serial.print(F("  D2=")); Serial.print(digitalRead(2) ? F("HI") : F("LO"));
      Serial.print(F("  rawD2=")); Serial.print(r0);
    }
    (void)r0;
    Serial.print(F("  total="));
    printPeso(totalCentavos + (coinTotalPesos * 100UL));
    Serial.println(F("]"));
  }
}
